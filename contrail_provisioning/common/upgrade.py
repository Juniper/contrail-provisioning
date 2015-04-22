#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Base Contrail upgrade module."""

import os
import shutil
import argparse
from distutils.dir_util import copy_tree

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
        conf_parser.add_argument("-F", "--from_rel", type=float, default=0.0,
            help="Release of contrail software installed in the node")
        conf_parser.add_argument("-T", "--to_rel", type=float, default=0.0,
            help="Release of contrail software to be upgraded in the node")
        conf_parser.add_argument("-P", "--packages", nargs='+', type=str,
            help = "List of packages to be upgraded.")
        args, self.remaining_argv = conf_parser.parse_known_args(args_str.split())

        if args.conf_file:
            config = ConfigParser.SafeConfigParser()
            config.read([args.conf_file])
            self.global_defaults.update(dict(config.items("GLOBAL")))
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
    
    def backup_source_list(self):
        os.rename('/etc/apt/sources.list', '/etc/apt/sources.list.upgradesave')

    def create_contrail_source_list(self):
        with open("/etc/apt/sources.list", 'w+') as fd:
            fd.write("deb file:/opt/contrail/contrail_install_repo ./")

    def restore_source_list(self):
        os.rename('/etc/apt/sources.list.upgradesave', '/etc/apt/sources.list')

    def _upgrade_package(self):
        if not self.upgrade_data['upgrade']:
            return
        pkgs = ' '.join(self.upgrade_data['upgrade'])
        if self.pdist in ['Ubuntu']:
            self.backup_source_list()
            self.create_contrail_source_list()
            cmd = 'DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes'
            cmd += ' -o Dpkg::Options::="--force-overwrite"'
            cmd += ' -o Dpkg::Options::="--force-confnew" install %s' % pkgs
            local(cmd)
            self.restore_source_list()
        else:
            local('yum clean all')
            cmd = 'yum -y --disablerepo=* --enablerepo=contrail_install_repo'
            cmd += ' install %s' % pkgs
            local(cmd)
    
    def _backup_config(self):
        self.backup_dir = "/var/tmp/contrail-%s-upgradesave" % self._args.to_rel

        for backup_elem in self.upgrade_data['backup']:
            backup_config = self.backup_dir + backup_elem
            if not os.path.exists(backup_config):
                os.makedirs(backup_config)
                copy_tree(backup_elem, backup_config)
            else:
                print "Already the config dir %s is backed up at %s." %\
                    (backup_elem, backup_config)

    def _restore_config(self):
        for restore_elem in self.upgrade_data['restore']:
            restore_config = self.backup_dir + restore_elem
            if os.path.isfile(restore_config):
                os.rename(restore_config, restore_elem)
            else:    
                copy_tree(restore_config, restore_elem)

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
            cmd += ' --enablerepo=contrail_install_repo install %s' % pkgs
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

    def _ensure_package(self):
        if not self.upgrade_data['ensure']:
            return
        pkgs = ' '.join(self.upgrade_data['ensure'])

    def _remove_config(self):
        for remove_config in self.upgrade_data['remove_config']:
            if os.path.isfile(remove_config):
                os.remove(remove_config)
            else:
                shutil.rmtree(remove_config)
            

    def _rename_config(self):
        for src, dst in self.upgrade_data['rename_config']:
            shutil.move(src, dst)

    def _upgrade(self):
        self._backup_config()
        if self.pdist in ['centos']:
            self.remove_package()
        self._ensure_package()
        self._downgrade_package()
        self._upgrade_package()
        if self.pdist in ['Ubuntu']:
            self._remove_package()
        self._restore_config()
        self._rename_config()
        self._remove_config()

    def upgrade_python_pkgs(self):
        # This step is required in customer env, becasue they used to call fab
        # commands from one of the node in the cluster(cfgm).
        # Installing packages(python-nova, python-cinder) brings in lower
        # version of python-paramiko(1.7.5), fabric-utils requires 1.9.0 or
        # above.ubuntu does not need this, as pycrypto and paramiko are
        # installed as debian packages. 
        cmd = "sudo easy_install \
              /opt/contrail/python_packages/pycrypto-2.6.tar.gz;\
              sudo easy_install \
              /opt/contrail/python_packages/paramiko-1.11.0.tar.gz"
        if self.pdist not in ['Ubuntu']:
            local(cmd)
