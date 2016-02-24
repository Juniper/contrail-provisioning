#!/usr/bin/python
#
# Copyright (c) 2016 Juniper Networks, Inc. All rights reserved.
#
"""Migrates Cassandra Database to specified Version."""
import os
import sys
from distutils.version import LooseVersion
from subprocess import Popen, PIPE

from setup import DatabaseSetup

from fabric.api import local


class DatabaseMigrate(DatabaseSetup):
    def __init__(self, args_str=None):
        DatabaseSetup.__init__(self)
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        repo = '/opt/contrail/contrail_install_repo'
        if self.pdist in ['Ubuntu']:
            self.inter_default = os.path.join(
                    repo, 'cassandra_2.0.17_all.deb')
        else:
            self.inter_default = os.path.join(
                    repo, 'cassandra20-2.0.17-1.noarch.rpm')

        self.global_defaults = {
            'inter_pkg': self.inter_default,
            'final_ver': '2.1.9'
        }
        self.parse_args(args_str)

    def parse_args(self, args_str):
        parser = self._parse_args(args_str)
        parser.add_argument("--inter-pkg",
                            help="Intermediate version of Cassandra package")
        parser.add_argument("--final-ver",
                            help="Final version of Cassandra package")
        self._args = parser.parse_args(self.remaining_argv)

    def migrated(self):
        if self.pdist in ['Ubuntu']:
            cmd = "dpkg -s cassandra | grep Version | awk '{print $2}'"
        else:
            cmd = "rpm -q --queryformat '%%{RELEASE}' cassandra21"
        cassandra_version = local(cmd, capture=True)
        if (cassandra_version.succeeded and
                LooseVersion(cassandra_version) >= LooseVersion('2.1')):
            print "Cassandra already upgraded to %s" % cassandra_version
            return True
        return False

    def stop_cassandra(self):
        local('service contrail-database stop')

    def upgrade_sstables(self):
        print 'Upgrading database sstables...'
        local('nodetool upgradesstables')

    def migrate(self, inter_pkg, final_ver):
        # run nodetool upgradesstables
        self.upgrade_sstables()
        self.stop_cassandra()

        # upgrade cassandra to intermediate rel first
        if self.pdist in ['Ubuntu']:
            cmd = ' '.join(['dpkg --force-overwrite --force-confnew',
                            '--install %s' % inter_pkg])
        else:
            cmd = 'rpm --nodeps -e cassandra12'
            local(cmd)
            cmd = 'yum -y install %s' % inter_pkg
        local(cmd)
        local('service cassandra stop')
        self.fixup_cassandra_config_files()
        local('chown -R cassandra: /var/lib/cassandra/')
        local('chown -R cassandra: /var/log/cassandra/')
        local('service cassandra start;sleep 5')

        cmds = ["cassandra-cli --host", self._args.self_ip,
                " --batch  < /dev/null | grep 'Connected to:'"]
        cassandra_cli_cmd = ' '.join(cmds)
        while True:
            proc = Popen(cassandra_cli_cmd, shell=True,
                         stdout=PIPE, stderr=PIPE)
            (output, errout) = proc.communicate()
            if proc.returncode == 0:
                break
            local('sleep 5')

        # run nodetool upgradesstables again
        self.upgrade_sstables()
        self.stop_cassandra()

        # upgrade cassandra to final release [this can be skipped]
        if self.pdist in ['Ubuntu']:
            cmd = 'DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes'
            cmd += ' -o Dpkg::Options::="--force-overwrite"'
            cmd += ' -o Dpkg::Options::="--force-confnew"'
            cmd += 'install cassandra>=%s' % final_ver
        else:
            cmd = 'rpm --nodeps -e cassandra20'
            local(cmd)
            local('yum clean all')
            cmd = 'yum -y --disablerepo=* --enablerepo=contrail*'
            cmd += ' install cassandra21>=%s' % final_ver

        local(cmd)

        self.stop_cassandra()
        self.fixup_cassandra_config_files()

    def migrate_cassandra(self, inter_pkg, final_ver):
        if not self.migrated():
            self.migrate_cassandra(inter_pkg, final_ver)


def main():
    database = DatabaseMigrate()
    database.migrate(database._args.inter_pkg, database._args.final_ver)

if __name__ == "__main__":
    main()
