#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Upgrade's Contrail Compute components."""

import os
from distutils.version import LooseVersion

from setup import ComputeSetup
from openstack import ComputeOpenstackSetup
from contrail_provisioning.common.upgrade import ContrailUpgrade
from contrail_provisioning.compute.common import ComputeBaseSetup

from fabric.api import local
from fabric.context_managers import settings


class ComputeUpgrade(ContrailUpgrade, ComputeSetup):
    def __init__(self, args_str = None):
        ContrailUpgrade.__init__(self)
        ComputeSetup.__init__(self)

        if self._args.orchestrator == 'openstack':
            self.compute_setup = ComputeOpenstackSetup(self._args)
        else:
            self.compute_setup = ComputeBaseSetup(self._args)

        self.update_upgrade_data()

    def update_upgrade_data(self):
        self.upgrade_data['upgrade'] = self._args.packages
        if 'tsn' not in self._args.roles:
            self.upgrade_data['backup'].append('/etc/nova')
            self.upgrade_data['backup'].append('/etc/libvirt')

        if self._args.mode == 'vcenter':
           self.upgrade_data['backup'].remove('/etc/nova')
           self.upgrade_data['backup'].remove('/etc/libvirt')

        self.upgrade_data['restore'] += ['/etc/contrail/agent_param',
                                     '/etc/contrail/contrail-vrouter-agent.conf',
                                     '/etc/contrail/vrouter_nodemgr_param',
                                     '/etc/nova/nova.conf',
                                     '/etc/libvirt/qemu.conf',
                                        ]

        if (self._args.from_rel >= LooseVersion('2.20')):
            self.upgrade_data['restore'].append('/etc/contrail/contrail-vrouter-nodemgr.conf')

        if 'vcenter_compute' in self._args.roles:
            self.upgrade_data['restore'].remove('/etc/contrail/agent_param')
            self.upgrade_data['restore'].remove('/etc/contrail/contrail-vrouter-agent.conf')
            self.upgrade_data['restore'].remove('/etc/contrail/vrouter_nodemgr_param')
            self.upgrade_data['restore'].remove('/etc/contrail/contrail-vrouter-nodemgr.conf')


        if self.pdist in ['Ubuntu']:
            self.upgrade_data['restore'].append(
                                    '/etc/nova/nova-compute.conf')
        if self._args.mode == 'vcenter':
           self.upgrade_data['restore'].remove('/etc/nova/nova.conf')
           self.upgrade_data['restore'].remove('/etc/nova/nova-compute.conf')
           self.upgrade_data['restore'].remove('/etc/libvirt/qemu.conf')
        if 'tsn' in self._args.roles:
            self.upgrade_data['restore'].remove('/etc/nova/nova.conf')
            self.upgrade_data['restore'].remove('/etc/libvirt/qemu.conf')
            if self.pdist in ['Ubuntu']:
                self.upgrade_data['restore'].remove('/etc/nova/nova-compute.conf')
        if 'toragent' in self._args.roles:
            # TODO :Restore toragent config files if required.
            pass

    def fix_nova_params(self):
        # Upgrade nova parameters in nova.conf of compute host from 2.0 to >2.1
        if self._args.internal_vip:
            nova_conf_file = '/etc/nova/nova.conf'
            openstack_compute_service = 'openstack-nova-compute'
            if self.pdist in ['Ubuntu']:
                openstack_compute_service = 'nova-compute'
            local("service %s stop" % openstack_compute_service)
            local("openstack-config --set %s DEFAULT rpc_response_timeout 30" %
                   nova_conf_file)
            local("openstack-config --set %s DEFAULT report_interval 15" %
                   nova_conf_file)
            local("service %s start" % openstack_compute_service)

    def fix_tor_agent_init_script(self):
        for tor_file in os.listdir('/etc/init.d/'):
            if 'contrail-tor-agent' in tor_file:
                local("cp /etc/init.d/contrail-vrouter-agent /etc/init.d/%s " % (tor_file))

    def fix_nova_config_kv3_params(self):
        local("openstack-config --set /etc/nova/nova.conf neutron project_domain_name Default")
        local("openstack-config --set /etc/nova/nova.conf neutron user_domain_name Default")

    def fix_agent_params(self):
        # kmod=vrouter after introduction of modprobe in centos/redhat
        # platforms. Ensure all upgraded system has kmod=vrouter
        with settings(warn_only=True):
            local("sed -i 's$^kmod[ ]*=[ ]*/lib/modules/[^/]*/extra/net/vrouter/vrouter.ko$kmod=vrouter$g' /tmp/np-agent-param")
        local("grep '^kmod[ ]*=[ ]*vrouter' /etc/contrail/agent_param")

    def fixup_apparmor(self):
        global LIBVIRT_QEMU_HELPER_TMP_FILE
        LIBVIRT_QEMU_HELPER_TMP_FILE = '/tmp/libvirt-qemu'
        global LIBVIRT_QEMU_HELPER_FILE
        LIBVIRT_QEMU_HELPER_FILE = '/etc/apparmor.d/abstractions/libvirt-qemu'
        virt_qemu_present=local('sudo ls %s 2>/dev/null | wc -l'
                                    %(LIBVIRT_QEMU_HELPER_FILE), capture=True)
        if virt_qemu_present != '0':
            global_virt_tmp_helper=local('sudo cat %s | \
                                    grep -n "deny \/tmp\/" | wc -l'
                                    %(LIBVIRT_QEMU_HELPER_FILE), capture=True)
            if global_virt_tmp_helper != '0':
                snap_lineno=int(local('sudo cat %s | \
                                    grep -n "deny \/tmp\/" | \
                                    cut -d \':\' -f 1'
                                    %(LIBVIRT_QEMU_HELPER_FILE), capture=True))
                local('sudo head -n %d %s > %s' %(snap_lineno-1,
                                    LIBVIRT_QEMU_HELPER_FILE,
                                    LIBVIRT_QEMU_HELPER_TMP_FILE))
                local('sudo tail -n +%d %s >> %s' %(snap_lineno+1,
                                    LIBVIRT_QEMU_HELPER_FILE,
                                    LIBVIRT_QEMU_HELPER_TMP_FILE))
                local('sudo echo "  capability mknod," \
                                    >> %s' %(LIBVIRT_QEMU_HELPER_TMP_FILE))
                local('sudo echo "  /etc/ceph/* r," \
                                    >> %s' %(LIBVIRT_QEMU_HELPER_TMP_FILE))
                local('sudo echo "  /etc/qemu-ifup ixr," \
                                    >> %s' %(LIBVIRT_QEMU_HELPER_TMP_FILE))
                local('sudo echo "  /etc/qemu-ifdown ixr," \
                                    >> %s' %(LIBVIRT_QEMU_HELPER_TMP_FILE))
                local('sudo echo "  owner /tmp/* rw," \
                                    >> %s' %(LIBVIRT_QEMU_HELPER_TMP_FILE))
                local('sudo echo "  /tmp/memfd-* rwk," \
                                    >> %s' %(LIBVIRT_QEMU_HELPER_TMP_FILE))
                local('sudo cp -f %s %s' %(LIBVIRT_QEMU_HELPER_TMP_FILE,
                                    LIBVIRT_QEMU_HELPER_FILE))

    def upgrade(self):
        self.disable_apt_get_auto_start()
        self._upgrade()
        self._upgrade_all_package()
        if ((self.pdist not in ['Ubuntu']) and
            ('running' in local('service supervisor-vrouter status',
                                capture=True))):
            local("service supervisor-vrouter stop")
        if self.pdist not in ['Ubuntu'] and \
           self._args.from_rel >= LooseVersion('2.21'):
            self.fix_agent_params()
        if (self.compute_setup.config_nova and
                self._args.orchestrator == 'openstack'):
           if self._args.from_rel == LooseVersion('2.00'):
               self.fix_nova_params()
        # Seperate contrail-<role>-nodemgr.conf is introduced from release 2.20
        if (self._args.from_rel < LooseVersion('2.20') and
            self._args.to_rel >= LooseVersion('2.20')):
            self.compute_setup.fixup_contrail_vrouter_nodemgr()
        if 'toragent' in self._args.roles:
            if (self._args.to_rel >= LooseVersion('3.00')):
                self.fix_tor_agent_init_script()
        # In 3.2+, nova.conf [neutron] extra parameters are created for v3
        if ('v3' in self._args.keystone_version and
                self._args.from_rel <= LooseVersion('3.1.2.0')):
            self.fix_nova_config_kv3_params()
        if self._args.dpdk:
            self.fixup_apparmor()
        self.enable_apt_get_auto_start()

def main():
    compute = ComputeUpgrade()
    compute.upgrade()

if __name__ == "__main__":
    main()
