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

        if (self._args.from_rel >= 2.2):
            self.upgrade_data['restore'].append('/etc/contrail/contrail-analytics-nodemgr.conf')

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

        # Kafka is introduced from release 2.30
        if (self._args.from_rel <= 2.2 and self._args.to_rel > 2.2):
            # regenerate alarm-gen INI file
            ALARM_GEN_INI_FILE = \
                '/etc/contrail/supervisord_analytics_files/contrail-alarm-gen.ini'
            cnd = os.path.exists(ALARM_GEN_INI_FILE)
            if cnd:
                local('rm -rf %s' % ALARM_GEN_INI_FILE)
            self.set_config(\
                ALARM_GEN_INI_FILE, 'program:contrail-alarm-gen', 'command',
                '/usr/bin/contrail-alarm-gen -c /etc/contrail/contrail-alarm-gen.conf')
            self.set_config(\
                ALARM_GEN_INI_FILE, 'program:contrail-alarm-gen', 'priority',
                '440')
            self.set_config(\
                ALARM_GEN_INI_FILE, 'program:contrail-alarm-gen', 'autostart',
                'true')
            self.set_config(\
                ALARM_GEN_INI_FILE, 'program:contrail-alarm-gen', 'killasgroup',
                'true')
            self.set_config(\
                ALARM_GEN_INI_FILE, 'program:contrail-alarm-gen', 'stopsignal',
                'KILL')
            self.set_config(\
                ALARM_GEN_INI_FILE, 'program:contrail-alarm-gen',
                'stdout_capture_maxbytes','1MB')
            self.set_config(\
                ALARM_GEN_INI_FILE, 'program:contrail-alarm-gen',
                'redirect_stderr','true')
            self.set_config(\
                ALARM_GEN_INI_FILE, 'program:contrail-alarm-gen',
                'stdout_logfile','/var/log/contrail/contrail-alarm-gen-stdout.log')
            self.set_config(\
                ALARM_GEN_INI_FILE, 'program:contrail-alarm-gen',
                'stderr_logfile','/var/log/contrail/contrail-alarm-gen-stderr.log')
            self.set_config(\
                ALARM_GEN_INI_FILE, 'program:contrail-alarm-gen',
                'startsecs','5')
            self.set_config(\
                ALARM_GEN_INI_FILE, 'program:contrail-alarm-gen',
                'exitcodes','0')
            self.set_config(\
                ALARM_GEN_INI_FILE, 'program:contrail-alarm-gen',
                'user','contrail')
            self.fixup_contrail_alarm_gen()
            kafka_broker_list = [server[0] + ":9092"\
                                 for server in self.cassandra_server_list]
            kafka_broker_list_str = ' '.join(map(str, kafka_broker_list))
            local('openstack-config --set\
                  /etc/contrail/contrail-collector.conf\
                  DEFAULT kafka_broker_list %s' % kafka_broker_list_str)
        self.restart()


def main():
    collector = CollectorUpgrade()
    collector.upgrade()

if __name__ == "__main__":
    main()
