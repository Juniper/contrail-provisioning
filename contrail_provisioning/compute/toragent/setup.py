#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import ConfigParser
import platform
from fabric.api import local, run
from fabric.state import env
from fabric.context_managers import settings, lcd

from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.compute.toragent.templates import tor_agent_conf
from contrail_provisioning.compute.toragent.templates import tor_agent_ini
from contrail_provisioning.compute.toragent.templates import tor_agent_service
from distutils.version import LooseVersion

(PLATFORM, VERSION, EXTRA) = platform.linux_distribution()

class TorAgentBaseSetup(ContrailSetup):
    def __init__(self, tor_agent_args, args_str=None):
        super(TorAgentBaseSetup, self).__init__()
        self._args = tor_agent_args


    def fixup_tor_agent(self):
        ssl_cert = ''
        ssl_privkey = ''
        ssl_cacert = ''
        if self._args.tor_ovs_protocol.lower() == 'pssl':
            ssl_cert = '/etc/contrail/ssl/certs/tor.' + self._args.tor_id + '.cert.pem'
            ssl_privkey = '/etc/contrail/ssl/private/tor.' + self._args.tor_id + '.privkey.pem'
            ssl_cacert = '/etc/contrail/ssl/certs/cacert.pem'

        template_vals = {'__contrail_control_ip__':self._args.self_ip,
                         '__contrail_agent_name__':self._args.agent_name,
                         '__contrail_http_server_port__':self._args.http_server_port,
                         '__contrail_tor_ip__':self._args.tor_ip,
                         '__contrail_tor_id__':self._args.tor_id,
                         '__contrail_tsn_ovs_port__':self._args.tor_ovs_port,
                         '__contrail_tsn_ip__':self._args.tsn_ip,
                         '__contrail_tor_ovs_protocol__':self._args.tor_ovs_protocol,
                         '__contrail_tor_agent_ovs_ka__':self._args.tor_agent_ovs_ka,
                         '__contrail_tor_ssl_cert__':ssl_cert,
                         '__contrail_tor_ssl_privkey__':ssl_privkey,
                         '__contrail_tor_ssl_cacert__':ssl_cacert,
                         '__contrail_control_node_list__' : \
                             ' '.join('%s:%s' %(server, '5269') for server \
                             in self._args.control_nodes),
                         '__contrail_dns_node_list__' : \
                             ' '.join('%s:%s' %(server, '53') for server \
                             in self._args.control_nodes),
                         '__contrail_collectors__' : \
                             ' '.join('%s:%s' %(server, '8086') for server \
                             in self._args.collectors)
                        }
        self._template_substitute_write(tor_agent_conf.template,
                                        template_vals, self._temp_dir_name + '/tor_agent_conf')
        self.tor_file_name='contrail-tor-agent-' + self._args.tor_id + '.conf'
        local("sudo mv %s/tor_agent_conf /etc/contrail/%s" %(self._temp_dir_name,self.tor_file_name))

    def fixup_tor_ini(self):
        self.tor_process_name='contrail-tor-agent-' + self._args.tor_id
        self.tor_log_file_name= self.tor_process_name + '-stdout.log'

        template_vals = {'__contrail_tor_agent__':self.tor_process_name,
                         '__contrail_tor_agent_conf_file__':self.tor_file_name,
                         '__contrail_tor_agent_log_file__':self.tor_log_file_name
                        }
        if (('ubuntu' in PLATFORM.lower()) and
            (LooseVersion(VERSION) > LooseVersion('14.04'))):
            self._template_substitute_write(tor_agent_service.template,
                                            template_vals, self._temp_dir_name + '/tor_agent_service')
            self.tor_file_name=self.tor_process_name + '.service'
            local("sudo mv %s/tor_agent_service /lib/systemd/system/%s" %(self._temp_dir_name,self.tor_file_name))
        else:
            self._template_substitute_write(tor_agent_ini.template,
                                            template_vals, self._temp_dir_name + '/tor_agent_ini')
            self.tor_file_name=self.tor_process_name + '.ini'
            local("sudo mv %s/tor_agent_ini /etc/contrail/supervisord_vrouter_files/%s" %(self._temp_dir_name,self.tor_file_name))

    def create_init_file(self):
        local("sudo cp /etc/init.d/contrail-vrouter-agent /etc/init.d/%s" %(self.tor_process_name))

    def setup(self):
        self.fixup_tor_agent()
        self.fixup_tor_ini()
        if (('ubuntu' in PLATFORM.lower()) and
            (LooseVersion(VERSION) <= LooseVersion('14.04'))):
            self.create_init_file()

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
            --tor_id 1 --tor_ip 10.204.221.35
            --tor_ovs_port 9999 --tsn_ip 10.204.221.33 --tor_ovs_protocol tcp
            --tor_agent_ovs_ka 10000
            --controllers 10.204.221.31 10.204.222
            --control-nodes  10.204.221.31 10.204.222
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--self_ip", help = "IP Address of this(compute) node")
        parser.add_argument("--agent_name", help = "Name of the TOR agent")
        parser.add_argument("--http_server_port", help = "Port number for the HTTP server.")
        parser.add_argument("--tor_ip", help = "TOR Switch IP")
        parser.add_argument("--tor_id", help = "Unique ID for the TOR")
        parser.add_argument("--tor_ovs_port", help = "OVS Port Number")
        parser.add_argument("--tsn_ip", help = "TSN Node IP")
        parser.add_argument("--tor_ovs_protocol", help = "TOR OVS Protocol. Currently Only TCP supported")
        parser.add_argument("--tor_agent_ovs_ka", help = "TOR Agent OVS Keepalive timer value in millisecs")
        parser.add_argument("--collectors", help = "List of IP addresses of the VNC collectors",
                            nargs='+', type=str)
        parser.add_argument("--control-nodes", help = "List of IP addresses of the VNC control-nodes",
                            nargs='+', type=str)

        self._args = parser.parse_args(self.remaining_argv)



def main(args_str = None):
    tor_agent_args = TorAgentSetup(args_str)._args
    tor_agent = TorAgentBaseSetup(tor_agent_args)
    tor_agent.setup()

if __name__ == "__main__":
    main()
