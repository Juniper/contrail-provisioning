#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Upgrade's Contrail Database components."""

from distutils.version import LooseVersion
from subprocess import Popen, PIPE

from setup import DatabaseSetup
from contrail_provisioning.common.upgrade import ContrailUpgrade

from fabric.api import local


class DatabaseUpgrade(ContrailUpgrade, DatabaseSetup):
    def __init__(self, args_str = None):
        ContrailUpgrade.__init__(self)
        DatabaseSetup.__init__(self)

        self.update_upgrade_data()

    def update_upgrade_data(self):
        self.upgrade_data['upgrade'] = self._args.packages
        self.upgrade_data['restore'].append(
             '/etc/contrail/contrail-database-nodemgr.conf')

    def restart(self):
        local('service zookeeper restart')
        local('service contrail-database restart')
        local('service supervisor-database restart')

    def fixup_cassandra_upgrade(self):
        # pre-3.0 we are running cassandra 1.2.11, for post-3.0 we want 2.1.x, but
        # we cannot go directly from 1.2.11 to 2.1.x, we first need to go to 2.0.x
        # hence the below steps...
        if (not (self._args.from_rel < LooseVersion('3.00') and
                    self._args.to_rel >= LooseVersion('3.00'))):
            return

        if self.pdist in ['Ubuntu']:
            cassandra_version = local("dpkg -s cassandra | grep Version | awk '{print $2}'", capture=True)
        else:
            cassandra_version = local("rpm -q --queryformat '%%{RELEASE}' cassandra21", capture=True)

        if (cassandra_version.succeeded and
            LooseVersion(cassandra_version) >= LooseVersion('2.1')):
            print "Cassandra already upgraded to %s" % cassandra_version
            return

        # run nodetool upgradesstables
        print 'Upgrading database sstables...'
        local('nodetool upgradesstables')
        local('service contrail-database stop')

        # first change owner on directories
        local('chown -R cassandra: /var/lib/cassandra/')
        local('chown -R cassandra: /var/log/cassandra/')
        if self._args.data_dir:
            local('chown -R cassandra: %s' % self._args.data_dir)
        if self._args.analytics_data_dir:
            local('chown -R cassandra: %s' % self._args.analytics_data_dir)
        if self._args.ssd_data_dir:
            local('chown -R cassandra: %s' % self._args.ssd_data_dir)
        # upgrade cassandra to 2.0.17 first
        if self.pdist in ['Ubuntu']:
            cmd = 'dpkg --force-overwrite --force-confnew --install '
            cmd += '/opt/contrail/contrail_install_repo/cassandra_2.0.17_all.deb'
        else:
            cmd = 'rpm --nodeps -e cassandra12'
            local(cmd)
            cmd = 'yum -y install /opt/contrail/contrail_install_repo/cassandra20-2.0.17-1.noarch.rpm'
        local(cmd)
        local('service cassandra stop')
        self.fixup_cassandra_config_file(self.database_listen_ip,
                                         self.database_seed_list,
                                         self._args.data_dir,
                                         self._args.ssd_data_dir,
                                         cluster_name='Contrail')
        local('service cassandra start;sleep 5')

        cassandra_cli_cmd = "cassandra-cli --host " + self._args.self_ip + \
            " --batch  < /dev/null | grep 'Connected to:'"
        while True:
            proc = Popen(cassandra_cli_cmd, shell=True, stdout=PIPE, stderr=PIPE)
            (output, errout) = proc.communicate()
            if proc.returncode == 0:
                break;
            local('sleep 5')

        # run nodetool upgradesstables again
        print 'Upgrading database sstables...'
        local('nodetool upgradesstables')
        local('service cassandra stop')

        # upgrade cassandra to 2.1.9 [this can be skipped]
        if self.pdist in ['Ubuntu']:
            cmd = 'DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes'
            cmd += ' -o Dpkg::Options::="--force-overwrite"'
            cmd += ' -o Dpkg::Options::="--force-confnew" install %s' % 'cassandra>=2.1.9'
        else:
            cmd = 'rpm --nodeps -e cassandra20'
            local(cmd)
            local('yum clean all')
            cmd = 'yum -y --disablerepo=* --enablerepo=contrail*'
            cmd += ' install %s' % 'cassandra21>=2.1.9'

        local(cmd)
        local('service cassandra stop')
        # Accomodate cassandra upgrade, if needed
        self.fixup_cassandra_config_file(self.database_listen_ip,
                                         self.database_seed_list,
                                         self._args.data_dir,
                                         self._args.ssd_data_dir,
                                         cluster_name='Contrail')

    def upgrade(self):
        self.fixup_cassandra_upgrade()

        self._upgrade()
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
