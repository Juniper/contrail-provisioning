#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
from fabric.api import local

from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.config.common import ConfigBaseSetup
from contrail_provisioning.config.openstack import ConfigOpenstackSetup


class ConfigSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(ConfigSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.global_defaults = {
            'self_ip': '127.0.0.1',
            'cfgm_index' : 1,
            'collector_ip': '127.0.0.1',
            'keystone_ip': '127.0.0.1',
            'keystone_admin_user': 'admin',
            'keystone_admin_passwd': 'contrail123',
            'keystone_admin_tenant_name': 'admin',
            'keystone_service_tenant_name' : 'service',
            'neutron_password': None,
            'service_token': '',
            'use_certs': False,
            'multi_tenancy': True,
            'nworkers': '1',
            'haproxy': False,
            'manage_db': False,
            'seed_list': '',
            'data_dir': '',
            'ssd_data_dir': '',
            'region_name': None,
            'keystone_auth_protocol': 'http',
            'keystone_auth_port': '35357',
            'keystone_version': 'v2.0',
            'amqp_server_ip': '127.0.0.1',
            'quantum_port': '9696',
            'quantum_service_protocol': 'http',
            'manage_neutron': 'yes',
            'orchestrator' : 'openstack',
            'amqp_port': '5672',
            'control_ip_list': '',
            'keystone_insecure': False,
            'keystone_certfile': None,
            'keystone_keyfile': None,
            'keystone_cafile': None,
            'apiserver_insecure': False,
            'apiserver_certfile': None,
            'apiserver_keyfile': None,
            'apiserver_cafile': None,
        }
        self.parse_args(args_str)

    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-cfgm --self_ip 10.1.5.11 --keystone_ip 10.1.5.12 
            --collector_ip 10.1.5.12 --service_token contrail123
            --cassandra_ip_list 10.1.5.11 10.1.5.12 
            --zookeeper_ip_list 10.1.5.11 10.1.5.12
            --nworkers 1
            optional: --use_certs, --multi_tenancy --haproxy
                      --region_name <name> --internal_vip 10.1.5.100
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--self_ip", help = "IP Address of this system")
        parser.add_argument("--cfgm_index", help = "The index of this cfgm node")
        parser.add_argument("--collector_ip", help = "IP Address of collector node")
        parser.add_argument("--keystone_ip", help = "IP Address of keystone node")
        parser.add_argument("--keystone_admin_user", help = "Keystone admin tenant user.")
        parser.add_argument("--keystone_admin_passwd", help = "Keystone admin user's password.")
        parser.add_argument("--keystone_admin_tenant_name", help = "Keystone admin tenant name.")
        parser.add_argument("--service_token", help = "The service password to access keystone")
        parser.add_argument("--use_certs", help = "Use certificates for authentication (irond)",
            action="store_true")
        parser.add_argument("--multi_tenancy", help = "(Deprecated, defaults to True) Enforce resource permissions (implies token validation)",
            action="store_true")
        parser.add_argument("--cassandra_ip_list", help = "List of IP Addresses of cassandra nodes",
                            nargs='+', type=str)
        parser.add_argument("--zookeeper_ip_list", help = "List of IP Addresses of zookeeper servers",
                            nargs='+', type=str)
        parser.add_argument("--control_ip_list", help = "List of IP Addresses of Control nodes",
                            nargs='+', type=str)
        parser.add_argument("--quantum_port", help = "Quantum Server port")
        parser.add_argument("--quantum_service_protocol", help = "Protocol of quantum/neutron for nova to use ")
        parser.add_argument("--keystone_auth_protocol", 
            help = "Auth protocol used to talk to keystone")
        parser.add_argument("--keystone_auth_port", help = "Port of Keystone to talk to",
            default = '35357')
        parser.add_argument("--neutron_password", help="Password of neutron user")
        parser.add_argument("--keystone_service_tenant_name",
            help="Tenant name of the networking service user - neutron/quantum")
        parser.add_argument("--keystone_insecure", 
            help = "Connect to keystone in secure or insecure mode if in https mode")
        parser.add_argument("--keystone_version", choices=['v2.0', 'v3'],
            help = "Keystone Version")
        parser.add_argument("--keystone_certfile", help="")
        parser.add_argument("--keystone_keyfile", help="")
        parser.add_argument("--keystone_cafile", help="")
        parser.add_argument("--apiserver_insecure", 
            help = "Connect to apiserver in secure or insecure mode if in https mode")
        parser.add_argument("--apiserver_certfile", help="")
        parser.add_argument("--apiserver_keyfile", help="")
        parser.add_argument("--apiserver_cafile", help="")

        parser.add_argument("--nworkers",
            help = "Number of worker processes for api and discovery services",
            default = '1')
        parser.add_argument("--haproxy", help = "Enable haproxy", action="store_true")
        parser.add_argument("--manage_db", action="store_true",
                help="Manage seperate cassandra DB for config")
        parser.add_argument("--seed_list",
                help = "List of seed nodes for config database", nargs='+')
        parser.add_argument("--data_dir",
                help = "Directory where config database stores data")
        parser.add_argument("--ssd_data_dir",
                help = "SSD directory that config database stores data")
        parser.add_argument("--region_name", help = "The Region name for the openstack")
        # TODO: Remove after https://review.opencontrail.org/#/c/15076/ is merged
        parser.add_argument("--amqp_server_ip",
            help = "IP of the AMQP server to be used for neutron and api server")
        # TODO END
        parser.add_argument("--amqp_ip_list", nargs='+', type=str,
            help = "IP of the AMQP server to be used for neutron and config services")
        parser.add_argument("--amqp_port",
            help = "IP of the AMQP server port to be used for neutron and config services")
        parser.add_argument("--manage_neutron", help = "Provision neutron user/role in Keystone.")
        parser.add_argument("--internal_vip", help = "VIP Address of openstack  nodes")
        parser.add_argument("--external_vip", help = "External VIP Address of HA Openstack Nodes")
        parser.add_argument("--contrail_internal_vip", help = "Internal VIP Address of HA config Nodes")
        parser.add_argument("--orchestrator", help="Orchestrator used by contrail")
        parser.add_argument("--cassandra_user", help = "Cassandra user name",
            default= None)
        parser.add_argument("--cassandra_password", help = "Cassandra password",
            default= None)
        self._args = parser.parse_args(self.remaining_argv)
        # Using keystone admin password for nova/neutron if not supplied
        if not self._args.neutron_password:
            self._args.neutron_password = self._args.keystone_admin_passwd

    def provision_alarm(self):
        alarm_args = "--api_server_ip %s" % self._args.self_ip
        alarm_args += " --api_server_port 8082"
        alarm_args += " --admin_user %s" % self._args.keystone_admin_user
        alarm_args += " --admin_password %s" % self._args.keystone_admin_passwd
        alarm_args += " --admin_tenant_name %s" % self._args.keystone_admin_tenant_name
        if (self.api_ssl_enabled == True):
            alarm_args += " --api_server_use_ssl True"
        local("sudo python /opt/contrail/utils/provision_alarm.py %s" % alarm_args)

def main(args_str = None):
    config_setup = ConfigSetup(args_str)
    config_args = config_setup._args
    if config_args.orchestrator == 'openstack':
        config = ConfigOpenstackSetup(config_args)
    # For future Orchestrator, inherit ConfigBaseSetup and
    # add functionality specific to Orchestrator.
    else:
        # Defaults to provision only contrail config without Orchestrator.
        config = ConfigBaseSetup(config_args)
    config.setup()
    config_setup.provision_alarm()

def fix_cfgm_config_files(args_str=None):
    config_args = ConfigSetup(args_str)._args
    if config_args.orchestrator == 'openstack':
        config = ConfigOpenstackSetup(config_args)
    else:
        config = ConfigBaseSetup(config_args)
    config.fixup_config_files()
    config.restart_config()

def update_ifmap_users(args_str=None):
    config_args = ConfigSetup(args_str)._args
    if config_args.orchestrator == 'openstack':
        config = ConfigOpenstackSetup(config_args)
    else:
        config = ConfigBaseSetup(config_args)
    config.fixup_ifmap_config_files()

if __name__ == "__main__":
    main() 
