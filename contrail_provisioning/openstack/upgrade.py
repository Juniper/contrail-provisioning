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

    def fix_cmon_config(self):
        with settings(warn_only=True):
            local('service contrail-hamon stop')
            local('kill -9 $(pidof cmon)')
            local("mysql -uroot -p$(cat /etc/contrail/mysql.token) -e 'drop database cmon'")
            local("sed -i '/pidfile=\/var\/run\//c\pidfile=\/var\/run\/cmon\/' /etc/cmon.cnf")

    def fix_cmon_param_file(self):
        with settings(warn_only=True):
            cmon_param='/etc/contrail/ha/cmon_param'
            local("grep -q '# New Param in 2.1 #' %s || echo '# New Param in 2.1 #' >> %s" % (cmon_param, cmon_param))
            local("sed -i '/EVIP/d' %s" % cmon_param)
            local("sed -i '$ a\EVIP=%s' %s" % (self._args.external_vip, cmon_param))
            local("grep -q '# Modified Params in 2.2 #' %s || echo '# Modified Params in 2.2 #' >> %s" % (cmon_param, cmon_param))
            local("sed -i '/PERIODIC_RMQ_CHK_INTER/d' %s" % cmon_param)
            local("sed -i '$ a\PERIODIC_RMQ_CHK_INTER=60' %s" % cmon_param)
            local("sed -i '/RABBITMQ_RESET/d' %s" % cmon_param)
            local("sed -i '$ a\RABBITMQ_RESET=True' %s" % cmon_param)
            local("sed -i '/RABBITMQ_MNESIA_CLEAN/d' %s" % cmon_param)
            local("sed -i '$ a\RABBITMQ_MNESIA_CLEAN=False' %s" % cmon_param)
            local("sed -i '/RMQ_CLIENTS/d' %s" % cmon_param)
            local("sed -i '$ a\RMQ_CLIENTS=(\"nova-conductor\" \"nova-scheduler\")' %s" % cmon_param)

    def fix_haproxy_config(self):
        with settings(warn_only=True):
             hap_cfg='/etc/haproxy/haproxy.cfg'
             local("sed -i -e 's/timeout client 48h/timeout client 0/g' %s" % hap_cfg)
             local("sed -i -e 's/timeout server 48h/timeout server 0/g' %s" % hap_cfg)
             local("sed -i -e 's/timeout client 24h/timeout client 0/g' %s" % hap_cfg)
             local("sed -i -e 's/timeout server 24h/timeout server 0/g' %s" % hap_cfg)


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
            self._args.from_rel <= 2.2 and
            self._args.to_rel >= 2.2):
            self.fix_cmon_config()
            self.fix_cmon_param_file()
            self.fix_haproxy_config()

        self.restart()


def main():
    openstack = OpenstackUpgrade()
    openstack.upgrade()

if __name__ == "__main__":
    main()
