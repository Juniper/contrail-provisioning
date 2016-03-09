#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Upgrade's Contrail Database components."""

from distutils.version import LooseVersion

from setup import DatabaseSetup
from contrail_provisioning.common.upgrade import ContrailUpgrade

from fabric.api import local


class DatabaseUpgrade(ContrailUpgrade, DatabaseSetup):
    def __init__(self, args_str = None):
        ContrailUpgrade.__init__(self)
        DatabaseSetup.__init__(self)

        self.update_upgrade_data()

    def update_upgrade_data(self):
        self.upgrade_data['upgrade'] = self._args.packages
        self.upgrade_data['restore'].append(
             '/etc/contrail/contrail-database-nodemgr.conf')

    def restart(self):
        local('service zookeeper restart')
        local('service supervisor-database restart')

    def upgrade(self):
        self._upgrade()
        # Kafka is introduced from release 2.20
        if (self._args.from_rel < LooseVersion('2.20') and
            self._args.to_rel >= LooseVersion('2.20')):
            self.fixup_kafka_server_properties()
            # Adding hostip in contrail-database-nodemgr.conf
            self.fixup_contrail_database_nodemgr()
        self.restart()


def main():
    database = DatabaseUpgrade()
    database.upgrade()

if __name__ == "__main__":
    main()
