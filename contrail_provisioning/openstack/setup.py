#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import ConfigParser
from distutils.version import LooseVersion

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
            'region_name': 'RegionOne',
            'nova_password': None,
            'neutron_password': None,
            'keystone_service_tenant_name': 'service',
            'amqp_server_ip':'127.0.0.1',
            'quantum_service_protocol': 'http',
            'quantum_port': 9696,
            'haproxy': False,
            'osapi_compute_workers': 40,
            'conductor_workers': 40,
            'sriov':False,
            'service_dbpass' : 'c0ntrail123',
            'keystone_insecure': False,
            'keystone_certfile': '/etc/keystone/ssl/keystone.pem',
            'keystone_keyfile': '/etc/keystone/ssl/keystone.key',
            'keystone_cafile': '/etc/keystone/ssl/keystone_ca.pem',
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
        parser.add_argument("--node_to_unregister", help = "IP Address of the node whose services needs to be removed")
        parser.add_argument("--mgmt_self_ip", help = "Management IP Address of this system")
        parser.add_argument("--openstack_index", help = "The index of this openstack node")
        parser.add_argument("--openstack_ip_list", nargs='+', type=str,
                            help = "List of IP Addresses of openstack servers")
        parser.add_argument("--cfgm_ip", help = "IP Address of quantum node")
        parser.add_argument("--haproxy", help = "Enable haproxy", action="store_true")
        parser.add_argument("--keystone_ip", help = "IP Address of keystone node")
        parser.add_argument("--keystone_admin_passwd", help = "Passwd of the admin tenant")
        parser.add_argument("--region_name", help = "Region name of the openstack services")
        parser.add_argument("--keystone_insecure",
            help = "Connect to keystone in secure or insecure mode if in https mode")
        parser.add_argument("--keystone_certfile", help="")
        parser.add_argument("--keystone_keyfile", help="")
        parser.add_argument("--keystone_cafile", help="")
        parser.add_argument("--neutron_password", help="Password of neutron user")
        parser.add_argument("--nova_password", help="Password of nova user")
        parser.add_argument("--keystone_service_tenant_name",
            help="Tenant name of services like nova, neutron...etc")
        parser.add_argument("--keystone_auth_protocol", help = "Protocol to use while talking to Keystone")
        parser.add_argument("--internal_vip", help = "Control network VIP Address of openstack nodes")
        parser.add_argument("--external_vip", help = "Management network VIP Address of openstack nodes")
        parser.add_argument("--contrail_internal_vip", help = "Control VIP Address of config  nodes")
        parser.add_argument("--service_token", help = "The service password to access keystone")
        parser.add_argument("--quantum_service_protocol", help = "Protocol of neutron for nova to use")
        parser.add_argument("--quantum_port", help = "Port of neutron service")
        parser.add_argument("--amqp_server_ip", help = "IP of the AMQP server to be used for openstack")
        parser.add_argument("--osapi_compute_workers", type=int,
                            help = "Number of worker threads for osapi compute")
        parser.add_argument("--conductor_workers", type=int,
                            help = "Number of worker threads for conductor")
        parser.add_argument("--sriov", help = "Enable SRIOV", action="store_true")
        parser.add_argument("--service-dbpass", help = "Database password for openstack service db user.")

        self._args = parser.parse_args(self.remaining_argv)
        # Using keystone admin password for nova/neutron if not supplied by user
        if not self._args.neutron_password:
            self._args.neutron_password = self._args.keystone_admin_passwd
        if not self._args.nova_password:
            self._args.nova_password = self._args.keystone_admin_passwd

    def build_ctrl_details(self):
        ctrl_infos = []
        ctrl_details = "%s/ctrl-details" % self._temp_dir_name
        ctrl_infos.append('SERVICE_TOKEN=%s' % self._args.service_token)
        ctrl_infos.append('AUTH_PROTOCOL=%s' % self._args.keystone_auth_protocol)
        ctrl_infos.append('QUANTUM_PROTOCOL=%s' % self._args.quantum_service_protocol)
        ctrl_infos.append('ADMIN_TOKEN=%s' % self._args.keystone_admin_passwd)
        ctrl_infos.append('REGION_NAME=%s' % self._args.region_name)
        ctrl_infos.append('CONTROLLER=%s' % self._args.keystone_ip)
        ctrl_infos.append('NEUTRON_PASSWORD=%s' % self._args.neutron_password)
        ctrl_infos.append('NOVA_PASSWORD=%s' % self._args.nova_password)
        ctrl_infos.append('SERVICE_TENANT_NAME=%s' % self._args.keystone_service_tenant_name)
        ctrl_infos.append('API_SERVER=%s' % self._args.cfgm_ip)
        ctrl_infos.append('OSAPI_COMPUTE_WORKERS=%s' % self._args.osapi_compute_workers)
        ctrl_infos.append('CONDUCTOR_WORKERS=%s' % self._args.conductor_workers)
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
        if self._args.sriov:
            ctrl_infos.append('SRIOV_ENABLED=%s' % 'True')
        else:
            ctrl_infos.append('SRIOV_ENABLED=%s' % 'False')
        ctrl_infos.append('SERVICE_DBPASS=%s' % self._args.service_dbpass)

        self.update_vips_in_ctrl_details(ctrl_infos)

        for ctrl_info in ctrl_infos:
            local ("sudo echo %s >> %s" % (ctrl_info, ctrl_details))
        local("sudo cp %s /etc/contrail/ctrl-details" % ctrl_details)
        local("sudo rm %s/ctrl-details" %(self._temp_dir_name))

    def get_openstack_dashboard_version(self):
        """Retrieve version of openstack-dashboard package installed in the
           local machine. Returns None if not installed.
        """
        pkg_name = "openstack-dashboard"
        with settings(warn_only=True):
            dashboard_version = local("rpm -q --queryformat \"%%{VERSION}\" %s" % pkg_name, capture=True)
        return dashboard_version if dashboard_version.succeeded else None

    def is_dashboard_juno_or_above(self, actual_dashboard_version):
        """Returns True if installed openstack-dashboard package belongs to
           Juno or higher sku, False if not.
        """
        # override for ubuntu when required
        juno_version = '2014.2.2'
        return LooseVersion(actual_dashboard_version) >= LooseVersion(juno_version)

    def unregister_all_services(self):
        hostname = local('sudo getent hosts %s | awk \'{print $2}\'' % self._args.node_to_unregister, capture=True)
        service_list = local("source /etc/contrail/openstackrc && nova service-list | \
                              grep %s | awk '{print $2}'" % hostname, capture=True, shell='/bin/bash').split()

        for service in service_list:
            local('source /etc/contrail/openstackrc && nova service-delete %s' % service, shell = '/bin/bash')

    def fixup_config_files(self):
        nova_conf_file = "/etc/nova/nova.conf"
        cinder_conf_file = "/etc/cinder/cinder.conf"

        # TODO till post of openstack-horizon.spec is fixed...
        if (os.path.isdir("/etc/openstack_dashboard")):
            dashboard_setting_file = "/etc/openstack_dashboard/local_settings"
        else:
            dashboard_setting_file = "/etc/openstack-dashboard/local_settings"

        if self.pdist in ['fedora', 'centos', 'redhat']:
            dashboard_version = self.get_openstack_dashboard_version()
            if dashboard_version:
                if self.is_dashboard_juno_or_above(dashboard_version):
                    local("sudo sed -i \"s/ALLOWED_HOSTS =.*$/ALLOWED_HOSTS = [\'*\']/g\" %s" % (dashboard_setting_file))
                else:
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

def service_unregister(args_str = None):
    openstack = OpenstackSetup(args_str)
    openstack.unregister_all_services()

if __name__ == "__main__":
    main() 
