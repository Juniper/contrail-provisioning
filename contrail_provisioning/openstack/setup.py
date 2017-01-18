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
            'keystone_version': 'v2.0',
            'amqp_server_ip':'127.0.0.1',
            'quantum_service_protocol': 'http',
            'quantum_port': 9696,
            'haproxy': False,
            'osapi_compute_workers': 40,
            'conductor_workers': 40,
            'sriov':False,
            'service_dbpass' : 'c0ntrail123',
            'keystone_insecure': True,
            'keystone_certfile': None,
            'keystone_keyfile':  None,
            'keystone_cafile': None,
        }
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])
        self.parse_args(args_str)

        if self.pdist in ['Ubuntu'] and self.pdistversion == '16.04':
            self.mysql_conf = '/etc/mysql/my.cnf'
            self.mysql_svc = 'mysql'
            self.openstack_services = ['cinder-api', 'cinder-scheduler',
                                      'glance-api', 'glance-registry',
                                      'heat-api', 'heat-engine', 'heat-api-cfn',
                                      'apache2', 'nova-api',
                                      'nova-conductor', 'nova-consoleauth',
                                      'nova-novncproxy', 'nova-scheduler']
        elif self.pdist in ['Ubuntu']:
            self.mysql_conf = '/etc/mysql/my.cnf'
            self.mysql_svc = 'mysql'
            self.openstack_services = ['supervisor-openstack']
        elif self.pdist in ['centos', 'redhat', 'centoslinux']:
            self.mysql_conf = '/etc/my.cnf'
            self.mysql_svc = 'mysqld'
            if os.path.isfile('/usr/lib/systemd/system/mariadb.service'):
                self.mysql_svc = 'mariadb'
            self.openstack_services = ['openstack-cinder-api', 'openstack-cinder-scheduler',
                                      'openstack-glance-api', 'openstack-glance-registry',
                                      'openstack-heat-api', 'openstack-heat-engine',
                                      'openstack-keystone', 'openstack-nova-api',
                                      'openstack-nova-conductor', 'openstack-nova-consoleauth',
                                      'openstack-nova-novncproxy', 'openstack-nova-scheduler']
        self.mysql_redo_log_sz='5242880'
        self.keystone_ssl_enabled = (self._args.keystone_keyfile and
                self._args.keystone_certfile and self._args.keystone_cafile)
        if self.keystone_ssl_enabled:
            self._args.keystone_auth_protocol = 'https'

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
        parser.add_argument("--keystone_version", choices=['v2.0', 'v3'],
            help = "Keystone Version")
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
        if self._args.keystone_auth_protocol == 'https':
            ctrl_infos.append('KEYSTONE_INSECURE=%s' % self._args.keystone_insecure)
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
        ctrl_infos.append('KEYSTONE_VERSION=%s' % self._args.keystone_version)
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
        if self.keystone_ssl_enabled:
            ctrl_infos.append('KEYSTONE_CERTFILE=%s' % self._args.keystone_certfile)
            ctrl_infos.append('KEYSTONE_KEYFILE=%s' % self._args.keystone_keyfile)
            ctrl_infos.append('KEYSTONE_CAFILE=%s' % self._args.keystone_cafile)

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
            dashboard_version = local("rpm -q --qf \"%%{epochnum} %%{V} %%{R}\" %s" % pkg_name, capture=True)
        return tuple(dashboard_version.split()) if dashboard_version.succeeded else None

    def is_dashboard_juno_or_above(self, actual_dashboard_version):
        """Returns True if installed openstack-dashboard package belongs to
           Juno or higher sku, False if not.
        """
        # override for ubuntu when required
        import rpm
        juno_version = ('0', '2014.2.2', '1.el7')
        return rpm.labelCompare(actual_dashboard_version, juno_version) >= 0

    def unregister_all_services(self):
        hostname = local('sudo getent hosts %s | awk \'{print $2}\'' % self._args.node_to_unregister, capture=True)
        service_list = local("source /etc/contrail/openstackrc && nova service-list | \
                              grep %s | awk '{print $2}'" % hostname, capture=True, shell='/bin/bash').split()

        for service in service_list:
            local('source /etc/contrail/openstackrc && nova service-delete %s' % service, shell = '/bin/bash')

    def fixup_config_files(self):
        nova_conf_file = "/etc/nova/nova.conf"
        cinder_conf_file = "/etc/cinder/cinder.conf"
        barbican_file = "/etc/barbican/barbican-api-paste.ini"
        barbican_ini_file = "/etc/barbican/vassals/barbican-api.ini"
        barbican_apache_file = "/etc/apache2/conf-available/barbican-api.conf"

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
        elif self.pdist in ['Ubuntu']:
            dashboard_setting_file = "/etc/openstack-dashboard/local_settings.py"

        with settings(warn_only=True):
            if self.keystone_ssl_enabled:
                local("sudo sed -i 's/^OPENSTACK_KEYSTONE_URL = \"http:/OPENSTACK_KEYSTONE_URL = \"https:/g' %s" % (dashboard_setting_file))
                local("sudo sed -i 's/^#OPENSTACK_SSL_NO_VERIFY.*/OPENSTACK_SSL_NO_VERIFY = True/g' %s" % (dashboard_setting_file))

        dashboard_setting_file = "/etc/openstack-dashboard/local_settings.py"
        dashboard_keystone_policy_file = "/usr/share/openstack-dashboard/openstack_dashboard/conf/keystone_policy.json"
        with settings(warn_only=True):
            is_v3 = local('grep "^OPENSTACK_KEYSTONE_MULTIDOMAIN_SUPPORT = True" %s' % dashboard_setting_file)
        if self._args.keystone_version == 'v3' and is_v3.failed:
            local('sudo echo OPENSTACK_API_VERSIONS = { \\\"identity\\\": 3, } >> %s' % (dashboard_setting_file))
            local("sudo sed -i \"s/^OPENSTACK_KEYSTONE_URL = \(.*\)v2.0\(.*\)/OPENSTACK_KEYSTONE_URL = \\1v3\\2/g\" %s" % (dashboard_setting_file))
            local("sudo echo SESSION_ENGINE = \\'django.contrib.sessions.backends.cache\\' >> %s" % (dashboard_setting_file))
            dir_path = os.path.dirname(os.path.realpath(__file__))
            local("sudo cp %s/templates/policy.v3cloudsample.json /etc/keystone" % dir_path)
            local('sudo sed -i "s/#policy_file = .*/policy_file = policy.v3cloudsample.json/" /etc/keystone/keystone.conf')
            local("sudo echo OPENSTACK_KEYSTONE_MULTIDOMAIN_SUPPORT = True >> %s" % (dashboard_setting_file))
            local("sudo cp %s %s.original" % (dashboard_keystone_policy_file, dashboard_keystone_policy_file))
            local("sudo cp %s/templates/policy.v3cloudsample.json %s" % (dir_path, dashboard_keystone_policy_file))
            local('sudo sed -i "s/^    \\\"cloud_admin\\\":.*/    \\\"cloud_admin\\\": \\\"role:admin and domain_id:default\\\",/" %s' % dashboard_keystone_policy_file)
        elif self._args.keystone_version == 'v2.0' and is_v3.succeeded:
            local('sudo sed -i "/OPENSTACK_API_VERSIONS = { \\\"identity\\\": 3, }/d" %s' % (dashboard_setting_file))
            local('sudo sed -i "/SESSION_ENGINE.*jango.contrib.sessions.backends.cache/d" %s' % (dashboard_setting_file))
            local("sudo sed -i \"s/^OPENSTACK_KEYSTONE_URL = \(.*\)v3\(.*\)/OPENSTACK_KEYSTONE_URL = \\1v2.0\\2/g\" %s" % (dashboard_setting_file))
            local('sudo sed -i "s/policy_file =/#policy_file = /" /etc/keystone/keystone.conf')
            local('sudo sed -i "/^OPENSTACK_KEYSTONE_MULTIDOMAIN_SUPPORT = True/d" %s' % (dashboard_setting_file))

        if os.path.exists(nova_conf_file):
            local("sudo sed -i 's/rpc_backend = nova.openstack.common.rpc.impl_qpid/#rpc_backend = nova.openstack.common.rpc.impl_qpid/g' %s" \
                   % (nova_conf_file))
        if os.path.exists(cinder_conf_file):
            local("sudo sed -i 's/rpc_backend = cinder.openstack.common.rpc.impl_qpid/#rpc_backend = cinder.openstack.common.rpc.impl_qpid/g' %s" \
                   % (cinder_conf_file))

        #barbican
        if os.path.exists(barbican_file):
            local("sudo sed -i 's/pipeline = unauthenticated-context apiapp/#pipeline = unauthenticated-context apiapp/g' %s" \
                   %(barbican_file))
            local("sudo sed -i 's/#pipeline = keystone_authtoken context apiapp/pipeline = keystone_authtoken context apiapp/g' %s" \
                   %(barbican_file))
        if self._args.internal_vip:
            if os.path.exists(barbican_ini_file):
                local("sudo sed -i 's/socket = :9311/socket = :9322/g' %s" %(barbican_ini_file)) 
            if os.path.exists(barbican_apache_file):
                local("sudo sed -i 's/Listen 9311/Listen 9322/g' %s" %(barbican_apache_file))

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
        if os.path.exists("/etc/barbican"):
            local("sudo barbican-server-setup.sh")
        with settings(warn_only=True):
            if (self.pdist in ['centos'] and
                local("rpm -qa | grep contrail-heat").succeeded):
                local("sudo heat-server-setup.sh")
            elif (self.pdist in ['Ubuntu'] and
                local("dpkg -l | grep contrail-heat").succeeded):
                local("sudo heat-server-setup.sh")
        local("service %s restart" % self.mysql_svc)
        for service in self.openstack_services:
            local("service %s restart" % service)

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
