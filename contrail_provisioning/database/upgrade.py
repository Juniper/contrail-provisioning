#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Upgrade's Contrail Database components."""
import json
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

    def _change_section(self, conf_file, old_section, new_section):
       is_present = self.has_config(conf_file, old_section)
       if is_present:
           # Get the contents
           contents = json.loads(self.get_config(conf_file, old_section))
           # Delete old section
           self.del_config(conf_file, old_section)
           # Add new section
           for content in contents:
               self.set_config(conf_file, new_section, content[0], content[1])
    # end _change_section

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
        self.fixup_cassandra_env_config()

        # Accomodate Kafka upgrade, if needed
        self.fixup_kafka_server_properties(self._args.self_ip)

        # Adding hostip in contrail-database-nodemgr.conf
        if (self._args.from_rel < LooseVersion('2.20') and
                self._args.to_rel >= LooseVersion('2.20')):
            self.fixup_contrail_database_nodemgr()

        # MessageTablev2 schema was defined in R4.1.0 but not used
        # schema changed in R4.1.1, hence dropping the table
        if (self._args.from_rel == LooseVersion('4.1.0') and
                self._args.to_rel >= LooseVersion('4.1.1')):
            local("cqlsh %s -e 'DROP TABLE \"ContrailAnalyticsCql\".MessageTablev2;'" %
                  (self.database_listen_ip))

        # Change DEFAULT to DEFAULTS in contrail-database-nodemgr.conf
        dn_conf_file = '/etc/contrail/contrail-database-nodemgr.conf'
        self._change_section(dn_conf_file, 'DEFAULT', 'DEFAULTS')
        self.restart()


def main():
    database = DatabaseUpgrade()
    database.upgrade()

if __name__ == "__main__":
    main()
