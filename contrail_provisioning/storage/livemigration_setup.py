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


class LiveMigrationSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(LiveMigrationSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.global_defaults = {
            'storage_master': '127.0.0.1',
        }
        self.parse_args(args_str)


    def parse_args(self, args_str):
        '''
        Eg. python setup-vnc-storage.py --storage-master 10.157.43.171
            --storage-hostnames cmbu-dt05 cmbu-ixs6-2
            --storage-hosts 10.157.43.171 10.157.42.166
            --storage-host-tokens n1keenA n1keenA
            --storage-disk-config 10.157.43.171:sde 10.157.43.171:sdf 10.157.43.171:sdg
            --storage-directory-config 10.157.42.166:/mnt/osd0
            --live-migration enabled
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--storage-master", help = "IP Address of storage master node")
        parser.add_argument("--storage-master-token", help = "password of storage master node")
        parser.add_argument("--storage-hostnames", help = "Host names of storage nodes", nargs='+', type=str)
        parser.add_argument("--storage-hosts", help = "IP Addresses of storage nodes", nargs='+', type=str)
        parser.add_argument("--storage-host-tokens", help = "Passwords of storage nodes", nargs='+', type=str)
        parser.add_argument("--storage-disk-config", help = "Disk list to be used for distrubuted storage", nargs="+", type=str)
        parser.add_argument("--storage-directory-config", help = "Directories to be sued for distributed storage", nargs="+", type=str)
        parser.add_argument("--live-migration", help = "Live migration enabled")
        parser.add_argument("--nfs-live-migration", help = "NFS for Live migration enabled")
        parser.add_argument("--nfs-livem-subnet", help = "Subnet for the NFS Live migration VM", nargs="+", type=str)
        parser.add_argument("--nfs-livem-image", help = "Image for the NFS Live migration VM", nargs="+", type=str)
        parser.add_argument("--nfs-livem-host", help = "Image for the NFS Live migration VM", nargs="+", type=str)
        parser.add_argument("--nfs-livem-mount", help = "mount point of external NFS server", nargs="+", type=str)
        parser.add_argument("--storage-setup-mode", help = "Storage configuration mode")
        parser.add_argument("--storage-os-hosts", help = "Host names of openstack nodes other than master", nargs='+', type=str)
        parser.add_argument("--storage-os-host-tokens", help = "passwords of openstack nodes other than master", nargs='+', type=str)
        parser.add_argument("--fix-nova-uid", help = "Enable/disable uid fix")
        parser.add_argument("--live-migration-scope", help = "live-migration scope")

        self._args = parser.parse_args(self.remaining_argv)


    def setup(self):
        self.enable_openstack_live_migration()
        self.enable_nfs_live_migration()

    def enable_nfs_live_migration(self):
        if self._args.nfs_live_migration == 'enabled':
            # Live migration NFS Configurations
            # Setup VM NFS services

            nfs_live_migration_enabled = self._args.nfs_live_migration
            nfs_live_migration_subnet = self._args.nfs_livem_subnet
            nfs_live_migration_image = self._args.nfs_livem_image
            nfs_live_migration_host = self._args.nfs_livem_host

            if nfs_live_migration_enabled == 'enabled':
                storage_setup_args = " --storage-master %s" %(self._args.storage_master)
                storage_setup_args = storage_setup_args + " --storage-setup-mode %s" % (self._args.storage_setup_mode)
                storage_setup_args = storage_setup_args + " --storage-hostnames %s" %(' '.join(self._args.storage_hostnames))
                storage_setup_args = storage_setup_args + " --storage-hosts %s" %(' '.join(self._args.storage_hosts))
                storage_setup_args = storage_setup_args + " --storage-host-tokens %s" %(' '.join(self._args.storage_host_tokens))
                if self._args.nfs_livem_subnet:
                    storage_setup_args = storage_setup_args + " --nfs-livem-subnet %s" % (' '.join(self._args.nfs_livem_subnet))
                    storage_setup_args = storage_setup_args + " --nfs-livem-image %s" % (' '.join(self._args.nfs_livem_image))
                    storage_setup_args = storage_setup_args + " --nfs-livem-host %s" % (' '.join(self._args.nfs_livem_host))
                if self._args.nfs_livem_mount:
                    storage_setup_args = storage_setup_args + " --nfs-livem-mount %s" % (' '.join(self._args.nfs_livem_mount))
                storage_setup_args = storage_setup_args + " --nfs-livem-scope %s" % (self._args.live_migration_scope)
                for storage_host, storage_host_token in zip(self._args.storage_hosts, self._args.storage_host_tokens):
                    if storage_host == self._args.storage_master:
                        storage_master_passwd = storage_host_token
                with settings(host_string=self._args.storage_master, password=self._args.storage_master_token):
                    run("livemnfs-setup %s" %(storage_setup_args))

    def enable_openstack_live_migration(self):
        # Generic live-migration configurations
        live_migration_enabled = self._args.live_migration
        if live_migration_enabled == 'enabled':
            livem_setup_args = " --storage-master %s" %(self._args.storage_master)
            livem_setup_args = livem_setup_args + " --storage-master-token %s" %(self._args.storage_master_token)
            livem_setup_args = livem_setup_args + " --storage-setup-mode %s" % (self._args.storage_setup_mode)
            livem_setup_args = livem_setup_args + " --storage-hostnames %s" %(' '.join(self._args.storage_hostnames))
            livem_setup_args = livem_setup_args + " --storage-hosts %s" %(' '.join(self._args.storage_hosts))
            livem_setup_args = livem_setup_args + " --storage-host-tokens %s" %(' '.join(self._args.storage_host_tokens))
            livem_setup_args = livem_setup_args + " --storage-os-hosts %s" %(' '.join(self._args.storage_os_hosts))
            livem_setup_args = livem_setup_args + " --storage-os-host-tokens %s" %(' '.join(self._args.storage_os_host_tokens))
            livem_setup_args = livem_setup_args + " --fix-nova-uid %s" %(self._args.fix_nova_uid)

            with settings(host_string=self._args.storage_master, password=self._args.storage_master_token):
                run("sudo compute-live-migration-setup %s" %(livem_setup_args))

def main(args_str = None):
    livemigration = LiveMigrationSetup(args_str)
    livemigration.setup()

if __name__ == "__main__":
    main()
