#!/usr/bin/python

import argparse
import ConfigParser

import platform
import os
import sys
import time
import re
import string
import socket
import netifaces, netaddr
import subprocess
import fnmatch
import struct
import shutil
import json
from pprint import pformat
import xml.etree.ElementTree as ET
import platform
import pdb

import tempfile
from fabric.api import local, env, run, settings
from fabric.operations import get, put
from fabric.context_managers import lcd, settings
from fabric.api import local, env, run
from fabric.operations import get, put
from fabric.context_managers import lcd, settings
sys.path.insert(0, os.getcwd())

class SetupStorageWebUI(object):
    # Enable the Storage feature to Contrail WebUI
    def contrail_storage_ui_add(self):
        print 'stopping... supervisor-webui service'
        local('sudo service supervisor-webui stop')
        time.sleep(5);
        # enable Contrail Web Storage feature
        with settings(warn_only=True):
            storage_enable_variable = local('cat /etc/contrail/config.global.js | grep config.featurePkg.webStorage', capture=True);
        if storage_enable_variable:
            print 'Re-enable Contrail Web Storage feature'
            local('sudo sed "s/config.featurePkg.webStorage.enable = *;/config.featurePkg.webStorage.enable = true;/g" /etc/contrail/config.global.js > config.global.js.new')
            local('sudo cp config.global.js.new /etc/contrail/config.global.js')
        else:
            print 'Enable Contrail Web Storage feature'
            local('sudo cp  /etc/contrail/config.global.js /usr/src/contrail/contrail-web-storage/config.global.js.org')
            local('sudo sed "/config.featurePkg.webController.enable/ a config.featurePkg.webStorage = {};\\nconfig.featurePkg.webStorage.path=\'\/usr\/src\/contrail\/contrail-web-storage\';\\nconfig.featurePkg.webStorage.enable = true;" /etc/contrail/config.global.js > config.global.js.new')
            local('sudo cp config.global.js.new /etc/contrail/config.global.js')

        #restart the webui server
        time.sleep(5);
        print 'starting... supervisor-webui service'
        local('sudo service supervisor-webui start')

    # Disable the Storage feature to Contrail WebUI
    def contrail_storage_ui_remove(self):
        #disable Contrail Web Storage feature
        with settings(warn_only=True):
            storage_enable_variable = local('cat /etc/contrail/config.global.js | grep config.featurePkg.webStorage', capture=True);
        if storage_enable_variable:
            print 'stopping... supervisor-webui service'
            local('sudo service supervisor-webui stop')
            print 'Disable Contrail Web Storage feature'
            local('sudo sed "/config.featurePkg.webStorage = {}/,/config.featurePkg.webStorage.enable = true;/d" /etc/contrail/config.global.js > config.global.js.new')
            local('sudo cp config.global.js.new /etc/contrail/config.global.js')
            #restart the webui server
            time.sleep(5);
            print 'starting... supervisor-webui service'
            local('sudo service supervisor-webui start')

    def __init__(self, args_str = None):
        #print sys.argv[1:]
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])
        self._parse_args(args_str)

        pdist = platform.dist()[0]

        # Whenever Storage setup mode is reconfigure or unconfigure needs to remove below service and a feature
        # remove the Storage UI feature
        if self._args.storage_setup_mode == 'reconfigure' or self._args.storage_setup_mode == 'unconfigure':
           if pdist == 'Ubuntu':
               self.contrail_storage_ui_remove()
               print 'Storage WebUI configuration removed'

        if self._args.storage_setup_mode == 'unconfigure':
            return

        # Enable the Storage feature to Contrail WebUI
        if pdist == 'Ubuntu':
            self.contrail_storage_ui_add()

    #end __init__

    def _parse_args(self, args_str):
        '''
        Eg. storage-webui-setup --storage-setup-mode setup
        '''

        # Source any specified config/ini file
        # Turn off help, so we print all options in response to -h
        conf_parser = argparse.ArgumentParser(add_help = False)

        conf_parser.add_argument("-c", "--conf_file",
                                 help="Specify config file", metavar="FILE")
        args, remaining_argv = conf_parser.parse_known_args(args_str.split())

        global_defaults = {
        }

        if args.conf_file:
            config = ConfigParser.SafeConfigParser()
            config.read([args.conf_file])
            global_defaults.update(dict(config.items("GLOBAL")))

        # Override with CLI options
        # Don't surpress add_help here so it will handle -h
        parser = argparse.ArgumentParser(
            # Inherit options from config_parser
            parents = [conf_parser],
            # print script description with -h/--help
            description =__doc__,
            # Don't mess with format of description
            formatter_class = argparse.RawDescriptionHelpFormatter,
            )

        all_defaults = {'global': global_defaults}
        parser.set_defaults(**all_defaults)
        parser.add_argument("--storage-setup-mode", help = "Configuration mode")

        self._args = parser.parse_args(remaining_argv)

    #end _parse_args

#end class SetupStorageWebUI

def main(args_str = None):
    SetupStorageWebUI(args_str)
#end main

if __name__ == "__main__":
    main() 
