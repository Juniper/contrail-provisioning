#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Upgrade's Contrail Database components."""
from distutils.version import LooseVersion

from setup import DatabaseSetup
from contrail_provisioning.database.migrate import DatabaseMigrate
from contrail_provisioning.common.upgrade import ContrailUpgrade


class DatabaseUpgrade(ContrailUpgrade, DatabaseSetup):
    def __init__(self, args_str=None):
        ContrailUpgrade.__init__(self)
        DatabaseSetup.__init__(self)
        self.update_upgrade_data()

    def update_upgrade_data(self):
        self.upgrade_data['upgrade'] = self._args.packages
        self.upgrade_data['restore'].append(
             '/etc/contrail/contrail-database-nodemgr.conf')
        # From R3.1, zookeeper-3.4.8-0contrail1 is in use
        # which creates zoo.cfg at /etc/zookeeper/zoo.cfg while the older
        # version zookeeper-3.4.3-1 created at /etc/zookeeper/conf/zoo.cfg
        if (self._args.from_rel < LooseVersion('3.1.0.0') and
               self.pdist in ['redhat']):
            self.upgrade_data['backup'] += ['/etc/zookeeper/conf/zoo.cfg']
            self.upgrade_data['restore'] += ['/etc/zookeeper/conf/zoo.cfg']
            self.upgrade_data['rename_config'] += [('/etc/zookeeper/conf/zoo.cfg', '/etc/zookeeper/zoo.cfg')]


    def upgrade(self):
        self._migrator = DatabaseMigrate()
        self._migrator.migrate(data_dir=self._args.data_dir,
                         analytics_data_dir=self._args.analytics_data_dir,
                         ssd_data_dir=self._args.ssd_data_dir,
                         database_listen_ip=self.database_listen_ip,
                         database_seed_list=self.database_seed_list,
                         cassandra_user=self._args.cassandra_user)

        self._upgrade()

        # Accomodate cassandra upgrade, if needed
        self.fixup_cassandra_config_file(self.database_listen_ip,
                                         self.database_seed_list,
                                         self._args.data_dir,
                                         self._args.ssd_data_dir,
                                         cluster_name='Contrail',
                                         user=self._args.cassandra_user)

        # Accomodate Kafka upgrade, if needed
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
