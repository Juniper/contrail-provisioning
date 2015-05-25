#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import ConfigParser
import time

from fabric.api import local,run
from fabric.context_managers import lcd, hide, settings
from fabric.operations import get, put


from contrail_provisioning.common import DEBIAN, RHEL, SSH_KEY_UPLOAD_FILE
from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.openstack.ha.templates import openstack_haproxy


class OpenstackHaSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(OpenstackHaSetup, self).__init__()
        self.global_defaults = {
            'nfs_glance_dir' : '/var/tmp/glance-images/',
            'self_ip': '127.0.0.1',
            'keystone_ip': '127.0.0.1',
            'openstack0_user': 'root',
            'openstack0_password': 'c0ntrail123',
        }
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])
        self.parse_args(args_str)
        self.mysql_redo_log_sz = '5242880'

    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-galera --openstack0_user root --openstack0_password c0ntrail123 --self_ip 10.1.5.11
                   --keystone_ip 10.1.5.11 --galera_ip_list 10.1.5.11 10.1.5.12 --openstack_index 1
                   --internal_vip 10.1.5.13
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--self_ip", help = "IP Address of this system")
        parser.add_argument("--keystone_ip", help = "IP Address of keystone node or Virtual IP of the cluster nodes.")
        parser.add_argument("--openstack_index", help = "The index of this openstack node", type = int)
        parser.add_argument("--openstack0_user", help = "Sudo user of this openstack node")
        parser.add_argument("--openstack0_passwd", help = "Sudo user password  of this openstack node")
        parser.add_argument("--galera_ip_list", help = "List of IP Addresses of galera servers", nargs='+', type=str)
        parser.add_argument("--internal_vip", help = "Virtual IPP Addresses of HA Openstack nodes"),
        self._args = parser.parse_args(self.remaining_argv)

    def fixup_restart_xinetd_conf(self):
        """Fix contrail-mysqlprobe to accept connection only from this node"""
        local("sudo sed -i -e 's#only_from       = 0.0.0.0/0#only_from       ="\
              " %s 127.0.0.1#' /etc/xinetd.d/contrail-mysqlprobe" %\
              self._args.self_ip)
        local("sudo service xinetd restart")
        local("sudo chkconfig xinetd on")

    def fixup_memcache_conf(self):
        """Increases the memcached memory to 2048 and listen address to mgmt ip"""
        memory = '2048'
        listen_ip = self._args.self_ip
        if self.pdist in DEBIAN:
            memcache_conf='/etc/memcached.conf'
            if local('sudo grep "\-m " %s' % memcache_conf).failed:
                #Write option to memcached config file
                local('sudo echo "-m %s" >> %s' % (memory, memcache_conf))
            else:
                local("sudo sed -i -e 's/\-m.*/\-m %s/' %s" % (memory,
                      memcache_conf))
            if local('sudo grep "\-l " %s' % memcache_conf).failed:
                #Write option to memcached config file
                local('sudo echo "-l %s" >> %s' % (listen_ip, memcache_conf))
            else:
                    local("sudo sed -i -e 's/\-l.*/\-l %s/' %s" % (listen_ip,
                           memcache_conf))
        else:
            memcache_conf='/etc/sysconfig/memcached'
            # Need to implement when HA supported in centos.

    def tune_tcp(self):
        conf_file = "/etc/sysctl.conf"
        tcp_params = {
                'net.netfilter.nf_conntrack_max' : 256000,
                'net.netfilter.nf_conntrack_tcp_timeout_time_wait' : 30,
                'net.ipv4.tcp_syncookies' : 1,
                'net.ipv4.tcp_tw_recycle' : 1,
                'net.ipv4.tcp_tw_reuse' : 1,
                'net.ipv4.tcp_fin_timeout' : 30,
                'net.unix.max_dgram_qlen' : 1000,
        }
        with settings(hide('stderr'), warn_only=True):
            for param, value in tcp_params.items():
                if local("sudo grep '^%s' %s" % (param, conf_file)).failed:
                    local('sudo echo "%s = %s" >> %s' % (param, value,
                                                         conf_file))

    def mount_glance_images(self):
        nfs_server = self._args.nfs_server
        if nfs_server == '127.0.0.1':
            nfs_server = self._args.openstack_host_list[0]
        nfs_glance_dir = self._args.nfs_glance_dir
        with settings(warn_only=True):
            out = local('sudo sudo mount %s:%s /var/lib/glance/images' %\
                        (nfs_server, nfs_glance_dir), capture=True)
            if out.failed and 'already mounted' not in out:
                raise RuntimeError(out)
            if local('sudo grep "%s:%s /var/lib/glance/images nfs" /etc/fstab'\
                     % (nfs_server, nfs_glance_dir)).failed:
                local("sudo echo'%s:%s /var/lib/glance/images nfs nfsvers=3,"\
                      "hard,intr,auto 0 ' >> /etc/fstab" % (nfs_server,
                                                            nfs_glance_dir))

    def setup_glance_images_loc(self):
        nfs_server = self._args.nfs_server
        nfs_glance_dir = self._args.nfs_glance_dir
        if (nfs_server == '127.0.0.1' and self._args.openstack_index == 1):
            local('sudo mkdir -p /var/tmp/glance-images/')
            local('sudo chmod 777 /var/tmp/glance-images/')
            local('sudo echo "/var/tmp/glance-images *(rw,sync,no_subtree_check)" >> /etc/exports')
            local('sudo sudo /etc/init.d/nfs-kernel-server restart')
        self.mount_glance_images()

    def sync_keystone_ssl_certs(self):
        temp_dir= tempfile.mkdtemp()
        host_string = '%s@%s' % (self._args.openstack0_user,
                                 self._args.openstack_ip_list[0])
        password = self._args.openstack0_password,
        with settings(host_string=host_string, password=password):
            get('/etc/keystone/ssl/', temp_dir)
            shutil.move('%s/ssl/' % temp_dir, '/etc/keystone/')
            local('sudo service keystone restart')

    def fixup_wsrep_cluster_address(self):
        if self._args.openstack_index != 1:
            # Only in first openstack node
            return
        galera_ip_list = self._args.openstack_ip_list
        wsrep_conf = '/etc/mysql/my.cnf'
        if self.pdist in DEBIAN:
            wsrep_conf = '/etc/mysql/conf.d/wsrep.cnf'
        local("sudo sed -ibak 's#wsrep_cluster_address=.*#"\
              "wsrep_cluster_address=gcomm://%s:4567#g' %s" %\
              (':4567,'.join(galera_ip_list), wsrep_conf))

    def setup_cluster_monitors(self):
        """start manage the contrail cluster monitor."""
        local("sudo service contrail-hamon restart")
        local("sudo chkconfig contrail-hamon on")

    def setup_galera_cluster(self):
        """Cluster's the openstack nodes with galera"""
        local("sudo setup-vnc-galera\
                --self_ip %s --keystone_ip %s --galera_ip_list %s\
                --internal_vip %s --openstack_index %d"\
                % (self.args.self_ip, self._args.keystone_ip,
                   ' '.join(self._args.openstack_ip_list),
                    self._args.internal_vip, self._args.openstack_index))


    def setup_contrail_keepalived(self):
        """Provision VIP for cfgm nodes with keepalived"""
        self.enable_haproxy()
        local("sudo service haproxy restart")
        cmd = "setup-vnc-keepalived\
               --self_ip %s --internal_vip %s --mgmt_self_ip %s\
               --self_index %d --num_nodes %d --role %s\
               --master_ip %s --master_user %s --master_password %s"\
               % (self._args.self_ip, self._args.contrail_internal_vip,
                  self._args.mgmt_ip, self._args.config_index,
                  len(self._args.config_list), self._args.config_ip_list[0],
                  self._args.config0_user, self._args.config0_password)
        if external_vip:
             cmd += ' --external_vip %s' % self._args.contrail_external_vip
        local(cmd)


    def setup_keepalived(self):
        """Provision VIP for openstack nodes with keepalived"""
        self.enable_haproxy()
        local("sudo service haproxy restart")
        cmd = "setup-vnc-keepalived\
               --self_ip %s --internal_vip %s --mgmt_self_ip %s\
               --self_index %d --num_nodes %d --role %s\
               --master_ip %s --master_user %s --master_password %s"\
               % (self._args.self_ip, self._args.internal_vip,
                  self._args.mgmt_ip, self._args.openstack_index,
                  len(self._args.openstack_ip_list),
                  self._args.openstack_ip_list[0], self._args.openstack0_user,
                  self._args.openstack0_password)
        if external_vip:
             cmd += ' --external_vip %s' % self._args.external_vip
        local(cmd)

    def fixup_restart_haproxy(self):
        keystone_server_lines = ''
        keystone_admin_server_lines = ''
        glance_server_lines = ''
        heat_server_lines = ''
        cinder_server_lines = ''
        ceph_restapi_server_lines = ''
        nova_api_server_lines = ''
        nova_meta_server_lines = ''
        nova_vnc_server_lines = ''
        memcached_server_lines = ''
        rabbitmq_server_lines = ''
        mysql_server_lines = ''
        space = ' ' * 3

        for mgmt_host_ip, host_ip in zip(self._args.openstack_mgmt_ip_list,
                                         self._args.openstack_ip_list):
            server_index = self._args.openstack_ip_list.index(host_ip) + 1
            keystone_server_lines +=\
            '%s server %s %s:6000 check inter 2000 rise 2 fall 1\n'\
             % (space, host_ip, host_ip)
            keystone_admin_server_lines +=\
            '%s server %s %s:35358 check inter 2000 rise 2 fall 1\n'\
             % (space, host_ip, host_ip)
            glance_server_lines +=\
            '%s server %s %s:9393 check inter 2000 rise 2 fall 1\n'\
             % (space, host_ip, host_ip)
            heat_server_lines +=\
            '%s server %s %s:8005 check inter 2000 rise 2 fall 1\n'\
             % (space, host_ip, host_ip)
            cinder_server_lines +=\
            '%s server %s %s:9776 check inter 2000 rise 2 fall 3\n'\
             % (space, host_ip, host_ip)
            ceph_restapi_server_lines +=\
            '%s server %s %s:5006 check inter 2000 rise 2 fall 3\n'\
             % (space, host_ip, host_ip)
            nova_api_server_lines +=\
            '%s server %s %s:9774 check inter 2000 rise 2 fall 1\n'\
             % (space, host_ip, host_ip)
            nova_meta_server_lines +=\
            '%s server %s %s:9775 check inter 2000 rise 2 fall 1\n'\
             % (space, host_ip, host_ip)
            nova_vnc_server_lines  +=\
            '%s server %s %s:6999 check inter 2000 rise 2 fall 3\n'\
             % (space, mgmt_host_ip, mgmt_host_ip)
            if server_index <= 2:
                memcached_server_lines +=\
                   '%s server repcache%s %s:11211 check inter 2000 rise 2 fall 3\n'\
                    % (space, server_index, host_ip)
            if server_index == 1:
                rabbitmq_server_lines +=\
                    '%s server rabbit%s %s:5672 weight 200 check inter 2000 rise 2 fall 3\n'\
                     % (space, server_index, host_ip)
            else:
                rabbitmq_server_lines +=\
                    '%s server rabbit%s %s:5672 weight 100 check inter 2000 rise 2 fall 3 backup\n'\
                     % (space, server_index, host_ip)
            if server_index == 1:
                mysql_server_lines +=\
                    '%s server mysql%s %s:3306 weight 200 check inter 2000 rise 2 fall 3\n'\
                     % (space, server_index, host_ip)
            else:
                mysql_server_lines +=\
                   '%s server mysql%s %s:3306 weight 100 check inter 2000 rise 2 fall 3 backup\n'\
                    % (space, server_index, host_ip)

        haproxy_config = openstack_haproxy.template.safe_substitute({
            '__keystone_backend_servers__' : keystone_server_lines,
            '__keystone_admin_backend_servers__' : keystone_admin_server_lines,
            '__glance_backend_servers__' : glance_server_lines,
            '__heat_backend_servers__' : heat_server_lines,
            '__cinder_backend_servers__' : cinder_server_lines,
            '__ceph_restapi_backend_servers__' : ceph_restapi_server_lines,
            '__nova_api_backend_servers__' : nova_api_server_lines,
            '__nova_meta_backend_servers__' : nova_meta_server_lines,
            '__nova_vnc_backend_servers__' : nova_vnc_server_lines,
            '__memcached_servers__' : memcached_server_lines,
            '__rabbitmq_servers__' : rabbitmq_server_lines,
            '__mysql_servers__' : mysql_server_lines,
            '__contrail_hap_user__': 'haproxy',
            '__contrail_hap_passwd__': 'contrail123',
        })

        # chop old settings including pesky default from pkg...
        tmp_fname = "/tmp/haproxy-%s-config" % (host_string)
        get_as_local("sudo /etc/haproxy/haproxy.cfg", tmp_fname)
        with settings(warn_only=True):
            local("sed -i -e '/^#contrail-openstack-marker-start/,/^#contrail-openstack-marker-end/d' %s" % (tmp_fname))
            local("sed -i -e 's/frontend\s*main\s*\*:5000/frontend  main *:5001/' %s" %(tmp_fname))
            local("sed -i -e 's/*:5000/*:5001/' %s" % (tmp_fname))
            local("sed -i -e 's/ssl-relay 0.0.0.0:8443/ssl-relay 0.0.0.0:5002/' %s" % (tmp_fname))
            local("sed -i -e 's/option\shttplog/option                  tcplog/' %s" % (tmp_fname))
            local("sed -i -e 's/maxconn 4096/maxconn 100000/' %s" % (tmp_fname))
            local('sed -i "/^global/a\\        tune.bufsize 16384" %s' % tmp_fname)
            local('sed -i "/^global/a\\        tune.maxrewrite 1024" %s' % tmp_fname)
            local('sed -i "/^global/a\        spread-checks 4" %s' % tmp_fname)
            local('sed -i "/^global/a\        maxconn 10000" %s' % tmp_fname)
            # Remove default HA config
            local("sed -i '/listen\sappli1-rewrite/,/rspidel/d' %s" % tmp_fname)
            local("sed -i '/listen\sappli3-relais/,/rspidel/d' %s" % tmp_fname)
        # ...generate new ones
        with open(tmp_fname, 'a') as cfg_file:
            cfg_file.write(haproxy_config)
        shutil.move(tmp_fname, "/etc/haproxy/haproxy.cfg")

        # haproxy enable
        local("sudo chkconfig haproxy on")
        local("sudo service supervisor-openstack stop")
        self.enable_haproxy()
        local("sudo service haproxy restart")
        #Change the keystone admin/public port
        local("sudo openstack-config --set /etc/keystone/keystone.conf DEFAULT public_port 6000")
        local("sudo openstack-config --set /etc/keystone/keystone.conf DEFAULT admin_port 35358")


    def fixup_restart_haproxy_in_collector(self):
        contrail_analytics_api_server_lines = ''
        space = ' ' * 3

        for host_ip in self._args.collector_ip_list:
            server_index = self._args.collector_ip_list.index(host_ip) + 1
            contrail_analytics_api_server_lines +=\
                '%s server %s %s:9081 check inter 2000 rise 2 fall 3\n'\
                 % (space, host_ip, host_ip)

        haproxy_config = collector_haproxy.template.safe_substitute({
            '__contrail_analytics_api_backend_servers__' : contrail_analytics_api_server_lines,
            '__contrail_hap_user__': 'haproxy',
            '__contrail_hap_passwd__': 'contrail123',
        })

        # chop old settings including pesky default from pkg...
        conf_file = '/etc/haproxy/haproxy.cfg'
        with settings(warn_only=True):
            local("sed -i -e '/^#contrail-collector-marker-start/,/^#contrail-collector-marker-end/d' %s" % (conf_file))
            local("sed -i -e 's/frontend\s*main\s*\*:5000/frontend  main *:5001/' %s" %(conf_file))
            local("sed -i -e 's/ssl-relay 0.0.0.0:8443/ssl-relay 0.0.0.0:5002/' %s" % (conf_file))
            local("sed -i -e 's/option\shttplog/option                  tcplog/' %s" % (conf_file))
            local("sed -i -e 's/maxconn 4096/maxconn 100000/' %s" % (conf_file))
            # Remove default HA config
            local("sed -i '/listen\sappli1-rewrite/,/rspidel/d' %s" % conf_file)
            local("sed -i '/listen\sappli3-relais/,/rspidel/d' %s" % conf_file)
        # ...generate new ones
        with open(conf_file, 'a') as cfg_file:
            cfg_file.write(haproxy_config)

        # haproxy enable
        local("sudo chkconfig haproxy on")
        self.enable_haproxy()
        local("sudo service haproxy restart")

    def fixup_cmon_param(self):
        cmon_param = '/etc/contrail/ha/cmon_param'
        compute_host_list = self._args.compute_host_list

        # Get AMQP host list
        amqp_host_list = self._args.amqp_host_list

        computes = 'COMPUTES=("' + '" "'.join(compute_host_list) + '")'
        local("sudo echo '%s' >> %s" % (computes, cmon_param))
        local("sudo echo 'COMPUTES_SIZE=${#COMPUTES[@]}' >> %s" % cmon_param)
        local("sudo echo 'COMPUTES_USER=root' >> %s" % cmon_param)
        local("sudo echo 'PERIODIC_RMQ_CHK_INTER=120' >> %s" % cmon_param)
        local("sudo echo 'RABBITMQ_RESET=True' >> %s" % cmon_param)
        amqps = 'DIPHOSTS=("' + '" "'.join(amqp_host_list) + '")'
        local("sudo echo '%s' >> %s" % (amqps, cmon_param))
        local("sudo echo 'DIPS_HOST_SIZE=${#DIPHOSTS[@]}' >> %s" % cmon_param)
        local("sudo echo 'EVIP="'%s'"' >> %s" % (self._args.intrnal_vip, cmon_param))

    def create_upload_ssh_keys(self):
        if files.exists('~/.ssh', use_sudo=True):
            local('sudo chmod 700 ~/.ssh')
        if (not files.exists('~/.ssh/id_rsa', use_sudo=True) and
            not files.exists('~/.ssh/id_rsa.pub', use_sudo=True)):
            local('sudo ssh-keygen -b 2048 -t rsa -f ~/.ssh/id_rsa -q -N ""')
        elif (not files.exists('~/.ssh/id_rsa', use_sudo=True) or
             not files.exists('~/.ssh/id_rsa.pub', use_sudo=True)):
            local('sudo rm -rf ~/.ssh/id_rsa*')
            local('sudo ssh-keygen -b 2048 -t rsa -f ~/.ssh/id_rsa -q -N ""')

        # Upload the public key to the first openstack node
        # Which will be later copied to all the openstack/compute nodes.
        openstack0 = '%s@%s' % (self._args.openstack0_user,
                                self._args.openstack_ip_list[0])
        password = self._args.openstack0_password
        pub_key = local("cat ~/.ssh/id_rsa.pub", capture=True)
        with settings(host_string=openstack0, password=password):
            local("echo %s >> %s" % (pub_key, SSH_KEY_UPLOAD_FILE))

    def update_service_token(self):
        local("sudo echo '%s' > /etc/contrail/service.token" % self._args.service_token)

    def setup_cmon_schema(self):
        """Configure cmon schema in the openstack nodes to monitor galera cluster"""
        galera_ip_list = self._args.openstack_ip_list
        internal_vip = self._args.internal_vip

        mysql_token = local("sudo cat /etc/contrail/mysql.token")
        if self.pdist in DEBIAN:
            mysql_svc = 'mysql'
        elif self.pdist in RHEL:
            mysql_svc = 'mysqld'
        # Create cmon schema
        local('sudo mysql -u root -p%s -e "CREATE SCHEMA IF NOT EXISTS cmon"' % mysql_token)
        local('sudo mysql -u root -p%s < /usr/local/cmon/share/cmon/cmon_db.sql' % mysql_token)
        local('sudo mysql -u root -p%s < /usr/local/cmon/share/cmon/cmon_data.sql' % mysql_token)

        # insert static data
        local('sudo mysql -u root -p%s -e "use cmon; insert into cluster(type) VALUES (\'galera\')"' % mysql_token)

        host_list = galera_ip_list + ['localhost', '127.0.0.1', internal_vip]
        # Create cmon user
        for host in host_list:
            mysql_cmon_user_cmd = 'mysql -u root -p%s -e "CREATE USER \'cmon\'@\'%s\' IDENTIFIED BY \'cmon\'"' % (
                                   mysql_token, host)
            with settings(hide('everything'),warn_only=True):
                sudo(mysql_cmon_user_cmd)

        mysql_cmd =  "mysql -uroot -p%s -e" % mysql_token
        # Grant privilages for cmon user.
        for host in host_list:
            local('sudo %s "GRANT ALL PRIVILEGES on *.* TO cmon@%s IDENTIFIED BY \'cmon\' WITH GRANT OPTION"' %
                   (mysql_cmd, host))
        # Restarting mysql in all openstack nodes
        local("sudo service %s restart" % mysql_svc)


    def setup_ha(self):
        #    self.setup_contrail_keepalived')
        #    self.fixup_restart_haproxy_in_collector')

        self.create_upload_ssh_keys() #all compute should get the keys
        self.setup_keepalived()
        self.setup_galera_cluster()
        self.fixup_wsrep_cluster_address()
        self.setup_cmon_schema()
        self.fixup_restart_xinetd_conf()
        self.fixup_restart_haproxy()
        self.setup_glance_images_loc()
        self.fixup_memcache_conf()
        #self.tune_tcp()
        self.fixup_cmon_param()
        self.update_service_token()
