#!/usr/bin/python
#
# Copyright (c) 2016 Juniper Networks, Inc. All rights reserved.
#
"""Migrates Cassandra Database to specified Version."""
import os
import sys
import re
from distutils.version import LooseVersion
from subprocess import Popen, PIPE

from contrail_provisioning.common.base import ContrailSetup

from fabric.api import local
from fabric.api import settings


class DatabaseMigrate(ContrailSetup):
    def __init__(self, args_str=None):
        ContrailSetup.__init__(self)
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
            'inter_pkg': [self.inter_default],
            'final_ver': '2.1.9'
        }
        self.parse_args(args_str)

    def parse_args(self, args_str):
        parser = self._parse_args(args_str)
        parser.add_argument("--inter-pkg",
                            help="Intermediate version of Cassandra package", nargs="*")
        parser.add_argument("--final-ver",
                            help="Final version of Cassandra package")
        self._args = parser.parse_args(self.remaining_argv)

    def stop_cassandra(self):
        local('service cassandra stop')

    def force_stop_cassandra(self):
        local('kill `ps auxw | grep -E "Dcassandra-pidfile=.*cassandra\.pid" | grep -v grep | awk \'{print $2}\'`')

    def stop_contrail_database(self):
        local('service contrail-database stop')

    def upgrade_sstables_and_drain(self):
        print 'Upgrading database sstables...'
        local('nodetool upgradesstables')
        local('nodetool drain')

    def _get_cassandra_version(self):
        with settings(warn_only=True):
            if self.pdist in ['Ubuntu']:
                cmd = "dpkg -s cassandra | grep Version | awk '{print $2}'"
                cassandra_version = local(cmd, capture=True)
            else:
                #for rpms the package name changes w/ every version
                cassandra_pkgs = ["cassandra12", "cassandra20", "cassandra21", "cassandra22"]
                for cassandra_pkg in cassandra_pkgs:
                    cmd = "rpm -q --queryformat '%{VERSION}' " + cassandra_pkg
                    cassandra_version = local(cmd, capture=True)
                    if cassandra_version.failed:
                        continue
                    else:
                        break
        if cassandra_version.failed:
            raise RuntimeError('Failed to get cassandra version')
        return cassandra_version

    def _get_final_ver(self):
        repo = '/opt/contrail/contrail_install_repo'
        if self.pdist in ['Ubuntu']:
            cmd = 'dpkg --info ' + repo + '/contrail-openstack-database_* | grep "Depends:"'
            cmd_out = local(cmd, capture=True)
            if cmd_out.failed:
                return '2.2'
            ver_re=re.compile('cassandra[\s(>=]*[0-9]+[0-9\.]*')
            ver=ver_re.search(cmd_out)
            if not ver:
                return '2.2'
            ver_re=re.compile('[0-9]+[0-9\.]*')
            ver = ver_re.search(ver.group())
            if not ver:
                return '2.2'
            return '.'.join(ver.group().split('.')[0:2])
        else:
            cmd = 'yum deplist ' + repo + '/contrail-database-* | grep "dependency:" | grep cassandra'
            cmd_out = local(cmd, capture=True)
            if cmd_out.failed:
                return '2.2'
            try:
               ver = '.'.join(list(cmd_out.split()[1][-2:]))
            except:
               raise RuntimeError('Failed to get final cassandra version')
            return ver

    def _get_inter_pkgs(self, final_ver):
        repo = '/opt/contrail/contrail_install_repo'
        current_version = self._get_cassandra_version()
        try:
            current_version = '.'.join(current_version.split('.')[0:2])
        except:
            raise RuntimeError('Cassandra version parse failed')
        if LooseVersion(current_version) == LooseVersion('1.2'):
            if final_ver == '2.1':
                if self.pdist in ['Ubuntu']:
                    return [os.path.join(repo, 'cassandra_2.0.*_all.deb'), os.path.join(repo, 'cassandra_2.1.*_all.deb')]
                else:
                    return [os.path.join(repo, 'cassandra20-2.0.*.noarch.rpm'), os.path.join(repo, 'cassandra21-2.1.*.noarch.rpm')]
            elif final_ver == '2.2':
                if self.pdist in ['Ubuntu']:
                    return [os.path.join(repo, 'cassandra_2.0.*_all.deb'), os.path.join(repo, 'cassandra_2.1.*_all.deb'),\
                            os.path.join(repo, 'cassandra_2.2.*_all.deb')]
                else:
                    return [os.path.join(repo, 'cassandra20-2.0.*.noarch.rpm'), os.path.join(repo, 'cassandra21-2.1.*.noarch.rpm'),\
                            os.path.join(repo, 'cassandra22-2.2.*.noarch.rpm')]
        elif LooseVersion(current_version) == LooseVersion('2.0'):
            if final_ver == '2.1':
                if self.pdist in ['Ubuntu']:
                    return [os.path.join(repo, 'cassandra_2.1.*_all.deb')]
                else:
                    return [os.path.join(repo, 'cassandra21-2.1.*.noarch.rpm')]
            elif final_ver == '2.2':
                if self.pdist in ['Ubuntu']:
                    return [os.path.join(repo, 'cassandra_2.1.*_all.deb'),\
                            os.path.join(repo, 'cassandra_2.2.*_all.deb')]
                else:
                    return [os.path.join(repo, 'cassandra21-2.1.*.noarch.rpm'),\
                            os.path.join(repo, 'cassandra22-2.2.*.noarch.rpm')]
        elif LooseVersion(current_version) == LooseVersion('2.1'):
            if final_ver == '2.2':
                if self.pdist in ['Ubuntu']:
                    return [os.path.join(repo, 'cassandra_2.2.*_all.deb')]
                else:
                    return [os.path.join(repo, 'cassandra22-2.2.*.noarch.rpm')]
        elif LooseVersion(current_version) == LooseVersion('2.2'):
            return []
        else:
            raise RuntimeError('Cassandra version not recognizable')
        return []

    def migrate_cassandra(self, inter_pkgs, final_ver):
        if final_ver is None:
            final_ver = self._get_final_ver()

        if inter_pkgs is None:
            inter_pkgs = self._get_inter_pkgs(final_ver)

        current_version = self._get_cassandra_version()
        try:
            current_version = '.'.join(current_version.split('.')[0:2])
        except:
            raise RuntimeError('Cassandra version parse failed')

        print 'Request to migrate cassandra from %s to %s...' % (current_version, final_ver)
        if current_version == final_ver:
            return

        # run nodetool upgradesstables
        self.upgrade_sstables_and_drain()
        self.stop_contrail_database()
        local('sleep 5')
        while not self.check_database_down():
            self.force_stop_cassandra()
            local('sleep 5')

        for inter_pkg in inter_pkgs:
            # upgrade cassandra to intermediate rel first
            if self.pdist in ['Ubuntu']:
                cmd = ' '.join(['dpkg --force-overwrite --force-confnew',
                                '--install %s' % inter_pkg])
            else:
                current_version = self._get_cassandra_version()
                try:
                    current_version = ''.join(current_version.split('.')[0:2])
                except:
                    raise RuntimeError('Cassandra version parse failed')
                cmd = 'rpm --nodeps -e cassandra' + current_version
                local(cmd)
                cmd = 'yum -y install %s' % inter_pkg

            local(cmd)

            if not self.pdist in ['Ubuntu']:
                local("systemctl daemon-reload")

            self.stop_cassandra()
            local('sleep 5')
            while not self.check_database_down():
                self.force_stop_cassandra()
                local('sleep 5')

            self.fixup_cassandra_config_file(self.database_listen_ip,
                                             self.database_seed_list,
                                             self._args.data_dir,
                                             self._args.ssd_data_dir,
                                             cluster_name='Contrail')
            local('chown -R cassandra: /var/lib/cassandra/')
            local('chown -R cassandra: /var/log/cassandra/')
            local('service cassandra start;sleep 5')

            while not self.check_database_up():
                local('sleep 5')

            # run nodetool upgradesstables again
            self.upgrade_sstables_and_drain()
            self.stop_cassandra()
            local('sleep 5')
            while not self.check_database_down():
                self.force_stop_cassandra()
                local('sleep 5')

    def migrate(self, inter_pkg=None, final_ver=None):
        self.migrate_cassandra(inter_pkg, final_ver)


def main():
    database = DatabaseMigrate()
    database.migrate(database._args.inter_pkg, database._args.final_ver)

if __name__ == "__main__":
    main()
