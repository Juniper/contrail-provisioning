#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Upgrade's Contrail Config components."""

from distutils.version import LooseVersion

from fabric.api import local

from setup import ConfigSetup
from contrail_provisioning.common.upgrade import ContrailUpgrade
from contrail_provisioning.config.common import ConfigBaseSetup
from contrail_provisioning.config.openstack import ConfigOpenstackSetup
from contrail_provisioning.database.migrate import DatabaseMigrate


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
        ifmap_dir = '/etc/ifmap-server'
        if self.pdist in ['centos', 'redhat']:
            if (self._args.from_rel < LooseVersion('2.00') and
                self._args.to_rel >= LooseVersion('2.20')):
                ifmap_dir = '/etc/irond'
        self.upgrade_data['backup'] += [ifmap_dir, '/etc/neutron',
                                    '/etc/init.d/contrail-api',
                                    '/etc/init.d/contrail-discovery',
                                    '/etc/sudoers.d/contrail_sudoers',
                                       ]

        self.upgrade_data['restore'] += ['/etc/contrail/vnc_api_lib.ini',
                                   '/etc/contrail/contrail-svc-monitor.conf',
                                   '/etc/contrail/contrail-schema.conf',
                                   '/etc/contrail/contrail-api.conf',
                                   '/etc/contrail/contrail-discovery.conf',
                                   '/etc/contrail/supervisord_config_files/contrail-api.ini',
                                   '/etc/contrail/supervisord_config_files/contrail-discovery.ini',
                                   '/etc/sudoers.d/contrail_sudoers',
                                   '/etc/init.d/contrail-api',
                                   '/etc/init.d/contrail-discovery',
                                   '/etc/neutron',
                                   ifmap_dir,
                                        ]

        # From R3.1, rabbitmq-server will be run as native systemd service
        # and not controlled by supervisor-support-service
        if (self._args.orchestrator != 'vcenter' and
               self._args.from_rel < LooseVersion('3.1.0.0') and
               self.pdist in ['redhat', 'centos']):
            self.upgrade_data['backup'] += ['/usr/lib/systemd/system/rabbitmq-server.service_backup']
            self.upgrade_data['restore'] += ['/usr/lib/systemd/system/rabbitmq-server.service_backup']
            self.upgrade_data['rename_config'] += [('/usr/lib/systemd/system/rabbitmq-server.service_backup',
                                                      '/usr/lib/systemd/system/rabbitmq-server.service')]
            self.upgrade_data['remove_config'] += ['/etc/rc.d/init.d/rabbitmq-server']


        if self._args.orchestrator == 'vcenter':
            self.upgrade_data['backup'].remove('/etc/neutron')
            self.upgrade_data['restore'].remove('/etc/neutron')

        if (self._args.from_rel >= LooseVersion('2.20')):
            self.upgrade_data['restore'].append('/etc/contrail/contrail-config-nodemgr.conf')
        if (self._args.from_rel >= LooseVersion('2.10')):
            self.upgrade_data['restore'].append('/etc/contrail/contrail-device-manager.conf')

        if self._args.manage_db:
            # From R3.1, zookeeper-3.4.8-0contrail1 is in use
            # which creates zoo.cfg at /etc/zookeeper/zoo.cfg while the older
            # version zookeeper-3.4.3-1 created at /etc/zookeeper/conf/zoo.cfg
            if (self._args.from_rel < LooseVersion('3.1.0.0') and
                   self.pdist in ['redhat']):
                self.upgrade_data['backup'] += ['/etc/zookeeper/conf/zoo.cfg']
                self.upgrade_data['restore'] += ['/etc/zookeeper/conf/zoo.cfg']
                self.upgrade_data['rename_config'] += [('/etc/zookeeper/conf/zoo.cfg', '/etc/zookeeper/zoo.cfg')]

    def upgrade(self):
        # Accomodate cassandra upgrade, if needed
        if self._args.manage_db:
            self._migrator = DatabaseMigrate()
            self._migrator.migrate(data_dir=self._args.data_dir,
                             ssd_data_dir=self._args.ssd_data_dir,
                             database_listen_ip=self._args.self_ip,
                             database_seed_list=self._args.seed_list)


        self._upgrade()

        if self._args.manage_db:
            db.fixup_cassandra_config_file(self._args.self_ip,
                                           self._args.seed_list,
                                           self._args.data_dir,
                                           self._args.ssd_data_dir,
                                           cluster_name='ContrailConfigDB')
            db.fixup_cassandra_env_config()
        # Device manager is introduced from release 2.1, So fixup the config
        # file if the upgrade is from pre releases to 2.1 release.
        if (self._args.from_rel < LooseVersion('2.10') and
            self._args.to_rel >= LooseVersion('2.10')):
            self.config_setup.fixup_device_manager_config_file()
        # Seperate contrail-<role>-nodemgr.conf is introduced from release 2.20
        if (self._args.from_rel < LooseVersion('2.20') and
            self._args.to_rel >= LooseVersion('2.20')):
            self.config_setup.fixup_contrail_config_nodemgr()
            # Populate RabbitMQ details in contrail-svc-monitor.conf
            conf_file = '/etc/contrail/contrail-svc-monitor.conf'
            self.set_config(conf_file, 'DEFAULTS', 'rabbit_server',
                            self.config_setup.rabbit_host)
            self.set_config(conf_file, 'DEFAULTS', 'rabbit_port',
                            self.config_setup.rabbit_port)
        # Populate collector configuration to retrieve loadbalancer stats
        if (self._args.from_rel < LooseVersion('2.20') and
            self._args.to_rel >= LooseVersion('2.20')):
            conf_file = '/etc/neutron/plugins/opencontrail/ContrailPlugin.ini'
            self.set_config(conf_file, 'COLLECTOR', 'analytics_api_ip',
                            self._args.internal_vip or self._args.self_ip)
            self.set_config(conf_file, 'COLLECTOR', 'analytics_api_port',
                            '8081')
        # Correct the rabbit server config parameter to use ip:port
        if (self._args.from_rel < LooseVersion('3.00') and
            self._args.to_rel >= LooseVersion('3.00')):
            conf_files = ['/etc/contrail/contrail-api.conf',
                          '/etc/contrail/contrail-schema.conf',
                          '/etc/contrail/contrail-device-manager.conf',
                          '/etc/contrail/contrail-svc-monitor.conf',
                         ]
            for conf_file in conf_files:
                self.del_config(conf_file, 'DEFAULTS', 'rabbit_port')
                self.set_config(conf_file, 'DEFAULTS', 'rabbit_server',
                                self.config_setup.rabbit_servers)



def main():
    config = ConfigUpgrade()
    config.upgrade()

if __name__ == "__main__":
    main()
