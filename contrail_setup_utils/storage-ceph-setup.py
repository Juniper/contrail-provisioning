#!/usr/bin/python

import argparse
import ConfigParser

import platform
import os
import sys
import time
import re
import string
import socket
import netifaces, netaddr
import subprocess
import fnmatch
import struct
import shutil
import json
from pprint import pformat
import xml.etree.ElementTree as ET
import platform

import tempfile
from fabric.api import local, env, run
from fabric.operations import get, put
from fabric.context_managers import lcd, settings
from fabric.api import local, env, run
from fabric.operations import get, put
from fabric.context_managers import lcd, settings
sys.path.insert(0, os.getcwd())

class SetupCeph(object):

    def reset_mon_local_list(self):
	local('echo "get_local_daemon_ulist() {" > /tmp/mon_local_list.sh')
	local('echo "if [ -d \\"/var/lib/ceph/mon\\" ]; then" >> /tmp/mon_local_list.sh')
	local('echo  "for i in \`find -L /var/lib/ceph/mon -mindepth 1 -maxdepth 1 -type d -printf \'%f\\\\\\n\'\`; do" >> /tmp/mon_local_list.sh')
	local('echo "if [ -e \\"/var/lib/ceph/mon/\$i/upstart\\" ]; then" >>  /tmp/mon_local_list.sh')
	local('echo "id=\`echo \$i | sed \'s/[^-]*-//\'\`" >>  /tmp/mon_local_list.sh')
	local('echo "sudo stop ceph-mon id=\$id"  >> /tmp/mon_local_list.sh')
	local('echo "fi done fi"  >> /tmp/mon_local_list.sh')
	local('echo "}"  >> /tmp/mon_local_list.sh')
	local('echo "get_local_daemon_ulist"  >> /tmp/mon_local_list.sh')
	local('echo "exit 0" >> /tmp/mon_local_list.sh')
	local('chmod a+x /tmp/mon_local_list.sh')
	local('/tmp/mon_local_list.sh')

    def reset_osd_local_list(self):
	local('echo "get_local_daemon_ulist() {" > /tmp/osd_local_list.sh')
	local('echo "if [ -d \\"/var/lib/ceph/osd\\" ]; then" >> /tmp/osd_local_list.sh')
	local('echo  "for i in \`find -L /var/lib/ceph/osd -mindepth 1 -maxdepth 1 -type d -printf \'%f\\\\\\n\'\`; do" >> /tmp/osd_local_list.sh')
	local('echo "if [ -e \\"/var/lib/ceph/osd/\$i/upstart\\" ]; then" >>  /tmp/osd_local_list.sh')
	local('echo "id=\`echo \$i | sed \'s/[^-]*-//\'\`" >>  /tmp/osd_local_list.sh')
	local('echo "sudo stop ceph-osd id=\$id"  >> /tmp/osd_local_list.sh')
	local('echo "fi done fi"  >> /tmp/osd_local_list.sh')
	local('echo "}"  >> /tmp/osd_local_list.sh')
	local('echo "get_local_daemon_ulist"  >> /tmp/osd_local_list.sh')
	local('echo "exit 0" >> /tmp/osd_local_list.sh')
	local('chmod a+x /tmp/osd_local_list.sh')
	local('/tmp/osd_local_list.sh')

    def reset_mon_remote_list(self):
	run('echo "get_local_daemon_ulist() {" > /tmp/mon_local_list.sh')
	run('echo "if [ -d \\\\"/var/lib/ceph/mon\\\\" ]; then" >> /tmp/mon_local_list.sh')
	run('echo  "for i in \\\\`find -L /var/lib/ceph/mon -mindepth 1 -maxdepth 1 -type d -printf \'%f\\\\\\n\'\\\\`; do" >> /tmp/mon_local_list.sh')
	run('echo "if [ -e \\\\"/var/lib/ceph/mon/\\\\$i/upstart\\\\" ]; then" >>  /tmp/mon_local_list.sh')
	run('echo "id=\\\\`echo \\\\$i | sed \'s/[^-]*-//\'\\\\`" >>  /tmp/mon_local_list.sh')
	run('echo "sudo stop ceph-mon id=\\\\$id"  >> /tmp/mon_local_list.sh')
	run('echo "fi done fi"  >> /tmp/mon_local_list.sh')
	run('echo "}"  >> /tmp/mon_local_list.sh')
	run('echo "get_local_daemon_ulist"  >> /tmp/mon_local_list.sh')
	run('echo "exit 0" >> /tmp/mon_local_list.sh')
	run('chmod a+x /tmp/mon_local_list.sh')
	run('/tmp/mon_local_list.sh')

    def reset_osd_remote_list(self):
	run('echo "get_local_daemon_ulist() {" > /tmp/osd_local_list.sh')
	run('echo "if [ -d \\\\"/var/lib/ceph/osd\\\\" ]; then" >> /tmp/osd_local_list.sh')
	run('echo  "for i in \\\\`find -L /var/lib/ceph/osd -mindepth 1 -maxdepth 1 -type d -printf \'%f\\\\\\n\'\\\\`; do" >> /tmp/osd_local_list.sh')
	run('echo "if [ -e \\\\"/var/lib/ceph/osd/\\\\$i/upstart\\\\" ]; then" >>  /tmp/osd_local_list.sh')
	run('echo "id=\\\\`echo \\\\$i | sed \'s/[^-]*-//\'\\\\`" >>  /tmp/osd_local_list.sh')
	run('echo "sudo stop ceph-osd id=\\\\$id"  >> /tmp/osd_local_list.sh')
	run('echo "fi done fi"  >> /tmp/osd_local_list.sh')
	run('echo "}"  >> /tmp/osd_local_list.sh')
	run('echo "get_local_daemon_ulist"  >> /tmp/osd_local_list.sh')
	run('echo "exit 0" >> /tmp/osd_local_list.sh')
	run('chmod a+x /tmp/osd_local_list.sh')
	run('/tmp/osd_local_list.sh')

    def __init__(self, args_str = None):
        #print sys.argv[1:]
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])
        self._parse_args(args_str)
        for entries, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
            with settings(host_string = 'root@%s' %(entries), password = entry_token):
                for hostname, host_ip in zip(self._args.storage_hostnames, self._args.storage_hosts):
                    run('cat /etc/hosts |grep -v %s > /tmp/hosts; echo %s %s >> /tmp/hosts; cp -f /tmp/hosts /etc/hosts' % (hostname, host_ip, hostname))
        ceph_mon_hosts=''
        pdist = platform.dist()[0]

        for entries in self._args.storage_hostnames:
            ceph_mon_hosts=ceph_mon_hosts+entries+' '

        #print ceph_mon_hosts
        # setup SSH for autologin for Ceph
        rsa_present=local('sudo ls ~/.ssh/id_rsa | wc -l', capture=True)
        if rsa_present != '1':
            local('sudo ssh-keygen -t rsa -N ""  -f ~/.ssh/id_rsa')
        sshkey=local('cat ~/.ssh/id_rsa.pub', capture=True)
        local('sudo mkdir -p ~/.ssh')
        already_present=local('grep "%s" ~/.ssh/known_hosts | wc -l' % (sshkey), capture=True)
	if already_present == '0':
	    local('sudo echo "%s" >> ~/.ssh/known_hosts' % (sshkey))
        already_present=local('grep "%s" ~/.ssh/authorized_keys | wc -l' % (sshkey), capture=True)
	if already_present == '0':
            local('sudo echo "%s" >> ~/.ssh/authorized_keys' % (sshkey))
        for entries, entry_token, hostname in zip(self._args.storage_hosts, self._args.storage_host_tokens, self._args.storage_hostnames):
            if entries != self._args.storage_master:
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    run('sudo mkdir -p ~/.ssh')
                    already_present=run('grep "%s" ~/.ssh/known_hosts | wc -l' % (sshkey))
                    print already_present
	            if already_present == '0':
                        run('sudo echo %s >> ~/.ssh/known_hosts' % (sshkey))
                    already_present=run('grep "%s" ~/.ssh/authorized_keys | wc -l' % (sshkey))
                    print already_present
	            if already_present == '0':
                        run('sudo echo %s >> ~/.ssh/authorized_keys' % (sshkey))
                    hostfound = local('sudo grep %s,%s ~/.ssh/known_hosts | wc -l' %(hostname,entries), capture=True)
                    if hostfound == "0":
                         out = run('sudo ssh-keyscan -t rsa %s,%s' %(hostname,entries))
                         local('sudo echo "%s" >> ~/.ssh/known_hosts' % (out))
                         #local('sudo echo "%s" >> ~/.ssh/authorized_keys' % (out))
        #Add a new node to the existing cluster
        if self._args.add_storage_node:
            ip_cidr=local('ip addr show |grep %s |awk \'{print $2}\'' %(self._args.storage_master), capture=True)
            local('sudo openstack-config --set /root/ceph.conf global public_network %s\/%s' %(netaddr.IPNetwork(ip_cidr).network, netaddr.IPNetwork(ip_cidr).prefixlen))
            add_storage_node = self._args.add_storage_node
            for entries, entry_token, hostname in zip(self._args.storage_hosts, self._args.storage_host_tokens, self._args.storage_hostnames):
                if hostname == add_storage_node:
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        ceph_running=run('ps -ef|grep ceph |grep -v grep|wc -l')
                        if ceph_running != '0':
                            print 'Ceph already running in node'
                            return
                        run('sudo mkdir -p /var/lib/ceph/bootstrap-osd')
                        run('sudo mkdir -p /var/lib/ceph/osd')
                        run('sudo mkdir -p /etc/ceph')
            local('sudo ceph-deploy --overwrite-conf mon create-initial %s' % (add_storage_node))
            if self._args.storage_directory_config[0] != 'none':
                for directory in self._args.storage_directory_config:
                    dirsplit = directory.split(':')
                    if dirsplit[0] == add_storage_node:
                        with settings(host_string = 'root@%s' %(entries), password = entry_token):
                            run('sudo mkdir -p %s' % (dirsplit[1]))
                            run('sudo rm -rf %s' % (dirsplit[1]))
                            run('sudo mkdir -p %s' % (dirsplit[1]))
                        local('sudo ceph-deploy osd prepare %s' % (directory))
                        local('sudo ceph-deploy osd activate %s' % (directory))
            if self._args.storage_disk_config[0] != 'none':
                for disks in self._args.storage_disk_config:
                    dirsplit = disks.split(':')
                    if dirsplit[0] == add_storage_node:
                        local('sudo ceph-deploy disk zap %s' % (disks))
	                if pdist == 'centos':
		            local('sudo ceph-deploy osd create %s' % (disks))
	                if pdist == 'Ubuntu':
                            local('sudo ceph-deploy osd prepare %s' % (disks))
                            local('sudo ceph-deploy osd activate %s' % (disks))
            virsh_secret=local('virsh secret-list  2>&1 |cut -d " " -f 1 | awk \'NR > 2 { print }\' | head -n 1', capture=True)
            volume_keyring_list=local('cat /etc/ceph/client.volumes.keyring | grep key', capture=True)
            volume_keyring=volume_keyring_list.split(' ')[2]
            for entries, entry_token, hostname in zip(self._args.storage_hosts, self._args.storage_host_tokens, self._args.storage_hostnames):
                if hostname == add_storage_node:
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        virsh_unsecret=run('virsh secret-list  2>&1 |cut -d " " -f 1 | awk \'NR > 2 { print }\' | head -n 1')
                        if virsh_unsecret != "":
                            run('virsh secret-undefine %s' %(virsh_unsecret))
                        run('echo "<secret ephemeral=\'no\' private=\'no\'>\n<uuid>%s</uuid><usage type=\'ceph\'>\n<name>client.volumes secret</name>\n</usage>\n</secret>" > secret.xml' % (virsh_secret))
                        run('virsh secret-define --file secret.xml')
                        run('virsh secret-set-value %s --base64 %s' % (virsh_secret,volume_keyring))
                        # Change nova conf for cinder client configuration
                        run('sudo openstack-config --set /etc/nova/nova.conf DEFAULT rbd_user volumes')
                        run('sudo openstack-config --set /etc/nova/nova.conf DEFAULT rbd_secret_uuid %s' % (virsh_secret))
                        run('sudo openstack-config --set /etc/nova/nova.conf DEFAULT cinder_endpoint_template "http://%s:8776/v1/%%(project_id)s"' % (self._args.storage_master), shell='/bin/bash')
                        if pdist == 'centos':
                            run('sudo service openstack-cinder-api restart')
                            run('sudo chkconfig openstack-cinder-api on')
                            run('sudo service openstack-cinder-scheduler restart')
                            run('sudo chkconfig openstack-cinder-scheduler on')
                            bash_cephargs = run('grep "bashrc" /etc/init.d/openstack-cinder-volume | wc -l')
                            if bash_cephargs == "0":
                                run('cat /etc/init.d/openstack-cinder-volume | sed "s/start)/start)  source ~\/.bashrc/" > /tmp/openstack-cinder-volume.tmp')
                                run('mv -f /tmp/openstack-cinder-volume.tmp /etc/init.d/openstack-cinder-volume; chmod a+x /etc/init.d/openstack-cinder-volume')
                            run('sudo chkconfig openstack-cinder-volume on')
                            run('sudo service openstack-cinder-volume restart')
                            run('sudo service libvirtd restart')
                            run('sudo service openstack-nova-compute restart')
                        if pdist == 'Ubuntu':
                            run('sudo service libvirt-bin restart')
                            run('sudo service nova-compute restart')
            return

        #Normal storage install. Remove previous configuration and reconfigure
        ocs_blk_disk = local('(. /etc/contrail/openstackrc ; cinder type-list | grep ocs-block-disk | cut -d"|" -f 2)', capture=True)
        if ocs_blk_disk != "":
            if self._args.storage_setup_mode == 'setup':
                print 'Storage already configured'
                return
            cinderlst = local('(. /etc/contrail/openstackrc ;  cinder list | grep ocs-block-disk | cut -d"|" -f 2)',  capture=True)
	    if cinderlst != "":
		cinderalst = cinderlst.split('\n')
		for x in cinderalst:
		    inuse = local('(. /etc/contrail/openstackrc ;  cinder list | grep %s | cut -d"|" -f 3)' % (x),  capture=True)
                    if inuse == "in-use":
                        detach = local('(. /etc/contrail/openstackrc ;  cinder list | grep %s | cut -d"|" -f 8)' % (x),  capture=True)
	                local('(. /etc/contrail/openstackrc ;  nova volume-detach %s %s)' % (detach, x))
		    local('(. /etc/contrail/openstackrc ;  cinder force-delete %s)' % (x))
            local('. /etc/contrail/openstackrc ; cinder type-delete %s' % (ocs_blk_disk))
        # stop existing ceph monitor/osd
        local('pwd')
	if pdist == 'centos':
            local('/etc/init.d/ceph stop osd')
            local('/etc/init.d/ceph stop mon')
        if pdist == 'Ubuntu':
	    self.reset_mon_local_list()
	    self.reset_osd_local_list()
        #local('chmod a+x /tmp/ceph.stop.sh')
        #local('/tmp/ceph.stop.sh')
        for entries, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
            if entries != self._args.storage_master:
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    if pdist == 'centos':
                        run('echo "/etc/init.d/ceph stop osd" > /tmp/ceph.stop.sh')
                        run('echo "/etc/init.d/ceph stop mon" >> /tmp/ceph.stop.sh')
                        run('chmod a+x /tmp/ceph.stop.sh')
                        run('/tmp/ceph.stop.sh')
		    if pdist == 'Ubuntu':
                        self.reset_mon_remote_list()
                        self.reset_osd_remote_list()
	time.sleep(2)
	local('sudo ceph-deploy purgedata %s <<< \"y\"' % (ceph_mon_hosts), capture=False, shell='/bin/bash')
        if self._args.storage_setup_mode == 'unconfigure':
            print 'Storage configuration removed'
            return
        local('sudo mkdir -p /var/lib/ceph/bootstrap-osd')
        local('sudo mkdir -p /var/lib/ceph/osd')
        local('sudo mkdir -p /etc/ceph')
        if self._args.storage_directory_config[0] != 'none':
            for directory in self._args.storage_directory_config:
                for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
                    dirsplit = directory.split(':')
                    if dirsplit[0] == hostname:
                        if entries != self._args.storage_master:
                            with settings(host_string = 'root@%s' %(entries), password = entry_token):
                                run('sudo mkdir -p %s' % (dirsplit[1]))
                                run('sudo rm -rf %s' % (dirsplit[1]))
                                run('sudo mkdir -p %s' % (dirsplit[1]))
                        else:
                            local('sudo mkdir -p %s' % (dirsplit[1]))
                            local('sudo rm -rf %s' % (dirsplit[1]))
                            local('sudo mkdir -p %s' % (dirsplit[1]))

        for entries, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
            if entries != self._args.storage_master:
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    run('sudo mkdir -p /var/lib/ceph/bootstrap-osd')
                    run('sudo mkdir -p /var/lib/ceph/osd')
                    run('sudo mkdir -p /etc/ceph')
        # Ceph deploy create monitor
        local('sudo ceph-deploy new %s' % (ceph_mon_hosts))
        local('sudo ceph-deploy mon create %s' % (ceph_mon_hosts))
        if self._args.storage_disk_config[0] != 'none':
            for disks in self._args.storage_disk_config:
                local('sudo ceph-deploy disk zap %s' % (disks))
	time.sleep(10)
        for entries in self._args.storage_hostnames:
            local('sudo ceph-deploy gatherkeys %s' % (entries))
        # Ceph deploy OSD create
        if self._args.storage_directory_config[0] != 'none':
            for directory in self._args.storage_directory_config:
                local('sudo ceph-deploy osd prepare %s' % (directory))
            for directory in self._args.storage_directory_config:
                local('sudo ceph-deploy osd activate %s' % (directory))
        if self._args.storage_disk_config[0] != 'none':
            for disks in self._args.storage_disk_config:
	        if pdist == 'centos':
		    local('sudo ceph-deploy osd create %s' % (disks))
	        if pdist == 'Ubuntu':
                    local('sudo ceph-deploy osd prepare %s' % (disks))
                    local('sudo ceph-deploy osd activate %s' % (disks))
        # Create pools
        local('unset CEPH_ARGS')
        local('sudo rados mkpool volumes')
        local('sudo rados mkpool images')
        #local('sudo ceph osd pool set images size 3')
        #local('sudo ceph osd pool set volumes size 3')
        # Authentication Configuration
        local('sudo ceph auth get-or-create client.volumes mon \'allow r\' osd \'allow class-read object_prefix rbd_children, allow rwx pool=volumes, allow rx pool=images\' -o /etc/ceph/client.volumes.keyring')
        local('sudo ceph auth get-or-create client.images mon \'allow r\' osd \'allow class-read object_prefix rbd_children, allow rwx pool=images\' -o /etc/ceph/client.images.keyring')
        local('sudo openstack-config --set /etc/ceph/ceph.conf client.volumes keyring /etc/ceph/client.volumes.keyring')
        local('sudo openstack-config --set /etc/ceph/ceph.conf client.images keyring /etc/ceph/client.images.keyring')
        for entries, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
            if entries != self._args.storage_master:
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    run('unset CEPH_ARGS')
                    run('sudo ceph -k /etc/ceph/ceph.client.admin.keyring  auth get-or-create client.volumes mon \'allow r\' osd \'allow class-read object_prefix rbd_children, allow rwx pool=volumes, allow rx pool=images\' -o /etc/ceph/client.volumes.keyring')
                    run('sudo ceph -k /etc/ceph/ceph.client.admin.keyring auth get-or-create client.images mon \'allow r\' osd \'allow class-read object_prefix rbd_children, allow rwx pool=images\' -o /etc/ceph/client.images.keyring')
                    run('sudo openstack-config --set /etc/ceph/ceph.conf client.volumes keyring /etc/ceph/client.volumes.keyring')
                    run('sudo openstack-config --set /etc/ceph/ceph.conf client.images keyring /etc/ceph/client.images.keyring')
        local('cat ~/.bashrc |grep -v CEPH_ARGS > /tmp/.bashrc')
        local('mv -f /tmp/.bashrc ~/.bashrc')
        local('echo export CEPH_ARGS=\\"--id volumes\\" >> ~/.bashrc')
        local('. ~/.bashrc')
        local('ceph-authtool -p -n client.volumes /etc/ceph/client.volumes.keyring > /etc/ceph/client.volumes')
        if pdist == 'centos':
            local('sudo service libvirtd restart')
        if pdist == 'Ubuntu':
            local('sudo service libvirt-bin restart')
        virsh_unsecret=local('virsh secret-list  2>&1 |cut -d " " -f 1 | awk \'NR > 2 { print }\' | head -n 1', capture=True)
        if virsh_unsecret != "":
            local('virsh secret-undefine %s' %(virsh_unsecret))
        local('echo "<secret ephemeral=\'no\' private=\'no\'>\n<usage type=\'ceph\'>\n<name>client.volumes secret</name>\n</usage>\n</secret>" > secret.xml')
        virsh_secret=local('virsh secret-define --file secret.xml  2>&1 |cut -d " " -f 2', capture=True)
        volume_keyring_list=local('cat /etc/ceph/client.volumes.keyring | grep key', capture=True)
        volume_keyring=volume_keyring_list.split(' ')[2]
        local('virsh secret-set-value %s --base64 %s' % (virsh_secret,volume_keyring))
        # remove this line
        # local('virsh secret-undefine %s' % (virsh_secret))
        #print volume_keyring
        #print virsh_secret
        for entries, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
            if entries != self._args.storage_master:
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    if pdist == 'centos':
                        run('cat ~/.bashrc |grep -v CEPH_ARGS > /tmp/.bashrc')
                        run('mv -f /tmp/.bashrc ~/.bashrc')
                        run('echo export CEPH_ARGS=\\\\"--id volumes\\\\" >> ~/.bashrc')
                        run('. ~/.bashrc')
                        run('sudo ceph-authtool -p -n client.volumes /etc/ceph/client.volumes.keyring > /etc/ceph/client.volumes')
                        local('sudo service libvirtd restart')
                    if pdist == 'Ubuntu':
                        run('sudo ceph-authtool -p -n client.volumes /etc/ceph/client.volumes.keyring > /etc/ceph/client.volumes')
                        local('sudo service libvirt-bin restart')
                    virsh_unsecret=run('virsh secret-list  2>&1 |cut -d " " -f 1 | awk \'NR > 2 { print }\' | head -n 1')
                    if virsh_unsecret != "":
                        run('virsh secret-undefine %s' %(virsh_unsecret))
                    run('echo "<secret ephemeral=\'no\' private=\'no\'>\n<uuid>%s</uuid><usage type=\'ceph\'>\n<name>client.volumes secret</name>\n</usage>\n</secret>" > secret.xml' % (virsh_secret))
                    run('virsh secret-define --file secret.xml')
                    run('virsh secret-set-value %s --base64 %s' % (virsh_secret,volume_keyring))
                    # remove this line
                    # run('virsh secret-undefine %s' % (virsh_secret))
        # Cinder Configuration
        local('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT enabled_backends rbd-disk')
        local('sudo cat /etc/cinder/cinder.conf |grep -v "\\[rbd-disk\\]"| sed s/rbd-disk/"rbd-disk\\n\\n[rbd-disk]"/ > /etc/cinder/cinder.conf.bk')
        local('sudo cp /etc/cinder/cinder.conf.bk /etc/cinder/cinder.conf')
        local('sudo openstack-config --set /etc/cinder/cinder.conf rbd-disk volume_driver cinder.volume.drivers.rbd.RBDDriver')
        local('sudo openstack-config --set /etc/cinder/cinder.conf rbd-disk rbd_pool volumes')
        local('sudo openstack-config --set /etc/cinder/cinder.conf rbd-disk rbd_user volumes')
        local('sudo openstack-config --set /etc/cinder/cinder.conf rbd-disk rbd_secret_uuid %s' % (virsh_secret))
        local('sudo openstack-config --set /etc/cinder/cinder.conf rbd-disk glance_api_version 2')
        local('sudo openstack-config --set /etc/cinder/cinder.conf rbd-disk volume_backend_name RBD')
        admin_pass = local('cat /etc/cinder/cinder.conf | grep admin_password | cut -d "=" -f 2', capture=True)
        for entries, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
            if entries != self._args.storage_master:
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    # Change nova conf for cinder client configuration
                    run('sudo openstack-config --set /etc/nova/nova.conf DEFAULT rbd_user volumes')
                    run('sudo openstack-config --set /etc/nova/nova.conf DEFAULT rbd_secret_uuid %s' % (virsh_secret))
                    run('sudo openstack-config --set /etc/nova/nova.conf DEFAULT cinder_endpoint_template "http://%s:8776/v1/%%(project_id)s"' % (self._args.storage_master), shell='/bin/bash')

        #Glance configuration
        local('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT default_store rbd')
        local('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT show_image_direct_url True')
        local('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT rbd_store_user images')

        #Restart services
        if pdist == 'centos':
            local('sudo service qpidd restart')
            local('sudo service quantum-server restart')
            local('sudo chkconfig openstack-cinder-api on')
            local('sudo service openstack-cinder-api restart')
            local('sudo chkconfig openstack-cinder-scheduler on')
            local('sudo service openstack-cinder-scheduler restart')
            bash_cephargs = local('grep "bashrc" /etc/init.d/openstack-cinder-volume | wc -l', capture=True)
            if bash_cephargs == "0":
                local('cat /etc/init.d/openstack-cinder-volume | sed "s/start)/start)  source ~\/.bashrc/" > /tmp/openstack-cinder-volume.tmp')
                local('mv -f /tmp/openstack-cinder-volume.tmp /etc/init.d/openstack-cinder-volume; chmod a+x /etc/init.d/openstack-cinder-volume')
            local('sudo chkconfig openstack-cinder-volume on')
            local('sudo service openstack-cinder-volume restart')
            local('sudo service openstack-glance-api restart')
            local('sudo service openstack-nova-api restart')
            local('sudo service openstack-nova-conductor restart')
            local('sudo service openstack-nova-scheduler restart')
            local('sudo service libvirtd restart')
            local('sudo service openstack-nova-api restart')
            local('sudo service openstack-nova-scheduler restart')
        if pdist == 'Ubuntu':
            local('sudo chkconfig cinder-api on')
            local('sudo service cinder-api restart')
            local('sudo chkconfig cinder-scheduler on')
            local('sudo service cinder-scheduler restart')
            bash_cephargs = local('grep "CEPH_ARGS" /etc/init.d/cinder-volume | wc -l', capture=True)
            print bash_cephargs
            if bash_cephargs == "0":
                local('cat /etc/init.d/cinder-volume | awk \'{ print; if ($1== "start|stop)") print \"    CEPH_ARGS=\\"--id volumes\\"\" }\' > /tmp/cinder-volume.tmp') 
                local('mv -f /tmp/cinder-volume.tmp /etc/init.d/cinder-volume; chmod a+x /etc/init.d/cinder-volume')
            local('sudo chkconfig cinder-volume on')
            local('sudo service cinder-volume restart')
            local('sudo service glance-api restart')
            local('sudo service nova-api restart')
            local('sudo service nova-conductor restart')
            local('sudo service nova-scheduler restart')
            local('sudo service libvirt-bin restart')
            local('sudo service nova-api restart')
            local('sudo service nova-scheduler restart')
        local('(. /etc/contrail/openstackrc ; cinder type-create ocs-block-disk)')
        local('(. /etc/contrail/openstackrc ; cinder type-key ocs-block-disk set volume_backend_name=RBD)')
        local('sudo service cinder-volume restart')
        avail=local('rados df | grep avail | awk  \'{ print $3 }\'', capture = True)
        # use only half the space as 1 replica is enabled
        avail_gb = int(avail)/1024/1024/2
        local('(. /etc/contrail/openstackrc ; cinder quota-update ocs-block-disk --gigabytes %s)' % (avail_gb))
        #local('(. /etc/contrail/openstackrc ; cinder quota-update ocs-block-disk --gigabytes 1000)')
        local('(. /etc/contrail/openstackrc ; cinder quota-update ocs-block-disk --volumes 100)')
        local('(. /etc/contrail/openstackrc ; cinder quota-update ocs-block-disk --snapshots 100)')
        for entries, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
            if entries != self._args.storage_master:
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    if pdist == 'centos':
                        run('sudo service openstack-cinder-api restart')
                        run('sudo chkconfig openstack-cinder-api on')
                        run('sudo service openstack-cinder-scheduler restart')
                        run('sudo chkconfig openstack-cinder-scheduler on')
                        bash_cephargs = run('grep "bashrc" /etc/init.d/openstack-cinder-volume | wc -l')
                        if bash_cephargs == "0":
                            run('cat /etc/init.d/openstack-cinder-volume | sed "s/start)/start)  source ~\/.bashrc/" > /tmp/openstack-cinder-volume.tmp')
                            run('mv -f /tmp/openstack-cinder-volume.tmp /etc/init.d/openstack-cinder-volume; chmod a+x /etc/init.d/openstack-cinder-volume')
                        run('sudo chkconfig openstack-cinder-volume on')
                        run('sudo service openstack-cinder-volume restart')
                        run('sudo service libvirtd restart')
                        run('sudo service openstack-nova-compute restart')
                    if pdist == 'Ubuntu':
                        run('sudo service libvirt-bin restart')
                        run('sudo service nova-compute restart')

    #end __init__

    def _parse_args(self, args_str):
        '''
        Eg. python storage-ceph-setup.py --storage-master 10.157.43.171 --storage-hostnames cmbu-dt05 cmbu-ixs6-2 --storage-hosts 10.157.43.171 10.157.42.166 --storage-host-tokens n1keenA n1keenA --storage-disk-config 10.157.43.171:sde 10.157.43.171:sdf 10.157.43.171:sdg --storage-directory-config 10.157.42.166:/mnt/osd0 --live-migration enabled
        '''

        # Source any specified config/ini file
        # Turn off help, so we print all options in response to -h
        conf_parser = argparse.ArgumentParser(add_help = False)

        conf_parser.add_argument("-c", "--conf_file",
                                 help="Specify config file", metavar="FILE")
        args, remaining_argv = conf_parser.parse_known_args(args_str.split())

        global_defaults = {
        }

        if args.conf_file:
            config = ConfigParser.SafeConfigParser()
            config.read([args.conf_file])
            global_defaults.update(dict(config.items("GLOBAL")))

        # Override with CLI options
        # Don't surpress add_help here so it will handle -h
        parser = argparse.ArgumentParser(
            # Inherit options from config_parser
            parents=[conf_parser],
            # print script description with -h/--help
            description=__doc__,
            # Don't mess with format of description
            formatter_class=argparse.RawDescriptionHelpFormatter,
            )

        all_defaults = {'global': global_defaults}
        parser.set_defaults(**all_defaults)

        parser.add_argument("--storage-master", help = "IP Address of storage master node")
        parser.add_argument("--storage-hostnames", help = "Host names of storage nodes", nargs='+', type=str)
        parser.add_argument("--storage-hosts", help = "IP Addresses of storage nodes", nargs='+', type=str)
        parser.add_argument("--storage-host-tokens", help = "Passwords of storage nodes", nargs='+', type=str)
        parser.add_argument("--storage-disk-config", help = "Disk list to be used for distrubuted storage", nargs="+", type=str)
        parser.add_argument("--storage-directory-config", help = "Directories to be sued for distributed storage", nargs="+", type=str)
        parser.add_argument("--add-storage-node", help = "Add a new storage node")
        parser.add_argument("--storage-setup-mode", help = "Storage configuration mode")

        self._args = parser.parse_args(remaining_argv)

    #end _parse_args

#end class SetupCeph

def main(args_str = None):
    SetupCeph(args_str)
#end main

if __name__ == "__main__":
    main() 
