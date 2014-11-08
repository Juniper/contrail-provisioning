#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import ConfigParser

from fabric.api import local
from fabric.context_managers import settings

from contrail_provisioning.common.base import ContrailSetup


class OpenstackSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(OpenstackSetup, self).__init__()
        self.global_defaults = {
            'self_ip': '127.0.0.1',
            'mgmt_self_ip': '127.0.0.1',
            'openstack_index': 1,
            'service_token': '',
            'cfgm_ip': '127.0.0.1',
            'keystone_ip': '127.0.0.1',
            'keystone_auth_protocol':'http',
            'keystone_admin_passwd': 'contrail123',
            'amqp_server_ip':'127.0.0.1',
            'quantum_service_protocol': 'http',
            'quantum_port': 9696,
            'haproxy': False,
        }
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])
        self.parse_args(args_str)

        if self.pdist in ['Ubuntu']:
            self.mysql_conf = '/etc/mysql/my.cnf'
            self.mysql_svc = 'mysql'
        elif self.pdist in ['centos', 'redhat']:
            self.mysql_conf = '/etc/my.cnf'
            self.mysql_svc = 'mysqld'
        self.mysql_redo_log_sz='5242880'

    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-openstack --self_ip 10.1.5.11 --cfgm_ip 10.1.5.12
                   --keystone_ip 10.1.5.13 --service_token c0ntrail123
                   --internal_vip 10.1.5.100 --openstack_index 1
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--self_ip", help = "IP Address of this system")
        parser.add_argument("--mgmt_self_ip", help = "Management IP Address of this system")
        parser.add_argument("--openstack_index", help = "The index of this openstack node")
        parser.add_argument("--openstack_ip_list", help = "List of IP Addresses of openstack servers", nargs='+', type=str)
        parser.add_argument("--cfgm_ip", help = "IP Address of quantum node")
        parser.add_argument("--haproxy", help = "Enable haproxy", action="store_true")
        parser.add_argument("--keystone_ip", help = "IP Address of keystone node")
        parser.add_argument("--keystone_admin_passwd", help = "Passwd of the admin tenant")
        parser.add_argument("--keystone_auth_protocol", help = "Protocol to use while talking to Keystone")
        parser.add_argument("--internal_vip", help = "Control network VIP Address of openstack nodes")
        parser.add_argument("--external_vip", help = "Management network VIP Address of openstack nodes")
        parser.add_argument("--contrail_internal_vip", help = "Control VIP Address of config  nodes")
        parser.add_argument("--service_token", help = "The service password to access keystone")
        parser.add_argument("--quantum_service_protocol", help = "Protocol of neutron for nova to use")
        parser.add_argument("--quantum_port", help = "Port of neutron service")
        parser.add_argument("--amqp_server_ip", help = "IP of the AMQP server to be used for openstack")

        self._args = parser.parse_args(self.remaining_argv)

    def build_ctrl_details(self):
        ctrl_infos = []
        ctrl_details = "%s/ctrl-details" % self._temp_dir_name
        ctrl_infos.append('SERVICE_TOKEN=%s' % self._args.service_token)
        ctrl_infos.append('AUTH_PROTOCOL=%s' % self._args.keystone_auth_protocol)
        ctrl_infos.append('QUANTUM_PROTOCOL=%s' % self._args.quantum_service_protocol)
        ctrl_infos.append('ADMIN_TOKEN=%s' % self._args.keystone_admin_passwd)
        ctrl_infos.append('CONTROLLER=%s' % self._args.keystone_ip)
        if self._args.mgmt_self_ip:
            ctrl_infos.append('SELF_MGMT_IP=%s' % self._args.mgmt_self_ip)
        if self._args.openstack_ip_list:
            ctrl_infos.append('MEMCACHED_SERVERS=%s' % 
                (':11211,'.join(self._args.openstack_ip_list) + ':11211'))
        ctrl_infos.append('AMQP_SERVER=%s' % self._args.amqp_server_ip)
        if self._args.haproxy:
            ctrl_infos.append('QUANTUM=127.0.0.1')
        else:
            ctrl_infos.append('QUANTUM=%s' % self._args.cfgm_ip)
        ctrl_infos.append('QUANTUM_PORT=%s' % self._args.quantum_port)
        if self._args.openstack_index:
            ctrl_infos.append('OPENSTACK_INDEX=%s' % self._args.openstack_index)

        self.update_vips_in_ctrl_details(ctrl_infos)

        for ctrl_info in ctrl_infos:
            local ("sudo echo %s >> %s" % (ctrl_info, ctrl_details))
        local("sudo cp %s /etc/contrail/ctrl-details" % ctrl_details)
        local("sudo rm %s/ctrl-details" %(self._temp_dir_name))

    def fixup_config_files(self):
        nova_conf_file = "/etc/nova/nova.conf"
        cinder_conf_file = "/etc/cinder/cinder.conf"

        # TODO till post of openstack-horizon.spec is fixed...
        if (os.path.isdir("/etc/openstack_dashboard")):
            dashboard_setting_file = "/etc/openstack_dashboard/local_settings"
        else:
            dashboard_setting_file = "/etc/openstack-dashboard/local_settings"
        if self.pdist == 'fedora' or self.pdist == 'centos' or self.pdist == 'redhat':
            local("sudo sed -i 's/ALLOWED_HOSTS =/#ALLOWED_HOSTS =/g' %s" %(dashboard_setting_file))

        if os.path.exists(nova_conf_file):
            local("sudo sed -i 's/rpc_backend = nova.openstack.common.rpc.impl_qpid/#rpc_backend = nova.openstack.common.rpc.impl_qpid/g' %s" \
                   % (nova_conf_file))
        if os.path.exists(cinder_conf_file):
            local("sudo sed -i 's/rpc_backend = cinder.openstack.common.rpc.impl_qpid/#rpc_backend = cinder.openstack.common.rpc.impl_qpid/g' %s" \
                   % (cinder_conf_file))

        local('sed -i -e "s/bind-address/#bind-address/" %s' % self.mysql_conf)
        self.service_token = self._args.service_token
        if not self.service_token:
            local("sudo setup-service-token.sh")

        with settings(warn_only = True):
            #comment out parameters from /etc/nova/api-paste.ini
            local("sudo sed -i 's/auth_host = /;auth_host = /' /etc/nova/api-paste.ini")
            local("sudo sed -i 's/auth_port = /;auth_port = /' /etc/nova/api-paste.ini")
            local("sudo sed -i 's/auth_protocol = /;auth_protocol = /' /etc/nova/api-paste.ini")
            local("sudo sed -i 's/admin_tenant_name = /;admin_tenant_name = /' /etc/nova/api-paste.ini")
            local("sudo sed -i 's/admin_user = /;admin_user = /' /etc/nova/api-paste.ini")
            local("sudo sed -i 's/admin_password = /;admin_password = /' /etc/nova/api-paste.ini")

            #comment out parameters from /etc/cinder/api-paste.ini
            local("sudo sed -i 's/auth_host = /;auth_host = /' /etc/cinder/api-paste.ini")
            local("sudo sed -i 's/auth_port = /;auth_port = /' /etc/cinder/api-paste.ini")
            local("sudo sed -i 's/auth_protocol = /;auth_protocol = /' /etc/cinder/api-paste.ini")
            local("sudo sed -i 's/admin_tenant_name = /;admin_tenant_name = /' /etc/cinder/api-paste.ini")
            local("sudo sed -i 's/admin_user = /;admin_user = /' /etc/cinder/api-paste.ini")
            local("sudo sed -i 's/admin_password = /;admin_password = /' /etc/cinder/api-paste.ini")

    def run_services(self):
        local("sudo keystone-server-setup.sh")
        local("sudo glance-server-setup.sh")
        local("sudo cinder-server-setup.sh")
        local("sudo nova-server-setup.sh")
        with settings(warn_only=True):
            if (self.pdist in ['centos'] and
                local("rpm -qa | grep contrail-heat").succeeded):
                local("sudo heat-server-setup.sh")
            elif (self.pdist in ['Ubuntu'] and
                local("dpkg -l | grep contrail-heat").succeeded):
                local("sudo heat-server-setup.sh")
        local("service %s restart" % self.mysql_svc)
        local("service supervisor-openstack restart")

    def setup(self):
        self.disable_selinux()
        self.disable_iptables()
        self.setup_coredump()
        self.fixup_config_files()
        self.build_ctrl_details()
        self.run_services()

def main(args_str = None):
    openstack = OpenstackSetup(args_str)
    openstack.setup()

if __name__ == "__main__":
    main() 
