#!/usr/bin/python

import argparse
import ConfigParser

import os
import sys

sys.path.insert(0, os.getcwd())
from contrail_setup_utils.setup import Setup

class SetupVncWebui(object):
    def __init__(self, args_str = None):
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])
        self._parse_args(args_str)
        cfgm_ip = self._args.cfgm_ip
        openstack_ip = self._args.openstack_ip
        collector_ip = self._args.collector_ip

        setup_args_str = "--role webui"
        setup_args_str = setup_args_str + " --cfgm_ip %s" % (cfgm_ip)
        setup_args_str = setup_args_str + " --openstack_ip %s" % (openstack_ip)
        if collector_ip:
            setup_args_str = setup_args_str + " --collector_ip %s" \
                                 % (collector_ip)
        if self._args.cassandra_ip_list:                         
            setup_args_str = setup_args_str + " --cassandra_ip_list %s" \
                             %(' '.join(self._args.cassandra_ip_list))                          

        setup_obj = Setup(setup_args_str)
        setup_obj.do_setup()
        setup_obj.run_services()
    #end __init__

    def _parse_args(self, args_str):
        '''
        Eg. python setup-vnc-webui.py --cfgm_ip 10.84.12.11 --openstack_ip 10.84.12.12
            --collector_ip 10.84.12.12 --cassandra_ip_list 10.1.5.11 10.1.5.12
        '''

        # Source any specified config/ini file
        # Turn off help, so we print all options in response to -h
        conf_parser = argparse.ArgumentParser(add_help = False)
        
        conf_parser.add_argument("-c", "--conf_file",
                                 help="Specify config file", metavar="FILE")
        args, remaining_argv = conf_parser.parse_known_args(args_str.split())

        global_defaults = {
            'cfgm_ip': '127.0.0.1',
            'openstack_ip': '127.0.0.1',
            'collector_ip' : '127.0.0.1',
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

        parser.add_argument("--cfgm_ip", help = "IP Address of the cfgm node")
        parser.add_argument("--openstack_ip", help = "IP Address of the openstack controller")
        parser.add_argument("--collector_ip", help = "IP Address of the Collector node")
        parser.add_argument("--cassandra_ip_list", help = "List of IP Addresses of cassandra nodes",
                            nargs='+', type=str)

        self._args = parser.parse_args(remaining_argv)

    #end _parse_args

#end class SetupVncWebui

def main(args_str = None):
    SetupVncWebui(args_str)
#end main

if __name__ == "__main__":
    main() 
