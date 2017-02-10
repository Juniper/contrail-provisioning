#!/usr/bin/python
import argparse
import ConfigParser

import os
import sys
import subprocess
from pprint import pformat

from fabric.api import local, env, run
from fabric.operations import get, put
from fabric.context_managers import lcd, settings
sys.path.insert(0, os.getcwd())

# set livemigration configurations in nova and libvirtd
class SetupLivem(object):

    def __init__(self, args_str = None):
        #print sys.argv[1:]
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])
        self._parse_args(args_str)

        if self._args.storage_setup_mode == 'unconfigure':
            return

        NOVA_CONF='/etc/nova/nova.conf'
        LIBVIRTD_CONF='/etc/libvirt/libvirtd.conf'
        LIBVIRTD_TMP_CONF='/tmp/libvirtd.conf'
        LIBVIRTD_CENTOS_BIN_CONF='/etc/sysconfig/libvirtd'
        LIBVIRTD_UBUNTU_BIN_CONF='/etc/default/libvirt-bin'
        LIBVIRTD_UBUNTU_INIT_CONF='/etc/init/libvirt-bin.conf'
        LIBVIRTD_TMP_BIN_CONF='/tmp/libvirtd.tmp'
        LIBVIRTD_TMP_INIT_CONF='/tmp/libvirt-bin.conf'

        for hostname, entry, entry_token in zip(self._args.storage_hostnames, self._args.storage_hosts, self._args.storage_host_tokens):
           with settings(host_string = 'root@%s' %(entry), password = entry_token):
               run('openstack-config --set %s DEFAULT live_migration_flag VIR_MIGRATE_UNDEFINE_SOURCE,VIR_MIGRATE_PEER2PEER,VIR_MIGRATE_LIVE' %(NOVA_CONF))
               run('openstack-config --set %s DEFAULT vncserver_listen 0.0.0.0' %(NOVA_CONF))
               run('cat %s | sed s/"#listen_tls = 0"/"listen_tls = 0"/ | sed s/"#listen_tcp = 1"/"listen_tcp = 1"/ | sed s/\'#auth_tcp = "sasl"\'/\'auth_tcp = "none"\'/ > %s' %(LIBVIRTD_CONF, LIBVIRTD_TMP_CONF), shell='/bin/bash')
               run('cp -f %s %s' %(LIBVIRTD_TMP_CONF, LIBVIRTD_CONF))
               libvirtd = run('ls %s 2>/dev/null |wc -l' %(LIBVIRTD_CENTOS_BIN_CONF))
               if libvirtd != '0':
                   run('cat %s | sed s/"#LIBVIRTD_ARGS=\"--listen\""/"LIBVIRTD_ARGS=\"--listen\""/ > %s' %(LIBVIRTD_CENTOS_BIN_CONF, LIBVIRTD_TMP_BIN_CONF), shell='/bin/bash')
                   run('cp -f %s %s' %(LIBVIRTD_TMP_BIN_CONF, LIBVIRTD_CENTOS_BIN_CONF))
                   run('service openstack-nova-compute restart')
                   run('service libvirtd restart')

               libvirtd = run('ls %s 2>/dev/null |wc -l' %(LIBVIRTD_UBUNTU_BIN_CONF))
               if libvirtd != '0':
                   libvirt_configured = run('cat %s |grep "\-d \-l"| wc -l' %(LIBVIRTD_UBUNTU_BIN_CONF))
                   if libvirt_configured == '0':
                       run('cat %s | sed s/"-d"/"-d -l"/ > %s' %(LIBVIRTD_UBUNTU_BIN_CONF, LIBVIRTD_TMP_BIN_CONF), shell='/bin/bash')
                       libvirt_enabled = run('cat %s |grep "^libvirtd_opts"| wc -l' %(LIBVIRTD_UBUNTU_BIN_CONF))
                       if libvirt_enabled == '0':
                           run('echo \'libvirtd_opts="-l"\' >> %s' %(LIBVIRTD_TMP_BIN_CONF))
                       #else:
                       #Handle other cases
                       run('cp -f %s %s' %(LIBVIRTD_TMP_BIN_CONF, LIBVIRTD_UBUNTU_BIN_CONF))
                       run('service nova-compute restart')
                       run('service libvirt-bin restart')

               libvirtd = run('ls %s 2>/dev/null |wc -l' %(LIBVIRTD_UBUNTU_INIT_CONF))
               if libvirtd != '0':
                   libvirt_configured = run('cat %s |grep "\-d \-l"| wc -l' %(LIBVIRTD_UBUNTU_INIT_CONF))
                   if libvirt_configured == '0':
                       run('cat %s | sed s/"-d"/"-d -l"/ > %s' %(LIBVIRTD_UBUNTU_INIT_CONF, LIBVIRTD_TMP_INIT_CONF), shell='/bin/bash')
                       run('cp -f %s %s' %(LIBVIRTD_TMP_INIT_CONF, LIBVIRTD_UBUNTU_INIT_CONF))
                       run('service nova-compute restart')
                       run('service libvirt-bin restart')

        # Fix nova uid
        if self._args.fix_nova_uid == 'enabled':
            uid_fix_nodes = []
            uid_fix_node_tokens = []

            #Form a list of all hosts and host_tokens
            for entry, entry_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
                uid_fix_nodes.append(entry)
                uid_fix_node_tokens.append(entry_token)
            #uid_fix_nodes.append(self._args.storage_master)
            #uid_fix_node_tokens.append(self._args.storage_master_token)
            if self._args.storage_os_hosts[0] != 'none':
                for entry, entry_token in zip(self._args.storage_os_hosts,
                                                self._args.storage_os_host_tokens):
                    uid_fix_nodes.append(entry)
                    uid_fix_node_tokens.append(entry_token)

            with settings(host_string = 'root@%s' %(uid_fix_nodes[0]),
                            password = uid_fix_node_tokens[0]):
                nova_id = run('sudo id -u nova')
                qemu_id = run('sudo id -u libvirt-qemu')
            uid_fix_required = 0

            #Check if nova/libvirt uid is different in each node
            for entry, entry_token in zip(uid_fix_nodes,
                                                uid_fix_node_tokens):
                with settings(host_string = 'root@%s' %(entry), password = entry_token):
                    nova_id_check = run('sudo id -u nova')
                    qemu_id_check = run('sudo id -u libvirt-qemu')
                    if nova_id != nova_id_check or \
                        qemu_id != qemu_id_check:
                        uid_fix_required = 1
                        break
            if uid_fix_required == 0:
                return

            new_nova_uid = 500
            new_nova_gid = 500

            new_qemu_uid = 501
            new_qemu_gid = 501

            # Start from 500 and find the id that is not used in the system
            while True:
                recheck = 0
                for entry, entry_token in zip(uid_fix_nodes,
                                                uid_fix_node_tokens):
                    with settings(host_string = 'root@%s' %(entry),
                                    password = entry_token):
                        id_check = run('sudo cat /etc/passwd | \
                                                cut -d \':\' -f 3 | \
                                                grep -w %d | wc -l'
                                                %(new_nova_uid))
                        if id_check != '0':
                            new_nova_uid += 1
                            new_qemu_uid += 1
                            recheck = 1
                        id_check = run('sudo cat /etc/passwd | \
                                                cut -d \':\' -f 3 | \
                                                grep -w %d | wc -l'
                                                %(new_qemu_uid))
                        if id_check != '0':
                            new_nova_uid += 1
                            new_qemu_uid += 1
                            recheck = 1
                        id_check = run('sudo cat /etc/group | \
                                                cut -d \':\' -f 3 | \
                                                grep -w %d | wc -l'
                                                %(new_nova_gid))
                        if id_check != '0':
                            new_nova_gid += 1
                            new_qemu_gid += 1
                            recheck = 1
                        id_check = run('sudo cat /etc/group | \
                                                cut -d \':\' -f 3 | \
                                                grep -w %d | wc -l'
                                                %(new_qemu_gid))
                        if id_check != '0':
                            new_nova_gid += 1
                            new_qemu_gid += 1
                            recheck = 1
                        if recheck == 1:
                            break
                if recheck == 0:
                    break

            # Stop nova services
            # Change nova/libvirt uid and gid.
            # Chown/chgrp on all the files from old uid/gid to new uid/gid
            # Start nova services back
            for entry, entry_token in zip(uid_fix_nodes,
                                                uid_fix_node_tokens):
                with settings(host_string = 'root@%s' %(entry), password = entry_token):
                    nova_services = []
                    services = run('ps -Af | grep nova | grep -v grep | \
                                    awk \'{print $9}\' | cut -d \'/\' -f 4 | \
                                    grep nova | uniq -d')
                    for service in services.split('\r\n'):
                        if service != '':
                            nova_services.append(service)
                    services = run('ps -Af | grep nova | grep -v grep | \
                                    awk \'{print $9}\' | cut -d \'/\' -f 4 | \
                                    grep nova | uniq -u')
                    for service in services.split('\r\n'):
                        if service != '':
                            nova_services.append(service)

                    print nova_services

                    for service in nova_services:
                        if service[0] != '':
                            run('service %s stop' %(service))
                    cur_nova_uid = run('sudo id -u nova')
                    cur_qemu_uid = run('sudo id -u libvirt-qemu')
                    cur_nova_gid = run('sudo id -g nova')
                    cur_qemu_gid = run('sudo id -g libvirt-qemu')
                    run('sudo usermod -u %d nova' %(new_nova_uid))
                    run('sudo groupmod -g %d nova' %(new_nova_gid))
                    run('sudo usermod -u %d libvirt-qemu' %(new_qemu_uid))
                    run('sudo groupmod -g %d kvm' %(new_qemu_gid))
                    run('sudo find / -uid %s -exec chown nova {} \; 2> /dev/null; echo done'
                                                        %(cur_nova_uid))
                    run('sudo find / -gid %s -exec chgrp nova {} \; 2> /dev/null; echo done'
                                                        %(cur_nova_gid))
                    run('sudo find / -uid %s -exec chown libvirt-qemu {} \; 2> /dev/null; echo done'
                                                        %(cur_qemu_uid))
                    run('sudo find / -gid %s -exec chgrp kvm {} \; 2> /dev/null; echo done'
                                                        %(cur_qemu_gid))
                    for service in nova_services:
                        if service[0] != '':
                            run('service %s start' %(service))
                    run('service libvirt-bin restart')

            return

    def _parse_args(self, args_str):
        '''
        Eg. compute-live-migration-setup --storage-master 10.157.43.171 --storage-hostnames cmbu-dt05 cmbu-ixs6-2 --storage-hosts 10.157.43.171 10.157.42.166 --storage-host-tokens n1keenA n1keenA 
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
        parser.add_argument("--storage-master-token", help = "password of storage master node")
        parser.add_argument("--storage-hostnames", help = "Host names of storage nodes", nargs='+', type=str)
        parser.add_argument("--storage-hosts", help = "IP Addresses of storage nodes", nargs='+', type=str)
        parser.add_argument("--storage-host-tokens", help = "Passwords of storage nodes", nargs='+', type=str)
        parser.add_argument("--add-storage-node", help = "Add a new storage node")
        parser.add_argument("--storage-setup-mode", help = "Storage configuration mode")
        parser.add_argument("--storage-os-hosts", help = "Host names of openstack nodes other than master", nargs='+', type=str)
        parser.add_argument("--storage-os-host-tokens", help = "passwords of openstack nodes other than master", nargs='+', type=str)
        parser.add_argument("--fix-nova-uid", help = "Enable/disable uid fix")

        self._args = parser.parse_args(remaining_argv)

    #end _parse_args

def main(args_str = None):
    SetupLivem(args_str)
#end main

if __name__ == "__main__":
    main() 
