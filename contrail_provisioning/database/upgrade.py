#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Upgrade's Contrail Database components."""
from distutils.version import LooseVersion

from contrail_provisioning.database.migrate import DatabaseMigrate
from contrail_provisioning.common.upgrade import ContrailUpgrade


class DatabaseUpgrade(ContrailUpgrade, DatabaseMigrate):
    def __init__(self, args_str=None):
        ContrailUpgrade.__init__(self)
        DatabaseMigrate.__init__(self)

        self.update_upgrade_data()

    def update_upgrade_data(self):
        self.upgrade_data['upgrade'] = self._args.packages
        self.upgrade_data['restore'].append(
             '/etc/contrail/contrail-database-nodemgr.conf')

    def upgrade(self):
        # pre-3.0 we are running cassandra 1.2.11, for post-3.0 we want 2.1.x,
        # but we cannot go directly from 1.2.11 to 2.1.x,
        # we first need to go to 2.0.x hence the below steps...
        if (self._args.from_rel < LooseVersion('3.00') and
                self._args.to_rel >= LooseVersion('3.00')):
            self.migrate(self._args.inter_pkg, self._args.final_ver)

        self._upgrade()
        # Kafka is must from release 3.00
        if (self._args.from_rel < LooseVersion('3.00') and
                self._args.to_rel >= LooseVersion('3.00')):
            self.fixup_kafka_server_properties(self._args.self_ip)
        # Adding hostip in contrail-database-nodemgr.conf
        if (self._args.from_rel < LooseVersion('2.20') and
                self._args.to_rel >= LooseVersion('2.20')):
            self.fixup_contrail_database_nodemgr()
        self.restart()


def main():
    database = DatabaseUpgrade()
    database.upgrade()

if __name__ == "__main__":
    main()
