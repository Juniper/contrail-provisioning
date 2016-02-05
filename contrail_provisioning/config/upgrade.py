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
                                        ]

        if (self._args.from_rel >= LooseVersion('2.20')):
            self.upgrade_data['restore'].append('/etc/contrail/contrail-config-nodemgr.conf')
        if (self._args.from_rel >= LooseVersion('2.10')):
            self.upgrade_data['restore'].append('/etc/contrail/contrail-device-manager.conf')

    def upgrade(self):
        self._upgrade()
        self.upgrade_python_pkgs()
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
                self.del_config(conf_file, 'DEFAULT', 'rabbit_port')
                self.set_config(conf_file, 'DEFAULT', 'rabbit_server',
                                self.config_setup.rabbit_servers)



def main():
    config = ConfigUpgrade()
    config.upgrade()

if __name__ == "__main__":
    main()
