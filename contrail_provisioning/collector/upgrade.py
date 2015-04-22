#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Upgrade's Contrail Collector components."""

from setup import CollectorSetup
from contrail_provisioning.common.upgrade import ContrailUpgrade

from fabric.api import local


class CollectorUpgrade(ContrailUpgrade, CollectorSetup):
    def __init__(self, args_str = None):
        ContrailUpgrade.__init__(self)
        CollectorSetup.__init__(self)

        self.update_upgrade_data()

    def update_upgrade_data(self):
        self.upgrade_data['upgrade'] = self._args.packages

        self.upgrade_data['restore'] += [
            '/etc/contrail/contrail-analytics-api.conf',
            '/etc/contrail/contrail-collector.conf',
            '/etc/contrail/contrail-query-engine.conf',
                                              ]
    def update_config(self):
        # DEvlop
        pass

    def restart(self):
        local('service supervisor-analytics restart')

    def upgrade(self):
        self._upgrade()
        self.upgrade_python_pkgs()
        self.update_config()
        self.restart()


def main():
    collector = CollectorUpgrade()
    collector.upgrade()

if __name__ == "__main__":
    main()
