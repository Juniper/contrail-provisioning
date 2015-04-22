#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Upgrade's Contrail Control components."""

from setup import ControlSetup
from contrail_provisioning.common.upgrade import ContrailUpgrade

from fabric.api import local


class ControlUpgrade(ContrailUpgrade, ControlSetup):
    def __init__(self, args_str = None):
        ContrailUpgrade.__init__(self)
        ControlSetup.__init__(self)

        self.update_upgrade_data()

    def update_upgrade_data(self):
        self.upgrade_data['upgrade'] = self._args.packages

        self.upgrade_data['restore'] += [
                            '/etc/contrail/contrail-control.conf',
                            '/etc/contrail/contrail-dns.conf',
                            '/etc/contrail/dns/contrail-named.conf',
                            '/etc/contrail/dns/contrail-rndc.conf',
                            '/etc/contrail/dns/contrail-named.pid'] 

    def restart(self):
        local('service supervisor-control restart')

    def upgrade(self):
        self._upgrade()
        self.upgrade_python_pkgs()
        self.restart()


def main():
    control = ControlUpgrade()
    control.upgrade()

if __name__ == "__main__":
    main()
