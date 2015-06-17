#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Upgrade's Contrail Openstack components."""

from setup import OpenstackSetup
from contrail_provisioning.common.upgrade import ContrailUpgrade
from fabric.context_managers import settings

from fabric.api import local


class OpenstackUpgrade(ContrailUpgrade, OpenstackSetup):
    def __init__(self, args_str = None):
        ContrailUpgrade.__init__(self)
        OpenstackSetup.__init__(self)

        self.update_upgrade_data()

    def update_upgrade_data(self):
        self.upgrade_data['upgrade'] = self._args.packages
        if self.pdist not in ['Ubuntu']:
            self.upgrade_data['upgrade'].append('openstack-dashboard')

        backup_data = ['/etc/keystone',
                       '/etc/glance',
                       '/etc/nova',
                       '/etc/cinder',
                      ]
        if self._args.internal_vip:
            backup_data += ['/etc/mysql',
                            '/etc/keepalived',
                            '/etc/contrail/ha',
                            '/etc/cmon.cnf']
        self.upgrade_data['backup'] += backup_data

        self.upgrade_data['restore'] = self.upgrade_data['backup']

    def stop(self):
        with settings(warn_only=True):
            if ('running' in
                local('service supervisor-openstack status', capture=True)):
                local('service supervisor-openstack stop')

    def restart(self):
        local('service supervisor-openstack restart')

    def fix_cmon_param_file(self):
        with settings(warn_only=True):
            local("sed -i '$ a\EVIP=%s' /etc/contrail/ha/cmon_param" % self._args.external_vip)
            local("sed -i '$ a\PERIODIC_RMQ_CHK_INTER=60' /etc/contrail/ha/cmon_param")
            local("sed -i '$ a\RABBITMQ_RESET=False' /etc/contrail/ha/cmon_param")

    def fix_cmon_config(self):
        with settings(warn_only=True):
            local('service contrail-hamon stop')
            local('kill -9 $(pidof cmon)')
            local("mysql -uroot -p$(cat /etc/contrail/mysql.token) -e 'drop database cmon'")
            local("sed -i '/pidfile=\/var\/run\//c\pidfile=\/var\/run\/cmon\/' /etc/cmon.cnf")

    def upgrade(self):
        self.stop()
        self._upgrade()
        self.upgrade_python_pkgs()
        # In Rel 2.0 and 2.1, the cmon was started as part of CMON monitor
        # script so that we could give a specific runtime directory.
        # From 2.2, we are using the conf file to specify the runtime
        # directory parameter.
        # Also, from 2.2, CMON tables are being
        # removed from Galera clustering. Hence, the following change
        # will drop CMON DB and re-provision CMON.
        if (self._args.internal_vip and
            self._args.from_rel < 2.2 and
            self._args.to_rel >= 2.2):
            self.fix_cmon_config()
            self.fix_cmon_param_file()
        self.restart()


def main():
    openstack = OpenstackUpgrade()
    openstack.upgrade()

if __name__ == "__main__":
    main()
