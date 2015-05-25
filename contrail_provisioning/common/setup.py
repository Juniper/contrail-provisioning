#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import ConfigParser

from fabric.api import local, settings

from contrail_provisioning.common.base import ContrailSetup


class CommonSetup(ContrailSetup):
    """ Common provisioning to be done in all the nodes in the VNS cluster."""
    def __init__(self, args_str = None):
        super(CommonSetup, self).__init__()
        self.global_defaults = {
            'self_ip': '127.0.0.1',
            'ntp_server': None,
        }
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])
        self.parse_args(args_str)

    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-common --self_ip 10.1.5.11 --ntp_server 10.10.5.100
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--self_ip", help = "IP Address of this system")
        parser.add_argument("--ntp_server", help = "IP Address of ntp server")

        self._args = parser.parse_args(self.remaining_argv)

    def fixup_ntp_conf(self):
        ntp_conf_file = "/etc/nova/nova.conf"
        if (self._args.ntp_server and os.path.exists(ntp_conf_file)):
            ntp_chk_cmd = 'grep "server %s" %s' % (self._args.ntp_server,
                                                   ntp_conf_file)
            with settings(warn_only=True):
                result = local(ntp_chk_cmd)
            if result.failed:
                ntp_cmd = 'echo "server %s" >> %s' % (self._args.ntp_server,
                                                      ntp_conf_file)
                local(ntp_cmd)

    def run_services(self):
        pass

    def setup(self):
        self.fixup_ntp_conf()
        self.run_services()

def main(args_str = None):
    common = CommonSetup(args_str)
    common.setup()

if __name__ == "__main__":
    main() 
