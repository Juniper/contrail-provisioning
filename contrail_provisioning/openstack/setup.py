#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import yaml
import argparse
import ConfigParser
from time import sleep
from distutils.version import LooseVersion

from fabric.api import local
from fabric.context_managers import settings

from contrail_provisioning.common import DEBIAN, RHEL
from contrail_provisioning.common.base import ContrailSetup
from haproxy import OpenstackHaproxyConfig

class OpenStackSetupError(Exception):
    pass

class OpenstackSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(OpenstackSetup, self).__init__()
        self.global_defaults = {
            'self_ip': '127.0.0.1',
            'mgmt_self_ip': '127.0.0.1',
            'openstack_index': 1,
            'service_token': '',
            'cfgm_ip': '127.0.0.1',
            'collector_ip': '127.0.0.1',
            'keystone_ip': '127.0.0.1',
            'keystone_auth_protocol':'http',
            'keystone_admin_passwd': 'contrail123',
            'amqp_server_ip':'127.0.0.1',
            'quantum_service_protocol': 'http',
            'quantum_port': 9696,
            'haproxy': False,
            'osapi_compute_workers': 40,
            'conductor_workers': 40,
            'manage_ceilometer' : False,
        }
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])
        self.parse_args(args_str)

        if self.pdist in ['Ubuntu']:
            self.mysql_conf = '/etc/mysql/my.cnf'
            self.mysql_svc = 'mysql'
        elif self.pdist in RHEL:
            self.mysql_conf = '/etc/my.cnf'
            self.mysql_svc = 'mysqld'
        self.mysql_redo_log_sz='5242880'
        self.contrail_horizon = self.is_package_installed(\
            'contrail-openstack-dashboard')

        # Create haproxy config
        if self._args.haproxy:
            self.enable_haproxy()
            haproxy = OpenstackHaproxyConfig(self._args)
            haproxy.create()
            haproxy.start()

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
        parser.add_argument("--openstack_ip_list", nargs='+', type=str,
                            help = "List of IP Addresses of openstack servers")
        parser.add_argument("--cfgm_ip", help = "IP Address of quantum node")
        parser.add_argument("--collector_ip", help = "IP Address of analytics/collector node")
        parser.add_argument("--haproxy", help = "Enable haproxy", action="store_true")
        parser.add_argument("--config_ip_list", help = "List of IP Addresses of config nodes",
                            nargs='+', type=str)
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
        parser.add_argument("--osapi_compute_workers", type=int,
                            help = "Number of worker threads for osapi compute")
        parser.add_argument("--conductor_workers", type=int,
                            help = "Number of worker threads for conductor")
        parser.add_argument("--manage_ceilometer", help = "Provision ceilometer", action="store_true")

        self._args = parser.parse_args(self.remaining_argv)

    def build_ctrl_details(self):
        ctrl_infos = []
        ctrl_details = "%s/ctrl-details" % self._temp_dir_name
        ctrl_infos.append('SERVICE_TOKEN=%s' % self._args.service_token)
        ctrl_infos.append('AUTH_PROTOCOL=%s' % self._args.keystone_auth_protocol)
        ctrl_infos.append('QUANTUM_PROTOCOL=%s' % self._args.quantum_service_protocol)
        ctrl_infos.append('ADMIN_TOKEN=%s' % self._args.keystone_admin_passwd)
        ctrl_infos.append('CONTROLLER=%s' % self._args.keystone_ip)
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
        if self._args.manage_ceilometer:
            ctrl_infos.append('CEILOMETER_ENABLED=yes')

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

    def fixup_config_files(self):
        nova_conf_file = "/etc/nova/nova.conf"
        cinder_conf_file = "/etc/cinder/cinder.conf"

        # TODO till post of openstack-horizon.spec is fixed...
        if (os.path.isdir("/etc/openstack_dashboard")):
            dashboard_setting_file = "/etc/openstack_dashboard/local_settings"
        else:
            dashboard_setting_file = "/etc/openstack-dashboard/local_settings"

        if self.pdist in RHEL:
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

        if self.contrail_horizon:
            self.fixup_dashboard_settings()

        if self._args.manage_ceilometer:
            self.fixup_ceilometer_pipeline_conf()

    def run_services(self):
        local("sudo keystone-server-setup.sh")
        if self.pdist in DEBIAN:
            # Rerun keystone server setup two times in Ubuntu
            # TODO: Need to debug and fix this
            local("sudo keystone-server-setup.sh")
        local("sudo glance-server-setup.sh")
        local("sudo cinder-server-setup.sh")
        local("sudo nova-server-setup.sh")
        if self._args.manage_ceilometer:
            local("sudo ceilometer-server-setup.sh")
        if self.is_package_installed('contrail-heat'):
            local("sudo heat-server-setup.sh")
        local("service %s restart" % self.mysql_svc)
        local("service supervisor-openstack restart")
        if self.contrail_horizon:
            self.restart_dashboard()

    def restart_dashboard(self):
        if self.pdist in DEBIAN:
            local("sudo service apache2 restart")
        elif self.pdist in RHEL:
            local("sudo service httpd restart")

    def increase_ulimits(self):
        """
        Increase ulimit in /etc/init.d/mysqld /etc/init/mysql.conf
        /etc/init.d/rabbitmq-server files
        """
        with settings(warn_only = True):
            if self.pdist in DEBIAN:
                local("sudo sed -i '/start|stop)/ a\    ulimit -n 10240' /etc/init.d/mysql")
                local("sudo sed -i '/start_rabbitmq () {/a\    ulimit -n 10240' /etc/init.d/rabbitmq-server")
                local("sudo sed -i '/umask 007/ a\limit nofile 10240 10240' /etc/init/mysql.conf")
                local("sudo sed -i '/\[mysqld\]/a\max_connections = 10000' /etc/mysql/my.cnf")
                local("sudo echo 'ulimit -n 10240' >> /etc/default/rabbitmq-server")
            else:
                local("sudo sed -i '/start(){/ a\    ulimit -n 10240' /etc/init.d/mysqld")
                local("sudo sed -i '/start_rabbitmq () {/a\    ulimit -n 10240' /etc/init.d/rabbitmq-server")
                local("sudo sed -i '/\[mysqld\]/a\max_connections = 2048' /etc/my.cnf")

    def fixup_dashboard_settings(self):
        """
        Configure horizon to pick up contrail customization
        Based on OS and SKU type pick conf file in following order:
        1. /etc/openstack-dashboard/local_settings.py
        2. /etc/openstack-dashboard/local_settings
        3. /usr/lib/python2.6/site-packages/openstack_dashboard/local/local_settings.py
        """
        file_name = '/etc/openstack-dashboard/local_settings.py'
        if not os.path.exists(file_name):
            file_name = '/etc/openstack-dashboard/local_settings'
        if not os.path.exists(file_name):
            file_name = '/usr/lib/python2.6/site-packages/openstack_dashboard/local/local_settings.py'
        if not os.path.exists(file_name):
            return

        pattern='^HORIZON_CONFIG.*customization_module.*'
        line = '''HORIZON_CONFIG[\'customization_module\'] = \'contrail_openstack_dashboard.overrides\' '''
        self.insert_line_to_file(file_name, line, pattern)

        pattern = 'LOGOUT_URL.*'
        if self.pdist in DEBIAN:
            line = '''LOGOUT_URL='/horizon/auth/logout/' '''
        elif self.pdist in RHEL:
            line = '''LOGOUT_URL='/dashboard/auth/logout/' '''
        self.insert_line_to_file(file_name, line, pattern)

        #HA settings
        if self._args.internal_vip:
            with settings(warn_only=True):
                hash_key = local("sudo grep 'def hash_key' %s" % file_name).succeeded
            if not hash_key:
                # Add a hash generating function
                local('sudo sed -i "/^SECRET_KEY.*/a\    return new_key" %s' % file_name)
                local('sudo sed -i "/^SECRET_KEY.*/a\        new_key = m.hexdigest()" %s' % file_name)
                local('sudo sed -i "/^SECRET_KEY.*/a\        m.update(new_key)" %s' % file_name)
                local('sudo sed -i "/^SECRET_KEY.*/a\        m = hashlib.md5()" %s' % file_name)
                local('sudo sed -i "/^SECRET_KEY.*/a\    if len(new_key) > 250:" %s' % file_name)
                local('sudo sed -i "/^SECRET_KEY.*/a\    new_key = \':\'.join([key_prefix, str(version), key])" %s' % file_name)
                local('sudo sed -i "/^SECRET_KEY.*/a\def hash_key(key, key_prefix, version):" %s' % file_name)
                local('sudo sed -i "/^SECRET_KEY.*/a\import hashlib" %s' % file_name)
                local('sudo sed -i "/^SECRET_KEY.*/a\# To ensure key size of 250" %s' % file_name)
            local("sudo sed  -i \"s/'LOCATION' : '127.0.0.1:11211',/'LOCATION' : '%s:11211',/\" %s" % (self._args.mgmt_self_ip, file_name))
            with settings(warn_only=True):
                if local("sudo grep '\'KEY_FUNCTION\': hash_key,' %s" % file_name).failed:
                    local('sudo sed -i "/\'LOCATION\'.*/a\       \'KEY_FUNCTION\': hash_key," %s' % file_name)
            local("sudo sed -i -e 's/OPENSTACK_HOST = \"127.0.0.1\"/OPENSTACK_HOST = \"%s\"/' %s" % (self._args.internal_vip,file_name))

    def fixup_ceilometer_pipeline_conf(self):
        conf_file = '/etc/ceilometer/pipeline.yaml'
        with open(conf_file, 'r') as fap:
            data = fap.read()
        pipeline_dict = yaml.safe_load(data)
        # If already configured with 'contrail_source' and/or 'contrail_sink' exit
        for source in pipeline_dict['sources']:
            if source['name'] == 'contrail_source':
                return
        for sink in pipeline_dict['sinks']:
            if sink['name'] == 'contrail_sink':
                return
        # Edit meters in sources to exclude floating IP meters if '*' is
        # configured
        for source in pipeline_dict['sources']:
            for mname in source['meters']:
                if mname == '*':
                    source['meters'].append('!ip.floating.*')
                    print('Excluding floating IP meters from source %s' % (source['name']))
                    break
        # Add contrail source and sinks to the pipeline
        contrail_source = {'interval': 600,
                           'meters': ['ip.floating.receive.bytes',
                                      'ip.floating.receive.packets',
                                      'ip.floating.transmit.bytes',
                                      'ip.floating.transmit.packets'],
                           'name': 'contrail_source',
                           'sinks': ['contrail_sink']}
        contrail_source['resources'] = ['contrail://%s:8081/' % (self._args.collector_ip)]
        contrail_sink = {'publishers': ['rpc://'],
                         'transformers': None,
                         'name': 'contrail_sink'}
        pipeline_dict['sources'].append(contrail_source)
        pipeline_dict['sinks'].append(contrail_sink)
        with open(conf_file, 'w') as fap:
            yaml.safe_dump(pipeline_dict, fap, explicit_start=True,
                       default_flow_style=False, indent=4)

    def add_openstack_reserved_ports(self):
        ports = '35357,35358,33306'
        self.add_reserved_ports(ports)

    def setup(self):
        self.increase_ulimits()
        self.add_openstack_reserved_ports()
        self.disable_selinux()
        self.disable_iptables()
        self.setup_coredump()
        self.fixup_config_files()
        self.build_ctrl_details()
        self.run_services()

    def verify(self):
        self.verify_service("supervisor-openstack")
        self.verify_service('keystone')
        for x in xrange(10):
            with settings(warn_only=True):
                cmd = 'source /etc/contrail/openstackrc;'
                cmd += 'keystone tenant-list'
                output = local(cmd, shell='bash')
            if output.failed:
                sleep(10)
            else:
                return
        raise OpenStackSetupError(output)

def main(args_str=None):
    openstack = OpenstackSetup(args_str)
    openstack.setup()
    openstack.verify()

if __name__ == "__main__":
    main() 
