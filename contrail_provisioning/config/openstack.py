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
from contrail_provisioning.config.templates import vnc_api_lib_ini
from contrail_provisioning.config.templates import contrail_plugin_ini
from contrail_provisioning.config.templates import contrail_config_nodemgr_template

class ConfigOpenstackSetup(ConfigBaseSetup):
    def __init__(self, config_args, args_str=None):
        super(ConfigOpenstackSetup, self).__init__(config_args)
        self._args = config_args

    def fixup_config_files(self):
        self.fixup_keystone_auth_config_file()
        self.fixup_ifmap_config_files()
        self.fixup_contrail_api_config_file()
        config_files = [
                        '/etc/contrail/contrail-api.conf',
                        '/etc/contrail/contrail-keystone-auth.conf',
                       ]
        self.fixup_contrail_api_supervisor_ini(config_files)
        self.fixup_contrail_api_initd()
        self.fixup_contrail_plugin_ini()
        self.fixup_schema_transformer_config_file()
        self.fixup_contrail_schema_supervisor_ini()
        self.fixup_device_manager_config_file()
        #self.fixup_contrail_device_manager_supervisor_ini()
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
        local('sudo openstack-config --set /etc/contrail/contrail-api.conf DEFAULTS auth keystone')

    def fixup_contrail_schema_supervisor_ini(self):
        contrail_svc_ini = "/etc/contrail/supervisord_config_files/contrail-schema.ini"
        config_files = [
                '/etc/contrail/contrail-schema.conf',
                '/etc/contrail/contrail-keystone-auth.conf',
               ]
        config_file_args = ' --conf_file '.join(config_files)
        local('sudo openstack-config --set %s program:contrail-schema command "/usr/bin/contrail-schema --conf_file %s"'
              % (contrail_svc_ini, config_file_args))

    def fixup_contrail_device_manager_supervisor_ini(self):
        contrail_svc_ini = "/etc/contrail/supervisord_config_files/contrail-device-manager.ini"
        config_files = [
                '/etc/contrail/contrail-device-manager.conf',
                '/etc/contrail/contrail-keystone-auth.conf',
               ]
        config_file_args = ' --conf_file '.join(config_files)
        local('sudo openstack-config --set %s program:contrail-device-manager command "/usr/bin/contrail-device-manager --conf_file %s"'
              % (contrail_svc_ini, config_file_args))

    def fixup_contrail_svc_monitor_supervisor_ini(self):
        contrail_svc_ini = "/etc/contrail/supervisord_config_files/contrail-svc-monitor.ini"
        config_files = [
                '/etc/contrail/contrail-svc-monitor.conf',
                '/etc/contrail/contrail-keystone-auth.conf',
               ]
        config_file_args = ' --conf_file '.join(config_files)
        local('sudo openstack-config --set %s program:contrail-svc-monitor command "/usr/bin/contrail-svc-monitor --conf_file %s"'
              % (contrail_svc_ini, config_file_args))

    def fixup_contrail_plugin_ini(self):
        # quantum/neutron plugin
        template_vals = {'__contrail_api_server_ip__': self._args.internal_vip or self._args.self_ip,
                         '__contrail_api_server_port__': '8082',
                         '__contrail_multi_tenancy__': self._args.multi_tenancy,
                         '__contrail_keystone_ip__': self._args.keystone_ip,
                         '__contrail_admin_token__': self._args.keystone_admin_token,
                         '__contrail_ks_auth_protocol__': self._args.keystone_auth_protocol,
                         '__contrail_ks_auth_port__': self._args.keystone_auth_port,
                         '__contrail_admin_user__': self._args.keystone_admin_user,
                         '__contrail_admin_password__': self._args.keystone_admin_passwd,
                         '__contrail_admin_tenant_name__': self._args.keystone_admin_tenant_name,
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

    def fixup_vnc_api_lib_ini(self):
        # vnc_api_lib.ini
        template_vals = {
                         '__contrail_keystone_ip__': self._args.keystone_ip,
                        }
        self._template_substitute_write(vnc_api_lib_ini.template,
                                        template_vals, self._temp_dir_name + '/vnc_api_lib.ini')
        local("sudo mv %s/vnc_api_lib.ini /etc/contrail/" %(self._temp_dir_name))

    def build_ctrl_details(self):
        ctrl_infos = []
        ctrl_details = "%s/ctrl-details" % self._temp_dir_name
        ctrl_infos.append('SERVICE_TENANT=%s' % self._args.keystone_service_tenant_name)
        ctrl_infos.append('SERVICE_TOKEN=%s' % self._args.service_token)
        ctrl_infos.append('AUTH_PROTOCOL=%s' % self._args.keystone_auth_protocol)
        ctrl_infos.append('QUANTUM_PROTOCOL=%s' % self._args.quantum_service_protocol)
        ctrl_infos.append('ADMIN_TOKEN=%s' % self._args.keystone_admin_passwd)
        ctrl_infos.append('CONTROLLER=%s' % self._args.keystone_ip)
        ctrl_infos.append('AMQP_SERVER=%s' % self._args.amqp_server_ip)
        if self._args.haproxy:
            ctrl_infos.append('QUANTUM=127.0.0.1')
        else:
            ctrl_infos.append('QUANTUM=%s' % self.cfgm_ip)
        ctrl_infos.append('QUANTUM_PORT=%s' % self._args.quantum_port)

        self.update_vips_in_ctrl_details(ctrl_infos)

        for ctrl_info in ctrl_infos:
            local ("sudo echo %s >> %s" % (ctrl_info, ctrl_details))
        local("sudo cp %s /etc/contrail/ctrl-details" % ctrl_details)
        local("sudo rm %s/ctrl-details" %(self._temp_dir_name))

    def run_services(self):
        if self._args.internal_vip:
            # Assumption cfgm and openstack in same node.
            # TO DO: When we introduce contrail_vip for cfgm nodes, this needs to be revisited.
            quantum_ip = self._args.internal_vip
        else:
            quantum_ip = self.cfgm_ip
        quant_args = "--ks_server_ip %s --quant_server_ip %s --tenant %s --user %s --password %s --svc_password %s --root_password %s" \
                      %(self._args.keystone_ip, quantum_ip, self._args.keystone_admin_tenant_name, self._args.keystone_admin_user, self._args.keystone_admin_passwd, self._args.keystone_admin_passwd,
                        env.password)
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
        self.fixup_config_files()
        self.build_ctrl_details()
        self.run_services()
