#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import argparse
import ConfigParser

import os
import sys

sys.path.insert(0, os.getcwd())
from contrail_setup_utils.setup import Setup

class SetupVncOpenstack(object):
    def __init__(self, args_str = None):
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])
        self._parse_args(args_str)
        self_ip = self._args.self_ip
        cfgm_ip = self._args.cfgm_ip
        keystone_ip = self._args.keystone_ip
        service_token = self._args.service_token

        setup_args_str = "--role openstack "
        setup_args_str = setup_args_str + " --cfgm_ip %s " %(cfgm_ip)
        setup_args_str = setup_args_str + " --keystone_ip %s " %(keystone_ip)
        if service_token:
            setup_args_str = setup_args_str + " --service_token %s " %(service_token)
        if self._args.haproxy:
            setup_args_str = setup_args_str + " --haproxy"
        
        setup_obj = Setup(setup_args_str)
        setup_obj.do_setup()
        setup_obj.run_services()
    #end __init__

    def _parse_args(self, args_str):
        '''
        Eg. python setup-vnc-openstack.py --self_ip 10.1.5.11 --cfgm_ip 10.1.5.12
                   --keystone_ip 10.1.5.13 --service_token c0ntrail123 --haproxy
        '''

        # Source any specified config/ini file
        # Turn off help, so we print all options in response to -h
        conf_parser = argparse.ArgumentParser(add_help = False)
        
        conf_parser.add_argument("-c", "--conf_file",
                                 help="Specify config file", metavar="FILE")
        args, remaining_argv = conf_parser.parse_known_args(args_str.split())

        global_defaults = {
            'self_ip': '127.0.0.1',
            'service_token': '',
            'cfgm_ip': '127.0.0.1',
            'keystone_ip': '127.0.0.1',
            'haproxy': False,
        }

        if args.conf_file:
            config = ConfigParser.SafeConfigParser()
            config.read([args.conf_file])
            global_defaults.update(dict(config.items("GLOBAL")))

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

        all_defaults = {'global': global_defaults}
        parser.set_defaults(**all_defaults)

        parser.add_argument("--self_ip", help = "IP Address of this system")
        parser.add_argument("--cfgm_ip", help = "IP Address of quantum node")
        parser.add_argument("--keystone_ip", help = "IP Address of keystone node")
        parser.add_argument("--service_token", help = "The service password to access keystone")
        parser.add_argument("--haproxy", help = "Enable haproxy", action="store_true")

        self._args = parser.parse_args(remaining_argv)

    #end _parse_args

#end class SetupVncOpenstack

def main(args_str = None):
    SetupVncOpenstack(args_str)
#end main

if __name__ == "__main__":
    main() 
