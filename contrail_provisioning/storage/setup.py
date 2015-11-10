#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import ConfigParser

from fabric.api import run
from fabric.context_managers import settings

from contrail_provisioning.common.base import ContrailSetup


class StorageSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(StorageSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.global_defaults = {
            'storage_master': '127.0.0.1',
        }
        self.parse_args(args_str)


    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-storage --storage-master 10.157.43.171
                --storage-hostnames cmbu-dt05 cmbu-ixs6-2
                --storage-hosts 10.157.43.171 10.157.42.166
                --storage-host-tokens n1keenA n1keenA
                --storage-disk-config 10.157.43.171:sde 10.157.43.171:sdf 10.157.43.171:sdg
                --storage-directory-config 10.157.42.166:/mnt/osd0
                --live-migration enabled
                --storage-chassis-config 10.157.43.171:T0 10.157.43.172:T0 10.157.43.173:T1 157.43.174:T2
                --collector-hosts 10.157.43.171 10.157.42.166
                --collector-host-tokens n1keenA n1keenA
                --cfg-host 10.157.43.171
                --storage-compute-hostnames cmbu-dt05 cmbu-ixs6-2
        '''

        parser = self._parse_args(args_str)

        parser.add_argument("--storage-master", help = "IP Address of storage master node")
        parser.add_argument("--storage-hostnames", help = "Host names of storage nodes", nargs='+', type=str)
        parser.add_argument("--storage-compute-hostnames", help = "Host names of storage compute nodes", nargs='+', type=str)
        parser.add_argument("--storage-hosts", help = "IP Addresses of storage nodes", nargs='+', type=str)
        parser.add_argument("--storage-host-tokens", help = "Passwords of storage nodes", nargs='+', type=str)
        parser.add_argument("--storage-disk-config", help = "Disk list to be used for distributed storage", nargs="+", type=str)
        parser.add_argument("--storage-ssd-disk-config", help = "SSD Disk list to be used for distributed storage", nargs="+", type=str)
        parser.add_argument("--storage-local-disk-config", help = "Disk list to be used for local storage", nargs="+", type=str)
        parser.add_argument("--storage-local-ssd-disk-config", help = "SSD Disk list to be used for local storage", nargs="+", type=str)
        parser.add_argument("--storage-nfs-disk-config", help = "Disk list to be used for nfs storage", nargs="+", type=str)
        parser.add_argument("--storage-journal-config", help = "Disk list to be used for distributed storage journal", nargs="+", type=str)
        parser.add_argument("--storage-directory-config", help = "Directories to be sued for distributed storage", nargs="+", type=str)
        parser.add_argument("--storage-chassis-config", help = "Chassis ID for the host to avoid replication between nodes in the same chassis", nargs="+", type=str)
        parser.add_argument("--cfg-vip", help = "cfg vip")
        parser.add_argument("--live-migration", help = "Live migration enabled")
        parser.add_argument("--collector-hosts", help = "IP Addresses of collector nodes", nargs='+', type=str)
        parser.add_argument("--collector-host-tokens", help = "Passwords of collector nodes", nargs='+', type=str)
        parser.add_argument("--cfg-host", help = "IP Address of config node")
        parser.add_argument("--cinder-vip", help = "Cinder vip")
        parser.add_argument("--config-hosts", help = "config host list", nargs='+', type=str)
        parser.add_argument("--storage-mon-hosts", help = "storage compute mon list", nargs='+', type=str)
        parser.add_argument("--storage-os-hosts", help = "storage openstack host list", nargs='+', type=str)
        parser.add_argument("--storage-os-host-tokens", help = "storage openstack host pass list", nargs='+', type=str)
        parser.add_argument("--add-storage-node", help = "Add a new storage node to the existing cluster")
        parser.add_argument("--storage-setup-mode", help = "Configuration mode")
        parser.add_argument("--disks-to-remove", help = "Disks to remove", nargs="+", type=str)
        parser.add_argument("--hosts-to-remove", help = "Hosts to remove", nargs="+", type=str)
        parser.add_argument("--storage-replica-size", help = "Replica size")
        parser.add_argument("--openstack-ip", help = "Openstack node ip")
        parser.add_argument("--orig-hostnames", help = "Actual Host names of storage nodes", nargs='+', type=str)


        self._args = parser.parse_args(self.remaining_argv)

    def setup(self):
        #Setup storage if storage is defined in testbed.py
        if (self._args.storage_disk_config[0] != 'none' or
            self._args.storage_directory_config[0] != 'none' or
            self._args.storage_local_disk_config[0] != 'none' or
            self._args.storage_nfs_disk_config[0] != 'none' or
            self._args.storage_local_ssd_disk_config[0] != 'none' or
            self._args.storage_ssd_disk_config[0] != 'none'):
            self.enable_storage()

    def enable_storage(self):
        # Storage Configurations
        # Setup Ceph services
        storage_setup_args = " --storage-master %s" %(self._args.storage_master)
        storage_setup_args = storage_setup_args + " --storage-setup-mode %s" % (self._args.storage_setup_mode)
        if self._args.add_storage_node:
            storage_setup_args = storage_setup_args + " --add-storage-node %s" % (self._args.add_storage_node)
        storage_setup_args = storage_setup_args + " --storage-hostnames %s" %(' '.join(self._args.storage_hostnames))
        storage_setup_args = storage_setup_args + " --storage-compute-hostnames %s" %(' '.join(self._args.storage_compute_hostnames))
        storage_setup_args = storage_setup_args + " --storage-hosts %s" %(' '.join(self._args.storage_hosts))
        storage_setup_args = storage_setup_args + " --storage-host-tokens %s" %(' '.join(self._args.storage_host_tokens))
        storage_setup_args = storage_setup_args + " --storage-disk-config %s" %(' '.join(self._args.storage_disk_config))
        storage_setup_args = storage_setup_args + " --storage-ssd-disk-config %s" %(' '.join(self._args.storage_ssd_disk_config))
        storage_setup_args = storage_setup_args + " --storage-journal-config %s" %(' '.join(self._args.storage_journal_config))
        storage_setup_args = storage_setup_args + " --storage-local-disk-config %s" %(' '.join(self._args.storage_local_disk_config))
        storage_setup_args = storage_setup_args + " --storage-local-ssd-disk-config %s" %(' '.join(self._args.storage_local_ssd_disk_config))
        storage_setup_args = storage_setup_args + " --storage-nfs-disk-config %s" %(' '.join(self._args.storage_nfs_disk_config))
        storage_setup_args = storage_setup_args + " --storage-directory-config %s" %(' '.join(self._args.storage_directory_config))
        storage_setup_args = storage_setup_args + " --storage-chassis-config %s" %(' '.join(self._args.storage_chassis_config))
        storage_setup_args = storage_setup_args + " --storage-mon-hosts %s" %(' '.join(self._args.storage_mon_hosts))
        if self._args.collector_hosts:
            storage_setup_args = storage_setup_args + " --collector-hosts %s" %(' '.join(self._args.collector_hosts))
            storage_setup_args = storage_setup_args + " --collector-host-tokens %s" %(' '.join(self._args.collector_host_tokens))
        if self._args.cfg_host:
            storage_setup_args = storage_setup_args + " --cfg-host %s" % (self._args.cfg_host)
        for storage_host, storage_host_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
            if storage_host == self._args.storage_master:
                storage_master_passwd = storage_host_token

        if self._args.cinder_vip:
            storage_setup_args = storage_setup_args + " --cinder-vip %s" %(self._args.cinder_vip)

        if self._args.config_hosts:
            storage_setup_args = storage_setup_args + " --config-hosts %s" %(' '.join(self._args.config_hosts))

        if self._args.storage_os_hosts:
            storage_setup_args = storage_setup_args + " --storage-os-hosts %s" %(' '.join(self._args.storage_os_hosts))
            storage_setup_args = storage_setup_args + " --storage-os-host-tokens %s" %(' '.join(self._args.storage_os_host_tokens))

        if self._args.cfg_vip:
            storage_setup_args = storage_setup_args + " --cfg-vip %s" %(self._args.cfg_vip)

        if self._args.disks_to_remove:
            storage_setup_args = storage_setup_args + " --disks-to-remove %s" %(' '.join(self._args.disks_to_remove))

        if self._args.hosts_to_remove:
            storage_setup_args = storage_setup_args + " --hosts-to-remove %s" %(' '.join(self._args.hosts_to_remove))
        storage_setup_args = storage_setup_args + " --storage-replica-size %s" %(self._args.storage_replica_size)
        storage_setup_args = storage_setup_args + " --openstack-ip %s" %(self._args.openstack_ip)
        storage_setup_args = storage_setup_args + " --orig-hostnames %s" %(' '.join(self._args.orig_hostnames))

        #Setup storage if storage is defined in testbed.py
        with settings(host_string=self._args.storage_master, password=storage_master_passwd):
            run("sudo storage-fs-setup %s" %(storage_setup_args))

def main(args_str = None):
    storage = StorageSetup(args_str)
    storage.setup()

if __name__ == "__main__":
    main()
