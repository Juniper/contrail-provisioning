#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import ConfigParser

from fabric.api import run, local
from fabric.context_managers import settings

from contrail_provisioning.common.base import ContrailSetup


class StorageWebuiSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(StorageWebuiSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.global_defaults = {
            'storage_rest_ip': '127.0.0.1',
            'storage_webui_ip': '127.0.0.1',
            'storage_webui_mode':'enabled'
        }
        self.parse_args(args_str)

    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-storage-webui --storage-rest-ip 10.157.43.171
            --storage-webui-ip  10.157.43.171 --storage-setup-mode setup
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--storage-rest-ip", help = "IP Address of ceph rest api ip address")
        parser.add_argument("--storage-webui-ip", help = "IP Address of storage webui node")
        parser.add_argument("--storage-webui-mode", help = "Config mode Storage WebUI Status")
        parser.add_argument("--storage-setup-mode", help = "Configuration mode")
        parser.add_argument("--storage-disk-config", help = "Disk list to be used for distributed storage", nargs="+", type=str)
        parser.add_argument("--storage-ssd-disk-config", help = "SSD Disk list to be used for distributed storage", nargs="+", type=str)

        self._args = parser.parse_args(self.remaining_argv)

    #end _parse_args

    def setup(self):
        if (self._args.storage_disk_config[0] != 'none' or
            self._args.storage_ssd_disk_config[0] != 'none'):
            self.setup_storage_webui()

    def setup_storage_webui(self):
        # Storage WebUI
        storage_webui_mode = self._args.storage_webui_mode
        if storage_webui_mode == 'enabled':
            storage_setup_args = " --storage-setup-mode %s" % (self._args.storage_setup_mode)
            with settings(host_string=self._args.storage_webui_ip):
                storage_rest_ip = self._args.storage_rest_ip
                # Configuring the ceph rest server ip to storage webui config
                local("sudo sed \"s/config.ceph.server_ip.*/config.ceph.server_ip = '%s';/g\" /usr/src/contrail/contrail-web-storage/webroot/common/config/storage.config.global.js > storage.config.global.js.new" %(storage_rest_ip))
                local("sudo mv storage.config.global.js.new /usr/src/contrail/contrail-web-storage/webroot/common/config/storage.config.global.js")
                run("sudo storage-webui-setup %s" %(storage_setup_args))

#end class SetupVncStorageWebUI

def main(args_str = None):
    storage_webui = StorageWebuiSetup(args_str)
    storage_webui.setup()
#end main

if __name__ == "__main__":
    main()
