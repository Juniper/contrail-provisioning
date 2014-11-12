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
import pdb

import tempfile
from fabric.api import local, env, run, settings
from fabric.operations import get, put
from fabric.context_managers import lcd, settings
from fabric.api import local, env, run
from fabric.operations import get, put
from fabric.context_managers import lcd, settings
sys.path.insert(0, os.getcwd())

class SetupCeph(object):

    # Added global variables for the files.
    # Use the variables instead of the filenames directly in the script
    # to avoid typos and readability.
    global CINDER_CONFIG_FILE
    CINDER_CONFIG_FILE='/etc/cinder/cinder.conf'
    global NOVA_CONFIG_FILE
    NOVA_CONFIG_FILE='/etc/nova/nova.conf'
    global CEPH_CONFIG_FILE
    CEPH_CONFIG_FILE='/etc/ceph/ceph.conf'
    global MAX_POOL_COUNT
    MAX_POOL_COUNT = 1024
    global ceph_pool_list
    ceph_pool_list = []
    global CS_CRUSH_MAP
    CS_CRUSH_MAP='/tmp/ma-crush-map-cs'
    global CS_CRUSH_MAP_MOD
    CS_CRUSH_MAP_MOD='/tmp/ma-crush-map-cs-mod'
    global CS_CRUSH_MAP_TXT
    CS_CRUSH_MAP_TXT='/tmp/ma-crush-map-cs.txt'
    global CS_CRUSH_MAP_MOD_TXT
    CS_CRUSH_MAP_MOD_TXT='/tmp/ma-crush-map-cs-mod.txt'
    global CS_CRUSH_MAP_MOD_TMP_TXT
    CS_CRUSH_MAP_MOD_TMP_TXT='/tmp/ma-crush-map-cs-mod-tmp.txt'
    global CEPH_ADMIN_KEYRING
    CEPH_ADMIN_KEYRING='/etc/ceph/ceph.client.admin.keyring'

    global SYSLOG_LOGPORT
    SYSLOG_LOGPORT='4514'

    global RABBIT_PORT
    RABBIT_PORT='5673'

    global MAX_MONS
    MAX_MONS = 10

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
    #end reset_mon_local_list()

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
    #end reset_osd_local_list()

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
    #end reset_mon_remote_list()

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
    #end reset_osd_remote_list()

    def ceph_rest_api_service_add(self):
        # check for ceph-rest-api.conf
        # write /etc/init conf for service upstrart
        # if service not running then replace app.ceph_port to 5005
        # start the ceph-rest-api service

        # first master node
        rest_api_conf_available=local('ls /etc/init/ceph-rest-api.conf  2>/dev/null | wc -l', capture=True)
        if rest_api_conf_available == '0':
            local('sudo echo description \\"Ceph REST API\\" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "start on started rc RUNLEVEL=[2345]" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "stop on runlevel [!2345]" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "respawn" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "respawn limit 5 30" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "limit nofile 16384 16384" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "pre-start script" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "    set -e" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "    test -x /usr/bin/ceph-rest-api || { stop; exit 0; }" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "end script" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "# this breaks oneiric" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "#usage \\"ceph-rest-api -c <conf-file> -n <client-name>\\"" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "exec ceph-rest-api -c /etc/ceph/ceph.conf -n client.admin" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "post-stop script" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "# nothing to do for now" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "end script" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')
            local('sudo echo "" >> /etc/init/ceph-rest-api.conf', shell='/bin/bash')

        ceph_rest_api_process_running=local('ps -ef|grep -v grep|grep ceph-rest-api|wc -l', capture=True)
        if ceph_rest_api_process_running == '0':
            entry_present=local('grep \"app.run(host=app.ceph_addr, port=app.ceph_port)\" /usr/bin/ceph-rest-api | wc -l', capture=True)
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
                    rest_api_conf_avail = run('ls /etc/init/ceph-rest-api.conf  2>/dev/null | wc -l')
                    if rest_api_conf_avail == '0':
                        put('/etc/init/ceph-rest-api.conf', '/etc/init/')
                    ceph_rest_api_process_running=run('ps -ef|grep -v grep|grep ceph-rest-api|wc -l')
                    if ceph_rest_api_process_running == '0':
                        entry_present=run('grep \"app.run(host=app.ceph_addr, port=app.ceph_port)\" /usr/bin/ceph-rest-api | wc -l')
                        if entry_present == '1':
                            if self._args.cinder_vip != 'none':
                                run('sudo sed -i "s/app.run(host=app.ceph_addr, port=app.ceph_port)/app.run(host=app.ceph_addr, port=5006)/" /usr/bin/ceph-rest-api')
                            else:
                                run('sudo sed -i "s/app.run(host=app.ceph_addr, port=app.ceph_port)/app.run(host=app.ceph_addr, port=5005)/" /usr/bin/ceph-rest-api')
                        run('sudo service ceph-rest-api start')

    #end ceph_rest_api_service_add()


    def unconfigure_syslog(self):
            # disable server:port syslog remote logging
            for entries in self._args.collector_hosts:
                syslog_present=local('grep "*.* @%s:%s" /etc/rsyslog.d/50-default.conf  | wc -l' %(entries, SYSLOG_LOGPORT), capture=True)
                if syslog_present == '1':
                    local('sed -i "/*.* @%s:%s/d" /etc/rsyslog.d/50-default.conf' %(entries, SYSLOG_LOGPORT))
                    # restart rsyslog service after remote logging enabled
                    local('service rsyslog restart')

            # find and replace syslog port to default in collector
            for entries, entry_token in zip(self._args.collector_hosts, self._args.collector_host_tokens):
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    syslog_port=run('grep "syslog_port=4514" /etc/contrail/contrail-collector.conf | wc -l')
                    if syslog_port == '1':
                        run('cat /etc/contrail/contrail-collector.conf | sed "s/syslog_port=4514/syslog_port=-1/" > /tmp/contrail-collector.conf; mv /tmp/contrail-collector.conf /etc/contrail/contrail-collector.conf')
                        # restart collector after syslog default port change
                        run('service contrail-collector restart')
    #end unconfigure_syslog()


    def ceph_rest_api_service_remove(self):
        # check the ceph-rest-api service
        # if it is running then trigger ceph-rest-api stop
        # finally removing ceph-rest-api.conf

        # first master node
        ceph_rest_api_process_running=local('ps -ef|grep -v grep|grep ceph-rest-api|wc -l', capture=True)
        if ceph_rest_api_process_running != '0':
            local('sudo service ceph-rest-api stop', shell='/bin/bash')
        rest_api_conf_available=local('ls /etc/init/ceph-rest-api.conf  2>/dev/null | wc -l', capture=True)
        if rest_api_conf_available != '0':
            local('sudo rm -rf /etc/init/ceph-rest-api.conf', shell='/bin/bash')
        # remaining configured master nodes for HA
        if self._args.storage_os_hosts[0] != 'none':
            for entries, entry_token in zip(self._args.storage_os_hosts, self._args.storage_os_host_tokens):
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    ceph_rest_api_process_running=run('ps -ef|grep -v grep|grep ceph-rest-api|wc -l')
                    if ceph_rest_api_process_running != '0':
                        run('sudo service ceph-rest-api stop')
                    rest_api_conf_avail=run('ls /etc/init/ceph-rest-api.conf  2>/dev/null | wc -l')
                    if rest_api_conf_available != '0':
                        run('sudo rm -rf /etc/init/ceph-rest-api.conf')
    #end ceph_rest_api_service_remove()

    def set_pg_count_increment(self, pool, pg_count):
        while True:
            time.sleep(2);
            creating_pgs=local('sudo ceph -s | grep creating | wc -l', capture=True)
            if creating_pgs == '0':
                break;
            print 'Waiting for create pgs to complete'
        local('sudo ceph -k /etc/ceph/ceph.client.admin.keyring osd pool set %s pg_num %d' %(pool, pg_count))
    #end set_pg_count_increment()

    def set_pgp_count_increment(self, pool, pg_count):
        while True:
            time.sleep(2);
            creating_pgs=local('sudo ceph -s | grep creating | wc -l', capture=True)
            if creating_pgs == '0':
                break;
            print 'Waiting for create pgs to complete'
        local('sudo ceph -k /etc/ceph/ceph.client.admin.keyring osd pool set %s pgp_num %d' %(pool, pg_count))
    #end set_pgp_count_increment()

    def set_pg_pgp_count(self, osd_num, pool, host_cnt):

        # Calculate/Set PG count
        # The pg/pgp set will not take into effect if ceph is already in the
        # process of creating pgs. So its required to do ceph -s and check
        # if the pgs are currently creating and if not set the values

        # Set the num of pgs to 32 times the OSD count. This is based on
        # Firefly release recomendation.

        while True:
            time.sleep(5);
            creating_pgs=local('sudo ceph -s | grep creating | wc -l', capture=True)
            if creating_pgs == '0':
                break;
            print 'Waiting for create pgs to complete'

        cur_pg = local('sudo ceph -k /etc/ceph/ceph.client.admin.keyring osd pool get %s pg_num' %(pool), capture=True)
        cur_pg_cnt = int(cur_pg.split(':')[1])
        max_pg_cnt = 30 * osd_num
        while True:
            cur_pg_cnt = 30 * cur_pg_cnt
            if cur_pg_cnt > max_pg_cnt:
                self.set_pg_count_increment(pool, max_pg_cnt)
                self.set_pgp_count_increment(pool, max_pg_cnt)
                break;
            else:
                self.set_pg_count_increment(pool, cur_pg_cnt)
                self.set_pgp_count_increment(pool, cur_pg_cnt)
    #end set_pg_pgp_count()

    # Create HDD/SSD Pool
    # For HDD/SSD pool, the crush map has to be changed to accomodate the
    # rules for the HDD/SSD pools. For this, new ssd, hdd specific hosts
    # have to be added to the map. The ssd, hdd specific maps will then
    # be linked to the root entry for SSD/HDD pool and finally which is linked
    # to a rule entry. The rules will then be applied to the respective pools
    # created using the mkpool command.
    # For populating the map with the host/tier specific entries, A dictionary
    # of host/tier specific entries will be created. This will include the
    # Total tier specific count, tier specific count for a particular host
    # and entries for the tier for a particular host.
    # The host_<tier>_dict will have the tier specific entries and the count
    # for a particular host.
    # The following operation is performed.
    # - Get existing crushmap.
    # - Populate the tier/host specific rules.
    # - Compile/Apply the new crush map.
    # - Apply the ruleset to the tier specific pools.
    def create_hdd_ssd_pool(self):
        local('sudo ceph osd getcrushmap -o /tmp/ma-crush-map')
        local('sudo crushtool -d /tmp/ma-crush-map -o /tmp/ma-crush-map.txt')
        #print self._args
        host_hdd_dict = {}
        host_ssd_dict = {}
        pool_count = 0
        while True:
            host_hdd_dict[('totalcount', '%s' %(pool_count))] = 0
            host_ssd_dict[('totalcount', '%s' %(pool_count))] = 0
            host_hdd_dict[('ruleid', '%s' %(pool_count))] = 0
            host_ssd_dict[('ruleid', '%s' %(pool_count))] = 0
            host_hdd_dict[('hostcount', '%s' %(pool_count))] = 0
            host_ssd_dict[('hostcount', '%s' %(pool_count))] = 0
            host_hdd_dict[('poolname', '%s' %(pool_count))] = ''
            host_ssd_dict[('poolname', '%s' %(pool_count))] = ''
            if pool_count > MAX_POOL_COUNT:
                break
            pool_count = pool_count + 1
        hdd_pool_count = 0
        ssd_pool_count = 0
        # Build the host/tier specific dictionary
        for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
            host_hdd_dict[hostname, 'count'] = 0
            host_ssd_dict[hostname, 'count'] = 0
            pool_count = 0
            while True:
                host_hdd_dict[('hostcountadded', '%s' %(pool_count))] = 0
                host_ssd_dict[('hostcountadded', '%s' %(pool_count))] = 0
                if pool_count > MAX_POOL_COUNT:
                    break
                pool_count = pool_count + 1
            for disks in self._args.storage_disk_config:
                diskcount = disks.count(':')
                disksplit = disks.split(':')
                pool_index = 0
                if disksplit[0] == hostname:
                    if (diskcount == 3 and
                        disksplit[3][0] == 'P') or \
                        (diskcount == 2 and
                            disksplit[2][0] == 'P'):
                        if diskcount == 3:
                            pool_name = disksplit[3]
                        if diskcount == 2:
                            pool_name = disksplit[2]
                        if hdd_pool_count != 0:
                            while True:
                                if pool_name == host_hdd_dict[('poolname', '%s' %(pool_index))]:
                                    break
                                pool_index = pool_index + 1
                                if pool_index == hdd_pool_count:
                                    hdd_pool_count = hdd_pool_count + 1
                                    break
                        else:
                            pool_index = hdd_pool_count
                            hdd_pool_count = hdd_pool_count + 1
                        host_hdd_dict[('poolname', '%s' %(pool_index))] = pool_name
                    if host_hdd_dict[('hostcountadded', '%s' %(pool_index))] == 0:
                        host_hdd_dict[('hostcount', '%s' %(pool_index))] += 1
                        host_hdd_dict[('hostcountadded', '%s' %(pool_index))] = 1

            for disks in self._args.storage_ssd_disk_config:
                diskcount = disks.count(':')
                disksplit = disks.split(':')
                pool_index = 0
                if disksplit[0] == hostname:
                    if (diskcount == 3 and
                        disksplit[3][0] == 'P') or \
                        (diskcount == 2 and
                            disksplit[2][0] == 'P'):
                        if diskcount == 3:
                            pool_name = disksplit[3]
                        if diskcount == 2:
                            pool_name = disksplit[2]
                        if ssd_pool_count != 0:
                            while True:
                                if pool_name == host_ssd_dict[('poolname', '%s' %(pool_index))]:
                                    break
                                pool_index = pool_index + 1
                                if pool_index == ssd_pool_count:
                                    ssd_pool_count = ssd_pool_count + 1
                                    break
                        else:
                            pool_index = ssd_pool_count
                            ssd_pool_count = ssd_pool_count + 1
                        host_ssd_dict[('poolname', '%s' %(pool_index))] = pool_name
                    if host_ssd_dict[('hostcountadded', '%s' %(pool_index))] == 0:
                        host_ssd_dict[('hostcount', '%s' %(pool_index))] += 1
                        host_ssd_dict[('hostcountadded', '%s' %(pool_index))] = 1

        for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
            pool_index = 0
            while True:
                host_hdd_dict['%s-%s' %(hostname, pool_index), 'count'] = 0
                pool_index = pool_index + 1
                if pool_index >= hdd_pool_count:
                    break
            pool_index = 0
            while True:
                host_ssd_dict['%s-%s' %(hostname, pool_index), 'count'] = 0
                pool_index = pool_index + 1
                if pool_index >= ssd_pool_count:
                    break

        for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
            for disks in self._args.storage_disk_config:
                disksplit = disks.split(':')
                diskcount = disks.count(':')
                pool_index = 0
                if disksplit[0] == hostname:
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        osddet=run('sudo mount | grep %s | awk \'{ print $3 }\'' %(disksplit[1]), shell='/bin/bash')
                        osdnum=osddet.split('-')[1]
                        if (diskcount == 3 and
                            disksplit[3][0] == 'P') or \
                            (diskcount == 2 and
                                disksplit[2][0] == 'P'):
                            if diskcount == 3:
                                pool_name = disksplit[3]
                            if diskcount == 2:
                                pool_name = disksplit[2]
                            while True:
                                if pool_name == host_hdd_dict[('poolname', '%s' %(pool_index))]:
                                    break
                                pool_index = pool_index + 1
                                if pool_index >= hdd_pool_count:
                                    print 'Cannot find the pool name for disk %s' %(disksplit[1])
                                    error
                        #host_hdd_dict[hostname, host_hdd_dict[hostname,'count']] = disksplit[1] + ':' + osdnum
                        host_hdd_dict['%s-%s' %(hostname, pool_index), host_hdd_dict['%s-%s' %(hostname, pool_index),'count']] = osdnum
                        host_hdd_dict['%s-%s' %(hostname, pool_index), 'count'] += 1
                        host_hdd_dict[('totalcount', '%s' %(pool_index))] += 1

            for disks in self._args.storage_ssd_disk_config:
                disksplit = disks.split(':')
                diskcount = disks.count(':')
                pool_index = 0
                if disksplit[0] == hostname:
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        osddet=run('sudo mount | grep %s | awk \'{ print $3 }\'' %(disksplit[1]), shell='/bin/bash')
                        osdnum=osddet.split('-')[1]
                        if (diskcount == 3 and
                            disksplit[3][0] == 'P') or \
                            (diskcount == 2 and
                                disksplit[2][0] == 'P'):
                            if diskcount == 3:
                                pool_name = disksplit[3]
                            if diskcount == 2:
                                pool_name = disksplit[2]
                            while True:
                                if pool_name == host_ssd_dict[('poolname', '%s' %(pool_index))]:
                                    break
                                pool_index = pool_index + 1
                                if pool_index >= ssd_pool_count:
                                    print 'Cannot find the pool name for disk %s' %(disksplit[1])
                                    error

                        #host_ssd_dict[hostname, host_ssd_dict[hostname,'count']] = disksplit[1] + ':' + osdnum
                        host_ssd_dict['%s-%s' %(hostname, pool_index), host_ssd_dict[hostname,'count']] = osdnum
                        host_ssd_dict['%s-%s' %(hostname, pool_index), 'count'] += 1
                        host_ssd_dict[('totalcount', '%s' %(pool_index))] += 1
        #print host_hdd_dict
        #print host_ssd_dict

        #pool_index = 0
        #print hdd_pool_count
        #while True:
        #    print 'Host Count = %s' %(host_hdd_dict[('hostcount','%s' %(pool_index))])
        #    print host_hdd_dict[('poolname','%s' %(pool_index))]
        #    for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
        #        print hostname
        #        print 'OSD Count = %s' %(host_hdd_dict['%s-%s' %(hostname, pool_index), 'count'])
        #        hsthddcnt=host_hdd_dict['%s-%s' %(hostname, pool_index), 'count']
        #        print 'OSDs - '
        #        while hsthddcnt != 0:
        #            hsthddcnt -= 1
        #            print host_hdd_dict['%s-%s' %(hostname, pool_index), hsthddcnt]
        #    pool_index = pool_index + 1
        #    if pool_index >= hdd_pool_count:
        #        break

        #pool_index = 0
        #print ssd_pool_count
        #while True:
        #    print 'Host Count = %s' %(host_ssd_dict[('hostcount','%s' %(pool_index))])
        #    print host_ssd_dict[('poolname','%s' %(pool_index))]
        #    for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
        #        print hostname
        #        print 'OSD Count = %s' %(host_ssd_dict['%s-%s' %(hostname, pool_index), 'count'])
        #        hstssdcnt=host_ssd_dict['%s-%s' %(hostname, pool_index), 'count']
        #        print 'OSDs - '
        #        while hstssdcnt != 0:
        #            hstssdcnt -= 1
        #            print host_ssd_dict['%s-%s' %(hostname, pool_index), hstssdcnt]
        #    pool_index = pool_index + 1
        #    if pool_index >= ssd_pool_count:
        #        break

        # Configure Crush map
        # Add host entries
        local('sudo cat /tmp/ma-crush-map.txt |grep -v "^# end" > /tmp/ma-crush-map-new.txt')
        # Find the next unique id to be used for the hdd/ssd pool configuration.
        # List all the IDS from the crush map file, which are in the format
        # "id -10". 
        # Capture the 2nd column and do a numeric sort and find the last entry
        # This will give the highest id.
        cur_id = int(local('sudo cat /tmp/ma-crush-map.txt |grep "id " |awk \'{print $2}\' | tr \'-\' \' \'| sort -n | tail -n 1', capture=True))
        cur_id += 1

        #print cur_id
        for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
            pool_index = 0
            while True:
                if host_hdd_dict['%s-%s' %(hostname, pool_index), 'count'] != 0:
                    if hdd_pool_count == 0:
                        local('sudo echo host %s-hdd { >> /tmp/ma-crush-map-new.txt' %(hostname))
                    else:
                        local('sudo echo host %s-hdd-%s { >> /tmp/ma-crush-map-new.txt' %(hostname, host_hdd_dict[('poolname','%s' %(pool_index))]))
                    local('sudo echo "        id -%d" >> /tmp/ma-crush-map-new.txt' %(cur_id))
                    cur_id += 1
                    local('sudo echo "        alg straw" >> /tmp/ma-crush-map-new.txt')
                    local('sudo echo "        hash 0 #rjenkins1" >> /tmp/ma-crush-map-new.txt')
                    hsthddcnt=host_hdd_dict['%s-%s' %(hostname, pool_index), 'count']
                    while hsthddcnt != 0:
                        hsthddcnt -= 1
                        local('sudo echo "        item osd.%s weight 1.000" >> /tmp/ma-crush-map-new.txt' %(host_hdd_dict['%s-%s' %(hostname, pool_index), hsthddcnt]))
                    local('sudo echo "}" >> /tmp/ma-crush-map-new.txt')
                    local('sudo echo "" >> /tmp/ma-crush-map-new.txt')
                pool_index = pool_index + 1
                if pool_index >= hdd_pool_count:
                    break

        for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
            pool_index = 0
            while True:
                if host_ssd_dict['%s-%s' %(hostname, pool_index), 'count'] != 0:
                    if ssd_pool_count == 0:
                        local('sudo echo host %s-ssd { >> /tmp/ma-crush-map-new.txt' %(hostname))
                    else:
                        local('sudo echo host %s-ssd-%s { >> /tmp/ma-crush-map-new.txt' %(hostname, host_ssd_dict[('poolname','%s' %(pool_index))]))
                    local('sudo echo "        id -%d" >> /tmp/ma-crush-map-new.txt' %(cur_id))
                    cur_id += 1
                    local('sudo echo "        alg straw" >> /tmp/ma-crush-map-new.txt')
                    local('sudo echo "        hash 0 #rjenkins1" >> /tmp/ma-crush-map-new.txt')
                    hstssdcnt=host_ssd_dict['%s-%s' %(hostname, pool_index), 'count']
                    while hstssdcnt != 0:
                        hstssdcnt -= 1
                        local('sudo echo "        item osd.%s weight 1.000" >> /tmp/ma-crush-map-new.txt' %(host_ssd_dict['%s-%s' %(hostname, pool_index), hstssdcnt]))
                    local('sudo echo "}" >> /tmp/ma-crush-map-new.txt')
                    local('sudo echo "" >> /tmp/ma-crush-map-new.txt')
                pool_index = pool_index + 1
                if pool_index >= ssd_pool_count:
                    break

        # Add root entries for hdd/ssd
        if self._args.storage_disk_config[0] != 'none':
            pool_index = 0
            while True:
                if hdd_pool_count == 0:
                    local('sudo echo "root hdd {" >> /tmp/ma-crush-map-new.txt')
                else:
                    local('sudo echo "root hdd-%s {" >> /tmp/ma-crush-map-new.txt' %(host_hdd_dict[('poolname','%s' %(pool_index))]))
                local('sudo echo "        id -%d" >> /tmp/ma-crush-map-new.txt' %(cur_id))
                cur_id += 1
                local('sudo echo "        alg straw" >> /tmp/ma-crush-map-new.txt')
                local('sudo echo "        hash 0 #rjenkins1" >> /tmp/ma-crush-map-new.txt')
                for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
                    if host_hdd_dict['%s-%s' %(hostname, pool_index), 'count'] != 0:
                        if hdd_pool_count == 0:
                                local('sudo echo "        item %s-hdd weight %s.000" >> /tmp/ma-crush-map-new.txt' %(hostname, host_hdd_dict['%s-%s' %(hostname, pool_index), 'count']))
                        else:
                                local('sudo echo "        item %s-hdd-%s weight %s.000" >> /tmp/ma-crush-map-new.txt' %(hostname, host_hdd_dict[('poolname','%s' %(pool_index))], host_hdd_dict['%s-%s' %(hostname, pool_index), 'count']))
                local('sudo echo "}" >> /tmp/ma-crush-map-new.txt')
                local('sudo echo "" >> /tmp/ma-crush-map-new.txt')
                pool_index = pool_index + 1
                if pool_index >= hdd_pool_count:
                    break

        if self._args.storage_ssd_disk_config[0] != 'none':
            pool_index = 0
            while True:
                if ssd_pool_count == 0:
                    local('sudo echo "root ssd {" >> /tmp/ma-crush-map-new.txt')
                else:
                    local('sudo echo "root ssd-%s {" >> /tmp/ma-crush-map-new.txt' %(host_ssd_dict[('poolname','%s' %(pool_index))]))
                local('sudo echo "        id -%d" >> /tmp/ma-crush-map-new.txt' %(cur_id))
                cur_id += 1
                local('sudo echo "        alg straw" >> /tmp/ma-crush-map-new.txt')
                local('sudo echo "        hash 0 #rjenkins1" >> /tmp/ma-crush-map-new.txt')
                for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
                    if host_ssd_dict['%s-%s' %(hostname, pool_index), 'count'] != 0:
                        if ssd_pool_count == 0:
                            local('sudo echo "        item %s-ssd weight %s.000" >> /tmp/ma-crush-map-new.txt' %(hostname, host_ssd_dict['%s-%s' %(hostname, pool_index), 'count']))
                        else:
                                local('sudo echo "        item %s-ssd-%s weight %s.000" >> /tmp/ma-crush-map-new.txt' %(hostname, host_ssd_dict[('poolname','%s' %(pool_index))], host_ssd_dict['%s-%s' %(hostname, pool_index), 'count']))
                local('sudo echo "}" >> /tmp/ma-crush-map-new.txt')
                local('sudo echo "" >> /tmp/ma-crush-map-new.txt')
                pool_index = pool_index + 1
                if pool_index >= ssd_pool_count:
                    break

        # Add ruleset for hdd/ssd
        rule_id=int(local('sudo cat /tmp/ma-crush-map.txt |grep "ruleset " |wc -l', capture=True))
        if self._args.storage_disk_config[0] != 'none':
            pool_index = 0
            while True:
                if hdd_pool_count == 0:
                    local('sudo echo "rule hdd {" >> /tmp/ma-crush-map-new.txt')
                else:
                    local('sudo echo "rule hdd-%s {" >> /tmp/ma-crush-map-new.txt' %(host_hdd_dict[('poolname','%s' %(pool_index))]))
                local('sudo echo "        ruleset %d" >> /tmp/ma-crush-map-new.txt' %(rule_id))
                host_hdd_dict[('ruleid', '%s' %(pool_index))] = rule_id
                rule_id += 1
                local('sudo echo "        type replicated" >> /tmp/ma-crush-map-new.txt')
                local('sudo echo "        min_size 0" >> /tmp/ma-crush-map-new.txt')
                local('sudo echo "        max_size 10" >> /tmp/ma-crush-map-new.txt')
                if hdd_pool_count == 0:
                    local('sudo echo "        step take hdd" >> /tmp/ma-crush-map-new.txt')
                else:
                    local('sudo echo "        step take hdd-%s" >> /tmp/ma-crush-map-new.txt' %(host_hdd_dict[('poolname','%s' %(pool_index))]))
                local('sudo echo "        step chooseleaf firstn 0 type host" >> /tmp/ma-crush-map-new.txt')
                local('sudo echo "        step emit" >> /tmp/ma-crush-map-new.txt')
                local('sudo echo "}" >> /tmp/ma-crush-map-new.txt')
                local('sudo echo "" >> /tmp/ma-crush-map-new.txt')
                pool_index = pool_index + 1
                if pool_index >= hdd_pool_count:
                    break

        if self._args.storage_ssd_disk_config[0] != 'none':
            pool_index = 0
            while True:
                if ssd_pool_count == 0:
                    local('sudo echo "rule ssd {" >> /tmp/ma-crush-map-new.txt')
                else:
                    local('sudo echo "rule ssd-%s {" >> /tmp/ma-crush-map-new.txt' %(host_ssd_dict[('poolname','%s' %(pool_index))]))
                local('sudo echo "        ruleset %d" >> /tmp/ma-crush-map-new.txt' %(rule_id))
                host_ssd_dict[('ruleid', '%s' %(pool_index))] = rule_id
                rule_id += 1
                local('sudo echo "        type replicated" >> /tmp/ma-crush-map-new.txt')
                local('sudo echo "        min_size 0" >> /tmp/ma-crush-map-new.txt')
                local('sudo echo "        max_size 10" >> /tmp/ma-crush-map-new.txt')
                if ssd_pool_count == 0:
                    local('sudo echo "        step take ssd" >> /tmp/ma-crush-map-new.txt')
                else:
                    local('sudo echo "        step take ssd-%s" >> /tmp/ma-crush-map-new.txt' %(host_ssd_dict[('poolname','%s' %(pool_index))]))
                local('sudo echo "        step chooseleaf firstn 0 type host" >> /tmp/ma-crush-map-new.txt')
                local('sudo echo "        step emit" >> /tmp/ma-crush-map-new.txt')
                local('sudo echo "}" >> /tmp/ma-crush-map-new.txt')
                local('sudo echo "" >> /tmp/ma-crush-map-new.txt')
                pool_index = pool_index + 1
                if pool_index >= ssd_pool_count:
                    break

        # Apply the  new crush map
        local('sudo crushtool -c /tmp/ma-crush-map-new.txt -o /tmp/ma-newcrush-map')
        local('sudo ceph -k /etc/ceph/ceph.client.admin.keyring osd setcrushmap -i /tmp/ma-newcrush-map')

        # Create HDD/SSD pools
        # Change the crush ruleset of images and volumes to point to HDD
        # Set replica size based on count
        # Set PG/PGPs for HDD/SSD Pool
        if self._args.storage_disk_config[0] != 'none':
            pool_index = 0
            while True:
                if hdd_pool_count == 0:
                    local('sudo rados mkpool volumes_hdd')
                    local('sudo ceph osd pool set volumes_hdd crush_ruleset %d' %(host_hdd_dict[('ruleid', '%s' %(pool_index))]))
                    if host_hdd_dict[('hostcount', '%s' %(pool_index))] <= 1:
                        local('sudo ceph osd pool set volumes_hdd size 1')
                    else:
                        local('sudo ceph osd pool set volumes_hdd size 2')
                    self.set_pg_pgp_count(host_hdd_dict[('totalcount', '%s' %(pool_index))], 'volumes_hdd', host_hdd_dict[('hostcount', '%s' %(pool_index))])
                    ceph_pool_list.append('volumes_hdd')
                else:
                    local('sudo rados mkpool volumes_hdd_%s' %(host_hdd_dict[('poolname','%s' %(pool_index))]))
                    local('sudo ceph osd pool set volumes_hdd_%s crush_ruleset %d' %(host_hdd_dict[('poolname','%s' %(pool_index))], host_hdd_dict[('ruleid', '%s' %(pool_index))]))
                    if host_hdd_dict[('hostcount', '%s' %(pool_index))] <= 1:
                        local('sudo ceph osd pool set volumes_hdd_%s size 1' %(host_hdd_dict[('poolname','%s' %(pool_index))]))
                    else:
                        local('sudo ceph osd pool set volumes_hdd_%s size 2' %(host_hdd_dict[('poolname','%s' %(pool_index))]))
                    self.set_pg_pgp_count(host_hdd_dict[('totalcount', '%s' %(pool_index))], 'volumes_hdd_%s' %(host_hdd_dict[('poolname','%s' %(pool_index))]), host_hdd_dict[('hostcount', '%s' %(pool_index))])
                    ceph_pool_list.append('volumes_hdd_%s' %(host_hdd_dict[('poolname', '%s' %(pool_index))]))
                pool_index = pool_index + 1
                if pool_index >= hdd_pool_count:
                    break

        if self._args.storage_ssd_disk_config[0] != 'none':
            pool_index = 0
            while True:
                if ssd_pool_count == 0:
                    local('sudo rados mkpool volumes_ssd')
                    local('sudo ceph osd pool set volumes_ssd crush_ruleset %d' %(host_ssd_dict[('ruleid', '%s' %(pool_index))]))
                    if host_ssd_dict[('hostcount', '%s' %(pool_index))] <= 1:
                        local('sudo ceph osd pool set volumes_ssd size 1')
                    else:
                        local('sudo ceph osd pool set volumes_ssd size 2')
                    self.set_pg_pgp_count(host_ssd_dict[('totalcount', '%s' %(pool_index))], 'volumes_ssd', host_ssd_dict[('hostcount', '%s' %(pool_index))])
                    ceph_pool_list.append('volumes_ssd')
                else:
                    local('sudo rados mkpool volumes_ssd_%s' %(host_ssd_dict[('poolname','%s' %(pool_index))]))
                    local('sudo ceph osd pool set volumes_ssd_%s crush_ruleset %d' %(host_ssd_dict[('poolname','%s' %(pool_index))], host_ssd_dict[('ruleid', '%s' %(pool_index))]))
                    if host_ssd_dict[('hostcount', '%s' %(pool_index))] <= 1:
                        local('sudo ceph osd pool set volumes_ssd_%s size 1' %(host_ssd_dict[('poolname','%s' %(pool_index))]))
                    else:
                        local('sudo ceph osd pool set volumes_ssd_%s size 2' %(host_ssd_dict[('poolname','%s' %(pool_index))]))
                    self.set_pg_pgp_count(host_ssd_dict[('totalcount', '%s' %(pool_index))], 'volumes_ssd_%s' %(host_ssd_dict[('poolname','%s' %(pool_index))]), host_ssd_dict[('hostcount', '%s' %(pool_index))])
                    ceph_pool_list.append('volumes_ssd_%s' %(host_ssd_dict[('poolname', '%s' %(pool_index))]))
                pool_index = pool_index + 1
                if pool_index >= ssd_pool_count:
                    break

        # Set ruleset for the default volumes/images pool
        pool_index = 0
        local('sudo ceph osd pool set images crush_ruleset %d' %(host_hdd_dict[('ruleid','%s' %(pool_index))]))
        local('sudo ceph osd pool set volumes crush_ruleset %d' %(host_hdd_dict[('ruleid','%s' %(pool_index))]))
        if host_hdd_dict[('hostcount', '%s' %(pool_index))] <= 1:
            local('sudo ceph osd pool set volumes size 1')
            local('sudo ceph osd pool set images size 1')
        else:
            local('sudo ceph osd pool set volumes size 2')
            local('sudo ceph osd pool set images size 2')
        self.set_pg_pgp_count(host_hdd_dict[('totalcount', '%s' %(pool_index))], 'volumes', host_hdd_dict[('hostcount', '%s' %(pool_index))])
        self.set_pg_pgp_count(host_hdd_dict[('totalcount', '%s' %(pool_index))], 'images', host_hdd_dict[('hostcount', '%s' %(pool_index))])

    #end create_hdd_ssd_pool()

    # Add a new node osds to HDD/SSD pool
    # For HDD/SSD pool, the crush map has to be changed to accomodate the
    # rules for the HDD/SSD pools. For this, new ssd, hdd specific hosts
    # have to be added to the map. The ssd, hdd specific maps will then
    # be linked to the root entry for SSD/HDD pool and finally which is linked
    # to a rule entry. The rules will then be applied to the respective pools
    # created using the mkpool command.
    # For populating the map with the host/tier specific entries, A dictionary
    # of host/tier specific entries will be created. This will include the
    # Total tier specific count, tier specific count for a particular host
    # and entries for the tier for a particular host.
    # The host_<tier>_dict will have the tier specific entries and the count
    # for a particular host.
    # The following operation is performed.
    # - Get existing crushmap.
    # - Populate the tier/host specific rules.
    # - Compile/Apply the new crush map.
    # - Apply the ruleset to the tier specific pools.
    def add_to_hdd_ssd_pool(self):
        add_storage_node = self._args.add_storage_node
        local('sudo ceph osd getcrushmap -o /tmp/ma-crush-map')
        local('sudo crushtool -d /tmp/ma-crush-map -o /tmp/ma-crush-map.txt')
        #print self._args
        host_hdd_dict = {}
        host_ssd_dict = {}
        pool_count = 0
        while True:
            host_hdd_dict[('totalcount', '%s' %(pool_count))] = 0
            host_ssd_dict[('totalcount', '%s' %(pool_count))] = 0
            host_hdd_dict[('ruleid', '%s' %(pool_count))] = 0
            host_ssd_dict[('ruleid', '%s' %(pool_count))] = 0
            host_hdd_dict[('hostcount', '%s' %(pool_count))] = 0
            host_ssd_dict[('hostcount', '%s' %(pool_count))] = 0
            host_hdd_dict[('poolname', '%s' %(pool_count))] = ''
            host_ssd_dict[('poolname', '%s' %(pool_count))] = ''
            if pool_count > MAX_POOL_COUNT:
                break
            pool_count = pool_count + 1
        hdd_pool_count = 0
        ssd_pool_count = 0
        # Build the host/tier specific dictionary
        for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
            host_hdd_dict[hostname, 'count'] = 0
            host_ssd_dict[hostname, 'count'] = 0
            pool_count = 0
            while True:
                host_hdd_dict[('hostcountadded', '%s' %(pool_count))] = 0
                host_ssd_dict[('hostcountadded', '%s' %(pool_count))] = 0
                if pool_count > MAX_POOL_COUNT:
                    break
                pool_count = pool_count + 1
            for disks in self._args.storage_disk_config:
                diskcount = disks.count(':')
                disksplit = disks.split(':')
                pool_index = 0
                if disksplit[0] == hostname:
                    if (diskcount == 3 and
                        disksplit[3][0] == 'P') or \
                        (diskcount == 2 and
                            disksplit[2][0] == 'P'):
                        if diskcount == 3:
                            pool_name = disksplit[3]
                        if diskcount == 2:
                            pool_name = disksplit[2]
                        if hdd_pool_count != 0:
                            while True:
                                if pool_name == host_hdd_dict[('poolname', '%s' %(pool_index))]:
                                    break
                                pool_index = pool_index + 1
                                if pool_index == hdd_pool_count:
                                    hdd_pool_count = hdd_pool_count + 1
                                    break
                        else:
                            pool_index = hdd_pool_count
                            hdd_pool_count = hdd_pool_count + 1
                        host_hdd_dict[('poolname', '%s' %(pool_index))] = pool_name
                    if host_hdd_dict[('hostcountadded', '%s' %(pool_index))] == 0:
                        host_hdd_dict[('hostcount', '%s' %(pool_index))] += 1
                        host_hdd_dict[('hostcountadded', '%s' %(pool_index))] = 1

            for disks in self._args.storage_ssd_disk_config:
                diskcount = disks.count(':')
                disksplit = disks.split(':')
                pool_index = 0
                if disksplit[0] == hostname:
                    if (diskcount == 3 and
                        disksplit[3][0] == 'P') or \
                        (diskcount == 2 and
                            disksplit[2][0] == 'P'):
                        if diskcount == 3:
                            pool_name = disksplit[3]
                        if diskcount == 2:
                            pool_name = disksplit[2]
                        if ssd_pool_count != 0:
                            while True:
                                if pool_name == host_ssd_dict[('poolname', '%s' %(pool_index))]:
                                    break
                                pool_index = pool_index + 1
                                if pool_index == ssd_pool_count:
                                    ssd_pool_count = ssd_pool_count + 1
                                    break
                        else:
                            pool_index = ssd_pool_count
                            ssd_pool_count = ssd_pool_count + 1
                        host_ssd_dict[('poolname', '%s' %(pool_index))] = pool_name
                    if host_ssd_dict[('hostcountadded', '%s' %(pool_index))] == 0:
                        host_ssd_dict[('hostcount', '%s' %(pool_index))] += 1
                        host_ssd_dict[('hostcountadded', '%s' %(pool_index))] = 1

        for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
            pool_index = 0
            while True:
                host_hdd_dict['%s-%s' %(hostname, pool_index), 'count'] = 0
                pool_index = pool_index + 1
                if pool_index >= hdd_pool_count:
                    break
            pool_index = 0
            while True:
                host_ssd_dict['%s-%s' %(hostname, pool_index), 'count'] = 0
                pool_index = pool_index + 1
                if pool_index >= ssd_pool_count:
                    break

        for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
            for disks in self._args.storage_disk_config:
                disksplit = disks.split(':')
                diskcount = disks.count(':')
                pool_index = 0
                if disksplit[0] == hostname:
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        osddet=run('sudo mount | grep %s | awk \'{ print $3 }\'' %(disksplit[1]), shell='/bin/bash')
                        osdnum=osddet.split('-')[1]
                        if (diskcount == 3 and
                            disksplit[3][0] == 'P') or \
                            (diskcount == 2 and
                                disksplit[2][0] == 'P'):
                            if diskcount == 3:
                                pool_name = disksplit[3]
                            if diskcount == 2:
                                pool_name = disksplit[2]
                            while True:
                                if pool_name == host_hdd_dict[('poolname', '%s' %(pool_index))]:
                                    break
                                pool_index = pool_index + 1
                                if pool_index >= hdd_pool_count:
                                    print 'Cannot find the pool name for disk %s' %(disksplit[1])
                                    error
                        #host_hdd_dict[hostname, host_hdd_dict[hostname,'count']] = disksplit[1] + ':' + osdnum
                        host_hdd_dict['%s-%s' %(hostname, pool_index), host_hdd_dict['%s-%s' %(hostname, pool_index),'count']] = osdnum
                        host_hdd_dict['%s-%s' %(hostname, pool_index), 'count'] += 1
                        host_hdd_dict[('totalcount', '%s' %(pool_index))] += 1

            for disks in self._args.storage_ssd_disk_config:
                disksplit = disks.split(':')
                diskcount = disks.count(':')
                pool_index = 0
                if disksplit[0] == hostname:
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        osddet=run('sudo mount | grep %s | awk \'{ print $3 }\'' %(disksplit[1]), shell='/bin/bash')
                        osdnum=osddet.split('-')[1]
                        if (diskcount == 3 and
                            disksplit[3][0] == 'P') or \
                            (diskcount == 2 and
                                disksplit[2][0] == 'P'):
                            if diskcount == 3:
                                pool_name = disksplit[3]
                            if diskcount == 2:
                                pool_name = disksplit[2]
                            while True:
                                if pool_name == host_ssd_dict[('poolname', '%s' %(pool_index))]:
                                    break
                                pool_index = pool_index + 1
                                if pool_index >= ssd_pool_count:
                                    print 'Cannot find the pool name for disk %s' %(disksplit[1])
                                    error

                        #host_ssd_dict[hostname, host_ssd_dict[hostname,'count']] = disksplit[1] + ':' + osdnum
                        host_ssd_dict['%s-%s' %(hostname, pool_index), host_ssd_dict[hostname,'count']] = osdnum
                        host_ssd_dict['%s-%s' %(hostname, pool_index), 'count'] += 1
                        host_ssd_dict[('totalcount', '%s' %(pool_index))] += 1

        #print host_hdd_dict
        #print host_ssd_dict

        local('sudo cat /tmp/ma-crush-map.txt |grep -v "^# end" > /tmp/ma-crush-map-new.txt')
        # Find the next unique id to be used for the hdd/ssd pool configuration.
        # List all the IDS from the crush map file, which are in the format
        # "id -10". 
        # Capture the 2nd column and do a numeric sort and find the last entry
        # This will give the highest id.
        cur_id = int(local('sudo cat /tmp/ma-crush-map.txt |grep "id " |awk \'{print $2}\' | tr \'-\' \' \'| sort -n | tail -n 1', capture=True))
        cur_id += 1

        root_line_str=local('cat /tmp/ma-crush-map-new.txt |grep -n \"root hdd\"', capture=True)
        root_line_num=int(root_line_str.split(":")[0])
        root_line_num-=1
        local('cat /tmp/ma-crush-map-new.txt | head -n %d > /tmp/ma-crush-map-tmp.txt' %(root_line_num))
        root_line_num+=1

        #print cur_id
        # Populate the crush map with the new host entries
        pool_index = 0
        while True:
            if host_hdd_dict['%s-%s' %(add_storage_node, pool_index), 'count'] != 0:
                if hdd_pool_count == 0:
                    local('sudo echo host %s-hdd { >> /tmp/ma-crush-map-tmp.txt' %(add_storage_node))
                else:
                    local('sudo echo host %s-hdd-%s { >> /tmp/ma-crush-map-tmp.txt' %(add_storage_node, host_hdd_dict[('poolname','%s' %(pool_index))]))
                local('sudo echo "        id -%d" >> /tmp/ma-crush-map-tmp.txt' %(cur_id))
                cur_id += 1
                local('sudo echo "        alg straw" >> /tmp/ma-crush-map-tmp.txt')
                local('sudo echo "        hash 0 #rjenkins1" >> /tmp/ma-crush-map-tmp.txt')
                hsthddcnt=host_hdd_dict['%s-%s' %(add_storage_node, pool_index), 'count']
                while hsthddcnt != 0:
                    hsthddcnt -= 1
                    local('sudo echo "        item osd.%s weight 1.000" >> /tmp/ma-crush-map-tmp.txt' %(host_hdd_dict['%s-%s' %(add_storage_node, pool_index), hsthddcnt]))
                local('sudo echo "}" >> /tmp/ma-crush-map-tmp.txt')
                local('sudo echo "" >> /tmp/ma-crush-map-tmp.txt')
            pool_index = pool_index + 1
            if pool_index >= hdd_pool_count:
                break

        pool_index = 0
        while True:
            if host_ssd_dict['%s-%s' %(add_storage_node, pool_index), 'count'] != 0:
                if ssd_pool_count == 0:
                    local('sudo echo host %s-ssd { >> /tmp/ma-crush-map-tmp.txt' %(add_storage_node))
                else:
                    local('sudo echo host %s-ssd-%s { >> /tmp/ma-crush-map-tmp.txt' %(add_storage_node, host_ssd_dict[('poolname','%s' %(pool_index))]))
                local('sudo echo "        id -%d" >> /tmp/ma-crush-map-tmp.txt' %(cur_id))
                cur_id += 1
                local('sudo echo "        alg straw" >> /tmp/ma-crush-map-tmp.txt')
                local('sudo echo "        hash 0 #rjenkins1" >> /tmp/ma-crush-map-tmp.txt')
                hstssdcnt=host_ssd_dict['%s-%s' %(add_storage_node, pool_index), 'count']
                while hstssdcnt != 0:
                    hstssdcnt -= 1
                    local('sudo echo "        item osd.%s weight 1.000" >> /tmp/ma-crush-map-tmp.txt' %(host_ssd_dict['%s-%s' %(add_storage_node, pool_index), hstssdcnt]))
                local('sudo echo "}" >> /tmp/ma-crush-map-tmp.txt')
                local('sudo echo "" >> /tmp/ma-crush-map-tmp.txt')
            pool_index = pool_index + 1
            if pool_index >= ssd_pool_count:
                break

        local('cat /tmp/ma-crush-map-new.txt | tail -n +%d >> /tmp/ma-crush-map-tmp.txt' %(root_line_num))
        local('cp /tmp/ma-crush-map-tmp.txt /tmp/ma-crush-map-new.txt')

        # Add the new host to the existing root entries
        pool_index = 0
        while True:
            if host_hdd_dict['%s-%s' %(add_storage_node, pool_index), 'count'] != 0:
                add_line_num = 0
                if hdd_pool_count == 0:
                    # Find the start of the "root hdd". search through each line
                    # after and find the end '}'. Once the end is found, we can
                    # cat till the end to a temp file and insert the new host
                    # entry and cat the rest of the file.
                    # This is to insert a host entry to the existing "root hdd"
                    # entry as below.
                    # root hdd {
                    # ...
                    #     item host1 weight 1.00
                    #     item host2 weight 1.00
                    #     item host3 weight 1.00
                    # }
                    # The code will eventually insert host4 after host3.
                    add_line_str=local('cat /tmp/ma-crush-map-new.txt |grep -n "root hdd" |head -n 1', shell='/bin/bash', capture=True)
                    add_line_end = int(add_line_str.split(':')[0])
                    while True:
                        item_line = local('cat /tmp/ma-crush-map-new.txt | tail -n +%d | head -n 1' %(add_line_end), capture=True)
                        if item_line.find('}') != -1:
                            break
                        add_line_end += 1
                    add_line_num = add_line_end - 1
                else:
                    add_line_str=local('cat /tmp/ma-crush-map-new.txt |grep -n item |grep \"\-hdd-%s\" |tail -n 1' %(host_hdd_dict[('poolname','%s' %(pool_index))]), shell='/bin/bash', capture=True)
                    add_line_num=int(add_line_str.split(":")[0])
                local('cat /tmp/ma-crush-map-new.txt | head -n %d > /tmp/ma-crush-map-tmp.txt' %(add_line_num))
                if hdd_pool_count == 0:
                    local('sudo echo "        item %s-hdd weight %s.000" >> /tmp/ma-crush-map-tmp.txt' %(add_storage_node, host_hdd_dict['%s-%s' %(add_storage_node, pool_index), 'count']))
                else:
                    local('sudo echo "        item %s-hdd-%s weight %s.000" >> /tmp/ma-crush-map-tmp.txt' %(add_storage_node, host_hdd_dict[('poolname','%s' %(pool_index))], host_hdd_dict['%s-%s' %(add_storage_node, pool_index), 'count']))
                add_line_num+=1
                local('cat /tmp/ma-crush-map-new.txt | tail -n +%d >> /tmp/ma-crush-map-tmp.txt' %(add_line_num))
                local('cp /tmp/ma-crush-map-tmp.txt /tmp/ma-crush-map-new.txt')
            pool_index = pool_index + 1
            if pool_index >= hdd_pool_count:
                break

        pool_index = 0
        while True:
            if host_ssd_dict['%s-%s' %(add_storage_node, pool_index), 'count'] != 0:
                add_line_num = 0
                if ssd_pool_count == 0:
                    # Find the start of the "root ssd". search through each line
                    # after and find the end '}'. Once the end is found, we can
                    # cat till the end to a temp file and insert the new host
                    # entry and cat the rest of the file.
                    # This is to insert a host entry to the existing "root ssd"
                    # entry as below.
                    # root ssd {
                    # ...
                    #     item host1 weight 1.00
                    #     item host2 weight 1.00
                    #     item host3 weight 1.00
                    # }
                    # The code will eventually insert host4 after host3.
                    add_line_str=local('cat /tmp/ma-crush-map-new.txt |grep -n "root ssd" |head -n 1', shell='/bin/bash', capture=True)
                    add_line_end = int(add_line_str.split(':')[0])
                    while True:
                        item_line = local('cat /tmp/ma-crush-map-new.txt | tail -n +%d | head -n 1' %(add_line_end), capture=True)
                        if item_line.find('}') != -1:
                            break
                        add_line_end += 1
                    add_line_num = add_line_end - 1
                else:
                    add_line_str=local('cat /tmp/ma-crush-map-new.txt |grep -n item |grep \"\-ssd-%s\" |tail -n 1' %(host_ssd_dict[('poolname','%s' %(pool_index))]), shell='/bin/bash', capture=True)
                    add_line_num=int(add_line_str.split(":")[0])
                local('cat /tmp/ma-crush-map-new.txt | head -n %d > /tmp/ma-crush-map-tmp.txt' %(add_line_num))
                if ssd_pool_count == 0:
                    local('sudo echo "        item %s-ssd weight %s.000" >> /tmp/ma-crush-map-tmp.txt' %(add_storage_node, host_ssd_dict['%s-%s' %(add_storage_node, pool_index), 'count']))
                else:
                    local('sudo echo "        item %s-ssd-%s weight %s.000" >> /tmp/ma-crush-map-tmp.txt' %(add_storage_node, host_ssd_dict[('poolname','%s' %(pool_index))], host_ssd_dict['%s-%s' %(add_storage_node, pool_index), 'count']))
                add_line_num+=1
                local('cat /tmp/ma-crush-map-new.txt | tail -n +%d >> /tmp/ma-crush-map-tmp.txt' %(add_line_num))
                local('cp /tmp/ma-crush-map-tmp.txt /tmp/ma-crush-map-new.txt')
            pool_index = pool_index + 1
            if pool_index >= ssd_pool_count:
                break

        # Load the new crush map
        local('sudo crushtool -c /tmp/ma-crush-map-new.txt -o /tmp/ma-newcrush-map')
        local('sudo ceph -k /etc/ceph/ceph.client.admin.keyring osd setcrushmap -i /tmp/ma-newcrush-map')

        if self._args.storage_disk_config[0] != 'none':
            pool_index = 0
            while True:
                if hdd_pool_count == 0:
                    if host_hdd_dict[('hostcount', '%s' %(pool_index))] <= 1:
                        local('sudo ceph osd pool set volumes_hdd size 1')
                    else:
                        rep_size=local('sudo ceph osd pool get volumes_hdd size | awk \'{print $2}\'', shell='/bin/bash', capture=True)
                        if rep_size != '2':
                            local('sudo ceph osd pool set volumes_hdd size 2')
                    self.set_pg_pgp_count(host_hdd_dict[('totalcount', '%s' %(pool_index))], 'volumes_hdd', host_hdd_dict[('hostcount', '%s' %(pool_index))])
                else:
                    if host_hdd_dict[('hostcount', '%s' %(pool_index))] <= 1:
                        local('sudo ceph osd pool set volumes_hdd_%s size 1' %(host_hdd_dict[('poolname','%s' %(pool_index))]))
                    else:
                        rep_size=local('sudo ceph osd pool get volumes_hdd_%s size | awk \'{print $2}\'' %(host_hdd_dict[('poolname','%s' %(pool_index))]), shell='/bin/bash', capture=True)
                        if rep_size != '2':
                            local('sudo ceph osd pool set volumes_hdd_%s size 2' %(host_hdd_dict[('poolname','%s' %(pool_index))]))
                    self.set_pg_pgp_count(host_hdd_dict[('totalcount', '%s' %(pool_index))], 'volumes_hdd_%s' %(host_hdd_dict[('poolname','%s' %(pool_index))]), host_hdd_dict[('hostcount', '%s' %(pool_index))])
                pool_index = pool_index + 1
                if pool_index >= hdd_pool_count:
                    break

        if self._args.storage_ssd_disk_config[0] != 'none':
            pool_index = 0
            while True:
                if ssd_pool_count == 0:
                    if host_ssd_dict[('hostcount', '%s' %(pool_index))] <= 1:
                        local('sudo ceph osd pool set volumes_ssd size 1')
                    else:
                        rep_size=local('sudo ceph osd pool get volumes_ssd size | awk \'{print $2}\'', shell='/bin/bash', capture=True)
                        if rep_size != '2':
                            local('sudo ceph osd pool set volumes_ssd size 2')
                    self.set_pg_pgp_count(host_ssd_dict[('totalcount', '%s' %(pool_index))], 'volumes_ssd', host_ssd_dict[('hostcount', '%s' %(pool_index))])
                else:
                    if host_ssd_dict[('hostcount', '%s' %(pool_index))] <= 1:
                        local('sudo ceph osd pool set volumes_ssd_%s size 1' %(host_ssd_dict[('poolname','%s' %(pool_index))]))
                    else:
                        rep_size=local('sudo ceph osd pool get volumes_ssd_%s size | awk \'{print $2}\'' %(host_ssd_dict[('poolname','%s' %(pool_index))]), shell='/bin/bash', capture=True)
                        if rep_size != '2':
                            local('sudo ceph osd pool set volumes_ssd_%s size 2' %(host_ssd_dict[('poolname','%s' %(pool_index))]))
                    self.set_pg_pgp_count(host_ssd_dict[('totalcount', '%s' %(pool_index))], 'volumes_ssd_%s' %(host_ssd_dict[('poolname','%s' %(pool_index))]), host_ssd_dict[('hostcount', '%s' %(pool_index))])
                pool_index = pool_index + 1
                if pool_index >= ssd_pool_count:
                    break

        # Set ruleset for the default volumes/images pool
        pool_index = 0
        self.set_pg_pgp_count(host_hdd_dict[('totalcount', '%s' %(pool_index))], 'volumes', host_hdd_dict[('hostcount', '%s' %(pool_index))])
        self.set_pg_pgp_count(host_hdd_dict[('totalcount', '%s' %(pool_index))], 'images', host_hdd_dict[('hostcount', '%s' %(pool_index))])
    #end add_to_hdd_ssd_pool()

    # Crush map modification for Chassis support
    # This ensures that the replica will not happen between nodes
    # in a single chassis.
    # The Chassis id given in the testbed.py for each host will
    # be used to create virtual groups. Replica will not happen between hosts
    # of the same chassis id.
    # For eg., consider a Quanta system that has 4 nodes in a single chassis.
    # All the nodes in a single chassis should be given the same chassis id.
    # Based on the chassis id, a hdd-chassis-<chassis-id> entry will be
    # created. The hdd-chassis-<x> will have the list hosts that are in the
    # Chassis.
    # The root entry for default/hdd(incase of hdd/ssd pools will be
    # modified to use hdd-chassis-<x>
    # instead of using the host directly.
    # The leaf in the rule will be set to use chassis instead of host.
    # Original crush map will be as below for a no hdd/ssd pool.
    # host cmbu-ceph-1 {
    # ...
    # }
    # host cmbu-ceph-2 {
    # ...
    # }
    # host cmbu-ceph-3 {
    # ...
    # }
    # host cmbu-ceph-4 {
    # ...
    # }
    # root default {
    # ...
    # item cmbu-ceph-1 weight 1.090
    # item cmbu-ceph-2 weight 1.090
    # item cmbu-ceph-3 weight 1.090
    # item cmbu-ceph-4 weight 1.090
    # }
    # rule replicated_ruleset {
    # ...
    # step chooseleaf firstn 0 type host
    # step emit
    # }
    # Consider each chassis has 2 nodes. Host1 and Host2 are in same chassis.
    # Host3 and Host4 are in a different chassis. Replica should not happen
    # between Host1 and Host2, similarly it should not happen between Host3
    # and Host4.
    # So the above crushmap will be modified to the following
    # host cmbu-ceph-1 {
    # ...
    # }
    # host cmbu-ceph-2 {
    # ...
    # }
    # host cmbu-ceph-3 {
    # ...
    # }
    # host cmbu-ceph-4 {
    # ...
    # }
    # chassis hdd-chassis-0 {
    # ...
    # item cmbu-ceph-1 weight 1.090
    # item cmbu-ceph-2 weight 1.090
    # }
    # chassis hdd-chassis-1 {
    # ...
    # item cmbu-ceph-3 weight 1.090
    # item cmbu-ceph-4 weight 1.090
    # }
    # root default {
    # ...
    # item hdd-chassis-0 weight 2.180
    # item hdd-chassis-1 weight 2.180
    # }
    # rule replicated_ruleset {
    # ...
    # step chooseleaf firstn 0 type chassis
    # step emit
    # }
    #
    # The above change will ensure that the chassis is the leaf node, which
    # means that the replica created for an object in cmbu-ceph-1 will not
    # be created under cmb-ceph-2 as they belong to the same chassis. Instead
    # it will be put under a node in hdd-chassis-1
    # This code is Idempotent.
    def do_chassis_config(self):
        if self._args.storage_chassis_config[0] == 'none':
            return
        # Get the decoded crush map in txt format
        local('sudo ceph osd getcrushmap -o %s' %(CS_CRUSH_MAP))
        local('sudo crushtool -d %s -o %s' %(CS_CRUSH_MAP, CS_CRUSH_MAP_TXT))

        # If multipool is enabled, we cannot configure chassis
        multipool_enabled = local('sudo cat %s | grep hdd-Pool|wc -l'
                                %(CS_CRUSH_MAP_TXT), capture=True)
        if multipool_enabled != '0':
            print 'Cannot have both multipool and Chassis config'
            return
        multipool_enabled = local('sudo cat %s | grep ssd-Pool|wc -l'
                                %(CS_CRUSH_MAP_TXT), capture=True)
        if multipool_enabled != '0':
            print 'Cannot have both multipool and Chassis config'
            return

        # Populate the chassis list with chassis id, indexed by hostname.
        host_chassis_info = {}
        chassis_list = {}
        chassis_count = 0
        for hostname, entries, entry_token in zip(self._args.storage_hostnames,
                    self._args.storage_hosts, self._args.storage_host_tokens):
            # The chassis_config is the list of host:chassis.
            # for eg: --storage-chassis-config host1:0 host2:0 host3:1 host4:1
            # The loop goes over the entries and finds unique chassis id and
            # creates the list 'chassis_list' indexed with an incrementing
            # starting from 0.
            for chassis in self._args.storage_chassis_config:
                chassissplit = chassis.split(':')
                if chassissplit[0] == hostname:
                    host_chassis_info[hostname] = chassissplit[1]
                    #print 'Chassis - %s %s' %(hostname, chassissplit[1])
                    if chassis_count == 0:
                        chassis_list['%d' %(chassis_count)] = chassissplit[1]
                        chassis_count = chassis_count + 1
                    else:
                        tmp_chassis_count = 0
                        while tmp_chassis_count < chassis_count:
                            if chassis_list['%d' %(tmp_chassis_count)] == \
                                            chassissplit[1]:
                                break
                            tmp_chassis_count = tmp_chassis_count + 1
                        if tmp_chassis_count >= chassis_count:
                            chassis_list['%d' %(chassis_count)] = \
                                                            chassissplit[1]
                            chassis_count = chassis_count + 1

        # Find the existing highest unique id. Remove the number of Chassis
        # IDs as we will be recreating the chassis information.
        # num_chassis_config = int(local('sudo cat %s |grep ^chassis | wc -l '
        #                                 %(CS_CRUSH_MAP_TXT), capture=True))
        # if num_chassis_config == 0:
        #    cur_id = int(local('sudo cat %s |grep "id " |wc -l'
        #                         %(CS_CRUSH_MAP_TXT),
        #                                 capture=True))
        # Find the next unique id to be used for the chassis configuration.
        # List all the IDS from the crush map file, which are in the format
        # "id -10". 
        # Capture the 2nd column and do a numeric sort and find the last entry
        # This will give the highest id.
        cur_id = int(local('sudo cat %s |grep "id " |awk \'{print $2}\' | \
                        tr \'-\' \' \'| sort -n | tail -n 1'
                        %(CS_CRUSH_MAP_TXT), capture=True))
        cur_id += 1
        # else:
        #     chs_line_str=local('cat  %s|grep -n "root chdd" | head -n 1'
        #                         %(CS_CRUSH_MAP_TXT), shell='/bin/bash',
        #                         capture=True)
        #     chs_line_start = int(chs_line_str.split(':')[0])
        #     while True:
        #         item_line = local('cat %s | tail -n +%d | head -n 1'
        #                             %(CS_CRUSH_MAP_TXT, chs_line_start),
        #                             capture=True)
        #         if item_line.find('id ') != -1:
        #             break
        #         chs_line_start += 1
        #     new_id = item_line.split(' ')[1]
        #     new_id = new_id.replace('-', '')
        #     new_id = new_id.replace('#', '')
        #     cur_id = int(new_id.replace('\t', ''))

        # Find if we have HDD/SSD pools configured.
        # If SSD pool is enabled, then it means that we have two pools
        # otherwise there is only one pool, which is the 'default' pool.
        ssd_pool_enabled = local('sudo cat %s | grep "root ssd"|wc -l'
                                %(CS_CRUSH_MAP_TXT), capture=True)

        root_entries=[]
        pool_enabled = 0
        if ssd_pool_enabled != '0':
            pool_enabled = 1
            root_entries.append('hdd')
            root_entries.append('ssd')
        else:
            root_entries.append('default')

        # The "root default", "root hdd" and the "root ssd" are the origin root
        # entries that has to be preserved, so that the hdd/ssd pool code or
        # Ceph's osd add code will use them. Also the chassis code will look at
        # the values in these entries and use them for the chassis
        # configuration.

        # Find Root default entry start and end.
        # This will be maintained across modifications
        def_line_str=local('cat  %s|grep -n ^root | grep -w default | tail -n 1'
                                %(CS_CRUSH_MAP_TXT), shell='/bin/bash',
                                capture=True)
        def_line_start = int(def_line_str.split(':')[0])
        def_line_end = def_line_start
        while True:
            item_line = local('cat %s | tail -n +%d | head -n 1'
                                %(CS_CRUSH_MAP_TXT, def_line_end),
                                capture=True)
            if item_line.find('}') != -1:
                break
            def_line_end += 1

        # Find the "root hdd" entry start and end.
        # This will be maintained across modifications
        rhdd_line_str=local('cat  %s|grep -n ^root | grep -w hdd | tail -n 1'
                                %(CS_CRUSH_MAP_TXT), shell='/bin/bash',
                                capture=True)
        rhdd_line_start = 0
        rhdd_line_end = 0
        if rhdd_line_str != '':
            rhdd_line_start = int(rhdd_line_str.split(':')[0])
            rhdd_line_end = rhdd_line_start
            while True:
                item_line = local('cat %s | tail -n +%d | head -n 1'
                                    %(CS_CRUSH_MAP_TXT, rhdd_line_end),
                                    capture=True)
                if item_line.find('}') != -1:
                    break
                rhdd_line_end += 1

        # Find the "root ssd" entry start and end.
        # This will be maintained across modifications
        rssd_line_str=local('cat  %s|grep -n ^root | grep -w ssd | tail -n 1'
                                %(CS_CRUSH_MAP_TXT), shell='/bin/bash',
                                capture=True)
        rssd_line_start = 0
        rssd_line_end = 0
        if rssd_line_str != '':
            rssd_line_start = int(rssd_line_str.split(':')[0])
            rssd_line_end = rssd_line_start
            while True:
                item_line = local('cat %s | tail -n +%d | head -n 1'
                                    %(CS_CRUSH_MAP_TXT, rssd_line_end),
                                    capture=True)
                if item_line.find('}') != -1:
                    break
                rssd_line_end += 1

        # Find if there are any host configurations after the "root default"
        # These are the hosts for the hdd/ssd pool and has to be maintained
        # across modifications
        # The following code greps for the 'host' entry after the "root default"
        # entry and finds the line number which is storaged in host_line_start.
        # It then finds the last 'host' entry and find the end of the entry by
        # searching for the '}'. These host entries if present, should have been
        # added as part of the HDD/SSD pool. These entries have to be preserved
        # without any modifications. By finding the start and end, the whole
        # section will be added to the modified crush map file.
        host_line_str = local('cat  %s | tail -n +%d | grep -n ^host |head -n 1'
                                %(CS_CRUSH_MAP_TXT, def_line_start),
                                shell='/bin/bash', capture=True)
        host_line_start = 0
        host_line_end = 0
        if host_line_str != '':
            host_line_start = def_line_start + \
                                int(host_line_str.split(':')[0]) - 1
            host_line_end_str = local('cat  %s | tail -n +%d | grep -n ^host | \
                                tail -n 1'
                                %(CS_CRUSH_MAP_TXT, def_line_start),
                                shell='/bin/bash', capture=True)
            host_line_end =  def_line_start + \
                                int(host_line_end_str.split(':')[0])
            while True:
                item_line = local('cat %s | tail -n +%d | head -n 1'
                                    %(CS_CRUSH_MAP_TXT, host_line_end),
                                    capture=True)
                if item_line.find('}') != -1:
                    break
                host_line_end += 1

        # Check if there is already a chassis configuration
        # If present ignore as we'll create again.
        skip_line_str = local('cat  %s|grep -n ^chassis |head -n 1'
                                %(CS_CRUSH_MAP_TXT), shell='/bin/bash',
                                capture=True)
        if skip_line_str != '':
            skip_line_num = int(skip_line_str.split(':')[0])
            if skip_line_num > def_line_start:
                skip_line_num = def_line_start
        else:
            skip_line_num = def_line_start

        # Start populating the modified Crush map
        # First populate from beginning till the "root default"
        local('cat %s | head -n %d > %s' %(CS_CRUSH_MAP_TXT,
                        (skip_line_num -1), CS_CRUSH_MAP_MOD_TXT))
        # Populate "root default"
        local('cat %s | tail -n +%d | head -n %d >> %s' %(CS_CRUSH_MAP_TXT,
                        def_line_start, (def_line_end - def_line_start + 1),
                        CS_CRUSH_MAP_MOD_TXT))
        # Populate host entries for hdd/ssd
        if host_line_start != 0:
            local('cat %s | tail -n +%d | head -n %d >> %s' %(CS_CRUSH_MAP_TXT,
                        host_line_start, (host_line_end - host_line_start + 1),
                        CS_CRUSH_MAP_MOD_TXT))
        # Populate "root hdd"
        if rhdd_line_start != 0:
            if rhdd_line_start > host_line_end:
                local('cat %s | tail -n +%d | head -n %d >> %s'
                            %(CS_CRUSH_MAP_TXT, rhdd_line_start,
                            (rhdd_line_end - rhdd_line_start + 1),
                            CS_CRUSH_MAP_MOD_TXT))
        # Populate "root ssd"
        if rssd_line_start != 0:
            if rssd_line_start > host_line_end:
                local('cat %s | tail -n +%d | head -n %d >> %s'
                            %(CS_CRUSH_MAP_TXT, rssd_line_start,
                            (rssd_line_end - rssd_line_start + 1),
                            CS_CRUSH_MAP_MOD_TXT))

        # Create new root entries for the chassis.
        # use prefix of 'c' for the chassis entries
        # The 'default' will be added as 'cdefault'
        # The 'hdd' will be added as 'chdd'
        # The 'ssd' will be added as 'cssd'
        for entries in root_entries:
            tmp_chassis_count = 0

            local('echo "root c%s {" > %s' %(entries,
                            CS_CRUSH_MAP_MOD_TMP_TXT))
            local('echo "   id -%d      #do not change unnecessarily" \
                            >> %s' %(cur_id, CS_CRUSH_MAP_MOD_TMP_TXT))
            cur_id += 1
            local('echo "   alg straw" >> %s' %(CS_CRUSH_MAP_MOD_TMP_TXT))
            local('echo "   hash 0 #rjenkins1" >> %s'
                            %(CS_CRUSH_MAP_MOD_TMP_TXT))
            while tmp_chassis_count < chassis_count:
                total_weight = float('0')
                local('echo "chassis chassis-%s-%s {" >> %s' %(entries,
                            tmp_chassis_count, CS_CRUSH_MAP_MOD_TXT))
                local('echo "   id -%d      #do not change unnecessarily" \
                            >> %s' %(cur_id, CS_CRUSH_MAP_MOD_TXT))
                cur_id += 1
                local('echo "   alg straw" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
                entry_str=local('cat  %s|grep -n ^root |grep -w %s |tail -n 1'
                                %(CS_CRUSH_MAP_TXT, entries), shell='/bin/bash',
                                capture=True)
                entry_line_num = int(entry_str.split(':')[0])
                while True:
                    item_line=local('cat %s | tail -n +%d | head -n 1'
                                    %(CS_CRUSH_MAP_TXT, entry_line_num),
                                    capture=True)
                    if item_line.find('}') != -1:
                        break
                    if item_line.find('item') != -1:
                        unmod_line = item_line
                        item_line.lstrip()
                        tmp_host_name = item_line.split(' ')[1]
                        tmp_host_name = tmp_host_name.replace('-hdd', '')
                        tmp_host_name = tmp_host_name.replace('-ssd', '')
                        #print tmp_host_name
                        #if tmp_host_name.find('-hdd') != -1 || \
                        #        tmp_host_name.find('-ssd') != -1:
                        if host_chassis_info[tmp_host_name] == \
                                    chassis_list['%d' %(tmp_chassis_count)]:
                            local('echo "   %s" >> %s' %(unmod_line,
                                    CS_CRUSH_MAP_MOD_TXT))
                            total_weight += float(item_line.split(' ')[3])
                    entry_line_num += 1
                local('echo "}" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
                local('echo "   item chassis-%s-%s weight %0.3f" >> %s'
                                %(entries, tmp_chassis_count, total_weight,
                                    CS_CRUSH_MAP_MOD_TMP_TXT))
                tmp_chassis_count += 1
            local('echo "}" >> %s' %(CS_CRUSH_MAP_MOD_TMP_TXT))
            local('cat %s >> %s' %(CS_CRUSH_MAP_MOD_TMP_TXT,
                                    CS_CRUSH_MAP_MOD_TXT))

        #root_line_str = local('cat %s|grep -n ^root |tail -n 1'
        #                        %(CS_CRUSH_MAP_TXT), shell='/bin/bash',
        #                            capture=True)
        #root_line_num = int(root_line_str.split(':')[0])
        #rule_line_str=local('cat %s|tail -n +%d|grep -n ^rule|tail -n 1'
        #                        %(CS_CRUSH_MAP_TXT, root_line_num),
        #                            shell='/bin/bash', capture=True)
        #rule_line_num = int(rule_line_str.split(':')[0])
        #local('cat %s|tail -n +%d|head -n %d >> %s' %(CS_CRUSH_MAP_TXT,
        #                        root_line_num, (rule_line_num - 1),
        #                        CS_CRUSH_MAP_MOD_TXT))

        # Now that we have added all the root entries, add the rules
        ruleset = 0
        # Add the default rule
        local('echo "rule replicated_ruleset {" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
        local('echo "   ruleset %d" >> %s' %(ruleset, CS_CRUSH_MAP_MOD_TXT))
        ruleset += 1
        local('echo "   type replicated" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
        local('echo "   min_size 1" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
        local('echo "   max_size 10" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
        if pool_enabled == 0:
            local('echo "   step take cdefault" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
            local('echo "   step chooseleaf firstn 0 type chassis" >> %s'
                                %(CS_CRUSH_MAP_MOD_TXT))
        else:
            local('echo "   step take default" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
            local('echo "   step chooseleaf firstn 0 type host" >> %s'
                                %(CS_CRUSH_MAP_MOD_TXT))
        local('echo "   step emit" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
        local('echo "}" >> %s' %(CS_CRUSH_MAP_MOD_TXT))

        if pool_enabled == 1:
            # Add the hdd rule
            local('echo "rule hdd {" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
            local('echo "   ruleset %d" >> %s' %(ruleset, CS_CRUSH_MAP_MOD_TXT))
            hdd_ruleset = ruleset
            ruleset += 1
            local('echo "   type replicated" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
            local('echo "   min_size 1" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
            local('echo "   max_size 10" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
            local('echo "   step take chdd" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
            local('echo "   step chooseleaf firstn 0 type chassis" >> %s'
                                %(CS_CRUSH_MAP_MOD_TXT))
            local('echo "   step emit" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
            local('echo "}" >> %s' %(CS_CRUSH_MAP_MOD_TXT))

            # Add the ssd rule
            local('echo "rule ssd {" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
            local('echo "   ruleset %d" >> %s' %(ruleset, CS_CRUSH_MAP_MOD_TXT))
            ssd_ruleset = ruleset
            ruleset += 1
            local('echo "   type replicated" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
            local('echo "   min_size 1" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
            local('echo "   max_size 10" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
            local('echo "   step take cssd" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
            local('echo "   step chooseleaf firstn 0 type chassis" >> %s'
                                %(CS_CRUSH_MAP_MOD_TXT))
            local('echo "   step emit" >> %s' %(CS_CRUSH_MAP_MOD_TXT))
            local('echo "}" >> %s' %(CS_CRUSH_MAP_MOD_TXT))

        # Load the new crush map
        local('sudo crushtool -c %s -o %s' %(CS_CRUSH_MAP_MOD_TXT,
                                CS_CRUSH_MAP_MOD))
        local('sudo ceph -k %s osd setcrushmap -i %s' %(CEPH_ADMIN_KEYRING,
                                CS_CRUSH_MAP_MOD))
        if pool_enabled == 1:
            local('sudo ceph osd pool set volumes_hdd crush_ruleset %d'
                                %(hdd_ruleset))
            local('sudo ceph osd pool set volumes_ssd crush_ruleset %d'
                                %(ssd_ruleset))
            local('sudo ceph osd pool set images crush_ruleset %d'
                                %(hdd_ruleset))
            local('sudo ceph osd pool set volumes crush_ruleset %d'
                                %(hdd_ruleset))
        else:
            local('sudo ceph osd pool set images crush_ruleset 0')
            local('sudo ceph osd pool set volumes crush_ruleset 0')
    #end do_chassis_config()


    def add_nfs_disk_config(self):
        NFS_SERVER_LIST_FILE='/etc/cinder/nfs_server_list.txt'
        if self._args.storage_nfs_disk_config[0] != 'none':
            # Create NFS mount list file
            file_present=local('sudo ls %s | wc -l' %(NFS_SERVER_LIST_FILE), capture=True)
            if file_present == '0':
                local('sudo touch %s' %(NFS_SERVER_LIST_FILE), capture=True)
                local('sudo chown root:cinder %s' %(NFS_SERVER_LIST_FILE), capture=True)
                local('sudo chmod 0640 %s' %(NFS_SERVER_LIST_FILE), capture=True)

            # Add NFS mount list to file
            for entry in self._args.storage_nfs_disk_config:
                entry_present=local('cat %s | grep \"%s\" | wc -l' %(NFS_SERVER_LIST_FILE, entry), capture=True)
                if entry_present == '0':
                    local('echo %s >> %s' %(entry, NFS_SERVER_LIST_FILE))

            # Cinder configuration to create backend
            cinder_configured=local('sudo cat %s | grep enabled_backends | grep nfs | wc -l' %(CINDER_CONFIG_FILE), capture=True)
            if cinder_configured == '0':
                existing_backends=local('sudo cat %s |grep enabled_backends |awk \'{print $3}\'' %(CINDER_CONFIG_FILE), shell='/bin/bash', capture=True)
                if existing_backends != '':
                    new_backend = existing_backends + ',' + 'nfs'
                    local('sudo openstack-config --set %s DEFAULT enabled_backends %s' %(CINDER_CONFIG_FILE, new_backend))
                else:
                    local('sudo openstack-config --set %s DEFAULT enabled_backends nfs' %(CINDER_CONFIG_FILE))

                local('sudo openstack-config --set %s nfs nfs_shares_config %s' %(CINDER_CONFIG_FILE, NFS_SERVER_LIST_FILE))
                local('sudo openstack-config --set %s nfs nfs_sparsed_volumes True' %(CINDER_CONFIG_FILE))
                #local('sudo openstack-config --set %s nfs nfs_mount_options ' %(CINDER_CONFIG_FILE, NFS_SERVER_LIST_FILE))
                local('sudo openstack-config --set %s nfs volume_driver cinder.volume.drivers.nfs.NfsDriver' %(CINDER_CONFIG_FILE))
                local('sudo openstack-config --set %s nfs volume_backend_name NFS' %(CINDER_CONFIG_FILE))
    #end add_nfs_disk_config()

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
        ceph_mon_hosts = ''
        ceph_mon_hosts_list = []
        ceph_mon_count = 0
        ceph_all_hosts = ''
        storage_master_hostname = ''
        pdist = platform.dist()[0]

        for entries, entry_token, hostname in zip(self._args.storage_hosts, self._args.storage_host_tokens, self._args.storage_hostnames):
            if entries == self._args.storage_master:
                ceph_mon_hosts = ceph_mon_hosts + hostname + ' '
                storage_master_hostname = hostname
                ceph_mon_count += 1;
                ceph_mon_hosts_list.append(hostname)
            if self._args.storage_os_hosts[0] != 'none':
                for osnode in self._args.storage_os_hosts:
                    if entries == osnode:
                        ceph_mon_hosts = ceph_mon_hosts + hostname + ' '
                        ceph_mon_count += 1;
                        ceph_mon_hosts_list.append(hostname)

        if self._args.storage_mon_hosts[0] != 'none':
            for entries in self._args.storage_mon_hosts:
                ceph_mon_count += 1;
                if ceph_mon_count <= MAX_MONS:
                    ceph_mon_hosts = ceph_mon_hosts + entries + ' '
                    ceph_mon_hosts_list.append(entries)
        else:
            for entries, hostname in zip(self._args.storage_hosts, self._args.storage_hostnames):
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

        #print ceph_mon_hosts
        # setup SSH for autologin for Ceph
        rsa_present=local('sudo ls ~/.ssh/id_rsa | wc -l', capture=True)
        if rsa_present != '1':
            local('sudo ssh-keygen -t rsa -N ""  -f ~/.ssh/id_rsa')
        sshkey=local('cat ~/.ssh/id_rsa.pub', capture=True)
        local('sudo mkdir -p ~/.ssh')
        already_present=local('grep "%s" ~/.ssh/known_hosts 2> /dev/null | wc -l' % (sshkey), capture=True)
        if already_present == '0':
            local('sudo echo "%s" >> ~/.ssh/known_hosts' % (sshkey))
        already_present=local('grep "%s" ~/.ssh/authorized_keys 2> /dev/null | wc -l' % (sshkey), capture=True)
        if already_present == '0':
            local('sudo echo "%s" >> ~/.ssh/authorized_keys' % (sshkey))
        for entries, entry_token, hostname in zip(self._args.storage_hosts, self._args.storage_host_tokens, self._args.storage_hostnames):
            if entries != self._args.storage_master:
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    run('sudo mkdir -p ~/.ssh')
                    already_present=run('grep "%s" ~/.ssh/known_hosts 2> /dev/null | wc -l' % (sshkey))
                    #print already_present
                    if already_present == '0':
                        run('sudo echo %s >> ~/.ssh/known_hosts' % (sshkey))
                    already_present=run('grep "%s" ~/.ssh/authorized_keys 2> /dev/null | wc -l' % (sshkey))
                    #print already_present
                    if already_present == '0':
                        run('sudo echo %s >> ~/.ssh/authorized_keys' % (sshkey))
                    hostfound = local('sudo grep %s,%s ~/.ssh/known_hosts | wc -l' %(hostname,entries), capture=True)
                    if hostfound == "0":
                         out = run('sudo ssh-keyscan -t rsa %s,%s' %(hostname,entries))
                         local('sudo echo "%s" >> ~/.ssh/known_hosts' % (out))
                         #local('sudo echo "%s" >> ~/.ssh/authorized_keys' % (out))

        # This is called with 'fab storage_chassis_configure'
        # This will be useful to provision an existing cluster with
        # the chassis configuration without destroying the data.
        if self._args.storage_setup_mode == 'chassis_configure':
            self.do_chassis_config()
            return

        #Add a new node to the existing cluster
        if self._args.add_storage_node:
            configure_with_ceph = 0
            add_storage_node = self._args.add_storage_node
            if self._args.storage_directory_config[0] != 'none':
                for directory in self._args.storage_directory_config:
                    dirsplit = directory.split(':')
                    if dirsplit[0] == add_storage_node:
                        configure_with_ceph = 1
            if self._args.storage_disk_config[0] != 'none':
                for disk in self._args.storage_disk_config:
                    dirsplit = disk.split(':')
                    if dirsplit[0] == add_storage_node:
                        configure_with_ceph = 1
            if self._args.storage_ssd_disk_config[0] != 'none':
                for disk in self._args.storage_ssd_disk_config:
                    dirsplit = disk.split(':')
                    if dirsplit[0] == add_storage_node:
                        configure_with_ceph = 1
            if configure_with_ceph == 1:
                public_ip = self._args.storage_master
                for entries, entry_token, hostname in zip(self._args.storage_hosts, self._args.storage_host_tokens, self._args.storage_hostnames):
                    if hostname == self._args.add_storage_node:
                        public_ip = entries
                        public_pass = entry_token
                        break
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    ip_cidr=run('ip addr show |grep -w %s |awk \'{print $2}\'' %(public_ip))
                local('sudo openstack-config --set /root/ceph.conf global public_network %s\/%s' %(netaddr.IPNetwork(ip_cidr).network, netaddr.IPNetwork(ip_cidr).prefixlen))
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
                for hostname in ceph_mon_hosts_list:
                    if hostname == add_storage_node:
                        local('sudo ceph-deploy --overwrite-conf mon create-initial %s' % (add_storage_node))

                with settings(host_string = 'root@%s' %(public_ip), password = public_pass):
                    put('/etc/ceph/ceph.client.admin.keyring', '/etc/ceph/')
                    put('/var/lib/ceph/bootstrap-osd/ceph.keyring', '/var/lib/ceph/bootstrap-osd/')

                if self._args.storage_directory_config[0] != 'none':
                    for directory in self._args.storage_directory_config:
                        dirsplit = directory.split(':')
                        if dirsplit[0] == add_storage_node:
                            with settings(host_string = 'root@%s' %(entries), password = entry_token):
                                run('sudo mkdir -p %s' % (dirsplit[1]))
                                run('sudo rm -rf %s' % (dirsplit[1]))
                                run('sudo mkdir -p %s' % (dirsplit[1]))
                            local('sudo ceph-deploy --overwrite-conf osd prepare %s' % (directory))
                            local('sudo ceph-deploy --overwrite-conf osd activate %s' % (directory))
                # Setup Journal disks
                storage_disk_list=[]
                # Convert configuration from --storage-journal-config to ":" format
                # for example --storage-disk-config ceph1:/dev/sdb ceph1:/dev/sdc
                # --storage-journal-config ceph1:/dev/sdd will be stored in
                # storage_disk_list as ceph1:/dev/sdb:/dev/sdd, ceph1:/dev/sdc:/dev/sdd
                if self._args.storage_journal_config[0] != 'none':
                    for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
                        host_disks = 0
                        journal_disks = 0
                        #print hostname
                        #print self._args.storage_disk_config
                        for disks in self._args.storage_disk_config:
                            disksplit = disks.split(':')
                            if disksplit[0] == hostname:
                                host_disks += 1
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
                                    journal_disks_list = journal_disks_list + ':' + journalsplit[1]
                        #print 'num disks %d' %(host_disks)
                        #print 'num journal %d' %(journal_disks)
                        if journal_disks != 0:
                            num_partitions = (host_disks / journal_disks) + (host_disks % journal_disks > 0)
                            #print 'num partitions %d' %(num_partitions)
                            index = num_partitions
                            init_journal_disks_list = journal_disks_list
                            while True:
                                index -= 1
                                if index == 0:
                                    break
                                journal_disks_list = journal_disks_list + ':' + init_journal_disks_list
                            #print journal_disks_list
                            journal_disks_split = journal_disks_list.split(':')
                        index = 0
                        for disks in self._args.storage_disk_config:
                            disksplit = disks.split(':')
                            if disksplit[0] == hostname:
                                #print journal_disks_list
                                if journal_disks_list != '':
                                    storage_disk_node = hostname + ':' + disksplit[1] + ':' + journal_disks_split[index]
                                    index += 1
                                else:
                                    storage_disk_node = disks
                                storage_disk_list.append(storage_disk_node)
                        for disks in self._args.storage_ssd_disk_config:
                            disksplit = disks.split(':')
                            if disksplit[0] == hostname:
                                #print journal_disks_list
                                if journal_disks_list != '':
                                    storage_disk_node = hostname + ':' + disksplit[1] + ':' + journal_disks_split[index]
                                    index += 1
                                else:
                                    storage_disk_node = disks
                                storage_disk_list.append(storage_disk_node)
                else:
                    if self._args.storage_ssd_disk_config[0] != 'none':
                        storage_disk_list = self._args.storage_disk_config + self._args.storage_ssd_disk_config
                    else:
                        storage_disk_list = self._args.storage_disk_config
                #print self._args.storage_disk_config

                # based on the coverted format or if the user directly provides in
                # storage_disk_list ceph1:/dev/sdb:/dev/sdd, ceph1:/dev/sdc:/dev/sdd
                # create journal partitions in the journal disk and assign partition
                # numbers to the storage_disk_list. The final storage_disk_list will
                # look as ceph1:/dev/sdb:/dev/sdd1, ceph1:/dev/sdc:/dev/sdd2
                # with sdd1 and sdd2 of default_journal_size.
                # TODO: make default_journal_size as configurable - currently its 1024M
                new_storage_disk_list=[]
                if storage_disk_list != []:
                    for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
                        for disks in storage_disk_list:
                            journal_available = disks.count(':')
                            disksplit = disks.split(':')
                            if disksplit[0] == add_storage_node and disksplit[0] == hostname:
                                #print hostname
                                if journal_available == 2:
                                    #print disksplit[2]
                                    if disksplit[2][0] != 'P':
                                        with settings(host_string = 'root@%s' %(entries), password = entry_token):
                                            run('dd if=/dev/zero of=%s  bs=512  count=1' %(disksplit[2]))
                                            run('parted -s %s mklabel gpt 2>&1 > /dev/null' %(disksplit[2]))

                    for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
                        for disks in storage_disk_list:
                            journal_available = disks.count(':')
                            disksplit = disks.split(':')
                            if disksplit[0] == add_storage_node and disksplit[0] == hostname:
                                #print hostname
                                # No need to partition
                                # Ceph will do the partition
                                #if journal_available == 2:
                                #    #print disksplit[2]
                                #    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                                #        default_journal_size = 1024
                                #        num_primary = run('parted -s %s print|grep primary|wc -l' %(disksplit[2]), shell='/bin/bash')
                                #        part_num = int(num_primary) + 1
                                #        start_part = default_journal_size * part_num
                                #        end_part = start_part + default_journal_size
                                #        run('parted -s %s mkpart primary %dM %dM' %(disksplit[2], start_part, end_part))
                                #        storage_disk_node = disks + str(part_num)
                                #        new_storage_disk_list.append(storage_disk_node)
                                #else:
                                diskcount = disks.count(':')
                                if diskcount == 3:
                                    new_storage_disk_list.append('%s:%s:%s' %(disksplit[0], disksplit[1], disksplit[2]))
                                elif diskcount == 2:
                                    if disksplit[2][0] == 'P':
                                        new_storage_disk_list.append('%s:%s' %(disksplit[0], disksplit[1]))
                                    else:
                                        new_storage_disk_list.append('%s:%s:%s' %(disksplit[0], disksplit[1], disksplit[2]))
                                else:
                                    new_storage_disk_list.append(disks)

                    #print new_storage_disk_list
                    #print self._args.storage_disk_config
                if new_storage_disk_list != []:
                    for disks in new_storage_disk_list:
                        dirsplit = disks.split(':')
                        if dirsplit[0] == add_storage_node:
                            local('sudo ceph-deploy disk zap %s' % (disks))
                            # For prefirefly use prepare/activate on ubuntu release
                            local('sudo ceph-deploy --overwrite-conf osd create %s' % (disks))


            # Find the host count
            host_count = 0
            if new_storage_disk_list != []:
                for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
                    for disks in storage_disk_list:
                        disksplit = disks.split(':')
                        if hostname == disksplit[0]:
                            host_count += 1
                            break

            volumes_pool_avail=local('sudo rados lspools |grep volumes_hdd | wc -l ', capture=True)
            if volumes_pool_avail == '0':
                # Set replica size based on new count
                if host_count <= 1:
                    local('sudo ceph osd pool set volumes size 1')
                else:
                    rep_size=local('sudo ceph osd pool get volumes size | awk \'{print $2}\'', shell='/bin/bash', capture=True)
                    if rep_size == '1':
                        local('sudo ceph osd pool set volumes size 2')

                osd_count=int(local('ceph osd stat | awk \'{print $3}\'', shell='/bin/bash', capture=True))
                # Set PG/PGP count based on osd new count
                self.set_pg_pgp_count(osd_count, 'images', host_count)
                self.set_pg_pgp_count(osd_count, 'volumes', host_count)

            time.sleep(3)

            # rbd cache enabled and rbd cache size set to 512MB
            local('ceph tell osd.* injectargs -- --rbd_cache=true')
            local('ceph tell osd.* injectargs -- --rbd_cache_size=536870912')
            local('sudo openstack-config --set /etc/ceph/ceph.conf global "rbd cache" true')
            local('sudo openstack-config --set /etc/ceph/ceph.conf global "rbd cache size" 536870912')

            # change default osd op threads 2 to 4
            local('ceph tell osd.* injectargs -- --osd_op_threads=4')
            local('sudo openstack-config --set /etc/ceph/ceph.conf osd "osd op threads" 4')

            # change default disk threads 1 to 2
            local('ceph tell osd.* injectargs -- --osd_disk_threads=2')
            local('sudo openstack-config --set /etc/ceph/ceph.conf osd "osd disk threads" 2')

            # compute ceph.conf configuration done here
            for entries, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
                if entries != self._args.storage_master:
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        run('sudo openstack-config --set /etc/ceph/ceph.conf global "rbd cache" true')
                        run('sudo openstack-config --set /etc/ceph/ceph.conf global "rbd cache size" 536870912')
                        run('sudo openstack-config --set /etc/ceph/ceph.conf osd "osd op threads" 4')
                        run('sudo openstack-config --set /etc/ceph/ceph.conf osd "osd disk threads" 2')


            # log ceph.log to syslog
            local('ceph tell mon.* injectargs -- --mon_cluster_log_to_syslog=true')

            # set ceph.log to syslog config in ceph.conf
            local('sudo openstack-config --set /etc/ceph/ceph.conf  mon "mon cluster log to syslog" true')
            for entries, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
                if entries != self._args.storage_master:
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        run('sudo openstack-config --set /etc/ceph/ceph.conf  mon "mon cluster log to syslog" true')

            # Add the new host/osds to HDD/SSD pool.
            volumes_pool_avail=local('sudo rados lspools |grep volumes_hdd | wc -l ', capture=True)
            if volumes_pool_avail != '0':
                self.add_to_hdd_ssd_pool()

            # Perform chassis configuration
            self.do_chassis_config()

            cinder_lvm_type_list=[]
            cinder_lvm_name_list=[]
            #Create LVM volumes on each node
            if self._args.storage_local_disk_config[0] != 'none':
                for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        local_disk_list=''
                        for local_disks in self._args.storage_local_disk_config:
                            disksplit = local_disks.split(':')
                            if disksplit[0] == hostname:
                                if disksplit[0] == add_storage_node:
                                    local_disk_list = local_disk_list + disksplit[1] + ' '
                                    run('sudo dd if=/dev/zero of=%s bs=512 count=1' %(disksplit[1]))
                        if local_disk_list != '':
                            if disksplit[0] == hostname:
                                if disksplit[0] == add_storage_node:
                                    run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT sql_connection mysql://cinder:cinder@%s/cinder' %(self._args.storage_master))
                                    if self._args.cinder_vip != 'none':
                                        run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT rabbit_host %s' %(self._args.cinder_vip))
                                        run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT rabbit_port %s' %(RABBIT_PORT))
                                    else:
                                        run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT rabbit_host %s' %(self._args.cfg_host))
                                    run('sudo cinder-manage db sync')
                                    existing_backends=run('sudo cat /etc/cinder/cinder.conf |grep enabled_backends |awk \'{print $3}\'', shell='/bin/bash')
                                    if existing_backends != '':
                                        new_backend = existing_backends + ',' + 'lvm-local-disk-volumes'
                                    else:
                                        new_backend = 'lvm-local-disk-volumes'
                                    run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT enabled_backends %s' %(new_backend))
                                    run('sudo pvcreate %s' %(local_disk_list))
                                    run('sudo vgcreate ocs-lvm-group %s' %(local_disk_list))
                                    run('sudo openstack-config --set /etc/cinder/cinder.conf lvm-local-disk-volumes volume_group ocs-lvm-group')
                                    run('sudo openstack-config --set /etc/cinder/cinder.conf lvm-local-disk-volumes volume_driver cinder.volume.drivers.lvm.LVMISCSIDriver')
                                    run('sudo openstack-config --set /etc/cinder/cinder.conf lvm-local-disk-volumes volume_backend_name OCS_LVM_%s' %(hostname))
                                    cinder_lvm_type_list.append('ocs-block-lvm-disk-%s' %(hostname))
                                    cinder_lvm_name_list.append('OCS_LVM_%s' %(hostname))

            #Create LVM volumes for SSD disks on each node
            if self._args.storage_local_ssd_disk_config[0] != 'none':
                for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        local_ssd_disk_list=''
                        for local_ssd_disks in self._args.storage_local_ssd_disk_config:
                            disksplit = local_ssd_disks.split(':')
                            if disksplit[0] == hostname:
                                if disksplit[0] == add_storage_node:
                                    local_ssd_disk_list = local_ssd_disk_list + disksplit[1] + ' '
                                    run('sudo dd if=/dev/zero of=%s bs=512 count=1' %(disksplit[1]))
                        if local_ssd_disk_list != '':
                            if disksplit[0] == hostname:
                                if disksplit[0] == add_storage_node:
                                    run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT sql_connection mysql://cinder:cinder@%s/cinder' %(self._args.storage_master))
                                    if self._args.cinder_vip != 'none':
                                        run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT rabbit_host %s' %(self._args.cinder_vip))
                                        run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT rabbit_port %s' %(RABBIT_PORT))
                                    else:
                                        run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT rabbit_host %s' %(self._args.cfg_host))
                                    run('sudo cinder-manage db sync')
                                    existing_backends=run('sudo cat /etc/cinder/cinder.conf |grep enabled_backends |awk \'{print $3}\'', shell='/bin/bash')
                                    if existing_backends != '':
                                        new_backend = existing_backends + ',' + 'lvm-local-ssd-disk-volumes'
                                    else:
                                        new_backend = 'lvm-local-ssd-disk-volumes'
                                    run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT enabled_backends %s' %(new_backend))
                                    run('sudo pvcreate %s' %(local_ssd_disk_list))
                                    run('sudo vgcreate ocs-lvm-ssd-group %s' %(local_ssd_disk_list))
                                    run('sudo openstack-config --set /etc/cinder/cinder.conf lvm-local-ssd-disk-volumes volume_group ocs-lvm-ssd-group')
                                    run('sudo openstack-config --set /etc/cinder/cinder.conf lvm-local-ssd-disk-volumes volume_driver cinder.volume.drivers.lvm.LVMISCSIDriver')
                                    run('sudo openstack-config --set /etc/cinder/cinder.conf lvm-local-ssd-disk-volumes volume_backend_name OCS_LVM_SSD_%s' %(hostname))
                                    cinder_lvm_type_list.append('ocs-block-lvm-ssd-disk-%s' %(hostname))
                                    cinder_lvm_name_list.append('OCS_LVM_SSD_%s' %(hostname))

            # Create Cinder type for all the LVM backends
            for lvm_types, lvm_names in zip(cinder_lvm_type_list, cinder_lvm_name_list):
                local('(. /etc/contrail/openstackrc ; cinder type-create %s)' %(lvm_types))
                local('(. /etc/contrail/openstackrc ; cinder type-key %s set volume_backend_name=%s)' %(lvm_types, lvm_names))

            # Add NFS configurations if present
            if self._args.storage_nfs_disk_config[0] != 'none':
                self.add_nfs_disk_config()
                nfs_type_present=local('(. /etc/contrail/openstackrc ; cinder type-list | grep ocs-block-nfs-disk | wc -l)', capture=True)
                if nfs_type_present == '0':
                    local('(. /etc/contrail/openstackrc ; cinder type-create ocs-block-nfs-disk)')
                    local('(. /etc/contrail/openstackrc ; cinder type-key ocs-block-nfs-disk set volume_backend_name=NFS)')

            # Find the list of pools
            avail_pools = []
            num_pools = int(local('sudo rados lspools |grep volumes | wc -l ', capture=True))
            while num_pools != 0:
                volume_pool = local('sudo rados lspools | grep volumes | tail -n +%d | head -n 1 ' %(num_pools),capture=True)
                avail_pools.append(volume_pool)
                num_pools -= 1

            # Set the virsh secret for all the pools found
            for entries, entry_token, hostname in zip(self._args.storage_hosts, self._args.storage_host_tokens, self._args.storage_hostnames):
                if hostname == add_storage_node:
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        if configure_with_ceph == 1:
                            while True:
                                virsh_unsecret=run('virsh secret-list  2>&1 | awk \'{print $1}\' | awk \'NR > 2 { print }\' | head -n 1')
                                if virsh_unsecret != "":
                                    run('virsh secret-undefine %s' %(virsh_unsecret))
                                else:
                                    break
                            for pool in avail_pools:
                                volume_keyring_list=local('cat /etc/ceph/client.%s.keyring | grep key' %(pool), capture=True)
                                volume_keyring=volume_keyring_list.split(' ')[2]
                                current_count = 1
                                while True:
                                    virsh_secret=local('virsh secret-list  2>&1 |awk \'{print $1}\'| awk \'NR > 2 { print }\' | head -n %d | tail -n 1' %(current_count), capture=True)
                                    if virsh_secret == '':
                                        break
                                    virsh_secret_key=local('virsh secret-get-value %s' %(virsh_secret), capture=True)
                                    if virsh_secret_key == volume_keyring:
                                        run('echo "<secret ephemeral=\'no\' private=\'no\'>\n<uuid>%s</uuid><usage type=\'ceph\'>\n<name>client.%s secret</name>\n</usage>\n</secret>" > secret_%s.xml' % (virsh_secret, pool, pool))
                                        run('virsh secret-define --file secret_%s.xml' %(pool))
                                        run('virsh secret-set-value %s --base64 %s' % (virsh_secret,volume_keyring))
                                        break
                                    current_count += 1

                            # Remove rbd_user configurations from nova if present
                            run('sudo openstack-config --del /etc/nova/nova.conf DEFAULT rbd_user')
                            run('sudo openstack-config --del /etc/nova/nova.conf DEFAULT rbd_secret_uuid')

                            # This should not be set for multi-backend. The virsh secret setting itself is enough for correct authentication.
                            #run('sudo openstack-config --set /etc/nova/nova.conf DEFAULT rbd_user volumes')
                            #run('sudo openstack-config --set /etc/nova/nova.conf DEFAULT rbd_secret_uuid %s' % (virsh_secret))
                        if self._args.cinder_vip != 'none':
                            run('sudo openstack-config --set /etc/nova/nova.conf DEFAULT cinder_endpoint_template "http://%s:8776/v1/%%(project_id)s"' % (self._args.cinder_vip), shell='/bin/bash')
                        else:
                            run('sudo openstack-config --set /etc/nova/nova.conf DEFAULT cinder_endpoint_template "http://%s:8776/v1/%%(project_id)s"' % (self._args.storage_master), shell='/bin/bash')
                        if pdist == 'centos':
                            run('sudo chkconfig tgt on')
                            run('sudo service tgt restart')
                            run('sudo service openstack-cinder-api restart')
                            run('sudo chkconfig openstack-cinder-api on')
                            run('sudo service openstack-cinder-scheduler restart')
                            run('sudo chkconfig openstack-cinder-scheduler on')
                            if configure_with_ceph == 1:
                                bash_cephargs = run('grep "bashrc" /etc/init.d/openstack-cinder-volume | wc -l')
                                if bash_cephargs == "0":
                                    run('cat /etc/init.d/openstack-cinder-volume | sed "s/start)/start)  source ~\/.bashrc/" > /tmp/openstack-cinder-volume.tmp')
                                    run('mv -f /tmp/openstack-cinder-volume.tmp /etc/init.d/openstack-cinder-volume; chmod a+x /etc/init.d/openstack-cinder-volume')
                            run('sudo chkconfig openstack-cinder-volume on')
                            run('sudo service openstack-cinder-volume restart')
                            run('sudo service libvirtd restart')
                            run('sudo service openstack-nova-compute restart')
                        if pdist == 'Ubuntu':
                            run('sudo chkconfig tgt on')
                            run('sudo service tgt restart')
                            run('sudo service libvirt-bin restart')
                            run('sudo service nova-compute restart')
                            run('sudo chkconfig cinder-volume on')
                            run('sudo service cinder-volume restart')

            # configure discovery details in storage stats configuration
            # restart contrail-stats-daemon on the newly added node.
            if configure_with_ceph == 1:
                for entries, entry_token, hostname in zip(self._args.storage_hosts, self._args.storage_host_tokens, self._args.storage_hostnames):
                    if hostname == add_storage_node:
                        with settings(host_string = 'root@%s' %(entries), password = entry_token):
                            if pdist == 'Ubuntu':
                                run('sudo openstack-config --set /etc/contrail/contrail-storage-nodemgr.conf DEFAULTS disc_server_ip %s' %(self._args.cfg_host))
                                run('sudo service contrail-storage-stats restart')
            return

        #Cleanup existing configuration
        #Normal storage install. Remove previous configuration and reconfigure
        ocs_blk_disk = local('(. /etc/contrail/openstackrc ; cinder type-list | grep ocs-block | cut -d"|" -f 2)', capture=True)
        if ocs_blk_disk != "":
            if self._args.storage_setup_mode == 'setup':
                print 'Storage already configured'
                return

        while True:
            glance_image = local('(. /etc/contrail/openstackrc ; glance image-list |grep active |awk \'{print $2}\' | head -n 1)', capture=True, shell='/bin/bash')
            if glance_image != '':
                local('(. /etc/contrail/openstackrc ; glance image-delete %s)' %(glance_image))
            else:
                break

        local('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT default_store file')
        local('sudo openstack-config --del /etc/glance/glance-api.conf DEFAULT show_image_direct_url')
        local('sudo openstack-config --del /etc/glance/glance-api.conf DEFAULT rbd_store_user')
        local('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT workers 1')
        if pdist == 'centos':
            local('sudo service openstack-glance-api restart')
        if pdist == 'Ubuntu':
            local('sudo service glance-api restart')
        if self._args.storage_os_hosts[0] != 'none':
            for entries, entry_token in zip(self._args.storage_os_hosts, self._args.storage_os_host_tokens):
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    run('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT default_store file')
                    run('sudo openstack-config --del /etc/glance/glance-api.conf DEFAULT show_image_direct_url')
                    run('sudo openstack-config --del /etc/glance/glance-api.conf DEFAULT rbd_store_user')
                    run('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT workers 1')
                    if pdist == 'centos':
                        run('sudo service openstack-glance-api restart')
                    if pdist == 'Ubuntu':
                        run('sudo service glance-api restart')

        cinderlst = local('(. /etc/contrail/openstackrc ;  cinder list --all-tenants| grep ocs-block | cut -d"|" -f 2)',  capture=True)
        if cinderlst != "":
            cinderalst = cinderlst.split('\n')
            for x in cinderalst:
                inuse = local('(. /etc/contrail/openstackrc ;  cinder list --all-tenants| grep %s | cut -d"|" -f 3)' % (x),  capture=True)
                if inuse == "in-use":
                    detach = local('(. /etc/contrail/openstackrc ;  cinder list --all-tenants| grep %s | cut -d"|" -f 8)' % (x),  capture=True)
                    local('(. /etc/contrail/openstackrc ;  nova volume-detach %s %s)' % (detach, x))
                local('(. /etc/contrail/openstackrc ;  cinder force-delete %s)' % (x))
                while True:
                    volavail = local('(. /etc/contrail/openstackrc ;  cinder list --all-tenants| grep %s | wc -l)' % (x),  capture=True)
                    if volavail == '0':
                        break
                    else:
                        print "Waiting for volume to be deleted"
                        time.sleep(5)
        # Delete all ocs-block disk types
        num_ocs_blk_disk = int(local('(. /etc/contrail/openstackrc ; cinder type-list | grep ocs-block | wc -l )', capture=True))
        while True:
            if num_ocs_blk_disk == 0:
                break
            ocs_blk_disk = local('(. /etc/contrail/openstackrc ; cinder type-list | grep ocs-block | head -n 1 | cut -d"|" -f 2)', capture=True)
            local('. /etc/contrail/openstackrc ; cinder type-delete %s' % (ocs_blk_disk))
            num_ocs_blk_disk -= 1

        # Remove LVM related configurations
        for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
            with settings(host_string = 'root@%s' %(entries), password = entry_token):
                volavail=run('vgdisplay 2>/dev/null |grep ocs-lvm-group|wc -l')
                if volavail != '0':
                    run('vgremove ocs-lvm-group')
                volavail=run('vgdisplay 2>/dev/null |grep ocs-lvm-ssd-group|wc -l')
                if volavail != '0':
                    run('vgremove ocs-lvm-ssd-group')
                if self._args.storage_local_disk_config[0] != 'none':
                    for disks in self._args.storage_local_disk_config:
                        disksplit = disks.split(':')
                        if disksplit[0] == hostname:
                            pvadded=run('pvdisplay 2> /dev/null |grep %s |wc -l' %(disksplit[1]))
                            if pvadded != '0':
                                run('pvremove -ff %s' %(disksplit[1]))
                if self._args.storage_local_ssd_disk_config[0] != 'none':
                    for disks in self._args.storage_local_ssd_disk_config:
                        disksplit = disks.split(':')
                        if disksplit[0] == hostname:
                            pvadded=run('pvdisplay 2> /dev/null |grep %s |wc -l' %(disksplit[1]))
                            if pvadded != '0':
                                run('pvremove -ff %s' %(disksplit[1]))
                existing_backends=run('sudo cat /etc/cinder/cinder.conf |grep enabled_backends |awk \'{print $3}\'', shell='/bin/bash')
                backends = existing_backends.split(',')
                #print backends
                for backend in backends:
                    if backend != '':
                        run('sudo openstack-config --del /etc/cinder/cinder.conf %s' %(backend))
                run('sudo openstack-config --del /etc/cinder/cinder.conf DEFAULT enabled_backends')
                run('sudo openstack-config --del /etc/cinder/cinder.conf DEFAULT rabbit_host')
                run('sudo openstack-config --del /etc/cinder/cinder.conf DEFAULT sql_connection')

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
        local('sudo ceph-deploy purgedata %s <<< \"y\"' % (ceph_all_hosts), capture=False, shell='/bin/bash')

        if pdist == 'Ubuntu':
            self.ceph_rest_api_service_remove()
            self.unconfigure_syslog()

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

        if self._args.storage_directory_config[0] != 'none' or self._args.storage_disk_config[0] != 'none' or self._args.storage_ssd_disk_config[0] != 'none':
            configure_with_ceph = 1
        else:
            configure_with_ceph = 0

        if configure_with_ceph == 1:
            for entries, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
                if entries != self._args.storage_master:
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        run('sudo mkdir -p /var/lib/ceph/bootstrap-osd')
                        run('sudo mkdir -p /var/lib/ceph/osd')
                        run('sudo mkdir -p /etc/ceph')



            create_hdd_ssd_pool = 0
            # Setup Journal disks
            storage_disk_list=[]
            # If there are SSD disks configured enabled the multi-pool support
            if self._args.storage_ssd_disk_config[0] != 'none':
                create_hdd_ssd_pool = 1
            # Convert configuration from --storage-journal-config to ":" format
            # for example --storage-disk-config ceph1:/dev/sdb ceph1:/dev/sdc
            # --storage-journal-config ceph1:/dev/sdd will be stored in
            # storage_disk_list as ceph1:/dev/sdb:/dev/sdd, ceph1:/dev/sdc:/dev/sdd
            if self._args.storage_journal_config[0] != 'none':
                for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
                    host_disks = 0
                    journal_disks = 0
                    #print hostname
                    #print self._args.storage_disk_config
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
                                journal_disks_list = journal_disks_list + ':' + journalsplit[1]
                    #print 'num disks %d' %(host_disks)
                    #print 'num journal %d' %(journal_disks)
                    if journal_disks != 0:
                        num_partitions = (host_disks / journal_disks) + (host_disks % journal_disks > 0)
                        #print 'num partitions %d' %(num_partitions)
                        index = num_partitions
                        init_journal_disks_list = journal_disks_list
                        while True:
                            index -= 1
                            if index == 0:
                                break
                            journal_disks_list = journal_disks_list + ':' + init_journal_disks_list
                        #print journal_disks_list
                        journal_disks_split = journal_disks_list.split(':')
                    index = 0
                    if self._args.storage_disk_config[0] != 'none':
                        for disks in self._args.storage_disk_config:
                            disksplit = disks.split(':')
                            if disksplit[0] == hostname:
                                #print journal_disks_list
                                if journal_disks_list != '':
                                    storage_disk_node = hostname + ':' + disksplit[1] + ':' + journal_disks_split[index]
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
                                    storage_disk_node = hostname + ':' + disksplit[1] + ':' + journal_disks_split[index]
                                    index += 1
                                else:
                                    storage_disk_node = disks
                                storage_disk_list.append(storage_disk_node)
            else:
                if self._args.storage_ssd_disk_config[0] != 'none':
                    storage_disk_list = self._args.storage_disk_config + self._args.storage_ssd_disk_config
                else:
                    storage_disk_list = self._args.storage_disk_config
            #print storage_disk_list

            # based on the coverted format or if the user directly provides in the
            # storage_disk_list as ceph1:/dev/sdb:/dev/sdd, ceph1:/dev/sdc:/dev/sdd
            # create journal partitions in the journal disk and assign partition
            # numbers to the storage_disk_list. The final storage_disk_list will
            # look as ceph1:/dev/sdb:/dev/sdd1, ceph1:/dev/sdc:/dev/sdd2
            # with sdd1 and sdd2 of default_journal_size.
            # TODO: make default_journal_size as configurable - currently its 1024M
            new_storage_disk_list=[]
            if storage_disk_list != []:
                for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
                    for disks in storage_disk_list:
                        journal_available = disks.count(':')
                        disksplit = disks.split(':')
                        if hostname == disksplit[0]:
                            #print hostname
                            if journal_available >= 2:
                                if disksplit[2][0] != 'P':
                                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                                        run('dd if=/dev/zero of=%s  bs=512  count=1' %(disksplit[2]))
                                        run('parted -s %s mklabel gpt 2>&1 > /dev/null' %(disksplit[2]))

                for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
                    for disks in storage_disk_list:
                        journal_available = disks.count(':')
                        disksplit = disks.split(':')
                        if hostname == disksplit[0]:
                            #print hostname
                            # No need to partition
                            # Ceph will do the partition
                            #if journal_available == 2:
                            #    #print disksplit[2]
                            #    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                            #        default_journal_size = 1024
                            #        num_primary = run('parted -s %s print|grep primary|wc -l' %(disksplit[2]), shell='/bin/bash')
                            #        part_num = int(num_primary) + 1
                            #        start_part = default_journal_size * part_num
                            #        end_part = start_part + default_journal_size
                            #        run('parted -s %s mkpart primary %dM %dM' %(disksplit[2], start_part, end_part))
                            #        storage_disk_node = disks + str(part_num)
                            #        new_storage_disk_list.append(storage_disk_node)
                            #else:
                            diskcount = disks.count(':')
                            if diskcount == 3:
                                if disksplit[3][0] == 'P':
                                    create_hdd_ssd_pool = 1
                                new_storage_disk_list.append('%s:%s:%s' %(disksplit[0], disksplit[1], disksplit[2]))
                            elif diskcount == 2:
                                if disksplit[2][0] == 'P':
                                    create_hdd_ssd_pool = 1
                                    new_storage_disk_list.append('%s:%s' %(disksplit[0], disksplit[1]))
                                else:
                                    new_storage_disk_list.append('%s:%s:%s' %(disksplit[0], disksplit[1], disksplit[2]))
                            else:
                                new_storage_disk_list.append(disks)
                #print new_storage_disk_list
                #print self._args.storage_disk_config
                #error

            # Ceph deploy create monitor
            local('sudo ceph-deploy new %s' % (ceph_mon_hosts))

            time.sleep(5)

            local('sudo ceph-deploy mon create %s' % (ceph_mon_hosts))

            time.sleep(5)

            if self._args.storage_disk_config[0] != 'none':
                if new_storage_disk_list != []:
                    for disks in new_storage_disk_list:
                        local('sudo ceph-deploy disk zap %s' % (disks))

            time.sleep(20)


            # gather keys for current system
            local('sudo ceph-deploy gatherkeys %s' % (storage_master_hostname))

            # gather keys for non monitor systems
            for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
                mon_present = 0
                for monentries in ceph_mon_hosts_list:
                    if hostname == monentries:
                        mon_present = 1
                        break

                if mon_present == 0:
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        put('/etc/ceph/ceph.client.admin.keyring', '/etc/ceph/')
                        put('/var/lib/ceph/bootstrap-osd/ceph.keyring', '/var/lib/ceph/bootstrap-osd/')

            osd_count = 0
            if self._args.storage_directory_config[0] != 'none':
                for directory in self._args.storage_directory_config:
                    local('sudo ceph-deploy --overwrite-conf  osd prepare %s' % (directory))
                for directory in self._args.storage_directory_config:
                    local('sudo ceph-deploy --overwrite-conf  osd activate %s' % (directory))
                    osd_count += 1

            # Ceph deploy OSD create
            if new_storage_disk_list != []:
                for disks in new_storage_disk_list:
                    # For prefirefly use prepare/activate on ubuntu release
                    local('sudo ceph-deploy --overwrite-conf osd create %s' % (disks))
                    osd_count += 1

            # Find the host count
            host_count = 0
            if new_storage_disk_list != []:
                for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
                    for disks in storage_disk_list:
                        disksplit = disks.split(':')
                        if hostname == disksplit[0]:
                            host_count += 1
                            break

            # Create pools
            local('unset CEPH_ARGS')
            # Remove unwanted pools
            local('sudo rados rmpool data data --yes-i-really-really-mean-it')
            local('sudo rados rmpool metadata metadata --yes-i-really-really-mean-it')
            local('sudo rados rmpool rbd rbd --yes-i-really-really-mean-it')
            # Add required pools
            local('sudo rados mkpool volumes')
            local('sudo rados mkpool images')
            if create_hdd_ssd_pool == 0:
                if host_count == 1:
                    local('sudo ceph osd pool set images size 1')
                    local('sudo ceph osd pool set volumes size 1')
                else:
                    local('sudo ceph osd pool set images size 2')
                    local('sudo ceph osd pool set volumes size 2')

                # Set PG/PGP count based on osd count
                self.set_pg_pgp_count(osd_count, 'images', host_count)
                self.set_pg_pgp_count(osd_count, 'volumes', host_count)

            # Create HDD/SSD pool
            if create_hdd_ssd_pool == 1:
                self.create_hdd_ssd_pool()

            # Perform chassis configuration
            self.do_chassis_config()

            time.sleep(3)

            # rbd cache enabled and rbd cache size set to 512MB
            local('ceph tell osd.* injectargs -- --rbd_cache=true')
            local('ceph tell osd.* injectargs -- --rbd_cache_size=536870912')
            local('sudo openstack-config --set /etc/ceph/ceph.conf global "rbd cache" true')
            local('sudo openstack-config --set /etc/ceph/ceph.conf global "rbd cache size" 536870912')

            # change default osd op threads 2 to 4
            local('ceph tell osd.* injectargs -- --osd_op_threads=4')
            local('sudo openstack-config --set /etc/ceph/ceph.conf osd "osd op threads" 4')

            # change default disk threads 1 to 2
            local('ceph tell osd.* injectargs -- --osd_disk_threads=2')
            local('sudo openstack-config --set /etc/ceph/ceph.conf osd "osd disk threads" 2')

            # compute ceph.conf configuration done here
            for entries, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
                if entries != self._args.storage_master:
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        run('sudo openstack-config --set /etc/ceph/ceph.conf global "rbd cache" true')
                        run('sudo openstack-config --set /etc/ceph/ceph.conf global "rbd cache size" 536870912')
                        run('sudo openstack-config --set /etc/ceph/ceph.conf osd "osd op threads" 4')
                        run('sudo openstack-config --set /etc/ceph/ceph.conf osd "osd disk threads" 2')


            # log ceph.log to syslog
            local('ceph tell mon.* injectargs -- --mon_cluster_log_to_syslog=true')

            # set ceph.log to syslog config in ceph.conf
            local('sudo openstack-config --set /etc/ceph/ceph.conf  mon "mon cluster log to syslog" true')
            for entries, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
                if entries != self._args.storage_master:
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        run('sudo openstack-config --set /etc/ceph/ceph.conf  mon "mon cluster log to syslog" true')

            # enable server:port syslog remote logging
            for entries in self._args.collector_hosts:
                syslog_present=local('grep "*.* @%s:%s" /etc/rsyslog.d/50-default.conf  | wc -l' %(entries, SYSLOG_LOGPORT), capture=True)
                if syslog_present == '0':
                    local('echo "*.* @%s:%s" >> /etc/rsyslog.d/50-default.conf' %(entries, SYSLOG_LOGPORT))

            # find and replace syslog port in collector
            for entries, entry_token in zip(self._args.collector_hosts, self._args.collector_host_tokens):
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    syslog_port=run('grep "# syslog_port=-1" /etc/contrail/contrail-collector.conf | wc -l')
                    if syslog_port == '1':
                        run('cat /etc/contrail/contrail-collector.conf | sed "s/# syslog_port=-1/syslog_port=4514/" > /tmp/contrail-collector.conf; mv /tmp/contrail-collector.conf /etc/contrail/contrail-collector.conf')

                    syslog_port=run('grep "syslog_port=-1" /etc/contrail/contrail-collector.conf | wc -l')
                    if syslog_port == '1':
                        run('cat /etc/contrail/contrail-collector.conf | sed "s/syslog_port=-1/syslog_port=4514/" > /tmp/contrail-collector.conf; mv /tmp/contrail-collector.conf /etc/contrail/contrail-collector.conf')

                    # restart collector after syslog port change
                    run('service contrail-collector restart')

            # restart rsyslog service after remote logging enabled
            local('service rsyslog restart')

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

            #print ceph_pool_list
            if create_hdd_ssd_pool == 1:
                for pool_name in ceph_pool_list:
                    local('sudo ceph auth get-or-create client.%s mon \'allow r\' osd \'allow class-read object_prefix rbd_children, allow rwx pool=%s, allow rx pool=images\' -o /etc/ceph/client.%s.keyring' %(pool_name, pool_name, pool_name))
                    local('sudo openstack-config --set /etc/ceph/ceph.conf client.%s keyring /etc/ceph/client.%s.keyring' %(pool_name, pool_name))
                    for entries, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
                        if entries != self._args.storage_master:
                            with settings(host_string = 'root@%s' %(entries), password = entry_token):
                                run('unset CEPH_ARGS')
                                run('sudo ceph -k /etc/ceph/ceph.client.admin.keyring  auth get-or-create client.%s mon \'allow r\' osd \'allow class-read object_prefix rbd_children, allow rwx pool=%s, allow rx pool=images\' -o /etc/ceph/client.%s.keyring' %(pool_name, pool_name, pool_name))
                                run('sudo openstack-config --set /etc/ceph/ceph.conf client.%s keyring /etc/ceph/client.%s.keyring' %(pool_name, pool_name))
                    local('ceph-authtool -p -n client.%s /etc/ceph/client.%s.keyring > /etc/ceph/client.%s' %(pool_name, pool_name, pool_name))

            if pdist == 'centos':
                local('sudo service libvirtd restart')
            if pdist == 'Ubuntu':
                local('sudo service libvirt-bin restart')

            #Remove existing secret keys and Set the secret keys for Ceph authentication
            time.sleep(5)
            while True:
                virsh_unsecret=local('virsh secret-list  2>&1 | awk \'{print $1}\' | awk \'NR > 2 { print }\' | head -n 1', capture=True)
                if virsh_unsecret != "":
                    local('virsh secret-undefine %s' %(virsh_unsecret))
                else:
                    break

            local('echo "<secret ephemeral=\'no\' private=\'no\'>\n<usage type=\'ceph\'>\n<name>client.volumes secret</name>\n</usage>\n</secret>" > secret.xml')
            virsh_secret=local('virsh secret-define --file secret.xml  2>&1 |cut -d " " -f 2', capture=True)
            volume_keyring_list=local('cat /etc/ceph/client.volumes.keyring | grep key', capture=True)
            volume_keyring=volume_keyring_list.split(' ')[2]
            local('virsh secret-set-value %s --base64 %s' % (virsh_secret,volume_keyring))
            local('sudo service libvirt-bin restart')

            # Cinder configuration for rbd-disk for the default pools
            # Note: This may be required for older version of Ceph on Centos
            #rbd_configured=local('sudo cat /etc/cinder/cinder.conf |grep -v "\\[rbd-disk\\]"| wc -l', capture=True)
            #if rbd_configured == '0':
            #    local('sudo cat /etc/cinder/cinder.conf |grep -v "\\[rbd-disk\\]"| sed s/rbd-disk/"rbd-disk\\n\\n[rbd-disk]"/ > /etc/cinder/cinder.conf.bk')
            #    local('sudo cp /etc/cinder/cinder.conf.bk /etc/cinder/cinder.conf')
            local('sudo openstack-config --set /etc/cinder/cinder.conf rbd-disk volume_driver cinder.volume.drivers.rbd.RBDDriver')
            local('sudo openstack-config --set /etc/cinder/cinder.conf rbd-disk rbd_pool volumes')
            local('sudo openstack-config --set /etc/cinder/cinder.conf rbd-disk rbd_user volumes')
            local('sudo openstack-config --set /etc/cinder/cinder.conf rbd-disk rbd_secret_uuid %s' % (virsh_secret))
            local('sudo openstack-config --set /etc/cinder/cinder.conf rbd-disk glance_api_version 2')
            local('sudo openstack-config --set /etc/cinder/cinder.conf rbd-disk volume_backend_name RBD')

            if self._args.storage_os_hosts[0] != 'none':
                for entries, entry_token in zip(self._args.storage_os_hosts, self._args.storage_os_host_tokens):
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        run('sudo openstack-config --set /etc/cinder/cinder.conf rbd-disk volume_driver cinder.volume.drivers.rbd.RBDDriver')
                        run('sudo openstack-config --set /etc/cinder/cinder.conf rbd-disk rbd_pool volumes')
                        run('sudo openstack-config --set /etc/cinder/cinder.conf rbd-disk rbd_user volumes')
                        run('sudo openstack-config --set /etc/cinder/cinder.conf rbd-disk rbd_secret_uuid %s' % (virsh_secret))
                        run('sudo openstack-config --set /etc/cinder/cinder.conf rbd-disk glance_api_version 2')
                        run('sudo openstack-config --set /etc/cinder/cinder.conf rbd-disk volume_backend_name RBD')

            for entries, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
                if entries != self._args.storage_master:
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        if pdist == 'centos':
                            run('cat ~/.bashrc |grep -v CEPH_ARGS > /tmp/.bashrc')
                            run('mv -f /tmp/.bashrc ~/.bashrc')
                            run('echo export CEPH_ARGS=\\\\"--id volumes\\\\" >> ~/.bashrc')
                            run('. ~/.bashrc')
                            run('sudo ceph-authtool -p -n client.volumes /etc/ceph/client.volumes.keyring > /etc/ceph/client.volumes')
                            run('sudo service libvirtd restart')

                        if pdist == 'Ubuntu':
                            run('sudo ceph-authtool -p -n client.volumes /etc/ceph/client.volumes.keyring > /etc/ceph/client.volumes')
                            run('sudo service libvirt-bin restart')

                        while True:
                            virsh_unsecret=run('virsh secret-list  2>&1 | awk \'{print $1}\' | awk \'NR > 2 { print }\' | head -n 1')
                            if virsh_unsecret != "":
                                run('virsh secret-undefine %s' %(virsh_unsecret))
                            else:
                                break

                        run('echo "<secret ephemeral=\'no\' private=\'no\'>\n<uuid>%s</uuid><usage type=\'ceph\'>\n<name>client.volumes secret</name>\n</usage>\n</secret>" > secret.xml' % (virsh_secret))
                        run('virsh secret-define --file secret.xml')
                        run('virsh secret-set-value %s --base64 %s' % (virsh_secret,volume_keyring))

            # Cinder Backend Configuration
            if create_hdd_ssd_pool == 0:
                local('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT enabled_backends rbd-disk')
                if self._args.storage_os_hosts[0] != 'none':
                    for entries, entry_token in zip(self._args.storage_os_hosts, self._args.storage_os_host_tokens):
                        with settings(host_string = 'root@%s' %(entries), password = entry_token):
                            run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT enabled_backends rbd-disk')
            else:
                back_end = 'rbd-disk'
                for pool_name in ceph_pool_list:
                    back_end = back_end + ',' + ('rbd-%s-disk' %(pool_name))

                local('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT enabled_backends %s' %(back_end))
                if self._args.storage_os_hosts[0] != 'none':
                    for entries, entry_token in zip(self._args.storage_os_hosts, self._args.storage_os_host_tokens):
                        with settings(host_string = 'root@%s' %(entries), password = entry_token):
                            run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT enabled_backends %s' %(back_end))


            if create_hdd_ssd_pool == 1:
                for pool_name in ceph_pool_list:
                    local('echo "<secret ephemeral=\'no\' private=\'no\'>\n<usage type=\'ceph\'>\n<name>client.%s secret</name>\n</usage>\n</secret>" > secret_%s.xml' %(pool_name, pool_name))
                    virsh_secret=local('virsh secret-define --file secret_%s.xml  2>&1 |cut -d " " -f 2' %(pool_name), capture=True)
                    volume_keyring_list=local('cat /etc/ceph/client.%s.keyring | grep key' %(pool_name), capture=True)
                    volume_keyring=volume_keyring_list.split(' ')[2]
                    local('virsh secret-set-value %s --base64 %s' % (virsh_secret,volume_keyring))
                    # Cinder rbd-disk configuration for all the pools
                    local('sudo openstack-config --set /etc/cinder/cinder.conf rbd-%s-disk volume_driver cinder.volume.drivers.rbd.RBDDriver' %(pool_name))
                    local('sudo openstack-config --set /etc/cinder/cinder.conf rbd-%s-disk rbd_pool %s' %(pool_name, pool_name))
                    local('sudo openstack-config --set /etc/cinder/cinder.conf rbd-%s-disk rbd_user %s' %(pool_name, pool_name))
                    local('sudo openstack-config --set /etc/cinder/cinder.conf rbd-%s-disk rbd_secret_uuid %s' %(pool_name, virsh_secret))
                    local('sudo openstack-config --set /etc/cinder/cinder.conf rbd-%s-disk volume_backend_name %s' %(pool_name, pool_name.upper()))
                    if self._args.storage_os_hosts[0] != 'none':
                        for entries, entry_token in zip(self._args.storage_os_hosts, self._args.storage_os_host_tokens):
                            with settings(host_string = 'root@%s' %(entries), password = entry_token):
                                run('sudo openstack-config --set /etc/cinder/cinder.conf rbd-%s-disk volume_driver cinder.volume.drivers.rbd.RBDDriver' %(pool_name))
                                run('sudo openstack-config --set /etc/cinder/cinder.conf rbd-%s-disk rbd_pool %s' %(pool_name, pool_name))
                                run('sudo openstack-config --set /etc/cinder/cinder.conf rbd-%s-disk rbd_user %s' %(pool_name, pool_name))
                                run('sudo openstack-config --set /etc/cinder/cinder.conf rbd-%s-disk rbd_secret_uuid %s' %(pool_name, virsh_secret))
                                run('sudo openstack-config --set /etc/cinder/cinder.conf rbd-%s-disk volume_backend_name %s' %(pool_name, pool_name.upper()))
                    for entries, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
                        if entries != self._args.storage_master:
                            with settings(host_string = 'root@%s' %(entries), password = entry_token):
                                if pdist == 'centos':
                                    run('sudo ceph-authtool -p -n client.%s /etc/ceph/client.%s.keyring > /etc/ceph/client.%s' %(pool_name, pool_name, pool_name))
                                    run('sudo service libvirtd restart')

                                if pdist == 'Ubuntu':
                                    run('sudo ceph-authtool -p -n client.%s /etc/ceph/client.%s.keyring > /etc/ceph/client.%s' %(pool_name, pool_name, pool_name))
                                    run('sudo service libvirt-bin restart')

                                run('echo "<secret ephemeral=\'no\' private=\'no\'>\n<uuid>%s</uuid><usage type=\'ceph\'>\n<name>client.%s secret</name>\n</usage>\n</secret>" > secret_%s.xml' % (virsh_secret, pool_name, pool_name))
                                run('virsh secret-define --file secret_%s.xml' %(pool_name))
                                run('virsh secret-set-value %s --base64 %s' % (virsh_secret,volume_keyring))


        # Set mysql listen ip to 0.0.0.0, so cinder volume manager from all
        # nodes can access.
        if self._args.storage_local_disk_config[0] != 'none' or self._args.storage_local_ssd_disk_config[0] != 'none':
            local('sudo sed -i "s/^bind-address/#bind-address/" /etc/mysql/my.cnf')
            local('sudo service mysql restart')

        local('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT sql_connection mysql://cinder:cinder@127.0.0.1/cinder')
        #recently contrail changed listen address from 0.0.0.0 to mgmt address so adding mgmt network to rabbit host
        if self._args.cinder_vip != 'none':
            local('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT rabbit_host %s' %(self._args.cinder_vip))
            local('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT rabbit_port %s' %(RABBIT_PORT))
        else:
            local('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT rabbit_host %s' %(self._args.cfg_host))

        local('sudo cinder-manage db sync')
        if self._args.storage_os_hosts[0] != 'none':
            for entries, cfg_entry, entry_token in zip(self._args.storage_os_hosts, self._args.config_hosts, self._args.storage_os_host_tokens):
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT sql_connection mysql://cinder:cinder@127.0.0.1/cinder')
                    #recently contrail changed listen address from 0.0.0.0 to mgmt address so adding mgmt network to rabbit host
                    if self._args.cinder_vip != 'none':
                        run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT rabbit_host %s' %(self._args.cinder_vip))
                        run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT rabbit_port %s' %(RABBIT_PORT))
                    else:
                        run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT rabbit_host %s' %(self._args.cfg_host))
                    run('sudo cinder-manage db sync')

        cinder_lvm_type_list=[]
        cinder_lvm_name_list=[]
        #Create LVM volumes on each node
        if self._args.storage_local_disk_config[0] != 'none':
            for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    local_disk_list=''
                    for local_disks in self._args.storage_local_disk_config:
                        disksplit = local_disks.split(':')
                        if disksplit[0] == hostname:
                            local_disk_list = local_disk_list + disksplit[1] + ' '
                            run('sudo dd if=/dev/zero of=%s bs=512 count=1' %(disksplit[1]))
                    if local_disk_list != '':
                        if entries != self._args.storage_master:
                            run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT sql_connection mysql://cinder:cinder@%s/cinder' %(self._args.storage_master))
                            if self._args.cinder_vip != 'none':
                                run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT rabbit_host %s' %(self._args.cinder_vip))
                                run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT rabbit_port %s' %(RABBIT_PORT))
                            else:
                                run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT rabbit_host %s' %(self._args.cfg_host))
                            run('sudo cinder-manage db sync')
                        existing_backends=run('sudo cat /etc/cinder/cinder.conf |grep enabled_backends |awk \'{print $3}\'', shell='/bin/bash')
                        if existing_backends != '':
                            new_backend = existing_backends + ',' + 'lvm-local-disk-volumes'
                        else:
                            new_backend = 'lvm-local-disk-volumes'
                        run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT enabled_backends %s' %(new_backend))
                        run('sudo pvcreate %s' %(local_disk_list))
                        run('sudo vgcreate ocs-lvm-group %s' %(local_disk_list))
                        run('sudo openstack-config --set /etc/cinder/cinder.conf lvm-local-disk-volumes volume_group ocs-lvm-group')
                        run('sudo openstack-config --set /etc/cinder/cinder.conf lvm-local-disk-volumes volume_driver cinder.volume.drivers.lvm.LVMISCSIDriver')
                        run('sudo openstack-config --set /etc/cinder/cinder.conf lvm-local-disk-volumes volume_backend_name OCS_LVM_%s' %(hostname))
                        cinder_lvm_type_list.append('ocs-block-lvm-disk-%s' %(hostname))
                        cinder_lvm_name_list.append('OCS_LVM_%s' %(hostname))

        #Create LVM volumes for SSD disks on each node
        if self._args.storage_local_ssd_disk_config[0] != 'none':
            for hostname, entries, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    local_ssd_disk_list=''
                    for local_ssd_disks in self._args.storage_local_ssd_disk_config:
                        disksplit = local_ssd_disks.split(':')
                        if disksplit[0] == hostname:
                            local_ssd_disk_list = local_ssd_disk_list + disksplit[1] + ' '
                            run('sudo dd if=/dev/zero of=%s bs=512 count=1' %(disksplit[1]))
                    if local_ssd_disk_list != '':
                        if entries != self._args.storage_master:
                            run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT sql_connection mysql://cinder:cinder@%s/cinder' %(self._args.storage_master))
                            if self._args.cinder_vip != 'none':
                                run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT rabbit_host %s' %(self._args.cinder_vip))
                                run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT rabbit_port %s' %(RABBIT_PORT))
                            else:
                                run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT rabbit_host %s' %(self._args.cfg_host))
                            run('sudo cinder-manage db sync')
                        existing_backends=run('sudo cat /etc/cinder/cinder.conf |grep enabled_backends |awk \'{print $3}\'', shell='/bin/bash')
                        if existing_backends != '':
                            new_backend = existing_backends + ',' + 'lvm-local-ssd-disk-volumes'
                        else:
                            new_backend = 'lvm-local-ssd-disk-volumes'
                        run('sudo openstack-config --set /etc/cinder/cinder.conf DEFAULT enabled_backends %s' %(new_backend))
                        run('sudo pvcreate %s' %(local_ssd_disk_list))
                        run('sudo vgcreate ocs-lvm-ssd-group %s' %(local_ssd_disk_list))
                        run('sudo openstack-config --set /etc/cinder/cinder.conf lvm-local-ssd-disk-volumes volume_group ocs-lvm-ssd-group')
                        run('sudo openstack-config --set /etc/cinder/cinder.conf lvm-local-ssd-disk-volumes volume_driver cinder.volume.drivers.lvm.LVMISCSIDriver')
                        run('sudo openstack-config --set /etc/cinder/cinder.conf lvm-local-ssd-disk-volumes volume_backend_name OCS_LVM_SSD_%s' %(hostname))
                        cinder_lvm_type_list.append('ocs-block-lvm-ssd-disk-%s' %(hostname))
                        cinder_lvm_name_list.append('OCS_LVM_SSD_%s' %(hostname))

        #Cinder/Nova/Glance Configurations
        admin_pass = local('cat /etc/cinder/cinder.conf | grep admin_password | cut -d "=" -f 2', capture=True)
        for entries, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
            if entries != self._args.storage_master:
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    if configure_with_ceph == 1:
                        # Remove rbd_user configurations from nova if present
                        run('sudo openstack-config --del /etc/nova/nova.conf DEFAULT rbd_user')
                        run('sudo openstack-config --del /etc/nova/nova.conf DEFAULT rbd_secret_uuid')
                        # This should not be set for multi-backend. The virsh secret setting itself is enough for correct authentication.
                        #run('sudo openstack-config --set /etc/nova/nova.conf DEFAULT rbd_user volumes')
                        #run('sudo openstack-config --set /etc/nova/nova.conf DEFAULT rbd_secret_uuid %s' % (virsh_secret))
                    if self._args.cinder_vip != 'none':
                        run('sudo openstack-config --set /etc/nova/nova.conf DEFAULT cinder_endpoint_template "http://%s:8776/v1/%%(project_id)s"' % (self._args.cinder_vip), shell='/bin/bash')
                    else:
                        run('sudo openstack-config --set /etc/nova/nova.conf DEFAULT cinder_endpoint_template "http://%s:8776/v1/%%(project_id)s"' % (self._args.storage_master), shell='/bin/bash')

        if configure_with_ceph == 1:
            #Glance configuration
            local('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT default_store rbd')
            local('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT show_image_direct_url True')
            local('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT rbd_store_user images')
            local('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT workers 120')
            local('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT rbd_store_chunk_size 8')
            local('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT rbd_store_pool images')
            local('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT rbd_store_ceph_conf /etc/ceph/ceph.conf')
            if self._args.storage_os_hosts[0] != 'none':
                for entries, entry_token in zip(self._args.storage_os_hosts, self._args.storage_os_host_tokens):
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        run('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT default_store rbd')
                        run('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT show_image_direct_url True')
                        run('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT rbd_store_user images')
                        run('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT workers 120')
                        run('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT rbd_store_chunk_size 8')
                        run('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT rbd_store_pool images')
                        run('sudo openstack-config --set /etc/glance/glance-api.conf DEFAULT rbd_store_ceph_conf /etc/ceph/ceph.conf')

        # Add NFS configurations if present
        create_nfs_disk_volume = 0
        if self._args.storage_nfs_disk_config[0] != 'none':
            self.add_nfs_disk_config()
            create_nfs_disk_volume = 1

        #Restart services
        if pdist == 'centos':
            local('sudo service qpidd restart')
            local('sudo service quantum-server restart')
            local('sudo chkconfig openstack-cinder-api on')
            local('sudo service openstack-cinder-api restart')
            local('sudo chkconfig openstack-cinder-scheduler on')
            local('sudo service openstack-cinder-scheduler restart')
            if configure_with_ceph == 1:
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
            if configure_with_ceph == 1:
                bash_cephargs = local('grep "CEPH_ARGS" /etc/init.d/cinder-volume | wc -l', capture=True)
                #print bash_cephargs
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
            if self._args.storage_os_hosts[0] != 'none':
                for entries, entry_token in zip(self._args.storage_os_hosts, self._args.storage_os_host_tokens):
                    with settings(host_string = 'root@%s' %(entries), password = entry_token):
                        run('sudo chkconfig cinder-api on')
                        run('sudo service cinder-api restart')
                        run('sudo chkconfig cinder-scheduler on')
                        run('sudo service cinder-scheduler restart')
                        if configure_with_ceph == 1:
                            bash_cephargs = run('grep "CEPH_ARGS" /etc/init.d/cinder-volume | wc -l')
                            #print bash_cephargs
                            if bash_cephargs == "0":
                                run('cat /etc/init.d/cinder-volume | awk \'{ print; if ($1== "start|stop)") print \"    CEPH_ARGS=\\\\"--id volumes\\\\"\" }\' > /tmp/cinder-volume.tmp')
                                run('mv -f /tmp/cinder-volume.tmp /etc/init.d/cinder-volume; chmod a+x /etc/init.d/cinder-volume')
                        run('sudo chkconfig cinder-volume on')
                        run('sudo service cinder-volume restart')
                        run('sudo service glance-api restart')
                        run('sudo service nova-api restart')
                        run('sudo service nova-conductor restart')
                        run('sudo service nova-scheduler restart')
                        run('sudo service libvirt-bin restart')
                        run('sudo service nova-api restart')
                        run('sudo service nova-scheduler restart')


        # Create Cinder type for all Ceph backend
        if configure_with_ceph == 1:
            local('(. /etc/contrail/openstackrc ; cinder type-create ocs-block-disk)')
            local('(. /etc/contrail/openstackrc ; cinder type-key ocs-block-disk set volume_backend_name=RBD)')

        if create_hdd_ssd_pool == 1:
            for pool_name in ceph_pool_list:
                # use the hdd-'pool name' (strip volumes_ from volumes_hdd/volumes_ssd/volumes_hdd_Pool_mypool/volumes_ssd_Pool_myssdpool)
                local('(. /etc/contrail/openstackrc ; cinder type-create ocs-block-%s-disk)' %(pool_name[8:]))
                local('(. /etc/contrail/openstackrc ; cinder type-key ocs-block-%s-disk set volume_backend_name=%s)' %(pool_name[8:], pool_name.upper()))

        if create_nfs_disk_volume == 1:
            local('(. /etc/contrail/openstackrc ; cinder type-create ocs-block-nfs-disk)')
            local('(. /etc/contrail/openstackrc ; cinder type-key ocs-block-nfs-disk set volume_backend_name=NFS)')

        # Create Cinder type for all the LVM backends
        for lvm_types, lvm_names in zip(cinder_lvm_type_list, cinder_lvm_name_list):
            local('(. /etc/contrail/openstackrc ; cinder type-create %s)' %(lvm_types))
            local('(. /etc/contrail/openstackrc ; cinder type-key %s set volume_backend_name=%s)' %(lvm_types, lvm_names))
        local('sudo service cinder-volume restart')

        if configure_with_ceph == 1:
            avail=local('rados df | grep avail | awk  \'{ print $3 }\'', capture = True)
            # use only half the space as 1 replica is enabled
            avail_gb = int(avail)/1024/1024/2
            local('(. /etc/contrail/openstackrc ; cinder quota-update ocs-block-disk --gigabytes %s)' % (avail_gb))
            #local('(. /etc/contrail/openstackrc ; cinder quota-update ocs-block-disk --gigabytes 1000)')
            local('(. /etc/contrail/openstackrc ; cinder quota-update ocs-block-disk --volumes 100)')
            local('(. /etc/contrail/openstackrc ; cinder quota-update ocs-block-disk --snapshots 100)')
        for entries, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
            isos= 0
            if self._args.storage_os_hosts[0] != 'none':
                for os_entries in self._args.storage_os_hosts:
                    if os_entries == entries:
                        isos = 1
                        break

            if isos == 1:
                continue
            if entries != self._args.storage_master:
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    if pdist == 'centos':
                        run('sudo chkconfig tgt on')
                        run('sudo service tgt restart')
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
                        run('sudo chkconfig tgt on')
                        run('sudo service tgt restart')
                        run('sudo chkconfig cinder-volume on')
                        run('sudo service cinder-volume restart')
                        run('sudo service libvirt-bin restart')
                        run('sudo service nova-compute restart')

        # start contrail-storage-stats daemon on all storage-compute nodes
        for entries, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
            isos= 0
            # skip all storage-master nodes
            if self._args.storage_os_hosts[0] != 'none':
                for os_entries in self._args.storage_os_hosts:
                    if os_entries == entries:
                        isos = 1
                        break

            if isos == 1:
                continue
            # skip first storage-master node
            if entries != self._args.storage_master :
                with settings(host_string = 'root@%s' %(entries), password = entry_token):
                    if pdist == 'Ubuntu':
                        run('sudo openstack-config --set /etc/contrail/contrail-storage-nodemgr.conf DEFAULTS disc_server_ip %s' %(self._args.cfg_host))
                        run('sudo service contrail-storage-stats restart')

        if pdist == 'Ubuntu':
            self.ceph_rest_api_service_add()

    #end __init__

    def _parse_args(self, args_str):
        '''
        Eg. python storage-ceph-setup.py --storage-master 10.157.43.171 --storage-hostnames cmbu-dt05 cmbu-ixs6-2 --storage-hosts 10.157.43.171 10.157.42.166 --storage-host-tokens n1keenA n1keenA --storage-disk-config 10.157.43.171:sde 10.157.43.171:sdf 10.157.43.171:sdg --storage-directory-config 10.157.42.166:/mnt/osd0 --storage-chassis-config 10.157.42.166:0 10.157.42.167:1 --live-migration enabled
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
        parser.add_argument("--storage-setup-mode", help = "Storage configuration mode")

        self._args = parser.parse_args(remaining_argv)

    #end _parse_args

#end class SetupCeph

def main(args_str = None):
    SetupCeph(args_str)
#end main

if __name__ == "__main__":
    main()
