#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Upgrade's Contrail Compute components."""

from setup import ComputeSetup
from openstack import ComputeOpenstackSetup
from contrail_provisioning.common.upgrade import ContrailUpgrade

from fabric.api import local


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
        self.upgrade_data['backup'].append('/etc/nova')

        self.upgrade_data['restore'] += ['/etc/contrail/agent_param',
                                 '/etc/contrail/contrail-vrouter-agent.conf',
                                 '/etc/contrail/vrouter_nodemgr_param',
                                 '/etc/nova/nova.conf']
        if self.pdist in ['Ubuntu']:
            self.upgrade_data['restore'].append(
                                    '/etc/nova/nova-compute.conf')

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

    def upgrade(self):
        self._upgrade()
        self.upgrade_python_pkgs()
        if self._args.from_rel == 2.0:
            self.fix_nova_params()
        # Seperate contrail-<role>-nodemgr.conf is introduced from release 2.20
        if (self._args.from_rel < 2.2 and self._args.to_rel >= 2.2):
            self.compute_setup.fixup_contrail_vrouter_nodemgr()


def main():
    compute = ComputeUpgrade()
    compute.upgrade()

if __name__ == "__main__":
    main()
