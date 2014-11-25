#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import ConfigParser

from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.compute.common import ComputeBaseSetup
from contrail_provisioning.compute.openstack import ComputeOpenstackSetup


class ComputeSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(ComputeSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.global_defaults = {
            'cfgm_ip': '127.0.0.1',
            'cfgm_user': 'root',
            'cfgm_passwd': 'c0ntrail123',
            'keystone_ip': '127.0.0.1',
            'openstack_mgmt_ip': None,
            'service_token': '',
            'self_ip': '127.0.0.1',
            'ncontrols': '2',
            'non_mgmt_ip': None,
            'non_mgmt_gw': None,
            'public_subnet': None,
            'public_vn_name': None,
            'vgw_intf': None,
            'gateway_routes': None,
            'haproxy': False,
            'keystone_auth_protocol':'http',
            'keystone_auth_port':'35357',
            'keystone_admin_user':None,
            'keystone_admin_passwd':None,
            'keystone_admin_tenant_name':'admin',
            'amqp_server_ip':'127.0.0.1',
            'quantum_service_protocol':'http',
            'esxi_vm': False,
            'vmware': None,
            'vmware_username': 'root',
            'vmware_passwd': 'c0ntrail123',
            'vmware_vmpg_vswitch': 'c0ntrail123',
            'vmware_vmpg_vswitch_mtu': None,
            'vmware_fabpg_vswitch_mtu': None,
            'no_contrail_openstack': False,
            'no_nova_config': False,
            'orchestrator': 'openstack',
            'cpu_mode': None,
            'cpu_model': None,
            'dpdk': False,
            'workaround_mgmt_ip': None,
        }

        self.parse_args(args_str)

    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-vrouter --cfgm_ip 10.1.5.11 --keystone_ip 10.1.5.12
                   --self_ip 10.1.5.12 --service_token 'c0ntrail123' --ncontrols 1
                   --haproxy --internal_vip 10.1.5.200
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--cfgm_ip", help = "IP Address of the config node")
        parser.add_argument("--cfgm_user", help = "Sudo User in the config node")
        parser.add_argument("--cfgm_passwd", help = "Password of the Sudo user in the config node")
        parser.add_argument("--keystone_ip", help = "IP Address of the keystone node")
        parser.add_argument("--openstack_mgmt_ip", help = "Mgmt IP Address of the openstack node if it is different from openstack_IP")
        parser.add_argument("--service_token", help = "The service password to access keystone")
        parser.add_argument("--self_ip", help = "IP Address of this(compute) node")
        parser.add_argument("--mgmt_self_ip", help = "Management IP Address of this system")
        parser.add_argument("--ncontrols", help = "Number of control-nodes in the system")
        parser.add_argument("--non_mgmt_ip", help = "IP Address of non-management interface(fabric network) on the compute  node")
        parser.add_argument("--non_mgmt_gw", help = "Gateway Address of the non-management interface(fabric network) on the compute node")
        parser.add_argument("--public_subnet", help = "Subnet of the virtual network used for public access")
        parser.add_argument("--physical_interface", help = "Name of the physical interface to use")
        parser.add_argument("--vgw_intf", help = "Virtual gateway intreface name")
        parser.add_argument("--vgw_public_subnet", help = "Subnet of the virtual network used for public access")
        parser.add_argument("--vgw_public_vn_name", help = "Fully-qualified domain name (FQDN) of the routing-instance that needs public access")
        parser.add_argument("--vgw_intf_list", help = "List of virtual getway intreface")
        parser.add_argument("--vgw_gateway_routes", help = "Static route to be configured in agent configuration for VGW")
        parser.add_argument("--public_vn_name", help = "Fully-qualified domain name (FQDN) of the routing-instance that needs public access")
        parser.add_argument("--gateway_routes", help = "List of route need to be added in agent configuration for virtual gateway")
        parser.add_argument("--haproxy", help = "Enable haproxy", action="store_true")
        parser.add_argument("--keystone_auth_protocol", help = "Auth protocol used to talk to keystone")
        parser.add_argument("--keystone_auth_port", help = "Port of Keystone to talk to")
        parser.add_argument("--keystone_admin_user", help = "Keystone admin tenants user name")
        parser.add_argument("--keystone_admin_password", help = "Keystone admin user's password")
        parser.add_argument("--keystone_admin_tenant_name", help = "Keystone admin tenant name")
        parser.add_argument("--quantum_service_protocol", help = "Protocol of neutron for nova to use")
        parser.add_argument("--quantum_port", help = "Quantum server port")
        parser.add_argument("--amqp_server_ip", help = "IP of the AMQP server to be used for openstack")
        parser.add_argument("--vmware", help = "The Vmware ESXI IP")
        parser.add_argument("--vmware_username", help = "The Vmware ESXI username")
        parser.add_argument("--vmware_passwd", help = "The Vmware ESXI password")
        parser.add_argument("--vmware_vmpg_vswitch", help = "The Vmware VMPG vswitch name")
        parser.add_argument("--vmware_vmpg_vswitch_mtu", help = "The Vmware VMPG vswitch MTU")
        parser.add_argument("--vmware_fabpg_vswitch_mtu", help = "The Vmware FABPG vswitch MTU")
        parser.add_argument("--internal_vip", help = "Internal VIP Address of openstack nodes")
        parser.add_argument("--external_vip", help = "External VIP Address of openstack nodes")
        parser.add_argument("--contrail_internal_vip", help = "VIP Address of config  nodes")
        parser.add_argument("--no_contrail_openstack", help = "Do not provision contrail Openstack in compute node.", action="store_true")
        parser.add_argument("--no_nova_config", help = "Do not configure anything related to nova.", action="store_true")
        parser.add_argument("--metadata_secret", help = "Metadata Proxy secret from openstack node")
        parser.add_argument("--orchestrator", help = "Orchestrator used, example openstack, vcenter")
        parser.add_argument("--cpu_mode", help = "VM cpu_mode, can be one of 'none', 'host-model', 'host-passthrough', 'custom'")
        parser.add_argument("--cpu_model", help = "VM cpu_model, required if cpu_mode is 'custom'. eg. 'Nehalem'")
        parser.add_argument("--dpdk", help = "vRouter/DPDK mode.", action="store_true")
        parser.add_argument("--workaround_mgmt_ip", help = "Workaround for managment IP Address")

        self._args = parser.parse_args(self.remaining_argv)



def main(args_str = None):
    compute_args = ComputeSetup(args_str)._args
    if compute_args.orchestrator == 'openstack':
        compute = ComputeOpenstackSetup(compute_args)
    # For future Orchestrator, inherit ComputeBaseSetup and
    # add functionality specific to Orchestrator.
    else:
        # Defaults to provision only contrail compute without Orchestrator.
        compute = ComputeBaseSetup(compute_args)
    compute.setup()

if __name__ == "__main__":
    main()
