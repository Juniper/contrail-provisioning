#!/usr/bin/python

import argparse
import ConfigParser

import os
import sys

import time
import subprocess

import json
from pprint import pformat

import tempfile
from fabric.api import local
from fabric.context_managers import lcd

class CreateInstaller(object):
    def __init__(self, args_str = None):
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])
        self._parse_args(args_str)

        self._setup_src_path = os.path.abspath(os.path.dirname(sys.argv[0]))
        self._temp_dir_name = tempfile.mkdtemp(dir = os.getcwd())

        self._create_installer()

        os.removedirs(self._temp_dir_name)
    #end __init__

    def _parse_args(self, args_str):
        '''
        Eg. python create_installer.py [--repo /home/ajayhn/combined_test_repo]
                                       [--embed_vrouter ]
                                       [--embed_guest ]
        '''

        # Source any specified config/ini file
        # Turn off help, so we print all options in response to -h
        conf_parser = argparse.ArgumentParser(add_help = False)
        
        conf_parser.add_argument("-c", "--conf_file",
                                 help="Specify config file", metavar="FILE")
        args, remaining_argv = conf_parser.parse_known_args(args_str.split())

        global_defaults = {
            'repo' : None,
            'embed_vrouter' : False,
            'embed_guest' : False,
        }

        if args.conf_file:
            config = ConfigParser.SafeConfigParser()
            config.read([args.conf_file])
            global_defaults.update(dict(config.items("")))

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

        all_defaults = {'': global_defaults,
                       }
        parser.set_defaults(**all_defaults)

        parser.add_argument("--repo", help = "Directory with RPMs")
        parser.add_argument("--embed_vrouter", action='store_true',
                            help = "Embed vrouter package in the installer")
        parser.add_argument("--embed_guest", action='store_true',
                            help = "Embed guest image in the installer")
    
        self._args = parser.parse_args(remaining_argv)

    #end _parse_args

    def _create_installer(self):
        temp_dir_name = self._temp_dir_name
        repo_dir = self._args.repo
        embed_vrouter = self._args.embed_vrouter
        embed_guest = self._args.embed_guest
        src_path = self._setup_src_path

        helper_scripts = [
                          'contrail_setup_utils/__init__.py',
                          'contrail_setup_utils/setup.py',
                          'contrail_setup_utils/reset.py',
                          'contrail_setup_utils/setup-pki.sh',
                          'contrail_setup_utils/ruby_puppet_cert.patch',
                          'contrail_setup_utils/config-server-setup.sh',
                          'contrail_setup_utils/config-server-cleanup.sh',
                          'contrail_setup_utils/collector-server-setup.sh',
                          'contrail_setup_utils/collector-server-cleanup.sh',
                          'contrail_setup_utils/control-server-setup.sh',
                          'contrail_setup_utils/control-server-cleanup.sh',
                          'contrail_setup_utils/compute-server-setup.sh',
                          'contrail_setup_utils/compute-server-cleanup.sh',
                          'contrail_setup_utils/webui-server-setup.sh',
                          'contrail_setup_utils/webui-server-cleanup.sh',
                          'contrail_setup_utils/drop-cassandra-cfgm-keyspaces',                 
                          'contrail_setup_utils/database-server-setup.sh',
                          'contrail_setup_utils/database-server-cleanup.sh',
                          'contrail_setup_utils/cinder-server-setup.sh',
                          'contrail_setup_utils/keystone-server-setup.sh',
                          'contrail_setup_utils/glance-server-setup.sh',
                          'contrail_setup_utils/nova-server-setup.sh',
                          'contrail_setup_utils/quantum-server-setup.sh',
                          'contrail_setup_utils/setup-quantum-in-keystone.py',
                          'contrail_setup_utils/setup-service-token.sh',
                          'contrail_setup_utils/storage-ceph-setup.py',
                          'contrail_setup_utils/compute-live-migration-setup.py',
                          'contrail_setup_utils/livemnfs-ceph-setup.py',
                          'devstack-cleanup.py',                 
                          'setup-all-in-one.py',                 
                          'reset-all-in-one.py',                 
                          'setup-openstack.py',
                          'reset-openstack.py',
                          'setup-vnc-cfgm.py',
                          'reset-vnc-cfgm.py',
                          'setup-vnc-vrouter.py',
                          'reset-vnc-vrouter.py',
                          'setup-vnc-control.py',
                          'reset-vnc-control.py',
                          'setup-vnc-collector.py',
                          'reset-vnc-collector.py',
                          'setup-vnc-webui.py',
                          'reset-vnc-webui.py',
                          'setup-vnc-database.py',
                          'reset-vnc-database.py',
                          'setup-vnc-openstack.py',
                          'setup-vnc-galera.py',
                          'contrail_setup_utils/contrail-bootstrap-galera.sh',
                          'contrail_setup_utils/contrail-cmon-monitor.sh',
                          'contrail_setup_utils/contrail-rmq-monitor.sh',
                          'contrail_setup_utils/contrail-ha-check.sh',
                          'contrail_setup_utils/contrail-token-clean.sh',
                          'setup-vnc-keepalived.py',
                          'setup-vnc-storage.py',
                          'setup-vnc-interfaces.py',
                          'setup-vnc-static-routes.py',
                          'setup-vnc-livemigration.py'
                         ]

        with lcd("%s" %(temp_dir_name)):
            local("mkdir contrail_installer")
            if repo_dir:
                local("mkdir contrail_installer/repo")
                local("cp -R %s/* contrail_installer/repo" %(repo_dir))
            local("mkdir contrail_installer/contrail_setup_utils")
            local("mkdir contrail_installer/contrail_config_templates")
            local("mkdir contrail_installer/extras")

            for h_scr in helper_scripts:
                local("cp %s/%s contrail_installer/%s" %(src_path, h_scr, h_scr))

            local("cp -R %s/templates/* contrail_installer/contrail_config_templates" %(src_path))

            if embed_vrouter:
                vrouter_str = local("ls ~/rpmbuild/RPMS/x86_64/contrail-vrouter*", capture = True)
                vrouter_rpms = vrouter_str.split()
                latest_vrouter_rpm = max(vrouter_rpms, key=os.path.getmtime)
                local("cp %s contrail_installer/extras" %(latest_vrouter_rpm))

            if embed_guest:
                guest_img = '/cs-shared/images/precise-server-cloudimg-amd64-disk1.img.gz'
                local("cp %s contrail_installer/extras" %(guest_img))

            local("tar cvfz contrail_installer.tgz contrail_installer/")

        local("mv %s/contrail_installer.tgz ." %(temp_dir_name))

        with lcd("%s" %(temp_dir_name)):
            local("rm -rf contrail_installer")
    #end _create_installer

#end class CreateInstaller

def main(args_str = None):
    CreateInstaller(args_str)
#end main

if __name__ == "__main__":
    main()
