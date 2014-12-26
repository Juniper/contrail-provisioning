#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import ConfigParser

from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.toragent.common import TorAgentBaseSetup


class TorAgentSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(TorAgentSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.global_defaults = {
        }

        self.parse_args(args_str)

    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-tor-agent --agent_name contrail-tor-1 --http_server_port 9090 
            --discovery_server_ip 10.204.217.39 --tor_id 1 --tor_ip 10.204.221.35 
            --tor_ovs_port 9999 --tsn_ip 10.204.221.33 --tor_ovs_protocol tcp
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--agent_name", help = "Name of the TOR agent")
        parser.add_argument("--http_server_port", help = "Port number for the HTTP server.")
        parser.add_argument("--discovery_server_ip", help = "IP Address of the config node")
        parser.add_argument("--tor_ip", help = "TOR Switch IP")
        parser.add_argument("--tor_id", help = "Unique ID for the TOR")
        parser.add_argument("--tor_ovs_port", help = "OVS Port Number")
        parser.add_argument("--tsn_ip", help = "TSN Node IP")
        parser.add_argument("--tor_ovs_protocol", help = "TOR OVS Protocol. Currently Only TCP supported")

        self._args = parser.parse_args(self.remaining_argv)



def main(args_str = None):
    tor_agent_args = TorAgentSetup(args_str)._args
    tor_agent = TorAgentBaseSetup(tor_agent_args)
    tor_agent.setup()

if __name__ == "__main__":
    main()
