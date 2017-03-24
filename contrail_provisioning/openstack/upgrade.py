#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Upgrade's Contrail Openstack components."""

from distutils.version import LooseVersion

from setup import OpenstackSetup
from contrail_provisioning.common.upgrade import ContrailUpgrade
from fabric.context_managers import settings

from fabric.api import local


class OpenstackUpgrade(ContrailUpgrade, OpenstackSetup):
    def __init__(self, args_str=None):
        ContrailUpgrade.__init__(self)
        OpenstackSetup.__init__(self)

        self.update_upgrade_data()
        if self.pdist in ['Ubuntu']:
            self.openstack_services = ['supervisor-openstack']
        else:
            self.openstack_services = ['openstack-cinder-api', 'openstack-cinder-scheduler',
                                       'openstack-glance-api', 'openstack-glance-registry',
                                       'openstack-heat-api', 'openstack-heat-engine',
                                       'openstack-keystone', 'openstack-nova-api',
                                       'openstack-nova-conductor', 'openstack-nova-consoleauth',
                                       'openstack-nova-novncproxy', 'openstack-nova-scheduler']
        self.nova_conf = "/etc/nova/nova.conf"

    def update_upgrade_data(self):
        self.upgrade_data['upgrade'] = self._args.packages
        if self.pdist not in ['Ubuntu']:
            self.upgrade_data['upgrade'].append('openstack-dashboard')

        backup_data = ['/etc/keystone',
                       '/etc/glance',
                       '/etc/nova',
                       '/etc/cinder']
        if self._args.internal_vip:
            backup_data += ['/etc/mysql',
                            '/etc/keepalived',
                            '/etc/cmon.cnf']
        self.upgrade_data['backup'] += backup_data

        self.upgrade_data['restore'] = self.upgrade_data['backup']
        # Never restore /etc/contrail fully, Because all contrail
        # services share same config dir, During upgrade rerun
        # restoring whole /etc/contrail will replace config files
        # with older version
        self.upgrade_data['restore'].remove('/etc/contrail')

    def stop(self):
        with settings(warn_only=True):
            for service in self.openstack_services:
                if ('running' in
                        local('service %s status' % service,
                              capture=True)):
                    local('service %s stop' % service)

    def restart(self):
        for service in self.openstack_services:
            local('service %s restart' % service)

    def fix_cmon_param_file(self):
        with settings(warn_only=True):
            cmon_param = '/etc/contrail/ha/cmon_param'
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

    def fix_cmon_config(self):
        with settings(warn_only=True):
            local('service contrail-hamon stop')
            local('kill -9 $(pidof cmon)')
            local("mysql -uroot -p$(cat /etc/contrail/mysql.token) -e 'drop database cmon'")
            local("sed -i '/pidfile=\/var\/run\//c\pidfile=\/var\/run\/cmon\/' /etc/cmon.cnf")

    def fix_haproxy_config(self):
        with settings(warn_only=True):
            hap_cfg = '/etc/haproxy/haproxy.cfg'
            local("sed -i -e 's/timeout client 48h/timeout client 0/g' %s" % hap_cfg)
            local("sed -i -e 's/timeout server 48h/timeout server 0/g' %s" % hap_cfg)
            local("sed -i -e 's/timeout client 24h/timeout client 0/g' %s" % hap_cfg)
            local("sed -i -e 's/timeout server 24h/timeout server 0/g' %s" % hap_cfg)

    def fix_sriov_nova_config(self):
        with settings(warn_only=True):
            if (self._args.from_rel >= LooseVersion('3.00')):
                default_filter= ('RetryFilter, AvailabilityZoneFilter, RamFilter, DiskFilter, '
                                 'ComputeFilter, ComputeCapabilitiesFilter, ImagePropertiesFilter, '
                                 'ServerGroupAntiAffinityFilter, ServerGroupAffinityFilter, PciPassthroughFilter')
            local("openstack-config --set %s DEFAULT scheduler_default_filters '%s'" % (self.nova_conf, default_filter))

    def upgrade(self):
        self.stop()
        self._upgrade()
        # In Rel 2.0 and 2.1, the cmon was started as part of CMON monitor
        # script so that we could give a specific runtime directory.
        # From 2.2, we are using the conf file to specify the runtime
        # directory parameter.
        # Also, from 2.2, CMON tables are being
        # removed from Galera clustering. Hence, the following change
        # will drop CMON DB and re-provision CMON.
        if (self._args.internal_vip and
                self._args.from_rel <= LooseVersion('2.20') and
                self._args.to_rel >= LooseVersion('2.20')):
            self.fix_cmon_config()
            self.fix_cmon_param_file()
            self.fix_haproxy_config()
        if (self._args.sriov):
            self.fix_sriov_nova_config()
        self.restart()


def main():
    openstack = OpenstackUpgrade()
    openstack.upgrade()

if __name__ == "__main__":
    main()
