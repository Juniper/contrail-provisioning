#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Upgrade's Contrail Collector components."""

import os
from distutils.version import LooseVersion

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

        if (self._args.from_rel >= LooseVersion('2.20')):
            self.upgrade_data['restore'].append('/etc/contrail/contrail-analytics-nodemgr.conf')

        #python-kafka-python is replaced by python-kafka
        if (self._args.from_rel >= LooseVersion('2.20') and
                self._args.from_rel < LooseVersion('3.00') and
                    self._args.to_rel >= LooseVersion('3.00')):
            self.upgrade_data['replace'].append(('python-kafka-python', 'python-kafka'))

    def restart(self):
        local('service supervisor-analytics restart')

    def upgrade(self):
        self._upgrade()
        self.update_config()
        self.restart()

    def update_config(self):
        # Seperate contrail-<role>-nodemgr.conf is introduced from release 2.20
        if (self._args.from_rel < LooseVersion('2.20') and
            self._args.to_rel >= LooseVersion('2.20')):
            self.fixup_contrail_analytics_nodemgr()
            # contrail-snmp-collector support
            self.fixup_contrail_snmp_collector()
            # contrail-topology support
            self.fixup_contrail_topology()
            # Create contrail-keystone-auth.conf
            if not os.path.exists('/etc/contrail/contrail-keystone-auth.conf'):
                self.fixup_keystone_auth_config_file()

        # From 3.0:
        # 1. Alarmgen is enabled by default.
        # 2. Analytics services no longer connect to the local collector.
        #    All analytics services other than collector would subscribe for
        #    the collector service with discovery server.
        # 3. Collector uses Zookeeper servers.
        # 4. Collector, query engine, analytics api use CQL to connect to
        #    cassandra and hence the port in DEFAULT.cassandra_server_list
        #    needs to be updated to the default CQL port - 9042
        if (self._args.from_rel < LooseVersion('3.00') and
            self._args.to_rel >= LooseVersion('3.00')):
            collector_conf = '/etc/contrail/contrail-collector.conf'
            qe_conf = '/etc/contrail/contrail-query-engine.conf'
            # Sanitize qe_conf by removing leading spaces from each line so
            # that iniparse can open it
            local('sed "s/^[ \t]*//" -i %s' % (qe_conf))
            # 1. Alarmgen is enabled by default.
            self.fixup_contrail_alarm_gen()
            kafka_broker_list = [server[0] + ":9092"\
                                 for server in self.cassandra_server_list]
            kafka_broker_list_str = ' '.join(map(str, kafka_broker_list))
            self.set_config(collector_conf, 'DEFAULT', 'kafka_broker_list',
                kafka_broker_list_str)
            # 2. Analytics services no longer connect to the local collector.
            #    All analytics services other than collector would subscribe for
            #    the collector service with discovery server.
            topology_conf = '/etc/contrail/contrail-topology.conf'
            self.set_config(topology_conf, 'DISCOVERY',
                            'disc_server_ip', self._args.cfgm_ip)
            self.set_config(topology_conf, 'DISCOVERY',
                            'disc_server_port', '5998')
            self.set_config(qe_conf, 'DISCOVERY',
                            'server', self._args.cfgm_ip)
            self.set_config(qe_conf, 'DISCOVERY',
                            'port', '5998')
            self.del_config(qe_conf, 'DEFAULT', 'collectors')
            analytics_api_conf = '/etc/contrail/contrail-analytics-api.conf'
            self.del_config(analytics_api_conf, 'DEFAULTS', 'collectors')
            # 3. Collector uses Zookeeper servers.
            if self.zookeeper_server_list:
                self.set_config(collector_conf, 'DEFAULT',
                    'zookeeper_server_list',
                    ','.join('%s:%s' % zookeeper_server for zookeeper_server in \
                    self.zookeeper_server_list))
            # 4. Collector, query engine, analytics api use CQL to connect to
            #    cassandra and hence the port in DEFAULT.cassandra_server_list
            #    needs to be updated to the default CQL port - 9042
            qe_cass_server_list = self.get_config(qe_conf, 'DEFAULT',
                'cassandra_server_list')
            self.set_config(qe_conf, 'DEFAULT', 'cassandra_server_list',
                ' '.join('%s:%s' % (server.split(':')[0], '9042') for server \
                in qe_cass_server_list.split()))
            collector_cass_server_list = self.get_config(collector_conf, 'DEFAULT',
                'cassandra_server_list')
            self.set_config(collector_conf, 'DEFAULT', 'cassandra_server_list',
                ' '.join('%s:%s' % (server.split(':')[0], '9042') for server \
                in collector_cass_server_list.split()))
            analytics_api_cass_server_list = self.get_config(analytics_api_conf,
                'DEFAULTS', 'cassandra_server_list')
            self.set_config(analytics_api_conf, 'DEFAULTS',
                'cassandra_server_list',
                ' '.join('%s:%s' % (server.split(':')[0], '9042') for server \
                in analytics_api_cass_server_list.split()))

def main():
    collector = CollectorUpgrade()
    collector.upgrade()

if __name__ == "__main__":
    main()
