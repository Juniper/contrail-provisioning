#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#

import sys
import argparse
import ConfigParser

from templates import tor_agent_haproxy
from contrail_provisioning.common.base import ContrailSetup

class TorAgentHaproxyConfig(ContrailSetup):
    def __init__(self, args_str = None):
        super(ComputeSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.global_defaults = {
            'standby_ip': None,
            'standby_port': None,
        }
        self.parse_args(args_str)

    def parse_args(self, args_str):
        '''
        Eg. setup_vnc-toragent-haproxy -self_ip 10.1.5.11 --torid 1 --port 9999
                   --standby_ip 10.1.5.110 --standby_port 9888
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--self_ip", help = "P address of this tor node")
        parser.add_argument("--torid", help = "Unique Id of the tor switch")
        parser.add_argument("--port", help = " Port number to be used by ovs")
        parser.add_argument("--standby_ip", help = "IP of the TOR agent where redundant TOR Agent will run")
        parser.add_argument("--standby_port", help = "Port number used for OVS by the redundant TOR agent")

        self._args = parser.parse_args(self.remaining_argv)

    def generate(self):
        haproxy_config = ''

        haproxy_fname = "/etc/haproxy.cfg"
        compute_haproxy = toragent_haproxy.template.safe_substitute({
            '__tor_proxy_name__' : 'contrail-tor-agent-' + self._args.torid,
            '__tor_ip__' : self._args.self_ip,
            '__tor_ovs_port__' : self._args.port,
            '__standby_ip__' : self._args.standby_ip,
            '__standby_port__' : self._args.standby_port,

        })

        with open(haproxy_fname, 'a') as cfg_file:
            cfg_file.write(compute_haproxy)

    def start(self):
        with settings(warn_only=True):
            local("sudo chkconfig haproxy on")
            local("sudo service haproxy restart")

    def create(self):
        if self._args.standby_ip and self._args.standby_port:
            self.generate()
            self.start()

def main(args_str=None):
    tor_agent_haproxy = TorAgentHaproxyConfig(args_str)
    tor_agent_haproxy.create()

if __name__ == "__main__":
    main()
