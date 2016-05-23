#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Base Contrail upgrade module."""

import os
import shutil
import argparse
import stat
from distutils.version import LooseVersion
from fabric.api import settings
from fabric.api import local

class ContrailUpgrade(object):
    def __init__(self):
        self.upgrade_data = {
            'upgrade' : [],
            'remove' : [],
            'downgrade' : [],
            'ensure' : [],
            'backup' : ['/etc/contrail'],
            'restore' : [],
            'remove_config' : [],
            'rename_config' : [],
            'replace' : [],
        }


    def _parse_args(self, args_str):
        '''
            Base parser.
        '''

        # Source any specified config/ini file
        # Turn off help, so we print all options in response to -h
        conf_parser = argparse.ArgumentParser(add_help = False)

        conf_parser.add_argument("-c", "--conf_file",
                                 help="Specify config file", metavar="FILE")
        conf_parser.add_argument("-F", "--from_rel", type=LooseVersion,
            help="Release of contrail software installed in the node")
        conf_parser.add_argument("-T", "--to_rel", type=LooseVersion,
            help="Release of contrail software to be upgraded in the node")
        conf_parser.add_argument("-P", "--packages", nargs='+', type=str,
            help = "List of packages to be upgraded.")
        conf_parser.add_argument("-R", "--roles", nargs='+', type=str,
            help = "List of contrail roles provisioned in this node.")
        args, self.remaining_argv = conf_parser.parse_known_args(args_str.split())

        if args.conf_file:
            config = ConfigParser.SafeConfigParser()
            config.read([args.conf_file])
            self.global_defaults.update(dict(config.items("GLOBAL")))
        if args.roles:
            self.global_defaults.update({'roles' : args.roles})
        if args.packages:
            self.global_defaults.update({'packages' : args.packages})
        if args.from_rel:
            self.global_defaults.update({'from_rel' : args.from_rel})
        if args.to_rel:
            self.global_defaults.update({'to_rel' : args.to_rel})

        # Override with CLI options
        # Don't surpress add_help here so it will handle -h
        parser = argparse.ArgumentParser(
            # Inherit options from config_parser
            parents=[conf_parser],
            # print script description with -h/--help
            description=__doc__,
            # Don't mess with format of description
            formatter_class=argparse.RawDescriptionHelpFormatter,
            )

        parser.set_defaults(**self.global_defaults)

        return parser

    def _upgrade_package(self):
        if not self.upgrade_data['upgrade']:
            return
        pkgs = ' '.join(self.upgrade_data['upgrade'])
        if self.pdist in ['Ubuntu']:
            if (self._args.from_rel >= LooseVersion('2.20') and
                    self._args.from_rel < LooseVersion('3.00') and
                        self._args.to_rel >= LooseVersion('3.00')):
                cmd = 'DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes'
                cmd += ' -o Dpkg::Options::="--force-overwrite"'
                cmd += ' -o Dpkg::Options::="--force-confmiss"'
                cmd += ' -o Dpkg::Options::="--force-confnew" install %s' % pkgs
            else:
                cmd = 'DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes'
                cmd += ' -o Dpkg::Options::="--force-overwrite"'
                cmd += ' -o Dpkg::Options::="--force-confnew" install %s' % pkgs
        else:
            local('yum clean all')
            cmd = 'yum -y --disablerepo=* --enablerepo=contrail*'
            cmd += ' install %s' % pkgs
        local(cmd)
    
    def _backup_config(self):
        self.backup_dir = "/var/tmp/contrail-%s-%s-upgradesave" % \
                           (self._args.to_rel, self.get_build().split('~')[0])

        for backup_elem in self.upgrade_data['backup']:
            backup_config = self.backup_dir + backup_elem
            if not os.path.exists(backup_config):
                print "Backing up %s at: %s" % (backup_elem, backup_config)
                backup_dir = os.path.dirname(os.path.abspath(backup_config))
                if not os.path.exists(backup_dir):
                    os.makedirs(backup_dir)
                if os.path.isfile(backup_elem):
                    shutil.copy2(backup_elem, backup_config)
                elif os.path.isdir(backup_elem):
                    local('cp -rfp %s %s' % (backup_elem, backup_config))
                else:
                    print "WARNING: [%s] is not present, no need to backup" % backup_elem
            else:
                print "Already the config dir %s is backed up at %s." %\
                    (backup_elem, backup_config)

    def _restore_config(self):
        for restore_elem in self.upgrade_data['restore']:
            restore_config = self.backup_dir + restore_elem
            print "Restoring %s to: %s" % (restore_config, restore_elem)
            if os.path.isfile(restore_config):
                shutil.copy2(restore_config, restore_elem)
            elif os.path.isdir(restore_config):
                local('cp -rfp %s %s' % ('%s/*' % restore_config, restore_elem))
            else:
                print "WARNING: [%s] is not backed up, no need to restore" % restore_elem

    def _downgrade_package(self):
        if not self.upgrade_data['downgrade']:
            return
        pkgs = ' '.join(self.upgrade_data['downgrade'])
        if self.pdist in ['Ubuntu']:
            cmd = 'DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes'
            cmd += ' -o Dpkg::Options::="--force-overwrite"'
            cmd += ' -o Dpkg::Options::="--force-confnew"'
            cmd += ' install %s' % pkgs
        else:
            cmd = 'yum -y --nogpgcheck --disablerepo=*'
            cmd += ' --enablerepo=contrail* install %s' % pkgs
        local(cmd)

    def _remove_package(self):
        if not self.upgrade_data['remove']:
            return
        pkgs = ' '.join(self.upgrade_data['remove'])
        if self.pdist in ['Ubuntu']:
            local('DEBIAN_FRONTEND=noninteractive apt-get -y remove --purge\
                   %s' % pkgs)
        else:
            local('rpm -e --nodeps %s' % pkgs)

    def _replace_package(self):
        if not self.upgrade_data['replace']:
            return

        rem_pkgs = ' '.join([x for (x,y) in self.upgrade_data['replace']])
        add_pkgs = ' '.join([y for (x,y) in self.upgrade_data['replace']])
        if self.pdist in ['Ubuntu']:
            with settings(warn_only = True):
                local('DEBIAN_FRONTEND=noninteractive apt-get -y remove --purge\
                       %s' % rem_pkgs)
            local('DEBIAN_FRONTEND=noninteractive apt-get -y install --reinstall\
                   %s' % add_pkgs)
        else:
            with settings(warn_only = True):
                local('rpm -e --nodeps %s' % rem_pkgs)
            cmd = 'yum -y --nogpgcheck --disablerepo=*'
            cmd += ' --enablerepo=contrail* install %s' % add_pkgs
            local(cmd)

    def _ensure_package(self):
        if not self.upgrade_data['ensure']:
            return
        pkgs = ' '.join(self.upgrade_data['ensure'])

    def _remove_config(self):
        for remove_config in self.upgrade_data['remove_config']:
            if os.path.isfile(remove_config):
                os.remove(remove_config)
            elif os.path.isdir(remove_config):
                shutil.rmtree(remove_config)
            else:
                print "WARNING: [%s] is not present, no need to remove" % remove_config

    def _rename_config(self):
        for src, dst in self.upgrade_data['rename_config']:
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                os.remove(src)
            elif os.path.isdir(src):
                local('cp -rfp %s %s' % src, dst)
                shutil.rmtree(src)
            else:
                print "WARNING: [%s] is not present, no need to rename" % src

    def get_build(self, pkg='contrail-install-packages'):
        pkg_rel = None
        if self.pdist in ['centos', 'redhat']:
            cmd = "rpm -q --queryformat '%%{RELEASE}' %s" %pkg
        elif self.pdist in ['Ubuntu']:
            cmd = "dpkg -s %s | grep Version: | cut -d' ' -f2 | cut -d'-' -f2" %pkg
        pkg_rel = local(cmd, capture=True)
        if 'is not installed' in pkg_rel or 'is not available' in pkg_rel:
            print "Package %s not installed." % pkg
            return None
        return pkg_rel

    def disable_apt_get_auto_start(self):
        if self.pdist in ['Ubuntu']:
            with open("/usr/sbin/policy-rc.d", "w+") as f:
                f.write('#!/bin/sh\n')
                f.write('exit 101\n')
                f.close()
            h = os.stat("/usr/sbin/policy-rc.d")
            os.chmod("/usr/sbin/policy-rc.d", h.st_mode | stat.S_IEXEC)

    def enable_apt_get_auto_start(self):
        if self.pdist in ['Ubuntu']:
            local('rm -f /usr/sbin/policy-rc.d')
 
    def _upgrade(self):
        self._backup_config()
        if self.pdist in ['centos']:
            self._remove_package()
        self._ensure_package()
        self._downgrade_package()
        self._upgrade_package()
        if self.pdist in ['Ubuntu']:
            self._remove_package()
        self._replace_package()
        self._restore_config()
        self._rename_config()
        self._remove_config()
