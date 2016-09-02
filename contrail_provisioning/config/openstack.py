#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#
"""Provision's Contrail Config components with Open Stack as Orchestrator."""

import os

from fabric.state import env
from fabric.api import local
from fabric.context_managers import settings

from contrail_provisioning.config.common import ConfigBaseSetup
from contrail_provisioning.config.templates import contrail_plugin_ini
from contrail_provisioning.config.templates import contrail_config_nodemgr_template
from contrail_provisioning.common.templates import contrail_database_template

class ConfigOpenstackSetup(ConfigBaseSetup):
    def __init__(self, config_args, args_str=None):
        super(ConfigOpenstackSetup, self).__init__(config_args)
        self._args = config_args
        self.keystone_ssl_enabled = False
        if (self._args.keystone_keyfile and
                self._args.keystone_certfile and self._args.keystone_cafile):
            self.keystone_ssl_enabled = True

    def fixup_config_files(self):
        self.fixup_cassandra_config()
        self.fixup_keystone_auth_config_file(True)
        self.fixup_ifmap_config_files()
        self.fixup_contrail_api_config_file()
        config_files = [
                        '/etc/contrail/contrail-api.conf',
                        '/etc/contrail/contrail-keystone-auth.conf',
                        '/etc/contrail/contrail-database.conf',
                       ]
        self.fixup_contrail_api_supervisor_ini(config_files)
        self.fixup_contrail_api_initd()
        self.fixup_contrail_plugin_ini()
        self.fixup_schema_transformer_config_file()
        self.fixup_contrail_schema_supervisor_ini()
        self.fixup_device_manager_config_file()
        self.fixup_contrail_device_manager_supervisor_ini()
        self.fixup_svc_monitor_config_file()
        self.fixup_contrail_svc_monitor_supervisor_ini()
        self.fixup_discovery_config_file()
        self.fixup_discovery_supervisor_ini()
        self.fixup_discovery_initd()
        self.fixup_vnc_api_lib_ini()
        self.fixup_contrail_config_nodemgr()
        self.fixup_contrail_sudoers()
        if self._args.use_certs:
            local("sudo setup-pki.sh /etc/contrail/ssl")

    def fixup_contrail_api_config_file(self):
        super(ConfigOpenstackSetup, self).fixup_contrail_api_config_file()
        self.set_config('/etc/contrail/contrail-api.conf', 'DEFAULTS',
                        'auth', 'keystone')

    def fixup_contrail_schema_supervisor_ini(self):
        contrail_svc_ini = "/etc/contrail/supervisord_config_files/contrail-schema.ini"
        config_files = [
                '/etc/contrail/contrail-schema.conf',
                '/etc/contrail/contrail-keystone-auth.conf',
                '/etc/contrail/contrail-database.conf',
               ]
        config_file_args = ' --conf_file '.join(config_files)
        commandline = "/usr/bin/contrail-schema --conf_file %s" % config_file_args
        self.set_config(contrail_svc_ini, 'program:contrail-schema',
                        'command', commandline)

    def fixup_contrail_device_manager_supervisor_ini(self):
        contrail_svc_ini = "/etc/contrail/supervisord_config_files/contrail-device-manager.ini"
        config_files = [
                '/etc/contrail/contrail-device-manager.conf',
                '/etc/contrail/contrail-keystone-auth.conf',
                '/etc/contrail/contrail-database.conf',
               ]
        config_file_args = ' --conf_file '.join(config_files)
        commandline = "/usr/bin/contrail-device-manager --conf_file %s" % config_file_args
        self.set_config(contrail_svc_ini, 'program:contrail-device-manager',
                        'command', commandline)

    def fixup_contrail_svc_monitor_supervisor_ini(self):
        contrail_svc_ini = "/etc/contrail/supervisord_config_files/contrail-svc-monitor.ini"
        config_files = [
                '/etc/contrail/contrail-svc-monitor.conf',
                '/etc/contrail/contrail-keystone-auth.conf',
                '/etc/contrail/contrail-database.conf',
               ]
        config_file_args = ' --conf_file '.join(config_files)
        commandline = "/usr/bin/contrail-svc-monitor --conf_file %s" % config_file_args
        self.set_config(contrail_svc_ini, 'program:contrail-svc-monitor',
                        'command', commandline)

    def fixup_contrail_plugin_ini(self):
        # quantum/neutron plugin
        template_vals = {'__contrail_api_server_ip__': self.contrail_internal_vip or self._args.self_ip,
                         '__contrail_api_server_port__': '8082',
                         '__contrail_analytics_server_ip__': self.contrail_internal_vip or self._args.self_ip,
                         '__contrail_analytics_server_port__': '8081',
                         '__contrail_keystone_ip__': self._args.keystone_ip,
                         '__contrail_ks_auth_protocol__': self._args.keystone_auth_protocol,
                         '__contrail_ks_auth_port__': self._args.keystone_auth_port,
                         '__contrail_admin_user__': self._args.keystone_admin_user,
                         '__contrail_admin_password__': self._args.keystone_admin_passwd,
                         '__contrail_admin_tenant_name__': self._args.keystone_admin_tenant_name,
                         '__contrail_cloud_admin_role__': "cloud_admin_role=%s" % self._args.cloud_admin_role if self._args.cloud_admin_role else '',
                         '__contrail_aaa_mode__': "aaa_mode=%s" % self._args.aaa_mode if self._args.aaa_mode else '',
                    }
        self._template_substitute_write(contrail_plugin_ini.template,
                                        template_vals, self._temp_dir_name + '/contrail_plugin.ini')
        if os.path.exists("/etc/neutron"):
            local("sudo mkdir -p /etc/neutron/plugins/opencontrail")
            local("sudo mv %s/contrail_plugin.ini /etc/neutron/plugins/opencontrail/ContrailPlugin.ini" %(self._temp_dir_name))
        else:
            local("sudo mv %s/contrail_plugin.ini /etc/quantum/plugins/contrail/contrail_plugin.ini" %(self._temp_dir_name))

        if self.pdist == 'Ubuntu':
            neutron_def_file = "/etc/default/neutron-server"
            if os.path.exists(neutron_def_file):
                local("sudo sed -i 's/NEUTRON_PLUGIN_CONFIG=.*/NEUTRON_PLUGIN_CONFIG=\"\/etc\/neutron\/plugins\/opencontrail\/ContrailPlugin.ini\"/g' %s" %(neutron_def_file))
        if self.api_ssl_enabled:
            certfile, cafile, keyfile = self._get_apiserver_certs(
                    '/etc/neutron/ssl/certs/')
            conf_file = '/etc/neutron/plugins/opencontrail/ContrailPlugin.ini'
            conf_vals = {'use_ssl' : True,
                         'insecure': self._args.apiserver_insecure,
                         'certfile' : certfile,
                         'keyfile' : keyfile,
                         'cafile' : cafile,
                        }
            for param, value in conf_vals.items():
                self.set_config(conf_file, 'APISERVER', param, value)


    def build_ctrl_details(self):
        ctrl_infos = []
        ctrl_details = "%s/ctrl-details" % self._temp_dir_name
        ctrl_infos.append('SERVICE_TENANT=%s' % self._args.keystone_service_tenant_name)
        ctrl_infos.append('SERVICE_TOKEN=%s' % self._args.service_token)
        ctrl_infos.append('AUTH_PROTOCOL=%s' % self._args.keystone_auth_protocol)
        if self._args.keystone_auth_protocol == 'https':
            ctrl_infos.append('KEYSTONE_INSECURE=%s' % self._args.keystone_insecure)
            ctrl_infos.append('APISERVER_INSECURE=%s' % self._args.apiserver_insecure)
        ctrl_infos.append('QUANTUM_PROTOCOL=%s' % self._args.quantum_service_protocol)
        ctrl_infos.append('ADMIN_TOKEN=%s' % self._args.keystone_admin_passwd)
        ctrl_infos.append('CONTROLLER=%s' % self._args.keystone_ip)
        ctrl_infos.append('AMQP_SERVER=%s' % self.rabbit_servers)
        ctrl_infos.append('NEUTRON_PASSWORD=%s' % self._args.neutron_password)
        ctrl_infos.append('KEYSTONE_VERSION=%s' % self._args.keystone_version)
        if self._args.haproxy:
            ctrl_infos.append('QUANTUM=127.0.0.1')
        else:
            ctrl_infos.append('QUANTUM=%s' % self.cfgm_ip)
        ctrl_infos.append('QUANTUM_PORT=%s' % self._args.quantum_port)
        ctrl_infos.append('AAA_MODE=%s' % (self._args.aaa_mode or ''))

        if self.keystone_ssl_enabled:
            certfile, cafile, keyfile = self._get_keystone_certs(
                    '/etc/neutron/ssl/certs/')
            ctrl_infos.append('KEYSTONE_CERTFILE=%s' % certfile)
            ctrl_infos.append('KEYSTONE_KEYFILE=%s' % certfile)
            ctrl_infos.append('KEYSTONE_CAFILE=%s' % certfile)

        self.update_vips_in_ctrl_details(ctrl_infos)

        for ctrl_info in ctrl_infos:
            local ("sudo echo %s >> %s" % (ctrl_info, ctrl_details))
        local("sudo cp %s /etc/contrail/ctrl-details" % ctrl_details)
        local("sudo rm %s/ctrl-details" %(self._temp_dir_name))

    def run_services(self):
        if self.contrail_internal_vip:
            quantum_ip = self.contrail_internal_vip
        else:
            quantum_ip = self.cfgm_ip
        quant_args = '--ks_server_ip     %s ' % self._args.keystone_ip + \
                     '--quant_server_ip  %s ' % quantum_ip + \
                     '--tenant           %s ' % self._args.keystone_admin_tenant_name + \
                     '--user             %s ' % self._args.keystone_admin_user + \
                     '--password         %s ' % self._args.keystone_admin_passwd + \
                     '--svc_password     %s ' % self._args.neutron_password + \
                     '--svc_tenant_name  %s ' % self._args.keystone_service_tenant_name + \
                     '--root_password    %s ' % env.password + \
                     '--auth_protocol    %s ' % self._args.keystone_auth_protocol
        if self._args.keystone_insecure:
            quant_args += '--insecure'

        if self._args.region_name:
            quant_args += " --region_name %s" %(self._args.region_name)
        if self._args.manage_neutron == 'yes':
            local("setup-quantum-in-keystone %s" %(quant_args))

        super(ConfigOpenstackSetup, self).run_services()
        local("sudo quantum-server-setup.sh")

    def setup(self):
        self.disable_selinux()
        self.disable_iptables()
        self.setup_coredump()
        self.setup_database()
        self.fixup_config_files()
        self.build_ctrl_details()
        self.run_services()
