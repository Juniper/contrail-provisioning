#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Upgrade's Contrail Collector components."""

import os

from fabric.api import local

from setup import CollectorSetup
from contrail_provisioning.common.upgrade import ContrailUpgrade


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
        # Seperate contrail-<role>-nodemgr.conf is introduced from release 2.20
        if (self._args.from_rel < 2.2 and self._args.to_rel >= 2.2):
            self.fixup_contrail_analytics_nodemgr()
            # contrail-snmp-collector support
            self.fixup_contrail_snmp_collector()
            # contrail-topology support
            self.fixup_contrail_topology()
            # Create contrail-keystone-auth.conf
            if not os.path.exists('/etc/contrail/contrail-keystone-auth.conf'):
                self.fixup_keystone_auth_config_file()
            # Kafka is introduced from release 2.20
            if self._args.kafka_enabled == 'True':
                self.fixup_contrail_alarm_gen()
                kafka_broker_list = [server[0] + ":9092"\
                                     for server in self.cassandra_server_list]
                kafka_broker_list_str = ' '.join(map(str, kafka_broker_list))
                local('openstack-config --set\
                      /etc/contrail/contrail-collector.conf\
                      DEFAULT kafka_broker_list %s' % kafka_broker_list_str)
            else:
                if os.path.exists('/etc/contrail/supervisord_analytics_files/contrail-alarm-gen.ini'):
                      os.remove('/etc/contrail/supervisord_analytics_files/contrail-alarm-gen.ini')

        self.restart()


def main():
    collector = CollectorUpgrade()
    collector.upgrade()

if __name__ == "__main__":
    main()
