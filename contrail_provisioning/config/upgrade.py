#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Upgrade's Contrail Config components."""

from setup import ConfigSetup
from contrail_provisioning.common.upgrade import ContrailUpgrade
from contrail_provisioning.config.common import ConfigBaseSetup
from contrail_provisioning.config.openstack import ConfigOpenstackSetup


class ConfigUpgrade(ContrailUpgrade, ConfigSetup):
    def __init__(self, args_str = None):
        ContrailUpgrade.__init__(self)
        ConfigSetup.__init__(self)

        if self._args.orchestrator == 'openstack':
            self.config_setup = ConfigOpenstackSetup(self._args)
        else:
            self.config_setup = ConfigBaseSetup(self._args)

        self.update_upgrade_data()

    def update_upgrade_data(self):
        self.upgrade_data['upgrade'] = self._args.packages

        ifmap_dir = '/etc/irond'
        if self.pdist in ['Ubuntu']:
            ifmap_dir = '/etc/ifmap-server'
        self.upgrade_data['backup'] += [ifmap_dir, '/etc/neutron']

        self.upgrade_data['restore'] += ['/etc/contrail/vnc_api_lib.ini',
                                     '/etc/contrail/contrail-svc-monitor.conf',
                                     '/etc/contrail/contrail-schema.conf',
                                     '/etc/contrail/contrail-api.conf',
                                     '/etc/contrail/contrail-discovery.conf',
                                             ]

    def upgrade(self):
        self._upgrade()
        self.upgrade_python_pkgs()
        # Device manager is introduced from release 2.1, So fixup the config
        # file if the upgrade is from pre releases to 2.1 release.
        if (self._args.from_rel < 2.1 and self._args.to_rel >= 2.1):
            self.config_setup.fixup_device_manager_config_file()


def main():
    config = ConfigUpgrade()
    config.upgrade()

if __name__ == "__main__":
    main()
