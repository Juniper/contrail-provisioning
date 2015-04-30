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
import commonport
import StringIO

import tempfile
from fabric.api import local, env, run, settings
from fabric.operations import get, put
from fabric.context_managers import lcd, settings
from fabric.api import local, env, run
from fabric.operations import get, put
from fabric.context_managers import lcd, settings
from contrail_provisioning.storage.storagefs.ceph_utils import SetupCephUtils

sys.path.insert(0, os.getcwd())

class SetupCeph(object):

    # Added global defines for the files.
    # Use the variables instead of the filenames directly in the script
    # to avoid typos and readability.
    # The following are read-only globals
    # Add read/writable global variables at the end of this section.
    global CINDER_CONFIG_FILE
    CINDER_CONFIG_FILE = '/etc/cinder/cinder.conf'
    global NOVA_CONFIG_FILE
    NOVA_CONFIG_FILE = '/etc/nova/nova.conf'
    global CEPH_CONFIG_FILE
    CEPH_CONFIG_FILE = '/etc/ceph/ceph.conf'
    global CEPH_ADMIN_KEYRING
    CEPH_ADMIN_KEYRING = '/etc/ceph/ceph.client.admin.keyring'
    global SYSLOGD_CONF
    SYSLOGD_CONF = '/etc/rsyslog.d/50-default.conf'
    global COLLECTOR_CONF
    COLLECTOR_CONF = '/etc/contrail/contrail-collector.conf'
    global COLLECTOR_TMP_CONF
    COLLECTOR_TMP_CONF = '/tmp/contrail-collector.conf'
    global NFS_SERVER_LIST_FILE
    NFS_SERVER_LIST_FILE = '/etc/cinder/nfs_server_list.txt'
    global GLANCE_API_CONF
    GLANCE_API_CONF = '/etc/glance/glance-api.conf'
    global VOLUMES_KEYRING
    VOLUMES_KEYRING = '/etc/ceph/client.volumes.keyring'
    global CLIENT_VOLUMES
    CLIENT_VOLUMES = '/etc/ceph/client.volumes'
    global IMAGES_KEYRING
    IMAGES_KEYRING = '/etc/ceph/client.images.keyring'
    global STORAGE_NODEMGR_CONF
    STORAGE_NODEMGR_CONF = '/etc/contrail/contrail-storage-nodemgr.conf'
    global CENTOS_INITD_CINDER_VOLUME
    CENTOS_INITD_CINDER_VOLUME = '/etc/init.d/openstack-cinder-volume'
    global CENTOS_TMP_CINDER_VOLUME
    CENTOS_TMP_CINDER_VOLUME = '/tmp/openstack-cinder-volume.tmp'
    global CEPH_REST_API_CONF
    CEPH_REST_API_CONF = '/etc/init/ceph-rest-api.conf'
    global CEPH_VOLUME_KEYRING
    CEPH_VOLUME_KEYRING = '/etc/ceph/client.volumes.keyring'
    global CEPH_BOOTSTRAP_OSD_KEYRING
    CEPH_BOOTSTRAP_OSD_KEYRING = '/var/lib/ceph/bootstrap-osd/ceph.keyring'
    global CONTRAIL_STORAGE_STATS_INIT
    CONTRAIL_STORAGE_STATS_INIT = '/etc/init/contrail-storage-stats.conf'
    global CONTRAIL_STORAGE_STATS_CONF
    CONTRAIL_STORAGE_STATS_CONF = '/etc/contrail/contrail-storage-nodemgr.conf'
    global CINDER_VOLUME_INIT_CONFIG
    CINDER_VOLUME_INIT_CONFIG = '/etc/init/cinder-volume.conf'
    global RBD_WORKERS
    RBD_WORKERS = 120
    global RBD_STORE_CHUNK_SIZE
    RBD_STORE_CHUNK_SIZE = 8
    global TRUE
    TRUE = 1
    global FALSE
    FALSE = 0
    # Denotes the OS type whether Ubuntu or Centos.
    global pdist
    pdist = platform.dist()[0]
    # Maximum monitors to be created
    global MAX_MONS
    MAX_MONS = 10
    # RBD cache size
    global RBD_CACHE_SIZE
    RBD_CACHE_SIZE = 536870912
    # Ceph OP thread count
    global CEPH_OP_THREADS
    CEPH_OP_THREADS = 4
    # Ceph disk thread count
    global CEPH_DISK_THREADS
    CEPH_DISK_THREADS = 2
    # Global variables used across functions
    # The following are read/writable globals
    # Ceph storage disk list, populated during journal initialization
    global storage_disk_list
    storage_disk_list = []
    # OSD count, populated during HDD/SSD pool configuration
    # Used during pg/pgp count configuration
    global osd_count
    osd_count = 0
    # LVM types and name list, populated during LVM configuration
    # Used during cinder type creation
    global cinder_lvm_type_list
    cinder_lvm_type_list = []
    global cinder_lvm_name_list
    cinder_lvm_name_list = []
    # Global variable to indicate if Ceph storage is enabled
    global configure_with_ceph
    configure_with_ceph = 0
    # Global variable to indicate if Cinder NFS storage is enabled
    global create_nfs_disk_volume
    create_nfs_disk_volume = 0

    # global mon host string
    global ceph_mon_hosts
    ceph_mon_hosts = ''
    # global mon host list
    global ceph_mon_hosts_list
    ceph_mon_hosts_list = []
    # monitor count
    global ceph_mon_count
    ceph_mon_count = 0
    # global all host list
    global ceph_all_hosts
    ceph_all_hosts = ''
    # The function create a script which runs and lists the mons
    # running on the local node
    def reset_mon_local_list(self):
        local('echo "get_local_daemon_ulist() {" > /tmp/mon_local_list.sh')
        local('echo "if [ -d \\"/var/lib/ceph/mon\\" ]; then" >> \
                /tmp/mon_local_list.sh')
        local('echo "for i in \`find -L /var/lib/ceph/mon -mindepth 1 \
                -maxdepth 1 -type d -printf \'%f\\\\\\n\'\`; do" >> \
                /tmp/mon_local_list.sh')
        local('echo "if [ -e \\"/var/lib/ceph/mon/\$i/upstart\\" ]; then" >> \
                /tmp/mon_local_list.sh')
        local('echo "id=\`echo \$i | sed \'s/[^-]*-//\'\`" >> \
                /tmp/mon_local_list.sh')
        local('echo "sudo stop ceph-mon id=\$id" >> /tmp/mon_local_list.sh')
        local('echo "fi done fi" >> /tmp/mon_local_list.sh')
        local('echo "}" >> /tmp/mon_local_list.sh')
        local('echo "get_local_daemon_ulist" >> /tmp/mon_local_list.sh')
        local('echo "exit 0" >> /tmp/mon_local_list.sh')
        local('chmod a+x /tmp/mon_local_list.sh')
        local('/tmp/mon_local_list.sh')
    #end reset_mon_local_list()

    # The function create a script which runs and lists the osds
    # running on the local node
    def reset_osd_local_list(self):
        local('echo "get_local_daemon_ulist() {" > /tmp/osd_local_list.sh')
        local('echo "if [ -d \\"/var/lib/ceph/osd\\" ]; then" >> \
                /tmp/osd_local_list.sh')
        local('echo "for i in \`find -L /var/lib/ceph/osd -mindepth 1 \
                -maxdepth 1 -type d -printf \'%f\\\\\\n\'\`; do" >> \
                /tmp/osd_local_list.sh')
        local('echo "if [ -e \\"/var/lib/ceph/osd/\$i/upstart\\" ]; then" >> \
                /tmp/osd_local_list.sh')
        local('echo "id=\`echo \$i | sed \'s/[^-]*-//\'\`" >> \
                /tmp/osd_local_list.sh')
        local('echo "sudo stop ceph-osd id=\$id" >> /tmp/osd_local_list.sh')
        local('echo "fi done fi" >> /tmp/osd_local_list.sh')
        local('echo "}" >> /tmp/osd_local_list.sh')
        local('echo "get_local_daemon_ulist" >> /tmp/osd_local_list.sh')
        local('echo "exit 0" >> /tmp/osd_local_list.sh')
        local('chmod a+x /tmp/osd_local_list.sh')
        local('/tmp/osd_local_list.sh')
    #end reset_osd_local_list()

    # The function create a script which runs and lists the mons
    # running on the remote node
    def reset_mon_remote_list(self):
        run('echo "get_local_daemon_ulist() {" > /tmp/mon_local_list.sh')
        run('echo "if [ -d \\\\"/var/lib/ceph/mon\\\\" ]; then" >> \
                /tmp/mon_local_list.sh')
        run('echo "for i in \\\\`find -L /var/lib/ceph/mon -mindepth 1 \
                -maxdepth 1 -type d -printf \'%f\\\\\\n\'\\\\`; do" >> \
                /tmp/mon_local_list.sh')
        run('echo "if [ -e \\\\"/var/lib/ceph/mon/\\\\$i/upstart\\\\" ]; \
                then" >> /tmp/mon_local_list.sh')
        run('echo "id=\\\\`echo \\\\$i | sed \'s/[^-]*-//\'\\\\`" >> \
                /tmp/mon_local_list.sh')
        run('echo "sudo stop ceph-mon id=\\\\$id" >> /tmp/mon_local_list.sh')
        run('echo "fi done fi" >> /tmp/mon_local_list.sh')
        run('echo "}" >> /tmp/mon_local_list.sh')
        run('echo "get_local_daemon_ulist" >> /tmp/mon_local_list.sh')
        run('echo "exit 0" >> /tmp/mon_local_list.sh')
        run('chmod a+x /tmp/mon_local_list.sh')
        run('/tmp/mon_local_list.sh')
    #end reset_mon_remote_list()

    # The function create a script which runs and lists the osds
    # running on the remote node
    def reset_osd_remote_list(self):
        run('echo "get_local_daemon_ulist() {" > /tmp/osd_local_list.sh')
        run('echo "if [ -d \\\\"/var/lib/ceph/osd\\\\" ]; then" >> \
                /tmp/osd_local_list.sh')
        run('echo "for i in \\\\`find -L /var/lib/ceph/osd -mindepth 1 \
                -maxdepth 1 -type d -printf \'%f\\\\\\n\'\\\\`; do" >> \
                /tmp/osd_local_list.sh')
        run('echo "if [ -e \\\\"/var/lib/ceph/osd/\\\\$i/upstart\\\\" ]; \
                then" >> /tmp/osd_local_list.sh')
        run('echo "id=\\\\`echo \\\\$i | sed \'s/[^-]*-//\'\\\\`" >> \
                /tmp/osd_local_list.sh')
        run('echo "sudo stop ceph-osd id=\\\\$id" >> /tmp/osd_local_list.sh')
        run('echo "fi done fi" >> /tmp/osd_local_list.sh')
        run('echo "}" >> /tmp/osd_local_list.sh')
        run('echo "get_local_daemon_ulist" >> /tmp/osd_local_list.sh')
        run('echo "exit 0" >> /tmp/osd_local_list.sh')
        run('chmod a+x /tmp/osd_local_list.sh')
        run('/tmp/osd_local_list.sh')
    #end reset_osd_remote_list()

    # Function to create ceph rest api service and start it
    def ceph_rest_api_service_add(self):
        # check for ceph-rest-api.conf
        # create /etc/init/ceph-rest-api.conf for service upstrart
        # if service not running then replace app.ceph_port to 5005
        # start the ceph-rest-api service
        # This works only on Ubuntu
        # first master node
        rest_api_conf_available = local('ls %s 2>/dev/null | wc -l'
                                            %(CEPH_REST_API_CONF), capture=True)
        if rest_api_conf_available == '0':
            local('sudo echo description \\"Ceph REST API\\" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo >> %s' %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "start on started rc RUNLEVEL=[2345]" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "stop on runlevel [!2345]" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "respawn" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "respawn limit 5 30" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "limit nofile 16384 16384" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "pre-start script" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "    set -e" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "    test -x /usr/bin/ceph-rest-api || { stop; exit 0; }" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "end script" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "# this breaks oneiric" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "#usage \\"ceph-rest-api -c <conf-file> -n <client-name>\\"" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "exec ceph-rest-api -c /etc/ceph/ceph.conf -n client.admin" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "post-stop script" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "# nothing to do for now" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "end script" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
            local('sudo echo "" >> %s'
                                    %(CEPH_REST_API_CONF), shell='/bin/bash')
        ceph_rest_api_process_running = local('ps -ef | grep -v grep | \
                                    grep ceph-rest-api | wc -l', capture=True)
        if ceph_rest_api_process_running == '0':
            # Change the port to 5006 (in vip case) or 5005 (in non-vip case) and start the service
            entry_present = local('grep \"app.run(host=app.ceph_addr, port=app.ceph_port)\" /usr/bin/ceph-rest-api | wc -l', capture=True)
            if entry_present == '1':
                if self._args.cinder_vip != 'none':
                    local('sudo sed -i "s/app.run(host=app.ceph_addr, port=app.ceph_port)/app.run(host=app.ceph_addr, port=5006)/" /usr/bin/ceph-rest-api')
                else:
                    local('sudo sed -i "s/app.run(host=app.ceph_addr, port=app.ceph_port)/app.run(host=app.ceph_addr, port=5005)/" /usr/bin/ceph-rest-api')
            local('sudo service ceph-rest-api start', shell='/bin/bash')

        # remaining configured master nodes for HA
        if self._args.storage_os_hosts[0] != 'none':
            for entries, entry_token in zip(self._args.storage_os_hosts, self._args.storage_os_host_tokens):
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    # check for rest api conf file
                    rest_api_conf_avail = run('ls %s 2>/dev/null | wc -l' %(CEPH_REST_API_CONF))
                    # if not present copy from first master to other master nodes
                    if rest_api_conf_avail == '0':
                        put(CEPH_REST_API_CONF, '/etc/init/')
                    # check for ceph rest api running status
                    ceph_rest_api_process_running=run('ps -ef|grep -v grep|grep ceph-rest-api|wc -l')
                    if ceph_rest_api_process_running == '0':
                        entry_present=run('grep \"app.run(host=app.ceph_addr, port=app.ceph_port)\" /usr/bin/ceph-rest-api | wc -l')
                        # Change the port to 5006 (in vip case) or 5005 (in non-vip case) and start the service
                        if entry_present == '1':
                            if self._args.cinder_vip != 'none':
                                run('sudo sed -i "s/app.run(host=app.ceph_addr, port=app.ceph_port)/app.run(host=app.ceph_addr, port=5006)/" /usr/bin/ceph-rest-api')
                            else:
                                run('sudo sed -i "s/app.run(host=app.ceph_addr, port=app.ceph_port)/app.run(host=app.ceph_addr, port=5005)/" /usr/bin/ceph-rest-api')
                        run('sudo service ceph-rest-api start')
    #end ceph_rest_api_service_add()

    # Function to remove ceph-rest-api service
    # Stop the service if running
    # Remove the file /etc/init/ceph-rest-api.conf
    def ceph_rest_api_service_remove(self):
        # check the ceph-rest-api service
        # if it is running then trigger ceph-rest-api stop
        # finally removing ceph-rest-api.conf
        ceph_rest_api_process_running = local('ps -ef | grep -v grep | \
                                                grep ceph-rest-api | wc -l',
                                                capture=True)
        if ceph_rest_api_process_running != '0':
            local('sudo service ceph-rest-api stop', shell='/bin/bash')

        rest_api_conf_available = local('ls %s 2>/dev/null | wc -l' %(CEPH_REST_API_CONF), capture=True)
        if rest_api_conf_available != '0':
            local('sudo rm -rf %s' %(CEPH_REST_API_CONF), shell='/bin/bash')
        # remaining configured master nodes for HA
        if self._args.storage_os_hosts[0] != 'none':
            for entries, entry_token in zip(self._args.storage_os_hosts, self._args.storage_os_host_tokens):
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    # check the ceph-rest-api service and stop it on remaining master nodes
                    ceph_rest_api_process_running=run('ps -ef|grep -v grep|grep ceph-rest-api|wc -l')
                    if ceph_rest_api_process_running != '0':
                        run('sudo service ceph-rest-api stop')
                    # remove rest api conf file from remaining master nodes
                    rest_api_conf_avail=run('ls %s 2>/dev/null | wc -l' %(CEPH_REST_API_CONF))
                    if rest_api_conf_available != '0':
                        run('sudo rm -rf %s' %(CEPH_REST_API_CONF))
    #end ceph_rest_api_service_remove()

    # stop contrail-storage-stats service on all compute nodes
    def contrail_storage_stats_service_remove(self):
        # check if contrail-storage-stats is running
        # if it is running then trigger contrail-storage-stats stop
        # finally revert discovery contrail-storage-stats config

        # loop over storage compute host list to start contrail-storage-stats
        # only on storage compute nodes
        for compute_hostname in self._args.storage_compute_hostnames:
            for entries, entry_token, hostname in zip(self._args.storage_hosts,
                self._args.storage_host_tokens, self._args.storage_hostnames):
                # match storage compute with current hostname
                # to get host ip and passwd
                if compute_hostname == hostname:
                    with settings(host_string = 'root@%s' %(entries),
                                  password = entry_token):
                        contrail_stats_process_running = run('ps -ef| \
                            grep -v grep| grep contrail-storage-stats |wc -l')
                        if contrail_stats_process_running != '0':
                            run('sudo service contrail-storage-stats stop')
                        # reset disc_server_ip
                        run('sudo openstack-config --set \
                            /etc/contrail/contrail-storage-nodemgr.conf \
                            DEFAULTS disc_server_ip 127.0.0.1')
                    break
    #end contrail_storage_stats_service_remove

    # Function to configure syslog for Ceph
    def do_configure_syslog(self):

        # log ceph.log to syslog
        local('ceph tell mon.* injectargs -- --mon_cluster_log_to_syslog=true')

        # set ceph.log to syslog config in ceph.conf
        local('sudo openstack-config --set %s mon \
                                            "mon cluster log to syslog" true'
                                            %(CEPH_CONFIG_FILE))
        for entries, entry_token in zip(self._args.storage_hosts,
                                            self._args.storage_host_tokens):
            if entries != self._args.storage_master:
                with settings(host_string = 'root@%s' %(entries),
                                            password = entry_token):
                    run('sudo openstack-config --set %s mon \
                                            "mon cluster log to syslog" true'
                                            %(CEPH_CONFIG_FILE))

        # enable server:port syslog remote logging
        for entries in self._args.collector_hosts:
            syslog_present = local('grep "*.* @%s:%s" %s | wc -l'
                                    %(entries, commonport.SYSLOG_LOGPORT,
                                    SYSLOGD_CONF), capture=True)
            if syslog_present == '0':
                local('echo "*.* @%s:%s" >> %s'
                                    %(entries, commonport.SYSLOG_LOGPORT,
                                    SYSLOGD_CONF))

        # find and replace syslog port in collector
        for entries, entry_token in zip(self._args.collector_hosts,
                                            self._args.collector_host_tokens):
            with settings(host_string = 'root@%s' %(entries),
                                            password = entry_token):
                syslog_port = run('grep "# syslog_port=-1" %s | wc -l'
                                            %(COLLECTOR_CONF))
                if syslog_port == '1':
                    run('cat %s | sed "s/# syslog_port=-1/syslog_port=4514/" > \
                                            %s; mv %s %s' %(COLLECTOR_CONF,
                                            COLLECTOR_TMP_CONF,
                                            COLLECTOR_TMP_CONF,
                                            COLLECTOR_CONF))

                syslog_port = run('grep "syslog_port=-1" %s | wc -l'
                                            %(COLLECTOR_CONF))
                if syslog_port == '1':
                    run('cat %s | sed "s/syslog_port=-1/syslog_port=4514/" > \
                                            %s; mv %s %s' %(COLLECTOR_CONF,
                                            COLLECTOR_TMP_CONF,
                                            COLLECTOR_TMP_CONF,
                                            COLLECTOR_CONF))

                # restart collector after syslog port change
                run('service contrail-collector restart')

        # restart rsyslog service after remote logging enabled
        local('service rsyslog restart')

        return
    #end do_configure_syslog()

    # Funtion to remove the syslog configuration
    def unconfigure_syslog(self):
            # disable server:port syslog remote logging
            for entries in self._args.collector_hosts:
                syslog_present = local('grep "*.* @%s:%s" %s | wc -l'
                                                %(entries,
                                                commonport.SYSLOG_LOGPORT,
                                                SYSLOGD_CONF), capture=True)
                if syslog_present == '1':
                    local('sed -i "/*.* @%s:%s/d" %s'
                                                %(entries,
                                                commonport.SYSLOG_LOGPORT,
                                                SYSLOGD_CONF))
                    # restart rsyslog service after remote logging enabled
                    local('service rsyslog restart')

            # find and replace syslog port to default in collector
            for entries, entry_token in zip(self._args.collector_hosts,
                                            self._args.collector_host_tokens):
                with settings(host_string = 'root@%s' %(entries),
                                                password = entry_token):
                    syslog_port = run('grep "syslog_port=4514" %s | wc -l'
                                                %(COLLECTOR_CONF))
                    if syslog_port == '1':
                        run('cat %s | sed "s/syslog_port=4514/syslog_port=-1/" >\
                                                %s; mv %s %s' %(COLLECTOR_CONF,
                                                COLLECTOR_TMP_CONF,
                                                COLLECTOR_TMP_CONF,
                                                COLLECTOR_CONF))
                        # restart collector after syslog default port change
                        run('service contrail-collector restart')
    #end unconfigure_syslog()

    # Function to check if multipool is disabled or not
    # Returns False if enabled
    # Returns True if disabled
    # Checks for 'P' (for Pool) entry in the disk list in
    # the 2nd or 3rd field.
    def is_multi_pool_disabled(self):
        global storage_disk_list

        for disks in storage_disk_list:
            journal_available = disks.count(':')
            disksplit = disks.split(':')
            diskcount = disks.count(':')
            if diskcount == 3:
                if disksplit[3][0] == 'P':
                    return FALSE
            elif diskcount == 2:
                if disksplit[2][0] == 'P':
                    return FALSE
        return TRUE
    #end is_multi_pool_disabled()

    # Function to check if SSD pool is disabled or not
    # Returns False if enabled
    # Returns True if disabled
    def is_ssd_pool_disabled(self):
        if self._args.storage_ssd_disk_config[0] == 'none':
            return TRUE
        else:
            return FALSE
    #end is_ssd_pool_disabled()

    # Function to check if Chassis configuration is disabled or not
    # Returns False if enabled
    # Returns True if disabled
    def is_chassis_disabled(self):
        if self._args.storage_chassis_config[0] == 'none':
            return TRUE
        else:
            return FALSE
    #end is_chassis_disabled()

    # Function to check if LVM storage configuration is disabled or not
    # Returns False if enabled
    # Returns True if disabled
    def is_lvm_config_disabled(self):
        if self._args.storage_local_disk_config[0] != 'none' or \
                    self._args.storage_local_ssd_disk_config[0] != 'none':
            return FALSE
        return TRUE
    #end is_lvm_config_disabled()

    # Function to create osd number to drive mapping
    # Uses the storage_disk_config and storage_ssd_disk_config and creates
    # a new list in the format hostname:diskname:osd-num
    # The osd number is found by checking the drive mount path.
    # /dev/sdb1 /var/lib/ceph/osd/ceph-5 xfs rw,...
    # The above will give the OSD number 5. This is a unique number
    def create_osd_map_config(self):
        osd_map_config = []
        for hostname, entries, entry_token in zip(self._args.storage_hostnames,
                                                self._args.storage_hosts,
                                                self._args.storage_host_tokens):
            for disks in self._args.storage_disk_config:
                disksplit = disks.split(':')
                diskcount = disks.count(':')
                pool_index = 0
                # For each disk, check the mounted OSD and get the osd number.
                # /dev/sdb1 /var/lib/ceph/osd/ceph-5 xfs rw,...
                # The above will give the OSD number 5. This is a unique number
                # assigned to each OSD in the cluster.
                if disksplit[0] == hostname:
                    with settings(host_string = 'root@%s' %(entries),
                                            password = entry_token):
                        osddet = run('sudo mount | grep %s | awk \'{ print $3 }\''
                                            %(disksplit[1]))
                        osdnum = osddet.split('-')[1]
                        osd_map_config.append('%s:%s:%s' %(disksplit[0],
                                                disksplit[1], osdnum))
            for disks in self._args.storage_ssd_disk_config:
                disksplit = disks.split(':')
                diskcount = disks.count(':')
                pool_index = 0
                # For each disk, check the mounted OSD and get the osd number.
                # /dev/sdb1 /var/lib/ceph/osd/ceph-5 xfs rw,...
                # The above will give the OSD number 5. This is a unique number
                # assigned to each OSD in the cluster.
                if disksplit[0] == hostname:
                    with settings(host_string = 'root@%s' %(entries),
                                            password = entry_token):
                        osddet = run('sudo mount | grep %s | awk \'{ print $3 }\''
                                            %(disksplit[1]))
                        osdnum = osddet.split('-')[1]
                        osd_map_config.append('%s:%s:%s' %(disksplit[0],
                                                disksplit[1], osdnum))
        return osd_map_config
    # create_osd_map_config()

    # Top level function for crush map changes
    def do_crush_map_pool_config(self):
        global ceph_pool_list

        crush_setup_utils = SetupCephUtils()

        # If there is no mutlipool/ssd pool/chassis configuration, return
        if self.is_multi_pool_disabled() != TRUE or \
                self.is_ssd_pool_disabled() != TRUE or \
                self.is_chassis_disabled() != TRUE:

            # Initialize crush map
            crush_map = crush_setup_utils.initialize_crush()
            # Get the osd -> drive map
            osd_map_config = self.create_osd_map_config()
            # Do pool configuration
            crush_map = crush_setup_utils.do_pool_config(crush_map,
                                            self._args.storage_hostnames,
                                            self._args.storage_disk_config,
                                            self._args.storage_ssd_disk_config,
                                            osd_map_config)
            # Do chassis configuration
            crush_map = crush_setup_utils.do_chassis_config(crush_map,
                                            self._args.storage_hostnames,
                                            self._args.storage_chassis_config)
            # Apply crushmap
            crush_setup_utils.apply_crush(crush_map)

        # Configure Pools
        ceph_pool_list = crush_setup_utils.do_configure_pools(
                                        self._args.storage_hostnames,
                                        self._args.storage_disk_config,
                                        self._args.storage_ssd_disk_config,
                                        self._args.storage_chassis_config)
    #end do_crush_map_pool_config()

    # Function for NFS cinder configuration
    def do_configure_nfs(self):
        global create_nfs_disk_volume

        if self._args.storage_nfs_disk_config[0] == 'none':
            return
        # Create NFS mount list file
        file_present = local('sudo ls %s | wc -l' %(NFS_SERVER_LIST_FILE),
                                                            capture=True)
        if file_present == '0':
            local('sudo touch %s' %(NFS_SERVER_LIST_FILE), capture=True)
            local('sudo chown root:cinder %s' %(NFS_SERVER_LIST_FILE),
                                                            capture=True)
            local('sudo chmod 0640 %s' %(NFS_SERVER_LIST_FILE),
                                                            capture=True)

        # Add NFS mount list to file
        for entry in self._args.storage_nfs_disk_config:
            entry_present = local('cat %s | grep \"%s\" | wc -l'
                                            %(NFS_SERVER_LIST_FILE, entry),
                                            capture=True)
            if entry_present == '0':
                local('echo %s >> %s' %(entry, NFS_SERVER_LIST_FILE))

        # Cinder configuration to create backend
        cinder_configured = local('sudo cat %s | grep enabled_backends | \
                                                    grep nfs | wc -l'
                                                    %(CINDER_CONFIG_FILE),
                                                    capture=True)
        if cinder_configured == '0':
            existing_backends = local('sudo cat %s | grep enabled_backends | \
                                                    awk \'{print $3}\''
                                                    %(CINDER_CONFIG_FILE),
                                                    shell='/bin/bash',
                                                    capture=True)
            if existing_backends != '':
                new_backend = existing_backends + ',' + 'nfs'
                local('sudo openstack-config --set %s DEFAULT \
                                                    enabled_backends %s'
                                                    %(CINDER_CONFIG_FILE,
                                                    new_backend))
            else:
                local('sudo openstack-config --set %s DEFAULT \
                                                    enabled_backends nfs'
                                                    %(CINDER_CONFIG_FILE))

            local('sudo openstack-config --set %s nfs nfs_shares_config %s'
                                                    %(CINDER_CONFIG_FILE,
                                                    NFS_SERVER_LIST_FILE))
            local('sudo openstack-config --set %s nfs nfs_sparsed_volumes True'
                                                    %(CINDER_CONFIG_FILE))
            local('sudo openstack-config --set %s nfs volume_driver \
                                        cinder.volume.drivers.nfs.NfsDriver'
                                        %(CINDER_CONFIG_FILE))
            local('sudo openstack-config --set %s nfs volume_backend_name NFS'
                                        %(CINDER_CONFIG_FILE))
        create_nfs_disk_volume = 1
        return
    #end do_configure_nfs()

    # do_ssh_config(): The function configures the /etc/hosts with all the
    # storage-compute hostnames/ip address.
    # The function also creates entry of the masters rsa public id to all the
    # storage-computes authorized keys and to the known hosts.
    # This is done so that ceph-deploy doesn't ask user to input 'yes' and
    # the password during the ssh login.
    def do_ssh_config(self):
        # Add all the storage-compute hostnames/ip to the /etc/host of master
        for entries, entry_token in zip(self._args.storage_hosts,
                                            self._args.storage_host_tokens):
            with settings(host_string = 'root@%s' %(entries),
                                            password = entry_token):
                for hostname, host_ip in zip(self._args.storage_hostnames,
                                            self._args.storage_hosts):
                    run('cat /etc/hosts | grep -v -w %s$ > /tmp/hosts; \
                            a=`cat /tmp/hosts | grep -w "%s[ ]*%s" | wc -l`; \
                            if [ "$a" == "0" ]; then echo %s %s >> /tmp/hosts; fi ; \
                            cp -f /tmp/hosts /etc/hosts' \
                            % (hostname, host_ip, hostname, host_ip, hostname))

        # Generate public id using ssh-keygen and first add the key to the
        # authorized keys file and the known_hosts file in the master itself.
        # This is required when ceph-deploy does an ssh to master to add
        # the first monitor
        rsa_present = local('sudo ls ~/.ssh/id_rsa | wc -l', capture=True)
        if rsa_present != '1':
            local('sudo ssh-keygen -t rsa -N ""  -f ~/.ssh/id_rsa')
        sshkey = local('cat ~/.ssh/id_rsa.pub', capture=True)
        local('sudo mkdir -p ~/.ssh')
        already_present = local('grep "%s" ~/.ssh/known_hosts 2> /dev/null | \
                                wc -l' % (sshkey), capture=True)
        if already_present == '0':
            local('sudo echo "%s" >> ~/.ssh/known_hosts' % (sshkey))
        already_present = local('grep "%s" ~/.ssh/authorized_keys 2>/dev/null |\
                                 wc -l' % (sshkey), capture=True)
        if already_present == '0':
            local('sudo echo "%s" >> ~/.ssh/authorized_keys' % (sshkey))

        # Add the master public key to all the storage-compute's known_hosts
        # and authorized_keys file.
        for entries, entry_token, hostname in zip(self._args.storage_hosts,
                self._args.storage_host_tokens, self._args.storage_hostnames):
            if entries != self._args.storage_master:
                with settings(host_string = 'root@%s' %(entries),
                                password = entry_token):
                    run('sudo mkdir -p ~/.ssh')
                    already_present = run('grep "%s" ~/.ssh/known_hosts \
                                            2> /dev/null | wc -l'
                                            % (sshkey))
                    if already_present == '0':
                        run('sudo echo %s >> ~/.ssh/known_hosts' % (sshkey))
                    already_present = run('grep "%s" ~/.ssh/authorized_keys \
                                            2> /dev/null | wc -l'
                                            % (sshkey))
                    if already_present == '0':
                        run('sudo echo %s >> ~/.ssh/authorized_keys' % (sshkey))
                    hostfound = local('sudo grep %s,%s ~/.ssh/known_hosts | \
                                            wc -l' %(hostname,entries),
                                            capture=True)
                    if hostfound == "0":
                         out = run('sudo ssh-keyscan -t rsa %s,%s' %(hostname,
                                            entries))
                         local('sudo echo "%s" >> ~/.ssh/known_hosts' % (out))
        return
    #end do_ssh_config()

    # create monlist
    def do_create_monlist(self):
        global configure_with_ceph
        global ceph_mon_hosts
        global ceph_mon_hosts_list
        global ceph_mon_count
        global ceph_all_hosts

        # first create master monitor list
        for entries, entry_token, hostname in zip(self._args.storage_hosts, self._args.storage_host_tokens, self._args.storage_hostnames):
            if entries == self._args.storage_master:
                ceph_mon_hosts = ceph_mon_hosts + hostname + ' '
                ceph_mon_count += 1;
                ceph_mon_hosts_list.append(hostname)
            if self._args.storage_os_hosts[0] != 'none':
                for osnode in self._args.storage_os_hosts:
                    if entries == osnode:
                        ceph_mon_hosts = ceph_mon_hosts + hostname + ' '
                        ceph_mon_count += 1;
                        ceph_mon_hosts_list.append(hostname)

        # first try to use configured compute monitor list
        # if configured monitor list is empty then start
        # monitors on first "N" computes
        # where master monitor list + "N" compute monitors <= MAX_MONS
        if self._args.storage_mon_hosts[0] != 'none':
            for entries in self._args.storage_mon_hosts:
                ceph_mon_count += 1;
                if ceph_mon_count <= MAX_MONS:
                    ceph_mon_hosts = ceph_mon_hosts + entries + ' '
                    ceph_mon_hosts_list.append(entries)
        else:
            for entries, entry_token, hostname in zip(self._args.storage_hosts, self._args.storage_host_tokens, self._args.storage_hostnames):
                if entries == self._args.storage_master:
                    continue
                entry_hit = 0
                if self._args.storage_os_hosts[0] != 'none':
                    for osnode in self._args.storage_os_hosts:
                        if entries == osnode:
                            entry_hit = 1
                            break
                if entry_hit == 0:
                    ceph_mon_count += 1;
                    if ceph_mon_count <= MAX_MONS:
                        ceph_mon_hosts = ceph_mon_hosts + hostname + ' '
                        ceph_mon_hosts_list.append(hostname)

        for entries in self._args.storage_hostnames:
            ceph_all_hosts = ceph_all_hosts + entries + ' '
    # end do_create_monlist


    # Function to unconfigure Storage
    # This will remove all the storage configurations
    def do_storage_unconfigure(self):
        global configure_with_ceph

        if self._args.storage_directory_config[0] != 'none' or \
                self._args.storage_disk_config[0] != 'none' or \
                self._args.storage_ssd_disk_config[0] != 'none':
            configure_with_ceph = 1
        else:
            configure_with_ceph = 0

        # Remove the glance configuration if Ceph is configured.
        if configure_with_ceph:
            while True:
                glance_image = local('(. /etc/contrail/openstackrc ; \
                                    glance image-list |grep active | \
                                    awk \'{print $2}\' | head -n 1)',
                                    capture=True, shell='/bin/bash')
                if glance_image != '':
                    local('(. /etc/contrail/openstackrc ; glance image-delete %s)'
                                    %(glance_image))
                else:
                    break

            local('sudo openstack-config --set /etc/glance/glance-api.conf \
                                    DEFAULT default_store file')
            local('sudo openstack-config --del /etc/glance/glance-api.conf \
                                    DEFAULT known_stores')
            local('sudo openstack-config --del /etc/glance/glance-api.conf \
                                    DEFAULT show_image_direct_url')
            local('sudo openstack-config --del /etc/glance/glance-api.conf \
                                    DEFAULT rbd_store_user')
            local('sudo openstack-config --set /etc/glance/glance-api.conf \
                                    DEFAULT workers 1')
            if pdist == 'centos':
                local('sudo service openstack-glance-api restart')
            if pdist == 'Ubuntu':
                local('sudo service glance-api restart')

            if self._args.storage_os_hosts[0] != 'none':
                for entries, entry_token in zip(self._args.storage_os_hosts,
                                                self._args.storage_os_host_tokens):
                    with settings(host_string = 'root@%s' %(entries),
                                                password = entry_token):
                        run('sudo openstack-config --set \
                                        /etc/glance/glance-api.conf \
                                        DEFAULT default_store file')
                        run('sudo openstack-config --del \
                                        /etc/glance/glance-api.conf \
                                        DEFAULT known_stores')
                        run('sudo openstack-config --del \
                                        /etc/glance/glance-api.conf \
                                        DEFAULT show_image_direct_url')
                        run('sudo openstack-config --del \
                                        /etc/glance/glance-api.conf \
                                        DEFAULT rbd_store_user')
                        run('sudo openstack-config --set \
                                        /etc/glance/glance-api.conf \
                                        DEFAULT workers 1')
                        if pdist == 'centos':
                            run('sudo service openstack-glance-api restart')
                        if pdist == 'Ubuntu':
                            run('sudo service glance-api restart')

        # Find all the cinder volumes that are of type 'ocs-block'
        # Loop over and remove the volumes
        cinderlst = local('(. /etc/contrail/openstackrc ; \
                                    cinder list --all-tenants| grep ocs-block |\
                                    cut -d"|" -f 2)',  capture=True)
        if cinderlst != "":
            cinderalst = cinderlst.split('\n')
            for x in cinderalst:
                inuse = local('(. /etc/contrail/openstackrc ; \
                                    cinder list --all-tenants| grep %s | \
                                    cut -d"|" -f 3)' % (x),  capture=True)
                if inuse == "in-use":
                    detach = local('(. /etc/contrail/openstackrc ; \
                                    cinder list --all-tenants| grep %s | \
                                    cut -d"|" -f 8)' % (x),  capture=True)
                    local('(. /etc/contrail/openstackrc ; \
                                    nova volume-detach %s %s)' % (detach, x))
                local('(. /etc/contrail/openstackrc ; \
                                    cinder force-delete %s)' % (x))
                while True:
                    volavail = local('(. /etc/contrail/openstackrc ; \
                                    cinder list --all-tenants| grep %s | \
                                    wc -l)' % (x),  capture=True)
                    if volavail == '0':
                        break
                    else:
                        print "Waiting for volume to be deleted"
                        time.sleep(5)

        # Find the number of Cinder types that was created during setup
        # All the types start with 'ocs-block'
        # Delete all ocs-block disk types
        num_ocs_blk_disk = int(local('(. /etc/contrail/openstackrc ; \
                                    cinder type-list | grep ocs-block | \
                                    wc -l )', capture=True))
        while True:
            if num_ocs_blk_disk == 0:
                break
            ocs_blk_disk = local('(. /etc/contrail/openstackrc ; \
                                    cinder type-list | grep ocs-block | \
                                    head -n 1 | cut -d"|" -f 2)', capture=True)
            local('. /etc/contrail/openstackrc ; cinder type-delete %s'
                                    % (ocs_blk_disk))
            num_ocs_blk_disk -= 1

        # Remove LVM related cinder configurations
        for hostname, entries, entry_token in zip(self._args.storage_hostnames,
                                                self._args.storage_hosts,
                                                self._args.storage_host_tokens):
            with settings(host_string = 'root@%s' %(entries),
                                    password = entry_token):
                # Remove the volume group, it will be ocs-lvm-group or
                # ocs-lvm-ssd-group
                volavail = run('vgdisplay 2>/dev/null | grep ocs-lvm-group | \
                                    wc -l')
                if volavail != '0':
                    run('vgremove ocs-lvm-group')
                volavail = run('vgdisplay 2>/dev/null | \
                                    grep ocs-lvm-ssd-group |wc -l')
                if volavail != '0':
                    run('vgremove ocs-lvm-ssd-group')
                # Remove all the disks from the physical volume
                if self._args.storage_local_disk_config[0] != 'none':
                    for disks in self._args.storage_local_disk_config:
                        disksplit = disks.split(':')
                        if disksplit[0] == hostname:
                            pvadded = run('pvdisplay 2> /dev/null | grep %s | \
                                            wc -l' %(disksplit[1]))
                            if pvadded != '0':
                                run('pvremove -ff %s' %(disksplit[1]))

                if self._args.storage_local_ssd_disk_config[0] != 'none':
                    for disks in self._args.storage_local_ssd_disk_config:
                        disksplit = disks.split(':')
                        if disksplit[0] == hostname:
                            pvadded = run('pvdisplay 2> /dev/null | grep %s | \
                                            wc -l' %(disksplit[1]))
                            if pvadded != '0':
                                run('pvremove -ff %s' %(disksplit[1]))
                # Remove the cinder configurations
                existing_backends = run('sudo cat /etc/cinder/cinder.conf | \
                                            grep enabled_backends | \
                                            awk \'{print $3}\'',
                                            shell='/bin/bash')
                backends = existing_backends.split(',')
                #print backends
                for backend in backends:
                    if backend != '':
                        run('sudo openstack-config --del \
                                            /etc/cinder/cinder.conf %s'
                                            %(backend))
                run('sudo openstack-config --del /etc/cinder/cinder.conf \
                                            DEFAULT enabled_backends')
                run('sudo openstack-config --del /etc/cinder/cinder.conf \
                                            DEFAULT rabbit_host')
                run('sudo openstack-config --del /etc/cinder/cinder.conf \
                                            DEFAULT sql_connection')

        # Remove Ceph configurations
        # stop existing ceph monitor/osd
        local('pwd')
        if pdist == 'centos':
            local('/etc/init.d/ceph stop osd')
            local('/etc/init.d/ceph stop mon')
        # Run osd list/mon list scripts and stop the mons and OSDS
        # in local and all storage compute nodes.
        if pdist == 'Ubuntu':
            self.reset_mon_local_list()
            self.reset_osd_local_list()

        for entries, entry_token in zip(self._args.storage_hosts,
                                            self._args.storage_host_tokens):
            if entries != self._args.storage_master:
                with settings(host_string = 'root@%s' %(entries),
                                            password = entry_token):
                    if pdist == 'centos':
                        run('echo "/etc/init.d/ceph stop osd" > \
                                            /tmp/ceph.stop.sh')
                        run('echo "/etc/init.d/ceph stop mon" >> \
                                            /tmp/ceph.stop.sh')
                        run('chmod a+x /tmp/ceph.stop.sh')
                        run('/tmp/ceph.stop.sh')
                    # Unmount OSDs and remove ceph directories
                    if pdist == 'Ubuntu':
                        self.reset_mon_remote_list()
                        self.reset_osd_remote_list()
                        while True:
                            osd_mount = run('sudo cat /proc/mounts | \
                                            grep -w "/var/lib/ceph/osd" | \
                                            head -n 1 | \
                                            awk \'{print $2}\'')
                            if osd_mount == '':
                                break
                            run('sudo umount %s' %(osd_mount))
                        run('sudo rm -rf /var/lib/ceph')
                        run('sudo rm -rf /var/run/ceph')
                        run('sudo rm -rf /etc/ceph')
        time.sleep(2)
        # Purge data on all the nodes.
        local('sudo ceph-deploy purgedata %s <<< \"y\"' % (ceph_all_hosts),
                                            capture=False, shell='/bin/bash')
        # Remove local Ceph directories
        local('sudo rm -rf /var/lib/ceph')
        local('sudo rm -rf /var/run/ceph')
        local('sudo rm -rf /etc/ceph')
        local('sudo rm -rf /root/ceph.conf')
        local('sudo rm -rf /root/ceph*.keyring')

        # Remove Ceph-rest-api service
        # Remove syslog configuration
        if pdist == 'Ubuntu':
            self.ceph_rest_api_service_remove()
            self.unconfigure_syslog()
            self.contrail_storage_stats_service_remove()

        return
    #end do_storage_unconfigure()

    # Function to get form the storage disk list based on the journal
    # configurations.
    def get_storage_disk_list(self):
        # Setup Journal disks
        # Convert configuration from --storage-journal-config to ":" format
        # for example --storage-disk-config ceph1:/dev/sdb ceph1:/dev/sdc
        # --storage-journal-config ceph1:/dev/sdd will be stored in
        # storage_disk_list as ceph1:/dev/sdb:/dev/sdd, ceph1:/dev/sdc:/dev/sdd

        global storage_disk_list
        new_storage_disk_list = []

        if self._args.storage_journal_config[0] != 'none':
            for hostname, entries, entry_token in \
                        zip(self._args.storage_hostnames,
                            self._args.storage_hosts,
                            self._args.storage_host_tokens):
                # Find the number of host disk and journal disks
                # This is done to make the calculation to divide
                # Journal among the data drives.
                host_disks = 0
                journal_disks = 0
                if self._args.storage_disk_config[0] != 'none':
                    for disks in self._args.storage_disk_config:
                        disksplit = disks.split(':')
                        if disksplit[0] == hostname:
                            host_disks += 1
                if self._args.storage_ssd_disk_config[0] != 'none':
                    for disks in self._args.storage_ssd_disk_config:
                        disksplit = disks.split(':')
                        if disksplit[0] == hostname:
                            host_disks += 1
                journal_disks_list = ''
                for journal in self._args.storage_journal_config:
                    journalsplit = journal.split(':')
                    if journalsplit[0] == hostname:
                        journal_disks += 1
                        if journal_disks_list == '':
                            journal_disks_list = journalsplit[1]
                        else:
                            journal_disks_list = journal_disks_list + ':' + \
                                                                journalsplit[1]
                # Find the number of journal partitions for each journal
                # and create a list of journal disks
                if journal_disks != 0:
                    num_partitions = (host_disks / journal_disks) + \
                                                (host_disks % journal_disks > 0)
                    #print 'num partitions %d' %(num_partitions)
                    index = num_partitions
                    init_journal_disks_list = journal_disks_list
                    while True:
                        index -= 1
                        if index == 0:
                            break
                        journal_disks_list = journal_disks_list + ':' + \
                                                        init_journal_disks_list
                    #print journal_disks_list
                    journal_disks_split = journal_disks_list.split(':')
                # Create the final disk list in the form of
                # hostname:disk:journaldisk for both HDD and SSD
                index = 0
                if self._args.storage_disk_config[0] != 'none':
                    for disks in self._args.storage_disk_config:
                        disksplit = disks.split(':')
                        if disksplit[0] == hostname:
                            #print journal_disks_list
                            if journal_disks_list != '':
                                storage_disk_node = hostname + ':' + \
                                                    disksplit[1] + ':' + \
                                                    journal_disks_split[index]
                                index += 1
                            else:
                                storage_disk_node = disks
                            storage_disk_list.append(storage_disk_node)
                if self._args.storage_ssd_disk_config[0] != 'none':
                    for disks in self._args.storage_ssd_disk_config:
                        disksplit = disks.split(':')
                        if disksplit[0] == hostname:
                            #print journal_disks_list
                            if journal_disks_list != '':
                                storage_disk_node = hostname + ':' + \
                                                    disksplit[1] + ':' + \
                                                    journal_disks_split[index]
                                index += 1
                            else:
                                storage_disk_node = disks
                            storage_disk_list.append(storage_disk_node)
        # If there is no 'journal' configuration, may be its inline in disk
        # Just use the storage_disk_config/storage_ssd_disk_config
        else:
            for hostname, entries, entry_token in \
                        zip(self._args.storage_hostnames,
                            self._args.storage_hosts,
                            self._args.storage_host_tokens):
                for disks in self._args.storage_disk_config:
                    disksplit = disks.split(':')
                    if disksplit[0] == hostname:
                        storage_disk_list.append(disks)
            if self._args.storage_ssd_disk_config[0] != 'none':
                for hostname, entries, entry_token in \
                        zip(self._args.storage_hostnames,
                            self._args.storage_hosts,
                            self._args.storage_host_tokens):
                    for ssd_disks in self._args.storage_ssd_disk_config:
                        disksplit = ssd_disks.split(':')
                        if disksplit[0] == hostname:
                            storage_disk_list.append(ssd_disks)

        # Remove the Pool numbers from the disk list. The pool name should
        # always start with 'P'
        for disks in storage_disk_list:
            journal_available = disks.count(':')
            disksplit = disks.split(':')
            diskcount = disks.count(':')
            if diskcount == 3:
                if disksplit[3][0] == 'P':
                    new_storage_disk_list.append('%s:%s:%s' %(disksplit[0],
                                                    disksplit[1], disksplit[2]))
            elif diskcount == 2:
                if disksplit[2][0] == 'P':
                    new_storage_disk_list.append('%s:%s' %(disksplit[0],
                                                    disksplit[1]))
                else:
                    new_storage_disk_list.append('%s:%s:%s' %(disksplit[0],
                                                    disksplit[1], disksplit[2]))
            else:
                new_storage_disk_list.append(disks)
        return new_storage_disk_list
    #end get_storage_disk_list()

    # Function to check if journal disk is used already.
    # Returns TRUE if used
    # Returns FALSE if not used
    def do_journal_usage_check(self, entry, entry_token, journal_disk):
        with settings(host_string = 'root@%s' %(entry), password = entry_token):
            # Loop over the OSDs running and check the journal file
            # in each OSD and check if the journal is same as the input
            # 'journal_disk'
            num_osds = int(run('cat /proc/mounts | grep osd | wc -l'))
            journal_disk = journal_disk.split('/')[2]
            while num_osds != 0:
                osd_dir = run('cat /proc/mounts | grep osd | tail -n %s | \
                                head -n 1 | awk \'{print $2 }\'' %(num_osds))
                journal_uuid = run('ls -l %s/journal | awk \'{print $11 }\''
                                    %(osd_dir))
                journal_used = run('ls -l %s | grep %s | wc -l'
                                    %(journal_uuid, journal_disk))
                if journal_used != '0':
                    return TRUE
                num_osds -= 1
        return FALSE

    #end do_journal_usage_check

    # Function to initialize journal
    def do_journal_initialize(self, ceph_disk_entry):
        journal_available = ceph_disk_entry.count(':')
        if journal_available >= 2:
            jhostname = ceph_disk_entry.split(':')[0]
            journal_disk = ceph_disk_entry.split(':')[2]
            for hostname, entry, entry_token in \
                                        zip(self._args.storage_hostnames,
                                            self._args.storage_hosts,
                                            self._args.storage_host_tokens):
                if jhostname == hostname:
                    # Check if the journal disk is used
                    # If its not used, then format/partition the drive
                    journal_used = self.do_journal_usage_check(entry,
                                                                entry_token,
                                                                journal_disk)
                    with settings(host_string = 'root@%s' %(entry),
                                                password = entry_token):
                        if journal_used == FALSE:
                            run('dd if=/dev/zero of=%s  bs=512  count=1'
                                                                %(journal_disk))
                            run('parted -s %s mklabel gpt 2>&1 > /dev/null'
                                                                %(journal_disk))

        return
    #end do_journal_initialize()

    # Function to check if the OSD is running or not
    # The function checks if the OSD drive is mounted for Ceph.
    # If the drive is mounted for Ceph and ceph-osd is not running,
    # The script will abort.
    # If the drive is mounted, but not for Ceph, then the script will
    # abort.
    # TODO: Try to recover OSD when drive is mounted for Ceph and ceph-osd
    #       is not running
    def do_osd_check(self, ceph_disk_entry):
        ohostname = ceph_disk_entry.split(':')[0]
        for hostname, entry, entry_token in \
                                        zip(self._args.storage_hostnames,
                                            self._args.storage_hosts,
                                            self._args.storage_host_tokens):
            if ohostname == hostname:
                with settings(host_string = 'root@%s' %(entry),
                                            password = entry_token):

                    # Wait for disk to be mounted during osd-start
                    osd_disk = ceph_disk_entry.split(':')[1]
                    retry = 0
                    while True:
                        osd_mounted = run('sudo cat /proc/mounts | grep %s | \
                                            wc -l' %(osd_disk))
                        if osd_mounted == '0':
                            retry += 1
                            if retry > 2:
                                break
                            time.sleep(3)
                        else:
                            break

                    osd_running = run('sudo cat /proc/mounts | grep osd | \
                                            grep %s | wc -l' %(osd_disk))
                    if osd_running != '0':
                        osddet = run('sudo mount | grep %s | grep -v grep | \
                                            grep -v tmp | head -n 1 | \
                                            awk \'{ print $3 }\''
                                            %(osd_disk), shell='/bin/bash')
                        osdnum = osddet.split('-')[1]
                        pr_running = run('sudo ps -ef | grep ceph-osd | \
                                            grep -w "i %s" | grep -v grep | \
                                            wc -l' %(osdnum))
                        if pr_running == '0':
                            print 'Ceph OSD process not running for disk %s in \
                                            host %s' %(osd_disk, entry)
                            sys.exit(-1)

                        return TRUE
                    else:
                        osd_mounted = run('sudo cat /proc/mounts | grep %s | \
                                            wc -l' %(osd_disk))
                        if osd_mounted != '0':
                            print 'Drive %s in host %s is in use, \
                                            Cannot create OSD' %(osd_disk, entry)
                            sys.exit(-1)
        return FALSE
    #end do_osd_check()

    # Function to create a OSD.
    # Checks if the OSD is already running, if not create ZAP/Create OSD
    def do_osd_create(self):
        global osd_count

        disk_list = self.get_storage_disk_list()
        for ceph_disk_entry in disk_list:
            self.do_journal_initialize(ceph_disk_entry)
            osd_running = self.do_osd_check(ceph_disk_entry)
            if osd_running == FALSE:
                # Zap the existing partitions
                local('sudo ceph-deploy disk zap %s' % (ceph_disk_entry))
                # Allow disk partition changes to sync.
                time.sleep(5)

                diskentry = ceph_disk_entry.split(':')
                for hostname, entries, entry_token in \
                        zip(self._args.storage_hostnames,
                            self._args.storage_hosts,
                            self._args.storage_host_tokens):
                    if hostname == diskentry[0]:
                        with settings(host_string = 'root@%s' %(entries),
                                      password = entry_token):
                            ip_cidr = run('ip addr show |grep -w %s |awk \'{print $2}\' | \
                                          head -n 1' %(entries))
                        local('sudo openstack-config --set /root/ceph.conf \
                                    global public_network %s\/%s'
                                    %(netaddr.IPNetwork(ip_cidr).network,
                                    netaddr.IPNetwork(ip_cidr).prefixlen))
                        break
                # For prefirefly use prepare/activate on ubuntu release
                local('sudo ceph-deploy --overwrite-conf osd create %s' % (ceph_disk_entry))
                time.sleep(10)
                osd_running = self.do_osd_check(ceph_disk_entry)
                if osd_running == FALSE:
                    print 'OSD not running for %s' %(ceph_disk_entry)
                    sys.exit(-1)
            osd_count += 1
        return
    #end do_osd_create()

    # Function for Ceph gather keys
    def do_gather_keys(self):
        global ceph_mon_hosts_list
        # perform gather keys on primary storage master
        # generated keys are then used on non-monitor nodes
        # to communicate
        for hostname, entry, entry_token in \
                                        zip(self._args.storage_hostnames,
                                            self._args.storage_hosts,
                                            self._args.storage_host_tokens):
            if entry == self._args.storage_master:
                storage_master_hostname = hostname
                break

        # gather keys on primary storage master
        local('sudo ceph-deploy gatherkeys %s' % (storage_master_hostname))

        # copy gathers keys from primary storage master
        # to non-monitor nodes
        for hostname, entry, entry_token in \
                                        zip(self._args.storage_hostnames,
                                            self._args.storage_hosts,
                                            self._args.storage_host_tokens):
            mon_present = 0
            for monentries in ceph_mon_hosts_list:
                if monentries == hostname:
                    mon_present = 1
                    break
            if mon_present == 0:
                with settings(host_string = 'root@%s' %(entry),
                              password = entry_token):
                    put(CEPH_ADMIN_KEYRING, \
                        '/etc/ceph/')
                    put(CEPH_BOOTSTRAP_OSD_KEYRING, \
                        '/var/lib/ceph/bootstrap-osd/')
        return
    #end do_gather_keys()

    # Function to update mon list in ceph.conf
    def do_update_monhost_config(self):
        global ceph_mon_hosts_list
        mon_initial_members = ''
        mon_host = ''

        # create mon_initial_members list
        for hostname in ceph_mon_hosts_list:
            mon_initial_members = mon_initial_members + hostname + ', '

        # create mon_host list
        for monhostname in ceph_mon_hosts_list:
            for hostname, entry, entry_token in \
                                        zip(self._args.storage_hostnames,
                                            self._args.storage_hosts,
                                            self._args.storage_host_tokens):
                if hostname == monhostname:
                    mon_host = mon_host + entry + ', '

        #loop over all storage hosts and replace mon_initial_memers and mon_host
        for hostname, entry, entry_token in \
                                        zip(self._args.storage_hostnames,
                                            self._args.storage_hosts,
                                            self._args.storage_host_tokens):
            with settings(host_string = 'root@%s' %(entry),
                          password = entry_token):
                run('sudo openstack-config --set %s global "mon_initial_members" "%s"'
                    %(CEPH_CONFIG_FILE, mon_initial_members[:-2]))
                run('sudo openstack-config --set %s global "mon_host" "%s"'
                    %(CEPH_CONFIG_FILE, mon_host[:-2]))

        # restart monitors after package upgrade
        self.do_monitor_restarts()

    # end do_create_monlist

    # Function to create monitor if its not already running
    def do_monitor_create(self):
        # TODO: use mon list to create the mons
        global ceph_mon_hosts_list
        for hostname, entry, entry_token in \
                                        zip(self._args.storage_hostnames,
                                            self._args.storage_hosts,
                                            self._args.storage_host_tokens):
            with settings(host_string = 'root@%s' %(entry),
                                    password = entry_token):
                run('sudo mkdir -p /var/lib/ceph/bootstrap-osd')
                run('sudo mkdir -p /var/lib/ceph/osd')
                run('sudo mkdir -p /var/run/ceph/')
                run('sudo mkdir -p /etc/ceph')
                ip_cidr = run('ip addr show |grep -w %s |awk \'{print $2}\' | \
                                    head -n 1' %(entry))

                # Check if monitor is already running
                # If mon is not running, start the mon.
                # If its the storage master, then start the first mon
                mon_running = run('sudo ps -ef | grep ceph-mon | grep -v grep |\
                                    wc -l')
                if mon_running == '0':
                    if entry != self._args.storage_master:
                        # Add new mon to existing cluster
                        # For this the requirement, the public network needs to
                        # be added for in the ceph.conf
                        local('sudo openstack-config --set /root/ceph.conf \
                                    global public_network %s\/%s'
                                    %(netaddr.IPNetwork(ip_cidr).network,
                                    netaddr.IPNetwork(ip_cidr).prefixlen))
                        for mon_hostname in ceph_mon_hosts_list:
                            if mon_hostname == hostname:
                                local('sudo ceph-deploy --overwrite-conf mon \
                                       create-initial %s' % (hostname))
                    else:
                        # Storage master, create a new mon
                        local('sudo ceph-deploy new %s' % (hostname))
                        local('sudo ceph-deploy mon create %s' % (hostname))

                # Verify if the monitor is started
                mon_running = local('ceph -s | grep -w %s | wc -l' %(hostname))
                if mon_running == '0':
                    print 'Ceph monitor not started for host %s' %(hostname)
                    sys.exit(-1)

        # wait for mons to sync
        time.sleep(20)

        # Run gather keys on all the nodes.
        self.do_gather_keys()
        return

    #end do_monitor_create()

    # Function to tune ceph related parameters.
    # Enable rbd cache
    # Set the rbd cache size
    # Set number of OP threads
    # Set number of disk threads
    def do_tune_ceph(self):

        # rbd cache enabled and rbd cache size set to 512MB
        local('ceph tell osd.* injectargs -- --rbd_cache=true')
        local('sudo openstack-config --set %s global "rbd cache" true'
                            %(CEPH_CONFIG_FILE))

        local('ceph tell osd.* injectargs -- --rbd_cache_size=%s'
                            %(RBD_CACHE_SIZE))
        local('sudo openstack-config --set %s global "rbd cache size" %s'
                            %(CEPH_CONFIG_FILE, RBD_CACHE_SIZE))

        # change default osd op threads 2 to 4
        local('ceph tell osd.* injectargs -- --osd_op_threads=%s'
                            %(CEPH_OP_THREADS))
        local('sudo openstack-config --set %s osd "osd op threads" %s'
                            %(CEPH_CONFIG_FILE, CEPH_OP_THREADS))

        # change default disk threads 1 to 2
        local('ceph tell osd.* injectargs -- --osd_disk_threads=%s'
                            %(CEPH_DISK_THREADS))
        local('sudo openstack-config --set %s osd "osd disk threads" %s'
                            %(CEPH_CONFIG_FILE, CEPH_DISK_THREADS))

        # compute ceph.conf configuration done here
        for entries, entry_token in zip(self._args.storage_hosts,
                                            self._args.storage_host_tokens):
            if entries != self._args.storage_master:
                with settings(host_string = 'root@%s' %(entries),
                                            password = entry_token):
                    run('sudo openstack-config --set %s global "rbd cache" true'
                            %(CEPH_CONFIG_FILE))
                    run('sudo openstack-config --set %s global "rbd cache size" %s'
                            %(CEPH_CONFIG_FILE, RBD_CACHE_SIZE))
                    run('sudo openstack-config --set %s osd "osd op threads" %s'
                            %(CEPH_CONFIG_FILE, CEPH_OP_THREADS))
                    run('sudo openstack-config --set %s osd "osd disk threads" %s'
                            %(CEPH_CONFIG_FILE, CEPH_DISK_THREADS))
        return
    #end do_tune_ceph()


    # Function for Ceph authentication related configurations
    # This has to be run on all the nodes.
    # Note: Do not split the lines in between the quotes. This will
    #       affect the configuraiton
    def do_configure_ceph_auth(self):

        # The function does an auth get-or-create for each pool and set the
        # ceph.conf with the keyring values.
        # Run local for the storage master for volumes/images pool
        local('sudo ceph auth get-or-create client.volumes mon \
                        \'allow r\' osd \
                        \'allow class-read object_prefix rbd_children, allow rwx pool=volumes, allow rx pool=images\' \
                        -o %s' %(VOLUMES_KEYRING))
        local('sudo ceph auth get-or-create client.images mon \
                        \'allow r\' osd \
                        \'allow class-read object_prefix rbd_children, allow rwx pool=images\' \
                        -o %s' %(IMAGES_KEYRING))
        local('sudo openstack-config --set %s client.volumes keyring  %s'
                                        %(CEPH_CONFIG_FILE, VOLUMES_KEYRING))
        local('sudo openstack-config --set %s client.images keyring %s'
                                        %(CEPH_CONFIG_FILE, IMAGES_KEYRING))
        local('cat ~/.bashrc |grep -v CEPH_ARGS > /tmp/.bashrc')
        local('mv -f /tmp/.bashrc ~/.bashrc')
        local('echo export CEPH_ARGS=\\"--id volumes\\" >> ~/.bashrc')
        local('ceph-authtool -p -n client.volumes %s > %s' %(VOLUMES_KEYRING,
                                                            CLIENT_VOLUMES))

        # Run for other openstack nodes for volumes/images pool
        if self._args.storage_os_hosts[0] != 'none':
            for entries, entry_token in zip(self._args.storage_os_hosts,
                                            self._args.storage_os_host_tokens):
                with settings(host_string = 'root@%s' %(entries),
                                            password = entry_token):
                    run('sudo ceph -k %s auth get-or-create client.volumes mon \
                            \'allow r\' osd \
                            \'allow class-read object_prefix rbd_children, allow rwx pool=volumes, allow rx pool=images\' \
                             -o %s' %(CEPH_ADMIN_KEYRING,
                            VOLUMES_KEYRING))
                    run('sudo ceph -k %s auth get-or-create client.images mon \
                            \'allow r\' osd \
                            \'allow class-read object_prefix rbd_children, allow rwx pool=images\' \
                            -o %s' %(CEPH_ADMIN_KEYRING, IMAGES_KEYRING))
                    run('sudo openstack-config --set %s client.volumes keyring \
                                        %s' %(CEPH_CONFIG_FILE, VOLUMES_KEYRING))
                    run('sudo openstack-config --set %s client.images keyring \
                                        %s' %(CEPH_CONFIG_FILE, IMAGES_KEYRING))
                    if pdist == 'centos':
                        run('cat ~/.bashrc |grep -v CEPH_ARGS > /tmp/.bashrc')
                        run('mv -f /tmp/.bashrc ~/.bashrc')
                        run('echo export CEPH_ARGS=\\\\"--id volumes\\\\" >> \
                                                                    ~/.bashrc')
                        run('. ~/.bashrc')
                    run('sudo ceph-authtool -p -n client.volumes %s > %s'
                                            %(VOLUMES_KEYRING, CLIENT_VOLUMES))

        # Run for all storage-computes for volumes/images pool
        for entries, entry_token in zip(self._args.storage_hosts,
                                                self._args.storage_host_tokens):
            if entries != self._args.storage_master:
                with settings(host_string = 'root@%s' %(entries),
                                                        password = entry_token):
                    run('sudo ceph -k %s auth get-or-create client.volumes mon \
                            \'allow r\' osd \
                            \'allow class-read object_prefix rbd_children, allow rwx pool=volumes, allow rx pool=images\' \
                            -o %s' %(CEPH_ADMIN_KEYRING, VOLUMES_KEYRING))
                    run('sudo ceph -k %s auth get-or-create client.images mon \
                            \'allow r\' osd \
                            \'allow class-read object_prefix rbd_children, allow rwx pool=images\' \
                            -o %s' %(CEPH_ADMIN_KEYRING, IMAGES_KEYRING))
                    run('sudo openstack-config --set %s client.volumes keyring \
                                        %s' %(CEPH_CONFIG_FILE, VOLUMES_KEYRING))
                    run('sudo openstack-config --set %s client.images keyring \
                                        %s' %(CEPH_CONFIG_FILE, IMAGES_KEYRING))
                    if pdist == 'centos':
                        run('cat ~/.bashrc |grep -v CEPH_ARGS > /tmp/.bashrc')
                        run('mv -f /tmp/.bashrc ~/.bashrc')
                        run('echo export CEPH_ARGS=\\\\"--id volumes\\\\" >> \
                                                                    ~/.bashrc')
                        run('. ~/.bashrc')
                    run('sudo ceph-authtool -p -n client.volumes %s > %s'
                                            %(VOLUMES_KEYRING, CLIENT_VOLUMES))

        if self.is_multi_pool_disabled() == FALSE or \
                        self.is_ssd_pool_disabled() == FALSE:
            for pool_name in ceph_pool_list:
                # Run local for storage-master for HDD/SSD pools
                local('sudo ceph auth get-or-create client.%s mon \
                                \'allow r\' osd \
                                \'allow class-read object_prefix rbd_children, allow rwx pool=%s, allow rx pool=images\' \
                                -o /etc/ceph/client.%s.keyring'
                                %(pool_name, pool_name, pool_name))
                local('sudo openstack-config --set %s client.%s keyring \
                                /etc/ceph/client.%s.keyring'
                                %(CEPH_CONFIG_FILE, pool_name, pool_name))
                local('ceph-authtool -p -n client.%s \
                                /etc/ceph/client.%s.keyring > \
                                /etc/ceph/client.%s'
                                %(pool_name, pool_name, pool_name))
                # Run for other openstack nodes for HDD/SSD pools
                if self._args.storage_os_hosts[0] != 'none':
                    for entries, entry_token in zip(self._args.storage_os_hosts,
                                            self._args.storage_os_host_tokens):
                        with settings(host_string = 'root@%s' %(entries),
                                            password = entry_token):
                            run('sudo ceph -k %s auth get-or-create \
                                    client.%s mon \
                                    \'allow r\' osd \
                                    \'allow class-read object_prefix rbd_children, allow rwx pool=%s, allow rx pool=images\' \
                                    -o /etc/ceph/client.%s.keyring'
                                    %(CEPH_ADMIN_KEYRING, pool_name,
                                    pool_name, pool_name))
                            run('sudo openstack-config --set %s client.%s \
                                    keyring /etc/ceph/client.%s.keyring'
                                    %(CEPH_CONFIG_FILE, pool_name, pool_name))
                            run('sudo ceph-authtool -p -n client.%s \
                                    /etc/ceph/client.%s.keyring > \
                                    /etc/ceph/client.%s'
                                    %(pool_name, pool_name, pool_name))
                # Run for all other storage-compute for HDD/SSD pools
                for entries, entry_token in zip(self._args.storage_hosts,
                                                self._args.storage_host_tokens):
                    if entries != self._args.storage_master:
                        with settings(host_string = 'root@%s' %(entries),
                                                password = entry_token):
                            run('sudo ceph -k %s auth get-or-create \
                                    client.%s mon \
                                    \'allow r\' osd \
                                    \'allow class-read object_prefix rbd_children, allow rwx pool=%s, allow rx pool=images\' \
                                    -o /etc/ceph/client.%s.keyring'
                                    %(CEPH_ADMIN_KEYRING, pool_name,
                                    pool_name, pool_name))
                            run('sudo openstack-config --set %s client.%s \
                                    keyring /etc/ceph/client.%s.keyring'
                                    %(CEPH_CONFIG_FILE, pool_name, pool_name))
                            run('sudo ceph-authtool -p -n client.%s \
                                    /etc/ceph/client.%s.keyring > \
                                    /etc/ceph/client.%s'
                                    %(pool_name, pool_name, pool_name))
        return
    #end do_configure_ceph_auth()

    # Function for Virsh/Cinder configurations for Ceph
    def do_configure_virsh_cinder_rbd(self):

        # Check for secret keys if present for volumes pool.
        # Virsh secret-list will list all the secrets.
        # run dumpxml and check if has client.volumes
        # If the client.volumes secret is already present,
        # then reuse the same secret
        secret_present = '0'
        line_num = 1
        while True:
            virsh_secret = local('virsh secret-list  2>&1 | \
                                        awk \'{print $1}\' | \
                                        awk \'NR > 2 { print }\' | \
                                        tail -n +%d | head -n 1'
                                        %(line_num), capture=True)
            if virsh_secret != "":
                secret_present = local('virsh secret-dumpxml %s | \
                                        grep -w "client.volumes" | \
                                        wc -l' %(virsh_secret), capture=True)
                if secret_present != '0':
                    break
            else:
                break
            line_num += 1

        # If the key is not present, create it.
        # Set the secret value for the key with the keyring vlaue
        # Restart libvirt service
        if secret_present == '0':
            local('echo "<secret ephemeral=\'no\' private=\'no\'> \
                            <usage type=\'ceph\'> \
                                <name>client.volumes secret</name> \
                            </usage> \
                            </secret>" > secret.xml')
            virsh_secret = local('virsh secret-define --file secret.xml 2>&1 | \
                                                cut -d " " -f 2', capture=True)
        volume_keyring_list = local('cat %s | grep key'
                                            %(CEPH_VOLUME_KEYRING),
                                            capture=True)
        volume_keyring = volume_keyring_list.split(' ')[2]
        local('virsh secret-set-value %s --base64 %s'
                                                %(virsh_secret,volume_keyring))
        local('sudo service libvirt-bin restart')

        # Cinder configuration for rbd-disk for the volume pool
        local('sudo openstack-config --set %s rbd-disk volume_driver \
                                    cinder.volume.drivers.rbd.RBDDriver'
                                    %(CINDER_CONFIG_FILE))
        local('sudo openstack-config --set %s rbd-disk rbd_pool volumes'
                                    %(CINDER_CONFIG_FILE))
        local('sudo openstack-config --set %s rbd-disk rbd_user volumes'
                                    %(CINDER_CONFIG_FILE))
        local('sudo openstack-config --set %s rbd-disk rbd_secret_uuid %s'
                                    %(CINDER_CONFIG_FILE, virsh_secret))
        local('sudo openstack-config --set %s rbd-disk glance_api_version 2'
                                    %(CINDER_CONFIG_FILE))
        local('sudo openstack-config --set %s rbd-disk volume_backend_name RBD'
                                    %(CINDER_CONFIG_FILE))

        # Configure cinder in all the other Openstack nodes.
        if self._args.storage_os_hosts[0] != 'none':
            for entries, entry_token in zip(self._args.storage_os_hosts,
                                            self._args.storage_os_host_tokens):
                with settings(host_string = 'root@%s' %(entries),
                                            password = entry_token):
                    run('sudo openstack-config --set %s rbd-disk volume_driver \
                                        cinder.volume.drivers.rbd.RBDDriver'
                                        %(CINDER_CONFIG_FILE))
                    run('sudo openstack-config --set %s rbd-disk rbd_pool \
                                        volumes' %(CINDER_CONFIG_FILE))
                    run('sudo openstack-config --set %s rbd-disk rbd_user \
                                        volumes' %(CINDER_CONFIG_FILE))
                    run('sudo openstack-config --set %s rbd-disk \
                                        rbd_secret_uuid %s'
                                        %(CINDER_CONFIG_FILE, virsh_secret))
                    run('sudo openstack-config --set %s rbd-disk \
                                        glance_api_version 2'
                                        %(CINDER_CONFIG_FILE))
                    run('sudo openstack-config --set %s rbd-disk \
                                        volume_backend_name RBD'
                                        %(CINDER_CONFIG_FILE))

        # Check for the virsh secret in all the storage-compute nodes.
        # If not present, add it.
        for entries, entry_token in zip(self._args.storage_hosts,
                                            self._args.storage_host_tokens):
            if entries != self._args.storage_master:
                with settings(host_string = 'root@%s' %(entries),
                                            password = entry_token):
                    # Virsh secret-list will list all the secrets.
                    # run dumpxml and check if has client.volumes
                    # If the client.volumes secret is already present,
                    # then reuse the same secret
                    same_secret = 0
                    line_num = 1
                    while True:
                        virsh_unsecret = run('virsh secret-list  2>&1 | \
                                                awk \'{print $1}\' | \
                                                awk \'NR > 2 { print }\' | \
                                                tail -n +%d | head -n 1'
                                                %(line_num))
                        if virsh_unsecret != "":
                            if virsh_unsecret == virsh_secret:
                                same_secret = 1
                                break
                            vol_present = run('virsh secret-dumpxml %s | \
                                                    grep -w "client.volumes" | \
                                                    wc -l' %(virsh_unsecret))
                            if vol_present != '0':
                                run('virsh secret-undefine %s' %(virsh_unsecret))
                        else:
                            break
                        line_num += 1

                    # If secret is not present, create new secret
                    # Set the secret with the keyring
                    if same_secret == 0:
                        run('echo "<secret ephemeral=\'no\' private=\'no\'> \
                                    <uuid>%s</uuid><usage type=\'ceph\'> \
                                    <name>client.volumes secret</name> \
                                    </usage> \
                                    </secret>" > secret.xml' % (virsh_secret))
                        run('virsh secret-define --file secret.xml')
                    run('virsh secret-set-value %s --base64 %s'
                                    %(virsh_secret,volume_keyring))

        # Cinder Backend Configuration
        # Based on the multipool configuration, configure the Backend.
        # add it in the storage-master and all other openstack nodes.
        if self.is_multi_pool_disabled() == TRUE and \
                        self.is_ssd_pool_disabled() == TRUE:
            local('sudo openstack-config --set %s DEFAULT enabled_backends \
                                            rbd-disk' %(CINDER_CONFIG_FILE))
            if self._args.storage_os_hosts[0] != 'none':
                for entries, entry_token in zip(self._args.storage_os_hosts,
                                            self._args.storage_os_host_tokens):
                    with settings(host_string = 'root@%s' %(entries),
                                            password = entry_token):
                        run('sudo openstack-config --set %s DEFAULT \
                                            enabled_backends rbd-disk'
                                            %(CINDER_CONFIG_FILE))
        else:
            back_end = 'rbd-disk'
            for pool_name in ceph_pool_list:
                back_end = back_end + ',' + ('rbd-%s-disk' %(pool_name))

            local('sudo openstack-config --set %s DEFAULT enabled_backends %s'
                                            %(CINDER_CONFIG_FILE, back_end))
            if self._args.storage_os_hosts[0] != 'none':
                for entries, entry_token in zip(self._args.storage_os_hosts,
                                            self._args.storage_os_host_tokens):
                    with settings(host_string = 'root@%s' %(entries),
                                            password = entry_token):
                        run('sudo openstack-config --set %s DEFAULT \
                                            enabled_backends %s'
                                            %(CINDER_CONFIG_FILE, back_end))


        if self.is_multi_pool_disabled() == FALSE or \
                        self.is_ssd_pool_disabled() == FALSE:
            # Based on the hdd/ssd pools created,
            # Check for secret keys if present for all the pools.
            # Virsh secret-list will list all the secrets.
            # run dumpxml and check if has client.pool
            # If the client.pool secret is already present,
            # then reuse the same secret
            for pool_name in ceph_pool_list:
                secret_present = '0'
                line_num = 1
                while True:
                    virsh_secret = local('virsh secret-list  2>&1 | \
                                                awk \'{print $1}\' | \
                                                awk \'NR > 2 { print }\' | \
                                                tail -n +%d | head -n 1'
                                                %(line_num), capture=True)
                    if virsh_secret != "":
                        secret_present = local('virsh secret-dumpxml %s | \
                                                grep -w "client.%s" | wc -l'
                                                %(virsh_secret, pool_name),
                                                capture=True)
                        if secret_present != '0':
                            break
                    else:
                        break
                    line_num += 1

                # If secret is not present, create new secret
                # Set the secret with the keyring
                if secret_present == '0':
                    local('echo "<secret ephemeral=\'no\' private=\'no\'> \
                                <usage type=\'ceph\'> \
                                <name>client.%s secret</name> \
                                </usage> \
                                </secret>" > secret_%s.xml'
                                %(pool_name, pool_name))
                    virsh_secret = local('virsh secret-define --file \
                                    secret_%s.xml  2>&1 | \
                                    cut -d " " -f 2' %(pool_name), capture=True)
                volume_keyring_list = local('cat /etc/ceph/client.%s.keyring | \
                                    grep key' %(pool_name), capture=True)
                volume_keyring = volume_keyring_list.split(' ')[2]
                local('virsh secret-set-value %s --base64 %s'
                                    %(virsh_secret,volume_keyring))

                # Configure cinder backend for all the pools.
                # Configure the backends in the storage master
                local('sudo openstack-config --set %s rbd-%s-disk \
                                    volume_driver \
                                    cinder.volume.drivers.rbd.RBDDriver'
                                    %(CINDER_CONFIG_FILE, pool_name))
                local('sudo openstack-config --set %s rbd-%s-disk rbd_pool %s'
                                    %(CINDER_CONFIG_FILE, pool_name, pool_name))
                local('sudo openstack-config --set %s rbd-%s-disk rbd_user %s'
                                    %(CINDER_CONFIG_FILE, pool_name, pool_name))
                local('sudo openstack-config --set %s rbd-%s-disk \
                                    rbd_secret_uuid %s'
                                    %(CINDER_CONFIG_FILE, pool_name,
                                    virsh_secret))
                local('sudo openstack-config --set %s rbd-%s-disk \
                                    volume_backend_name %s'
                                    %(CINDER_CONFIG_FILE, pool_name,
                                    pool_name.upper()))
                # Configure the backends in all the openstack nodes.
                if self._args.storage_os_hosts[0] != 'none':
                    for entries, entry_token in zip(self._args.storage_os_hosts,
                                            self._args.storage_os_host_tokens):
                        with settings(host_string = 'root@%s' %(entries),
                                            password = entry_token):
                            run('sudo openstack-config --set %s rbd-%s-disk \
                                            volume_driver \
                                            cinder.volume.drivers.rbd.RBDDriver'
                                            %(CINDER_CONFIG_FILE, pool_name))
                            run('sudo openstack-config --set %s \
                                            rbd-%s-disk rbd_pool %s'
                                            %(CINDER_CONFIG_FILE, pool_name,
                                            pool_name))
                            run('sudo openstack-config --set %s \
                                            rbd-%s-disk rbd_user %s'
                                            %(CINDER_CONFIG_FILE, pool_name,
                                            pool_name))
                            run('sudo openstack-config --set %s \
                                            rbd-%s-disk rbd_secret_uuid %s'
                                            %(CINDER_CONFIG_FILE, pool_name,
                                            virsh_secret))
                            run('sudo openstack-config --set %s \
                                            rbd-%s-disk volume_backend_name %s'
                                            %(CINDER_CONFIG_FILE, pool_name,
                                            pool_name.upper()))
                for entries, entry_token in zip(self._args.storage_hosts,
                                            self._args.storage_host_tokens):
                    if entries != self._args.storage_master:
                        with settings(host_string = 'root@%s' %(entries),
                                            password = entry_token):
                            # Based on the hdd/ssd pools created,
                            # Check for secret keys if present for all the pools.
                            # Virsh secret-list will list all the secrets.
                            # run dumpxml and check if has the client.pool
                            # If the client.pool secret is already present,
                            # then reuse the same secret
                            same_secret = 0
                            line_num = 1
                            while True:
                                virsh_unsecret = run('virsh secret-list  2>&1 | \
                                                    awk \'{print $1}\' | \
                                                    awk \'NR > 2 { print }\' | \
                                                    tail -n +%d | head -n 1'
                                                    %(line_num))
                                if virsh_unsecret != "":
                                    if virsh_unsecret == virsh_secret:
                                        same_secret = 1
                                        break
                                    vol_present = run('virsh secret-dumpxml %s | \
                                                        grep -w "client.%s" | \
                                                        wc -l' %(virsh_unsecret,
                                                        pool_name))
                                    if vol_present != '0':
                                        run('virsh secret-undefine %s'
                                                        %(virsh_unsecret))
                                else:
                                    break
                                line_num += 1

                            # If secret is not present, create new secret
                            # Set the secret with the keyring
                            if same_secret == 0:
                                run('echo "<secret ephemeral=\'no\' private=\'no\'> \
                                        <uuid>%s</uuid><usage type=\'ceph\'> \
                                        <name>client.%s secret</name> \
                                        </usage> \
                                        </secret>" > secret_%s.xml'
                                        %(virsh_secret, pool_name, pool_name))
                                run('virsh secret-define --file secret_%s.xml'
                                                    %(pool_name))
                            run('virsh secret-set-value %s --base64 %s'
                                                %(virsh_secret,volume_keyring))
        return
    #end do_configure_virsh_cinder_rbd()

    # Function for generic cinder configuration
    def do_configure_cinder(self):
        # Set mysql listen ip to 0.0.0.0, so cinder volume manager from all
        # nodes can access.
        if self.is_lvm_config_disabled() == FALSE:
            local('sudo sed -i "s/^bind-address/#bind-address/" /etc/mysql/my.cnf')
            local('sudo service mysql restart')

        local('sudo openstack-config --set %s DEFAULT sql_connection \
                                        mysql://cinder:cinder@127.0.0.1/cinder'
                                        %(CINDER_CONFIG_FILE))
        # recently contrail changed listen address from 0.0.0.0 to mgmt address
        # so adding mgmt network to rabbit host
        # If the cinder_vip is present, use it as the rabbit host.
        if self._args.cinder_vip != 'none':
            local('sudo openstack-config --set %s DEFAULT rabbit_host %s'
                                        %(CINDER_CONFIG_FILE,
                                        self._args.cinder_vip))
            local('sudo openstack-config --set %s DEFAULT rabbit_port %s'
                                        %(CINDER_CONFIG_FILE,
                                        commonport.RABBIT_PORT))
        else:
            local('sudo openstack-config --set %s DEFAULT rabbit_host %s'
                                        %(CINDER_CONFIG_FILE,
                                        self._args.cfg_host))

        # After doing the mysql change, do a db sync
        local('sudo cinder-manage db sync')

        # Run the above for all openstack nodes
        if self._args.storage_os_hosts[0] != 'none':
            for entries, cfg_entry, entry_token in \
                            zip(self._args.storage_os_hosts,
                                        self._args.config_hosts,
                                        self._args.storage_os_host_tokens):
                with settings(host_string = 'root@%s' %(entries),
                                                password = entry_token):
                    run('sudo openstack-config --set %s DEFAULT sql_connection \
                                        mysql://cinder:cinder@127.0.0.1/cinder'
                                        %(CINDER_CONFIG_FILE))
                    # recently contrail changed listen address from 0.0.0.0 to
                    # mgmt address so adding mgmt network to rabbit host
                    # If the cinder_vip is present, use it as the rabbit host.
                    if self._args.cinder_vip != 'none':
                        run('sudo openstack-config --set %s DEFAULT \
                                        rabbit_host %s' %(CINDER_CONFIG_FILE,
                                        self._args.cinder_vip))
                        run('sudo openstack-config --set %s DEFAULT \
                                        rabbit_port %s' %(CINDER_CONFIG_FILE,
                                        commonport.RABBIT_PORT))
                    else:
                        run('sudo openstack-config --set %s DEFAULT \
                                        rabbit_host %s' %(CINDER_CONFIG_FILE,
                                        self._args.cfg_host))
                    # After doing the mysql change, do a db sync
                    run('sudo cinder-manage db sync')

        # configure cinder db retries
        local('sudo openstack-config --set %s database db_max_retries -1' \
                                            %(CINDER_CONFIG_FILE))
        if self._args.storage_os_hosts[0] != 'none':
            for entries, entry_token in zip(self._args.storage_os_hosts,
                                            self._args.storage_os_host_tokens):
                with settings(host_string = 'root@%s' %(entries),
                              password = entry_token):
                    run('sudo openstack-config --set %s database \
                         db_max_retries -1' %(CINDER_CONFIG_FILE))

        # set nofile limit
        nofilecheck = local('sudo cat %s | grep -w \
                             "limit nofile 102400 102400" | wc -l' \
                             %(CINDER_VOLUME_INIT_CONFIG), capture=True)
        if nofilecheck == '0':
            local('awk \'/exec/{print \"limit nofile 102400 102400\"}1\' %s > \
                   /tmp/cinder_volume_init' %(CINDER_VOLUME_INIT_CONFIG))
            local('mv /tmp/cinder_volume_init %s' %(CINDER_VOLUME_INIT_CONFIG))
        if self._args.storage_os_hosts[0] != 'none':
            for entries, entry_token in zip(self._args.storage_os_hosts,
                                            self._args.storage_os_host_tokens):
                with settings(host_string = 'root@%s' %(entries),
                              password = entry_token):
                    nofilecheck = run('sudo cat %s | grep -w \
                                      "limit nofile 102400 102400" | wc -l' \
                                      %(CINDER_VOLUME_INIT_CONFIG))
                    if nofilecheck == '0':
                        run('awk \'/exec/{print \
                            \"limit nofile 102400 102400\"}1\' %s > \
                            /tmp/cinder_volume_init' \
                            %(CINDER_VOLUME_INIT_CONFIG))
                        run('mv /tmp/cinder_volume_init %s' \
                            %(CINDER_VOLUME_INIT_CONFIG))

        return
    #end do_configure_cinder()

    # Function for LVM configuration
    def do_configure_lvm(self):
        global cinder_lvm_type_list
        global cinder_lvm_name_list

        # Create LVM volumes on each node
        if self._args.storage_local_disk_config[0] != 'none':
            for hostname, entries, entry_token in \
                            zip(self._args.storage_hostnames,
                                self._args.storage_hosts,
                                self._args.storage_host_tokens):
                with settings(host_string = 'root@%s' %(entries),
                                                        password = entry_token):
                    local_disk_list = ''
                    # Check if the disks are part of an existing LVM
                    # configuration. If its not present add to local_disk_list
                    # and zap the drive
                    for local_disks in self._args.storage_local_disk_config:
                        disksplit = local_disks.split(':')
                        disk_present = run('sudo pvdisplay | grep -w "%s" |wc -l'
                                                            %(disksplit[1]))
                        if disk_present != '0':
                            continue
                        if disksplit[0] == hostname:
                            local_disk_list = local_disk_list + \
                                                        disksplit[1] + ' '
                            run('sudo dd if=/dev/zero of=%s bs=512 count=1'
                                                                %(disksplit[1]))
                    if local_disk_list != '':
                        if entries != self._args.storage_master:
                            # Set the cinder mysql and rabbit configutaion on
                            # compute node
                            run('sudo openstack-config --set %s DEFAULT \
                                sql_connection mysql://cinder:cinder@%s/cinder'
                                %(CINDER_CONFIG_FILE, self._args.storage_master))
                            if self._args.cinder_vip != 'none':
                                run('sudo openstack-config --set %s DEFAULT \
                                    rabbit_host %s' %(CINDER_CONFIG_FILE,
                                    self._args.cinder_vip))
                                run('sudo openstack-config --set %s DEFAULT \
                                    rabbit_port %s' %(CINDER_CONFIG_FILE,
                                    commonport.RABBIT_PORT))
                            else:
                                run('sudo openstack-config --set %s DEFAULT \
                                    rabbit_host %s' %(CINDER_CONFIG_FILE,
                                    self._args.cfg_host))
                            run('sudo cinder-manage db sync')

                        # Enable lvm backend in cinder
                        existing_backends = run('sudo cat %s | \
                                                grep enabled_backends | \
                                                awk \'{print $3}\''
                                                %(CINDER_CONFIG_FILE),
                                                shell='/bin/bash')
                        if existing_backends != '':
                            new_backend = existing_backends + ',' + \
                                                        'lvm-local-disk-volumes'
                        else:
                            new_backend = 'lvm-local-disk-volumes'
                        run('sudo openstack-config --set %s DEFAULT \
                                                enabled_backends %s'
                                                %(CINDER_CONFIG_FILE,
                                                new_backend))
                        # Create the physical volume
                        run('sudo pvcreate %s' %(local_disk_list))
                        # Create the volume group if not present.
                        # If already present, extend it with new drives.
                        vg_present = run('sudo vgdisplay 2>&1 | \
                                            grep -w ocs-lvm-group | wc -l')
                        if vg_present == '0':
                            run('sudo vgcreate ocs-lvm-group %s'
                                                        %(local_disk_list))
                        else:
                            run('sudo vgextend ocs-lvm-group %s'
                                                        %(local_disk_list))
                        # Set cinder backend with the lvm configuration
                        run('sudo openstack-config --set %s \
                            lvm-local-disk-volumes volume_group ocs-lvm-group'
                            %(CINDER_CONFIG_FILE))
                        run('sudo openstack-config --set %s \
                            lvm-local-disk-volumes volume_driver \
                            cinder.volume.drivers.lvm.LVMISCSIDriver'
                            %(CINDER_CONFIG_FILE))
                        run('sudo openstack-config --set %s \
                            lvm-local-disk-volumes volume_backend_name \
                            OCS_LVM_%s'
                            %(CINDER_CONFIG_FILE, hostname))
                        # Add to the type, name list. this will be used during
                        # the creation of cinder types.
                        cinder_lvm_type_list.append('ocs-block-lvm-disk-%s'
                                                                    %(hostname))
                        cinder_lvm_name_list.append('OCS_LVM_%s' %(hostname))

        #Create LVM volumes for SSD disks on each node
        if self._args.storage_local_ssd_disk_config[0] != 'none':
            for hostname, entries, entry_token in \
                                zip(self._args.storage_hostnames,
                                    self._args.storage_hosts,
                                    self._args.storage_host_tokens):
                with settings(host_string = 'root@%s' %(entries),
                                                        password = entry_token):
                    # Check if the disks are part of an existing LVM
                    # configuration. If its not present add to local_disk_list
                    # and zap the drive
                    local_ssd_disk_list = ''
                    for local_ssd_disks in \
                                    self._args.storage_local_ssd_disk_config:
                        disksplit = local_ssd_disks.split(':')
                        disk_present = run('sudo pvdisplay | grep -w "%s" |wc -l'
                                                            %(disksplit[1]))
                        if disk_present != '0':
                            continue
                        if disksplit[0] == hostname:
                            local_ssd_disk_list = local_ssd_disk_list + \
                                                        disksplit[1] + ' '
                            run('sudo dd if=/dev/zero of=%s bs=512 count=1'
                                                                %(disksplit[1]))
                    if local_ssd_disk_list != '':
                        if entries != self._args.storage_master:
                            # Set the cinder mysql and rabbit configutaion on
                            # compute node
                            run('sudo openstack-config --set %s DEFAULT \
                                sql_connection mysql://cinder:cinder@%s/cinder'
                                %(CINDER_CONFIG_FILE, self._args.storage_master))
                            if self._args.cinder_vip != 'none':
                                run('sudo openstack-config --set %s DEFAULT \
                                    rabbit_host %s' %(CINDER_CONFIG_FILE,
                                    self._args.cinder_vip))
                                run('sudo openstack-config --set %s DEFAULT \
                                    rabbit_port %s' %(CINDER_CONFIG_FILE,
                                    commonport.RABBIT_PORT))
                            else:
                                run('sudo openstack-config --set %s DEFAULT \
                                    rabbit_host %s' %(CINDER_CONFIG_FILE,
                                    self._args.cfg_host))
                            run('sudo cinder-manage db sync')

                        # Enable lvm backend in cinder
                        existing_backends = run('sudo cat %s | \
                                                grep enabled_backends | \
                                                awk \'{print $3}\''
                                                %(CINDER_CONFIG_FILE),
                                                shell='/bin/bash')
                        if existing_backends != '':
                            new_backend = existing_backends + ',' + \
                                                    'lvm-local-ssd-disk-volumes'
                        else:
                            new_backend = 'lvm-local-ssd-disk-volumes'
                        run('sudo openstack-config --set %s DEFAULT \
                                                enabled_backends %s'
                                                %(CINDER_CONFIG_FILE,
                                                new_backend))
                        # Create the physical volume
                        run('sudo pvcreate %s' %(local_ssd_disk_list))
                        # Create the volume group if not present.
                        # If already present, extend it with new drives.
                        vg_present = run('sudo vgdisplay 2>&1 | \
                                            grep -w ocs-lvm-ssd-group | wc -l')
                        if vg_present == '0':
                            run('sudo vgcreate ocs-lvm-ssd-group %s'
                                                        %(local_ssd_disk_list))
                        else:
                            run('sudo vgextend ocs-lvm-ssd-group %s'
                                                        %(local_ssd_disk_list))
                        # Set cinder backend with the lvm configuration
                        run('sudo openstack-config --set %s \
                            lvm-local-ssd-disk-volumes volume_group \
                            ocs-lvm-ssd-group'
                            %(CINDER_CONFIG_FILE))
                        run('sudo openstack-config --set %s \
                            lvm-local-ssd-disk-volumes volume_driver \
                            cinder.volume.drivers.lvm.LVMISCSIDriver'
                            %(CINDER_CONFIG_FILE))
                        run('sudo openstack-config --set %s \
                            lvm-local-ssd-disk-volumes volume_backend_name \
                            OCS_LVM_SSD_%s'
                            %(CINDER_CONFIG_FILE, hostname))
                        # Add to the type, name list. this will be used during
                        # the creation of cinder types.
                        cinder_lvm_type_list.append('ocs-block-lvm-ssd-disk-%s'
                                                                    %(hostname))
                        cinder_lvm_name_list.append('OCS_LVM_SSD_%s' %(hostname))
        return
    #end do_config_lvm()

    # Function for nova configuration to work with cinder
    # This is required for all storage types
    # Run this in all the storage-compute nodes.
    def do_configure_nova(self):
        for entries, entry_token in zip(self._args.storage_hosts,
                                                self._args.storage_host_tokens):
            if entries != self._args.storage_master:
                with settings(host_string = 'root@%s' %(entries),
                                                password = entry_token):
                    # Remove rbd_user configurations from nova if present
                    run('sudo openstack-config --del %s DEFAULT rbd_user'
                                    %(NOVA_CONFIG_FILE))
                    run('sudo openstack-config --del %s DEFAULT rbd_secret_uuid'
                                    %(NOVA_CONFIG_FILE))
                    # Set the cinder end point to point to either the cinder_vip
                    # in case of HA or the storage master.
                    if self._args.cinder_vip != 'none':
                        run('sudo openstack-config --set %s DEFAULT \
                                    cinder_endpoint_template \
                                    "http://%s:8776/v1/%%(project_id)s"'
                                    %(NOVA_CONFIG_FILE, self._args.cinder_vip),
                                    shell='/bin/bash')
                    else:
                        run('sudo openstack-config --set %s DEFAULT \
                                    cinder_endpoint_template \
                                    "http://%s:8776/v1/%%(project_id)s"'
                                    %(NOVA_CONFIG_FILE, self._args.storage_master),
                                    shell='/bin/bash')
        return
    #end do_configure_nova()

    # Function for glance configuration for Ceph
    def do_configure_glance_rbd(self):
        #Glance configuration on the storage master
        local('sudo openstack-config --set %s DEFAULT default_store rbd'
                                            %(GLANCE_API_CONF))
        local('sudo openstack-config --set %s DEFAULT known_stores glance.store.rbd.Store'
                                            %(GLANCE_API_CONF))
        local('sudo openstack-config --set %s DEFAULT show_image_direct_url True'
                                            %(GLANCE_API_CONF))
        local('sudo openstack-config --set %s DEFAULT rbd_store_user images'
                                            %(GLANCE_API_CONF))
        local('sudo openstack-config --set %s DEFAULT workers %s'
                                            %(GLANCE_API_CONF, RBD_WORKERS))
        local('sudo openstack-config --set %s DEFAULT rbd_store_chunk_size %s'
                                            %(GLANCE_API_CONF,
                                            RBD_STORE_CHUNK_SIZE))
        local('sudo openstack-config --set %s DEFAULT rbd_store_pool images'
                                            %(GLANCE_API_CONF))
        local('sudo openstack-config --set %s DEFAULT rbd_store_ceph_conf %s'
                                            %(GLANCE_API_CONF, CEPH_CONFIG_FILE))
        #Glance configuration on all the other openstack nodes
        if self._args.storage_os_hosts[0] != 'none':
            for entries, entry_token in zip(self._args.storage_os_hosts,
                                            self._args.storage_os_host_tokens):
                with settings(host_string = 'root@%s' %(entries),
                                            password = entry_token):
                    run('sudo openstack-config --set %s DEFAULT \
                                            default_store rbd'
                                            %(GLANCE_API_CONF))
                    run('sudo openstack-config --set %s DEFAULT \
                                            known_stores glance.store.rbd.Store'
                                            %(GLANCE_API_CONF))
                    run('sudo openstack-config --set %s DEFAULT \
                                            show_image_direct_url True'
                                            %(GLANCE_API_CONF))
                    run('sudo openstack-config --set %s DEFAULT \
                                            rbd_store_user images'
                                            %(GLANCE_API_CONF))
                    run('sudo openstack-config --set %s DEFAULT \
                                            workers %s'
                                            %(GLANCE_API_CONF,
                                            RBD_WORKERS))
                    run('sudo openstack-config --set %s DEFAULT \
                                            rbd_store_chunk_size %s'
                                            %(GLANCE_API_CONF,
                                            RBD_STORE_CHUNK_SIZE))
                    run('sudo openstack-config --set %s DEFAULT \
                                            rbd_store_pool images'
                                            %(GLANCE_API_CONF))
                    run('sudo openstack-config --set %s DEFAULT \
                                            rbd_store_ceph_conf %s'
                                            %(GLANCE_API_CONF, CEPH_CONFIG_FILE))
        return
    #end do_configure_glance_rbd()

    # Function to check cluster health
    def do_cluster_health_check(self):
        monstate = run('ceph  health')
        monslen = len(monstate)
        while  monstate.find("HEALTH_OK", 0, monslen) == -1  and \
               monstate.find("HEALTH_WARN", 0, monslen):
            time.sleep(2)
            monstate = run('ceph  health')
            monslen = len(monstate)


    # Function to restart monitors after package upgrade
    def do_monitor_restarts(self):
        for monhostname in ceph_mon_hosts_list:
            for entries, entry_token, hostname in zip(self._args.storage_hosts, \
                self._args.storage_host_tokens, self._args.storage_hostnames):
                if monhostname == hostname:
                    with settings(host_string = 'root@%s' %(entries),
                                  password = entry_token):
                        mon = run('sudo ps -ef | grep ceph-mon | \
                                  grep -v grep | tr -s \' \' | cut -d \" \" -f 11')
                        if mon != '':
                            run('sudo sudo restart ceph-mon id=%s' %(mon))
                            print ('checking health after restarting \
                                    ceph-mon %s' %(mon))
                            self.do_cluster_health_check()
    #end do_monitor_restarts

    # Function to restart osds after package upgrade
    def do_osd_restarts(self):
        for entries, entry_token, hostname in zip(self._args.storage_hosts, \
            self._args.storage_host_tokens, self._args.storage_hostnames):
                with settings(host_string = 'root@%s' %(entries),
                              password = entry_token):
                    osdlist = run('sudo ps -ef | grep ceph-osd | \
                                  grep -v grep | tr -s \' \' | cut -d \" \" -f 11')
                    osdl = StringIO.StringIO(osdlist)
                    osd = osdl.readline()
                    while osd:
                        osd = osd.strip('\n\r')
                        if osd != '':
                            run('sudo sudo restart ceph-osd id=%s' %(osd))
                            print ('checking health after restarting \
                                ceph-osd %s' %(osd))
                            self.do_cluster_health_check()
                        osd = osdl.readline()
    #end do_osd_restarts



    # Function for first set of restarts.
    # This is done after all the cinder/nova/glance configurations
    def do_service_restarts_1(self):
        #Restart services
        if pdist == 'centos':
            local('sudo service qpidd restart')
            local('sudo service quantum-server restart')
            local('sudo chkconfig openstack-cinder-api on')
            local('sudo service openstack-cinder-api restart')
            local('sudo chkconfig openstack-cinder-scheduler on')
            local('sudo service openstack-cinder-scheduler restart')
            if configure_with_ceph == 1:
                bash_cephargs = local('grep "bashrc" \
                                         /etc/init.d/openstack-cinder-volume | \
                                         wc -l', capture=True)
                if bash_cephargs == "0":
                    local('cat /etc/init.d/openstack-cinder-volume | \
                            sed "s/start)/start)  source ~\/.bashrc/" > \
                            /tmp/openstack-cinder-volume.tmp')
                    local('mv -f /tmp/openstack-cinder-volume.tmp \
                            /etc/init.d/openstack-cinder-volume; \
                            chmod a+x /etc/init.d/openstack-cinder-volume')
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
            if configure_with_ceph == 1:
                bash_cephargs = local('grep "CEPH_ARGS" \
                                        /etc/init.d/cinder-volume | \
                                        wc -l', capture=True)
                #print bash_cephargs
                if bash_cephargs == "0":
                    local('cat /etc/init.d/cinder-volume | \
                            awk \'{ print; if ($1== "start|stop)") \
                            print \"    CEPH_ARGS=\\"--id volumes\\"\" }\' > \
                            /tmp/cinder-volume.tmp')
                    local('mv -f /tmp/cinder-volume.tmp \
                            /etc/init.d/cinder-volume; \
                            chmod a+x /etc/init.d/cinder-volume')
            local('sudo chkconfig cinder-volume on')
            local('sudo service cinder-volume restart')
            local('sudo service glance-api restart')
            local('sudo service nova-api restart')
            local('sudo service nova-conductor restart')
            local('sudo service nova-scheduler restart')
            local('sudo service libvirt-bin restart')
            local('sudo service nova-api restart')
            local('sudo service nova-scheduler restart')
            if self._args.storage_os_hosts[0] != 'none':
                for entries, entry_token in zip(self._args.storage_os_hosts,
                                            self._args.storage_os_host_tokens):
                    with settings(host_string = 'root@%s' %(entries),
                                            password = entry_token):
                        run('sudo chkconfig cinder-api on')
                        run('sudo service cinder-api restart')
                        run('sudo chkconfig cinder-scheduler on')
                        run('sudo service cinder-scheduler restart')
                        if configure_with_ceph == 1:
                            bash_cephargs = run('grep "CEPH_ARGS" \
                                                /etc/init.d/cinder-volume | \
                                                wc -l')
                            #print bash_cephargs
                            if bash_cephargs == "0":
                                run('cat /etc/init.d/cinder-volume | \
                                        awk \'{ print; if ($1== "start|stop)") \
                                        print \"    CEPH_ARGS=\\\\"--id volumes\\\\"\" }\' > \
                                        /tmp/cinder-volume.tmp')
                                run('mv -f /tmp/cinder-volume.tmp \
                                        /etc/init.d/cinder-volume; \
                                        chmod a+x /etc/init.d/cinder-volume')
                        run('sudo chkconfig cinder-volume on')
                        run('sudo service cinder-volume restart')
                        run('sudo service glance-api restart')
                        run('sudo service nova-api restart')
                        run('sudo service nova-conductor restart')
                        run('sudo service nova-scheduler restart')
                        run('sudo service libvirt-bin restart')
                        run('sudo service nova-api restart')
                        run('sudo service nova-scheduler restart')
        return
    #end do_service_restarts_1()

    # Function for cinder type configurations
    # This will create all the 'ocs-block' types.
    def do_configure_cinder_types(self):
        global configure_with_ceph

        # Create Cinder type for all Ceph backend
        # Create the default type for volumes pool if not present
        if configure_with_ceph == 1:
            type_configured = local('(. /etc/contrail/openstackrc ; \
                                        cinder type-list | \
                                        grep -w ocs-block-disk | \
                                        wc -l)', capture=True)
            if type_configured == '0':
                local('(. /etc/contrail/openstackrc ; \
                                    cinder type-create ocs-block-disk)')
            local('(. /etc/contrail/openstackrc ; \
                    cinder type-key ocs-block-disk set volume_backend_name=RBD)')

        if self.is_multi_pool_disabled() == FALSE or \
                        self.is_ssd_pool_disabled() == FALSE:
            # Based on the hdd/ssd pools created, create cinder types
            # if not present
            for pool_name in ceph_pool_list:
                # use the hdd-'pool name' (strip volumes_ from
                # volumes_hdd/volumes_ssd/volumes_hdd_Pool_0/volumes_ssd_Pool_1)
                type_configured = local('(. /etc/contrail/openstackrc ; \
                                            cinder type-list | \
                                            grep -w ocs-block-%s-disk | \
                                            wc -l)' %(pool_name[8:]),
                                            capture=True)
                if type_configured == '0':
                    local('(. /etc/contrail/openstackrc ; \
                        cinder type-create ocs-block-%s-disk)' %(pool_name[8:]))
                local('(. /etc/contrail/openstackrc ; \
                        cinder type-key ocs-block-%s-disk set volume_backend_name=%s)'
                        %(pool_name[8:], pool_name.upper()))

        # Create cinder type for NFS if not present already
        if create_nfs_disk_volume == 1:
            type_configured = local('(. /etc/contrail/openstackrc ; \
                                        cinder type-list | \
                                        grep -w ocs-block-nfs-disk | \
                                        wc -l)', capture=True)
            if type_configured == '0':
                local('(. /etc/contrail/openstackrc ; \
                        cinder type-create ocs-block-nfs-disk)')
            local('(. /etc/contrail/openstackrc ; \
                cinder type-key ocs-block-nfs-disk set volume_backend_name=NFS)')

        # Create Cinder type for all the LVM backends if not present already
        for lvm_types, lvm_names in zip(cinder_lvm_type_list,
                                        cinder_lvm_name_list):
            type_configured = local('(. /etc/contrail/openstackrc ; \
                                        cinder type-list | \
                                        grep -w %s | wc -l)' %(lvm_types),
                                        capture=True)
            if type_configured == '0':
                local('(. /etc/contrail/openstackrc ; \
                                cinder type-create %s)' %(lvm_types))
            local('(. /etc/contrail/openstackrc ; \
                                cinder type-key %s set volume_backend_name=%s)'
                                %(lvm_types, lvm_names))
        local('sudo service cinder-volume restart')
        return

    #end do_configure_cinder_types()

    # Function for 2nd set of restarts
    # This is done after the cinder type creation.
    # This is done on all the storage-compute nodes.
    def do_service_restarts_2(self):
        for entries, entry_token in zip(self._args.storage_hosts,
                                        self._args.storage_host_tokens):
            # Check if the node is not an openstack node.
            is_openstack = 0
            if self._args.storage_os_hosts[0] != 'none':
                for os_entries in self._args.storage_os_hosts:
                    if os_entries == entries:
                        is_openstack = 1
                        break

            if is_openstack == 1:
                continue
            # Check if the node is not a storage master
            if entries != self._args.storage_master:
                with settings(host_string = 'root@%s' %(entries),
                                                password = entry_token):
                    if pdist == 'centos':
                        run('sudo chkconfig tgt on')
                        run('sudo service tgt restart')
                        run('sudo service openstack-cinder-api restart')
                        run('sudo chkconfig openstack-cinder-api on')
                        run('sudo service openstack-cinder-scheduler restart')
                        run('sudo chkconfig openstack-cinder-scheduler on')
                        bash_cephargs = run('grep "bashrc" %s | wc -l'
                                                %(CENTOS_INITD_CINDER_VOLUME))
                        if bash_cephargs == "0":
                            run('cat %s | \
                                sed "s/start)/start)  source ~\/.bashrc/" > %s'
                                %(CENTOS_INITD_CINDER_VOLUME,
                                CENTOS_TMP_CINDER_VOLUME ))
                            run('mv -f %s %s; chmod a+x %s'
                                    %(CENTOS_TMP_CINDER_VOLUME,
                                    CENTOS_INITD_CINDER_VOLUME,
                                    CENTOS_INITD_CINDER_VOLUME))
                        run('sudo chkconfig openstack-cinder-volume on')
                        run('sudo service openstack-cinder-volume restart')
                        run('sudo service libvirtd restart')
                        run('sudo service openstack-nova-compute restart')
                    if pdist == 'Ubuntu':
                        run('sudo chkconfig tgt on')
                        run('sudo service tgt restart')
                        run('sudo chkconfig cinder-volume on')
                        run('sudo service cinder-volume restart')
                        run('sudo service libvirt-bin restart')
                        run('sudo service nova-compute restart')
        return
    #end do_service_restarts_2()

    # Function for configuration of storage stats daemon
    def do_configure_stats_daemon(self):
        # loop over storage compute host list to start contrail-storage-stats
        # only on storage compute nodes
        for compute_hostname in self._args.storage_compute_hostnames:
            for entries, entry_token, hostname in zip(self._args.storage_hosts,
                self._args.storage_host_tokens, self._args.storage_hostnames):
                # match storage compute with current hostname to get
                # host ip and passwd
                if compute_hostname == hostname:
                    with settings(host_string = 'root@%s' %(entries),
                                  password = entry_token):
                        if pdist == 'Ubuntu':
                            # Set the discovery server ip in the config and
                            # start the service.
                            if self._args.cfg_vip != 'none':
                                run('sudo openstack-config --set \
                                     %s DEFAULTS disc_server_ip %s' \
                                     %(CONTRAIL_STORAGE_STATS_CONF, \
                                     self._args.cfg_vip))
                            elif self._args.cinder_vip != 'none':
                                run('sudo openstack-config --set \
                                     %s DEFAULTS disc_server_ip %s' \
                                     %(CONTRAIL_STORAGE_STATS_CONF, \
                                     self._args.cinder_vip))
                            else:
                                run('sudo openstack-config --set \
                                     %s DEFAULTS disc_server_ip %s' \
                                     %(CONTRAIL_STORAGE_STATS_CONF, \
                                     self._args.cfg_host))
                            run('sudo service contrail-storage-stats restart')
                    break

        # loop over and remove init files to prevent starting
        # contrail-storage-stats on rebooting the node
        for entries, entry_token, hostname in zip(self._args.storage_hosts,
            self._args.storage_host_tokens, self._args.storage_hostnames):
                matchfound = 0
                # first master node match
                if entries == self._args.storage_master:
                    for compute_host in self._args.storage_compute_hostnames:
                        #match found -- don't remove init file
                        if compute_host == hostname:
                            matchfound = 1
                            break
                    # match not found then remove to prevent
                    # storage daemon start on reboot
                    if matchfound == 0:
                        with settings(host_string = 'root@%s' %(entries),
                                      password = entry_token):
                            storage_stats=run('ps -ef|grep -v grep|grep contrail-storage-stats|wc -l')
                            if storage_stats == '1':
                                run('service contrail-storage-stats stop')
                            run('sudo rm -rf %s' %(CONTRAIL_STORAGE_STATS_INIT))
                # all master node match except first master
                if self._args.storage_os_hosts[0] != 'none':
                    for entries_os in self._args.storage_os_hosts:
                        if entries == entries_os:
                            for compute_host in \
                                self._args.storage_compute_hostnames:
                                #match found -- don't remove init file
                                if compute_host == hostname:
                                    matchfound = 1
                                    break
                            # match not found then remove to prevent
                            # storage daemon start on reboot
                            if matchfound == 0:
                                with settings(host_string = 'root@%s' \
                                    %(entries), password = entry_token):
                                    storage_stats=run('ps -ef|grep -v grep|grep contrail-storage-stats|wc -l')
                                    if storage_stats == '1':
                                        run('service contrail-storage-stats stop')
                                    run('sudo rm -rf %s' \
                                        %(CONTRAIL_STORAGE_STATS_INIT))
        return
    #end do_configure_stats_daemon()

    # Function to remove each OSD in the self._args.disks_to_remove list.
    def do_remove_osd(self):
        for entries, entry_token, hostname in zip(self._args.storage_hosts,
                self._args.storage_host_tokens, self._args.storage_hostnames):
            for disk_to_remove in self._args.disks_to_remove:
                if hostname == disk_to_remove.split(':')[0]:
                    with settings(host_string = 'root@%s' %(entries),
                                                    password = entry_token):
                        # Find the mounts and using the mount, find the OSD
                        # number.
                        # Remove osd using ceph commands.
                        # Unmount the drive and destroy the partitions
                        mounted = run('sudo cat /proc/mounts | grep %s | wc -l'
                                            %(disk_to_remove.split(':')[1]))
                        if mounted != '0':
                            osd_det = run('sudo mount | grep %s | \
                                                awk \'{ print $3 }\''
                                                %(disk_to_remove.split(':')[1]),
                                                shell='/bin/bash')
                            if osd_det != '':
                                osd_num = osd_det.split('-')[1]
                                run('sudo stop ceph-osd id=%s' %(osd_num))
                                run('sudo ceph -k %s osd out %s'
                                            %(CEPH_ADMIN_KEYRING, osd_num))
                                run('sudo ceph osd crush remove osd.%s'
                                                                %(osd_num))
                                run('sudo ceph -k %s auth del osd.%s'
                                            %(CEPH_ADMIN_KEYRING, osd_num))
                                run('sudo ceph -k %s osd rm %s'
                                            %(CEPH_ADMIN_KEYRING, osd_num))
                                run('sudo umount /var/lib/ceph/osd/ceph-%s'
                                                                %(osd_num))
                                run('sudo parted -s %s mklabel gpt 2>&1 > \
                                                                /dev/null'
                                            %(disk_to_remove.split(':')[1]))
        return
    #end do_remove_osd()

    # Function to create the list of OSDs to remove.
    # This is called during a storage node delete.
    def do_create_osd_remove_config(self):

        disks_to_remove = []
        for entries, entry_token, hostname in zip(self._args.storage_hosts,
                self._args.storage_host_tokens, self._args.storage_hostnames):
            for host_to_remove in self._args.hosts_to_remove:
                if hostname == host_to_remove:
                    with settings(host_string = 'root@%s' %(entries),
                                        password = entry_token):
                        # Check if ceph-osd process is running on the node which
                        # has to be removed.
                        # If ceph-osd is running, get the osd number and find
                        # the corresponding mount name.
                        # Create the list of hostname:mountname and save it to
                        # self._args.disks_to_remove.
                        # This will be removed using the do_remove_osd()
                        line_num = 1
                        while True:
                            ceph_id = run('ps  -ef | grep ceph-osd | \
                                                    grep -v grep | grep -v asok | \
                                                    tail -n +%s | head -n 1 | \
                                                    awk \'{print $11}\''
                                                    %(line_num))
                            if ceph_id != '':
                                mount_name = run('sudo cat /proc/mounts | \
                                                grep -w ceph-%s | \
                                                awk \'{print $1}\'' %(ceph_id))
                                disk_name = mount_name[:-1]
                                disks_to_remove.append('%s:%s' %(hostname,
                                                                    disk_name))
                            else:
                                break
                            line_num += 1
        self._args.disks_to_remove = disks_to_remove
        return

    #end do_create_osd_remove_config()

    # Function to remove the monitor when a storage node is deleted.
    def do_remove_monitor(self):
        for entries, entry_token, hostname in zip(self._args.storage_hosts,
                self._args.storage_host_tokens, self._args.storage_hostnames):
            for host_to_remove in self._args.hosts_to_remove:
                if hostname == host_to_remove:
                    with settings(host_string = 'root@%s' %(entries),
                                        password = entry_token):
                        # Check if mon is running, if so destroy the mon
                        # Remove ceph related directories.
                        mon_running = local('ceph mon stat | grep -w %s | wc -l'
                                                    %(hostname), capture=True)
                        if mon_running != '0':
                            local('ceph-deploy mon destroy %s' %(hostname))
                        run('sudo rm -rf /var/lib/ceph')
                        run('sudo rm -rf /var/run/ceph')
                        run('sudo rm -rf /etc/ceph')
        return
    #end do_remove_monitor()

    # Remove the disks to be deleted from the configuration variables.
    # The variables will be used during crush map setting
    def do_remove_osd_config(self):

        disk_list = []
        # Find the delete entries in the storage_disk_config
        # and remove it.
        for disks in self._args.storage_disk_config:
            disksplit = disks.split(':')
            disk_match = 0
            for disk_to_remove in self._args.disks_to_remove:
                if ('%s:%s' %(disksplit[0], disksplit[1]) ==
                                                    disk_to_remove):
                    disk_match = 1
            if disk_match == 0:
                disk_list.append(disks)
        self._args.storage_disk_config = disk_list
        # Find the delete entries in the storage_ssd_disk_config
        # and remove it.
        if self._args.storage_ssd_disk_config[0] != 'none':
            disk_list = []
            for disks in self._args.storage_ssd_disk_config:
                disksplit = disks.split(':')
                disk_match = 0
                for disk_to_remove in self._args.disks_to_remove:
                    if ('%s:%s' %(disksplit[0], disksplit[1]) ==
                                                    disk_to_remove):
                        disk_match = 1
                if disk_match == 0:
                    disk_list.append(disks)
            self._args.storage_ssd_disk_config = disk_list
        return

    #end do_remove_osd_config()

    # Top level function for remove disk
    # TODO: Add support for local lvm disks
    def do_storage_remove_disk(self):
        global configure_with_ceph
        if self._args.storage_directory_config[0] != 'none' or \
                self._args.storage_disk_config[0] != 'none' or \
                self._args.storage_ssd_disk_config[0] != 'none':
            configure_with_ceph = 1
        else:
            configure_with_ceph = 0

        if configure_with_ceph:

            # remove osd info from config
            self.do_remove_osd_config()

            # Remove OSD
            self.do_remove_osd()

            # Modify the crush map for HDD/SSD/Chassis
            # and Configure Ceph pools
            self.do_crush_map_pool_config()

        return

    # Top level function for remove disk
    # TODO: Add support for local lvm disk hosts
    def do_storage_remove_host(self):
        global configure_with_ceph
        if self._args.storage_directory_config[0] != 'none' or \
                self._args.storage_disk_config[0] != 'none' or \
                self._args.storage_ssd_disk_config[0] != 'none':
            configure_with_ceph = 1
        else:
            configure_with_ceph = 0

        if configure_with_ceph:

            # remove host info from config
            self.do_create_osd_remove_config()

            # remove osd info from config
            self.do_remove_osd_config()

            # Remove OSD
            self.do_remove_osd()

            # Remove mon if present
            self.do_remove_monitor()

            # Modify the crush map for HDD/SSD/Chassis
            # and Configure Ceph pools
            self.do_crush_map_pool_config()

            # stop contrail-storage-stats
            self.contrail_storage_stats_service_remove()

        return

    def do_storage_upgrade(self):

        if self._args.storage_directory_config[0] != 'none' or \
                self._args.storage_disk_config[0] != 'none' or \
                self._args.storage_ssd_disk_config[0] != 'none':
            # restart monitors after package upgrade
            self.do_monitor_restarts()
            # restart osds after package upgrade
            self.do_osd_restarts()



    # Top level function for storage setup.
    def do_storage_setup(self):
        global configure_with_ceph

        if self._args.storage_directory_config[0] != 'none' or \
                self._args.storage_disk_config[0] != 'none' or \
                self._args.storage_ssd_disk_config[0] != 'none':
            configure_with_ceph = 1
        else:
            configure_with_ceph = 0

        if configure_with_ceph:
            # Create the required ceph monitors
            self.do_monitor_create()

            # Create the required OSDs
            self.do_osd_create()

            # update ceph mon host list on all storage nodes
            self.do_update_monhost_config()

            # Modify the crush map for HDD/SSD/Chassis
            # and Configure Ceph pools
            self.do_crush_map_pool_config()

            # Tune Ceph for performance
            self.do_tune_ceph()

            # Configure syslog for Ceph logs
            self.do_configure_syslog()

            # Configure Ceph pool authentications
            self.do_configure_ceph_auth()

            # Configure Virsh/Cinder with ceph authentication
            self.do_configure_virsh_cinder_rbd()

            # Configure glance to use Ceph
            self.do_configure_glance_rbd()

        # Configure base cinder
        self.do_configure_cinder()

        # Configure base nova to use cinder
        self.do_configure_nova()

        # Configure LVM based storage
        self.do_configure_lvm()

        # Configure NFS based storage
        self.do_configure_nfs()

        # Peform 1st set of restarts
        self.do_service_restarts_1()

        # Configure Volume types
        self.do_configure_cinder_types()

        # Perform 2nd set of restarts
        self.do_service_restarts_2()

        # For ceph based configurations,
        # Configure stats daemon and rest api.
        if configure_with_ceph:
            self.do_configure_stats_daemon()

            self.ceph_rest_api_service_add()

        return
    #end do_storage_setup()

    # Main function for storage related configurations
    # Note: All the functions are idempotent. Any additions/modifications
    #       should ensure that the behavior stays the same.
    def __init__(self, args_str = None):
        #print sys.argv[1:]
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        # Parse the arguments
        self._parse_args(args_str)

        # Do the ssh key configuration
        self.do_ssh_config()

        # Create monitor list
        self.do_create_monlist()
        # Following all are specific setups based on the setup_mode

        # Do a unconfigure of all the nodes that are part of ceph.
        if self._args.storage_setup_mode == 'unconfigure':
            self.do_storage_unconfigure()
            return

        # The do_storage_setup() is idempotent. All the setup
        # modes will call do_storage_setup().

        # This is called with 'fab storage_chassis_configure'
        # This will be useful to provision an existing cluster with
        # the chassis configuration without destroying the data.
        if self._args.storage_setup_mode == 'chassis_configure':
            self.do_storage_setup()
            return

        # This is a standard setup mode called with 'fab setup_storage'
        if self._args.storage_setup_mode == 'setup':
            self.do_storage_setup()
            return

        # This is a add node mode called with 'fab add_storage_node'
        if self._args.storage_setup_mode == 'addnode':
            self.do_storage_setup()
            return

        # This is a reconfigure storage called with 'fab reconfigure_storage'
        # This will clear out existing configuration and performs a fresh setup.
        if self._args.storage_setup_mode == 'reconfigure':
            self.do_storage_unconfigure()
            self.do_storage_setup()
            return

        # Remove disk from Ceph/LVM/NFS
        if self._args.storage_setup_mode == 'remove_disk':
            self.do_storage_remove_disk()
            return

        # Remove host from storage
        if self._args.storage_setup_mode == 'remove_host':
            self.do_storage_remove_host()
            return

        if self._args.storage_setup_mode == 'upgrade':
            self.do_storage_upgrade()
            self.do_storage_setup()
            return

        return

    #end __init__

    def _parse_args(self, args_str):
        '''
        Eg. storage-fs-setup --storage-master 10.157.43.171 --storage-hostnames cmbu-dt05 cmbu-ixs6-2 --storage-hosts 10.157.43.171 10.157.42.166 --storage-host-tokens n1keenA n1keenA --storage-disk-config 10.157.43.171:sde 10.157.43.171:sdf 10.157.43.171:sdg --storage-directory-config 10.157.42.166:/mnt/osd0 --storage-chassis-config 10.157.166:0 10.157.42.167:1 --live-migration enabled
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
            parents = [conf_parser],
            # print script description with -h/--help
            description = __doc__,
            # Don't mess with format of description
            formatter_class = argparse.RawDescriptionHelpFormatter,
            )

        all_defaults = {'global': global_defaults}
        parser.set_defaults(**all_defaults)

        parser.add_argument("--storage-master", help = "IP Address of storage master node")
        parser.add_argument("--storage-hostnames", help = "Host names of storage nodes", nargs='+', type=str)
        parser.add_argument("--storage-compute-hostnames", help = "Host names of storage compute nodes", nargs='+', type=str)
        parser.add_argument("--storage-hosts", help = "IP Addresses of storage nodes", nargs='+', type=str)
        parser.add_argument("--storage-host-tokens", help = "Passwords of storage nodes", nargs='+', type=str)
        parser.add_argument("--storage-disk-config", help = "Disk list to be used for distrubuted storage", nargs="+", type=str)
        parser.add_argument("--storage-ssd-disk-config", help = "SSD Disk list to be used for distrubuted storage", nargs="+", type=str)
        parser.add_argument("--storage-local-disk-config", help = "Disk list to be used for local storage", nargs="+", type=str)
        parser.add_argument("--storage-local-ssd-disk-config", help = "SSD Disk list to be used for local storage", nargs="+", type=str)
        parser.add_argument("--storage-nfs-disk-config", help = "Disk list to be used for local storage", nargs="+", type=str)
        parser.add_argument("--storage-journal-config", help = "Disk list to be used for distrubuted storage journal", nargs="+", type=str)
        parser.add_argument("--storage-directory-config", help = "Directories to be sued for distributed storage", nargs="+", type=str)
        parser.add_argument("--storage-chassis-config", help = "Chassis ID for the host to avoid replication between nodes in the same chassis", nargs="+", type=str)
        parser.add_argument("--collector-hosts", help = "IP Addresses of collector nodes", nargs='+', type=str)
        parser.add_argument("--collector-host-tokens", help = "Passwords of collector nodes", nargs='+', type=str)
        parser.add_argument("--cfg-host", help = "IP Address of config node")
        parser.add_argument("--cinder-vip", help = "Cinder vip")
        parser.add_argument("--storage-mon-hosts", help = "storage compute mon list", nargs='+', type=str)
        parser.add_argument("--config-hosts", help = "config host list", nargs='+', type=str)
        parser.add_argument("--storage-os-hosts", help = "storage openstack host list", nargs='+', type=str)
        parser.add_argument("--storage-os-host-tokens", help = "storage openstack host pass list", nargs='+', type=str)
        parser.add_argument("--add-storage-node", help = "Add a new storage node")
        parser.add_argument("--cfg-vip", help = "Config vip")
        parser.add_argument("--storage-setup-mode", help = "Storage configuration mode")
        parser.add_argument("--disks-to-remove", help = "Disks to remove", nargs="+", type=str)
        parser.add_argument("--hosts-to-remove", help = "Hosts to remove", nargs="+", type=str)

        self._args = parser.parse_args(remaining_argv)

    #end _parse_args

#end class SetupCeph

def main(args_str = None):
    SetupCeph(args_str)
#end main

if __name__ == "__main__":
    main()
