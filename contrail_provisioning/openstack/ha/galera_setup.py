#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import ConfigParser
import time

from fabric.api import local,run
from fabric.context_managers import lcd, hide, settings
from fabric.operations import get, put


from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.openstack.ha.templates import galera_param_template
from contrail_provisioning.openstack.ha.templates import cmon_param_template
from contrail_provisioning.openstack.ha.templates import cmon_conf_template
from contrail_provisioning.openstack.ha.templates import wsrep_conf_template
from contrail_provisioning.openstack.ha.templates import wsrep_conf_centos_template


class GaleraSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(GaleraSetup, self).__init__()
        self.global_defaults = {
            'self_ip': '127.0.0.1',
            'keystone_ip': '127.0.0.1',
            'openstack0_user': 'root',
            'openstack0_password': 'c0ntrail123',
            'external_vip': 'None',
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
        parser.add_argument("--internal_vip", help = "Internal Virtual IP Address of HA Openstack nodes")
        parser.add_argument("--external_vip", help = "External Virtual IP Address of HA Openstack nodes"),
        self._args = parser.parse_args(self.remaining_argv)

    def fixup_config_files(self):
        with settings(warn_only=True):
            local("service contrail-hamon stop")
            local("service cmon stop")
            local("service mysql stop")
            local("rm -rf /var/lib/mysql/grastate.dat")
            local("rm -rf /var/lib/mysql/galera.cache")
            self.cleanup_redo_log()

        # fix galera_param
        template_vals = {'__mysql_host__' : self._args.self_ip,
                         '__mysql_wsrep_nodes__' :
                         '"' + '" "'.join(self._args.galera_ip_list) + '"'}
        self._template_substitute_write(galera_param_template.template,
                                        template_vals,
                                        self._temp_dir_name + '/galera_param')
        local("sudo mv %s/galera_param /etc/contrail/ha/" % (self._temp_dir_name))

        # fix cmon_param
        template_vals = {'__internal_vip__' : self._args.internal_vip,
                         '__haproxy_dips__' :
                         '"' + '" "'.join(self._args.galera_ip_list) + '"',
                         '__external_vip__' : self._args.external_vip}
        self._template_substitute_write(cmon_param_template.template,
                                        template_vals,
                                        self._temp_dir_name + '/cmon_param')
        local("sudo mv %s/cmon_param /etc/contrail/ha/" % (self._temp_dir_name))

        local("echo %s > /etc/contrail/galeraid" % self._args.openstack_index)
        if self.pdist in ['Ubuntu']:
            local("ln -sf /bin/true /sbin/chkconfig")
            self.mysql_svc = 'mysql'
            self.mysql_conf = '/etc/mysql/my.cnf'
            wsrep_conf = '/etc/mysql/conf.d/wsrep.cnf'
            wsrep_conf_file = 'wsrep.cnf'
            wsrep_template = wsrep_conf_template.template
        elif self.pdist in ['centos', 'redhat']:
            self.mysql_svc = 'mysqld'
            self.mysql_conf = '/etc/my.cnf'
            wsrep_conf = self.mysql_conf
            wsrep_conf_file = 'my.cnf'
            wsrep_template = wsrep_conf_centos_template.template
        self.mysql_token_file = '/etc/contrail/mysql.token'

        self.install_mysql_db()
        if self._args.openstack_index == 1:
            self.create_mysql_token_file()
        else:
            self.get_mysql_token_file()
        self.set_mysql_root_password()
        self.setup_grants()
        self.setup_cron()
        # fixup mysql/wsrep config
        local('sed -i -e "s/bind-address/#bind-address/" %s' % self.mysql_conf)
        local('sed -ibak "s/max_connections.*/max_connections=10000/" %s' % self.mysql_conf)
        local('sed -i -e "s/key_buffer/#key_buffer/" %s' % self.mysql_conf)
        local('sed -i -e "s/max_allowed_packet/#max_allowed_packet/" %s' % self.mysql_conf)
        local('sed -i -e "s/thread_stack/#thread_stack/" %s' % self.mysql_conf)
        local('sed -i -e "s/thread_cache_size/#thread_cache_size/" %s' % self.mysql_conf)
        local('sed -i -e "s/myisam-recover/#myisam-recover/" %s' % self.mysql_conf)
        local('sed -i "/\[mysqld\]/a\lock_wait_timeout=600" %s' % self.mysql_conf)
        local('sed -i "/\[mysqld\]/a\interactive_timeout = 60" %s' % self.mysql_conf)
        local('sed -i "/\[mysqld\]/a\wait_timeout = 60" %s' % self.mysql_conf)
        # FIX for UTF8
        if self.pdist in ['Ubuntu']:
            sku = local("dpkg -p contrail-install-packages | grep Version: | cut -d'~' -f2", capture=True)
            if sku == 'icehouse':
                local('sed -i "/\[mysqld\]/a\character-set-server = utf8" %s' % self.mysql_conf)
                local('sed -i "/\[mysqld\]/a\init-connect=\'SET NAMES utf8\'" %s' % self.mysql_conf)
                local('sed -i "/\[mysqld\]/a\collation-server = utf8_general_ci" %s' % self.mysql_conf)

        if self._args.openstack_index == 1:
            wsrep_cluster_address= ''
        else:
            wsrep_cluster_address =  (':4567,'.join(self._args.galera_ip_list) + ':4567')
            
        template_vals = {'__wsrep_nodes__' : wsrep_cluster_address,
                         '__wsrep_node_address__' : self._args.self_ip,
                         '__mysql_token__' : self.mysql_token,
                         '__wsrep_cluster_size__': len(self._args.galera_ip_list),
                         '__wsrep_inc_offset__': self._args.openstack_index*100,
                        }
        self._template_substitute_write(wsrep_template, template_vals,
                                self._temp_dir_name + '/%s' % wsrep_conf_file)
        local("sudo mv %s/%s %s" % (self._temp_dir_name, wsrep_conf_file,
                                    wsrep_conf))
        if self._args.openstack_index == 1:
            local('sed -ibak "s#wsrep_cluster_address=.*#wsrep_cluster_address=gcomm://#g" %s' % (wsrep_conf))

        # fixup cmon config
        template_vals = {'__mysql_nodes__' : ','.join(self._args.galera_ip_list),
                         '__mysql_node_address__' : self._args.internal_vip,
                        }
        self._template_substitute_write(cmon_conf_template.template, template_vals,
                                        self._temp_dir_name + '/cmon.cnf')
        local("sudo mv %s/cmon.cnf /etc/cmon.cnf" % (self._temp_dir_name))

    def install_mysql_db(self):
        local('chkconfig %s on' % self.mysql_svc)
        local('chown -R mysql:mysql /var/lib/mysql/')
        with settings(warn_only=True):
            install_db = local("service %s restart" % self.mysql_svc).failed
        if install_db:
            local('mysql_install_db --user=mysql --ldata=/var/lib/mysql')
            self.cleanup_redo_log()
            local("service %s restart" % self.mysql_svc)

    def create_mysql_token_file(self):
        # Use MYSQL_ROOT_PW from the environment or generate a new password
        if os.path.isfile(self.mysql_token_file):
            self.mysql_token = local('cat %s' % self.mysql_token_file, capture=True).strip()
        else:
            if os.environ.get('MYSQL_ROOT_PW'):
                self.mysql_token = os.environ.get('MYSQL_ROOT_PW')
            else:
                 self.mysql_token = local('openssl rand -hex 10', capture=True).strip()
            local("echo %s > %s" % (self.mysql_token, self.mysql_token_file))
            local("chmod 400 %s" % self.mysql_token_file)

    def get_mysql_token_file(self):
        retries = 10
        if not os.path.isfile(self.mysql_token_file):
            while retries:
                with settings(host_string = '%s@%s' % (self._args.openstack0_user, self._args.galera_ip_list[0]),
                              password=self._args.openstack0_passwd, warn_only=True):
                    if get('%s' % self.mysql_token_file, '/etc/contrail/').failed:
                        time.sleep(1)
                        retries -= 1
                        print " Retry(%s) to get the %s." % ((5 - retries), self.mysql_token_file)
                    else:
                        break
        self.mysql_token = local('cat %s' % self.mysql_token_file, capture=True).strip()

    def set_mysql_root_password(self):
        # Only for the very first time
        mysql_priv_access = "mysql -uroot -e"
        # Set root password for mysql
        with settings(warn_only=True):
            if local('echo show databases |mysql -u root > /dev/null').succeeded:
                local('%s "use mysql; update user set password=password(\'%s\') where user=\'root\'"' % (mysql_priv_access, self.mysql_token))
                local('mysqladmin password %s' % self.mysql_token)
            elif local('echo show databases |mysql -u root -p%s> /dev/null' % self.mysql_token).succeeded:
                print "Mysql root password is already set to '%s'" % self.mysql_token
            else:
                raise RuntimeError("MySQL root password unknown, reset and retry")

    def setup_grants(self):
        mysql_cmd =  "mysql --defaults-file=%s -uroot -p%s -e" % (self.mysql_conf, self.mysql_token)
        host_list = self._args.galera_ip_list + ['localhost', '127.0.0.1']
        for host in host_list:
            with settings(hide('everything'),warn_only=True):
                 local('mysql -u root -p%s -e "CREATE USER \'root\'@\'%s\' IDENTIFIED BY %s"' % (self.mysql_token, host, self.mysql_token))
            local('%s "SET WSREP_ON=0;SET SQL_LOG_BIN=0; GRANT ALL ON *.* TO root@%s IDENTIFIED BY \'%s\'"' %
                   (mysql_cmd, host, self.mysql_token))
        local('%s "SET wsrep_on=OFF; DELETE FROM mysql.user WHERE user=\'\'"' % mysql_cmd)
        local('%s "FLUSH PRIVILEGES"' % mysql_cmd)

    def setup_cron(self):
        with settings(hide('everything'), warn_only=True):
            local('crontab -l > %s/galera_cron' % self._temp_dir_name)
        local('echo "0 * * * * /opt/contrail/bin/contrail-token-clean.sh" >> %s/galera_cron' % self._temp_dir_name)
        local('crontab %s/galera_cron' % self._temp_dir_name)
        local('rm %s/galera_cron' % self._temp_dir_name)

    def run_services(self):
        self.cleanup_redo_log()
        if self._args.openstack_index == 1:
            local("service %s restart" % self.mysql_svc)
        else:
            cmd = "mysql -h%s -uroot -p%s " % (self._args.galera_ip_list[0], self.mysql_token)
            cmd += "-e \"show global status where variable_name='wsrep_local_state'\" | awk '{print $2}' | sed '1d'"
            for i in range(10):
                wsrep_local_state = local(cmd, capture=True).strip()
                if wsrep_local_state == '4':
                    break
                else:
                    time.sleep(2)
                    print "Waiting for first galera node to create new cluster."
            if wsrep_local_state != '4':
                raise RuntimeError("Unable able to bring up galera in first node, please verify and continue.")
            local("service %s restart" % self.mysql_svc)
        local("sudo update-rc.d -f mysql remove")
        local("sudo update-rc.d mysql defaults")

    def cleanup_redo_log(self):
        # Delete the default initially created redo log file
        # This is required coz the wsrep config changes the
        # size of redo log file
        with settings(warn_only = True):
            siz = local("ls -l /var/lib/mysql/ib_logfile1 | awk '{print $5}'", capture=True).strip()
            if siz == self.mysql_redo_log_sz:
                local("rm -rf /var/lib/mysql/ib_logfile*")

def main(args_str = None):
    galera = GaleraSetup(args_str)
    galera.setup()

if __name__ == "__main__":
    main() 
