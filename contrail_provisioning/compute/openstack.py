#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import argparse
import subprocess
import ConfigParser

from fabric.api import local
from fabric.context_managers import settings

from contrail_provisioning.compute.common import ComputeBaseSetup


class ComputeOpenstackSetup(ComputeBaseSetup):
    def __init__(self, compute_args, args_str=None):
        super(ComputeOpenstackSetup, self).__init__(compute_args)
        self._args = compute_args

    def fixup_nova_conf(self):
        with settings(warn_only = True):
            if self.pdist in ['Ubuntu']:
                cmd = "dpkg -l | grep 'ii' | grep nova-compute | grep -v vif | grep -v nova-compute-kvm | awk '{print $3}'"
                nova_compute_version = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
                if (nova_compute_version != "2:2013.1.3-0ubuntu1"):
                    local("openstack-config --set /etc/nova/nova.conf DEFAULT neutron_admin_auth_url http://%s:5000/v2.0" % self._args.keystone_ip)

        nova_conf_file = "/etc/nova/nova.conf"
        if os.path.exists(nova_conf_file):
            local("sudo sed -i 's/rpc_backend = nova.openstack.common.rpc.impl_qpid/#rpc_backend = nova.openstack.common.rpc.impl_qpid/g' %s" \
                   % (nova_conf_file))

    def build_ctrl_details(self):
        ctrl_infos = []
        ctrl_details = "%s/ctrl-details" % self._temp_dir_name
        ctrl_infos.append('SERVICE_TOKEN=%s' % self._args.service_token)
        ctrl_infos.append('AUTH_PROTOCOL=%s' % self._args.keystone_auth_protocol)
        ctrl_infos.append('QUANTUM_PROTOCOL=%s' % self._args.quantum_service_protocol)
        ctrl_infos.append('ADMIN_TOKEN=%s' % self._args.keystone_admin_password)
        ctrl_infos.append('CONTROLLER=%s' % self._args.keystone_ip)
        ctrl_infos.append('AMQP_SERVER=%s' % self._args.amqp_server_ip)
        ctrl_infos.append('HYPERVISOR=%s' % self._args.hypervisor)
        if self._args.haproxy:
            ctrl_infos.append('QUANTUM=127.0.0.1')
        else:
            ctrl_infos.append('QUANTUM=%s' % self._args.cfgm_ip)
        ctrl_infos.append('QUANTUM_PORT=%s' % self._args.quantum_port)

        ctrl_infos.append('COMPUTE=%s' % self._args.self_ip)
        ctrl_infos.append('CONTROLLER_MGMT=%s' % self._args.openstack_mgmt_ip)
        if self._args.vmware:
            ctrl_infos.append('VMWARE_IP=%s' % self._args.vmware)
            ctrl_infos.append('VMWARE_USERNAME=%s' % self._args.vmware_username)
            ctrl_infos.append('VMWARE_PASSWD=%s' % self._args.vmware_passwd)
            ctrl_infos.append('VMWARE_VMPG_VSWITCH=%s' % self._args.vmware_vmpg_vswitch)
        if self._args.dpdk:
            ctrl_infos.append('DPDK_MODE=True')
        self.update_vips_in_ctrl_details(ctrl_infos)

        for ctrl_info in ctrl_infos:
            local ("sudo echo %s >> %s" % (ctrl_info, ctrl_details))
        local("sudo cp %s /etc/contrail/ctrl-details" % ctrl_details)
        local("sudo rm %s/ctrl-details" %(self._temp_dir_name))

    def fixup_config_files(self):
        self.fixup_nova_conf()
        super(ComputeOpenstackSetup, self).fixup_config_files()

    def run_services(self):
        contrail_openstack = not(getattr(self._args, 'no_contrail_openstack', False))
        if contrail_openstack:
            if self._fixed_qemu_conf:
                if self.pdist in ['centos', 'fedora', 'redhat']:
                    local("sudo service libvirtd restart")
                if self.pdist in ['Ubuntu']:
                    local("sudo service libvirt-bin restart")

            # running compute-server-setup.sh on cfgm sets nova.conf's
            # sql access from ip instead of localhost, causing privilege
            # degradation for nova tables
            local("sudo compute-server-setup.sh")
        else:
            config_nova = not(getattr(self._args, 'no_nova_config', False))
            if config_nova:
                #use contrail specific vif driver
                local('openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_vif_driver nova_contrail_vif.contrailvif.VRouterVIFDriver')
                # Use noopdriver for firewall
                local('openstack-config --set /etc/nova/nova.conf DEFAULT firewall_driver nova.virt.firewall.NoopFirewallDriver')
                network_api = 'quantum'
                with(open('/etc/nova/nova.conf', 'r+')) as nova_conf:
                    if 'neutron_url' in nova_conf.read():
                        network_api = 'neutron'
                local('openstack-config --set /etc/nova/nova.conf DEFAULT %s_connection_host %s' % (network_api, self._args.cfgm_ip))
                local('openstack-config --set /etc/nova/nova.conf DEFAULT %s_url http://%s:9696' % (network_api, self._args.cfgm_ip))
                local('openstack-config --set /etc/nova/nova.conf DEFAULT %s_admin_password %s' % (network_api, self._args.service_token))
        cpu_mode = self._args.cpu_mode
        cpu_model = self._args.cpu_model
        valid_cpu_modes = ['none', 'host-model', 'host-passthrough', 'custom']
        if cpu_mode is not None and cpu_mode.lower() in valid_cpu_modes:
            local("openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_cpu_mode %s" % cpu_mode.lower())
            if cpu_mode == 'custom':
                if cpu_model is None:
                    raise Exception("cpu_model is required if cpu_mode is 'custom'")
                local("openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_cpu_model %s" % cpu_model)

        super(ComputeOpenstackSetup, self).run_services()

    def setup(self):
        self.disable_selinux()
        self.disable_iptables()
        self.setup_coredump()
        self.fixup_config_files()
        self.build_ctrl_details()
        self.run_services()
        self.add_vnc_config()
