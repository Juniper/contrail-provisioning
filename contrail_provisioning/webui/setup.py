#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import ConfigParser

from fabric.api import local

from contrail_provisioning.common.base import ContrailSetup


class WebuiSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(WebuiSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.global_defaults = {
            'cfgm_ip': '127.0.0.1',
            'keystone_ip': '127.0.0.1',
            'openstack_ip': '127.0.0.1',
            'collector_ip' : '127.0.0.1',
        }
        self.parse_args(args_str)


    def parse_args(self, args_str):        
        '''
        Eg. setup-vnc-webui --cfgm_ip 10.84.12.11 --keystone_ip 10.84.12.12 
            --openstack_ip 10.84.12.12 --collector_ip 10.84.12.12
            --cassandra_ip_list 10.1.5.11 10.1.5.12 --internal_vip 10.84.12.200
            --contrail_internal_vip 10.84.12.250
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--cfgm_ip", help = "IP Address of the cfgm node")
        parser.add_argument("--keystone_ip", help = "IP Address of the keystone node")
        parser.add_argument("--openstack_ip", help = "IP Address of the openstack controller")
        parser.add_argument("--collector_ip", help = "IP Address of the Collector node")
        parser.add_argument("--cassandra_ip_list", help = "List of IP Addresses of cassandra nodes",
                            nargs='+', type=str)
        parser.add_argument("--internal_vip", help = "VIP Address of openstack  nodes")
        parser.add_argument("--contrail_internal_vip", help = "VIP Address of config  nodes")

        self._args = parser.parse_args(self.remaining_argv)

    def  fixup_config_files(self):
        self.fixup_config_global_js()

    def fixup_config_global_js(self):
        openstack_ip = self._args.openstack_ip
        keystone_ip = self._args.keystone_ip
        internal_vip = self._args.internal_vip
        contrail_internal_vip = self._args.contrail_internal_vip or internal_vip
        local("sudo sed \"s/config.cnfg.server_ip.*/config.cnfg.server_ip = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(contrail_internal_vip or self._args.cfgm_ip))
        local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        local("sudo sed \"s/config.networkManager.ip.*/config.networkManager.ip = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(contrail_internal_vip or self._args.cfgm_ip))
        local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        local("sudo sed \"s/config.imageManager.ip.*/config.imageManager.ip = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(internal_vip or openstack_ip))
        local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        local("sudo sed \"s/config.computeManager.ip.*/config.computeManager.ip = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(internal_vip or openstack_ip))
        local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        local("sudo sed \"s/config.identityManager.ip.*/config.identityManager.ip = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(internal_vip or keystone_ip))
        local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        local("sudo sed \"s/config.storageManager.ip.*/config.storageManager.ip = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(internal_vip or openstack_ip))
        local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        if self._args.collector_ip:
            local("sudo sed \"s/config.analytics.server_ip.*/config.analytics.server_ip = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(contrail_internal_vip or self._args.collector_ip))
            local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        if self._args.cassandra_ip_list:
            local("sudo sed \"s/config.cassandra.server_ips.*/config.cassandra.server_ips = %s;/g\" /etc/contrail/config.global.js > config.global.js.new" %(str(self._args.cassandra_ip_list)))
            local("sudo mv config.global.js.new /etc/contrail/config.global.js")


    def run_services(self):
        local("sudo webui-server-setup.sh")

def main(args_str = None):
    webui = WebuiSetup(args_str)
    webui.setup()

if __name__ == "__main__":
    main()
