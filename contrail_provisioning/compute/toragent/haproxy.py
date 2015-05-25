#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#

import sys
import argparse
import ConfigParser

from templates import tor_agent_haproxy
from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.utils import unique

class TorAgentHaproxyConfig(ContrailSetup):
    def __init__(self, args_str = None):
        super(ComputeSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.parse_args(args_str)

    def parse_args(self, args_str):
        '''
        Eg. setup_vnc-toragent-haproxy --tsn_ip_port_list 1.1.1.1:4000 2.2.2.2:5000
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--tsn_ip_port_list",
                            help = "tsn_ip:ovs_port list of all toragents")

        self._args = parser.parse_args(self.remaining_argv)

    def find_ip_port_groups(self):
        # Get the unique ip:port list
        tsn_ip_port_list = unique(self._args.tsn_ip_port_list)
        # Convert to a list of (ip, port) tuple
        ip_port_tuple = [ip_port.split(':') for ip_port in tsn_ip_port_list]
        # Determine the ip and list of ports to bind
        ip_port_groups = {}
        for ip, port in ip_port_tuple:
            ip_port_groups[ip].append(port)

        return ip_port_groups

    def generate(self):
        haproxy_config = ''
        haproxy_fname = "/etc/haproxy.cfg"

        ip_port_groups = self.find_ip_port_groups()
        unique_port_groups = ip_port_groups.values()
        for port_group in unique_port_groups:
            index = unique_port_groups.index(port_group) + 1
            # Add server ip's of same ovs port group to backend server lines
            server_lines = ''
            for ip, next_port_group in ip_port_groups.items():
                if port_group == next_port_group:
                    server_lines += '    server %s %s\n' % (ip, ip)
            # Add haproxy config for each ovs port group
            haproxy_config += toragent_haproxy.template.safe_substitute({
                '__tor_proxy_name__' : 'contrail-tor-agent-%s' % index,
                '__tor_ovs_ports__' : ':%s' % ',:'.join(port_group),
                '__server_lines__' : server_lines

            })

        with open(haproxy_fname, 'a') as cfg_file:
            cfg_file.write(haproxy_config)

    def start(self):
        with settings(warn_only=True):
            local("sudo chkconfig haproxy on")
            local("sudo service haproxy restart")

    def setup(self):
        self.generate()
        self.start()

def main(args_str=None):
    tor_agent_haproxy = TorAgentHaproxyConfig(args_str)
    tor_agent_haproxy.setup()

if __name__ == "__main__":
    main()
