#!/usr/bin/python

import argparse
import ConfigParser

import os
import sys

sys.path.insert(0, os.getcwd())
from contrail_setup_utils.setup import Setup

class SetupVncStorageWebUI(object):
    def __init__(self, args_str = None):
        #print sys.argv[1:]
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])
        self._parse_args(args_str)

        storage_master_ip = self._args.storage_master_ip
        storage_webui_ip = self._args.storage_webui_ip
        storage_webui_mode = 'enabled'
        storage_setup_mode = self._args.storage_setup_mode

        setup_args_str = "--role storage"
        setup_args_str = setup_args_str + " --storage-webui-ip %s" % (storage_webui_ip)
        setup_args_str = setup_args_str + " --storage-webui-mode %s" % (storage_webui_mode)
        setup_args_str = setup_args_str + " --storage-setup-mode %s" % (storage_setup_mode)
        setup_args_str = setup_args_str + " --storage-master-ip %s" % (storage_master_ip)

        if self._args.storage_disk_config[0] != 'none' or self._args.storage_ssd_disk_config[0] != 'none':
            #Setup storage WebUI
            setup_obj = Setup(setup_args_str)
            setup_obj.do_setup()
            setup_obj.run_services()
    #end __init__

    def _parse_args(self, args_str):
        '''
        Eg. python setup-vnc-storage-webui.py --storage-master-ip 10.157.43.171
            --storage-webui-ip  10.157.43.171 --storage-setup-mode setup
        '''

        # Source any specified config/ini file
        # Turn off help, so we print all options in response to -h
        conf_parser = argparse.ArgumentParser(add_help = False)
        
        conf_parser.add_argument("-c", "--conf_file",
                                 help="Specify config file", metavar="FILE")
        args, remaining_argv = conf_parser.parse_known_args(args_str.split())

        global_defaults = {
            'storage_master_ip': '127.0.0.1',
            'storage_webui_ip': '127.0.0.1',
            'storage_webui':'enabled'
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
            description = __doc__,
            # Don't mess with format of description
            formatter_class = argparse.RawDescriptionHelpFormatter,
            )

        all_defaults = {'global': global_defaults}
        parser.set_defaults(**all_defaults)

        parser.add_argument("--storage-master-ip", help = "IP Address of storage master node")
        parser.add_argument("--storage-webui-ip", help = "IP Address of storage webui node")
        parser.add_argument("--storage-webui-mode", help = "Config mode Storage WebUI Status")
        parser.add_argument("--storage-setup-mode", help = "Configuration mode")
        parser.add_argument("--storage-disk-config", help = "Disk list to be used for distributed storage", nargs="+", type=str)
        parser.add_argument("--storage-ssd-disk-config", help = "SSD Disk list to be used for distributed storage", nargs="+", type=str)

        self._args = parser.parse_args(remaining_argv)

    #end _parse_args

#end class SetupVncStorageWebUI

def main(args_str = None):
    SetupVncStorageWebUI(args_str)
#end main

if __name__ == "__main__":
    main() 
