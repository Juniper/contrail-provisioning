#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import ConfigParser

from fabric.api import local

from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.control.templates import contrail_control_conf
from contrail_provisioning.control.templates import dns_conf
from contrail_provisioning.control.templates import contrail_control_nodemgr_template

class ControlSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(ControlSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.global_defaults = {
            'cfgm_ip': '127.0.0.1',
            # [NIPAK] To be removed once CI passes and fab provisioning merges
            'collector_ip': '127.0.0.1',
            # [NIPAK] To be removed once CI passes and fab provisioning merges
            'discovery_ip': '127.0.0.1',
            'self_ip': '127.0.0.1',
            'use_certs': False,
            'puppet_server': None,
            'collectors' : None,
        }

        self.parse_args(args_str)
        self.control_ip = self._args.self_ip

    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-control --cfgm_ip 10.1.5.11
                              --collector_ip 10.1.5.11
                              --discovery_ip 10.1.5.11
                              --self_ip 10.1.5.12
                --use_certs --puppet_server a3s19.contrail.juniper.net
                --collectors 10.1.5.11 10.1.5.12
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--cfgm_ip", help = "IP Address of the openstack controller")
        # [NIPAK] To be removed once CI passes and fab provisioning merges
        parser.add_argument("--collector_ip", help = "IP Address of the VNC collector")
        # [NIPAK] To be removed once CI passes and fab provisioning merges
        parser.add_argument("--discovery_ip", help = "IP Address of the VNC discovery server") 
        parser.add_argument("--self_ip", help = "IP Address of the VNC control node")
        parser.add_argument("--use_certs", help = "Use certificates for authentication",
            action="store_true")
        parser.add_argument("--puppet_server", help = "FQDN of Puppet Master")
        parser.add_argument('--collectors', help = "List of IP:port of the VNC collectors",
                            nargs="+")

        self._args = parser.parse_args(self.remaining_argv)


    def fixup_config_files(self): 
        self.fixup_contrail_control()
        self.fixup_dns()
        self.fixup_contrail_control_nodemgr()
        if self._args.puppet_server:
            local("echo '    server = %s' >> /etc/puppet/puppet.conf" \
                %(self._args.puppet_server))

    def fixup_contrail_control(self):
        certdir = '/var/lib/puppet/ssl' if self._args.puppet_server else '/etc/contrail/ssl'
        template_vals = {'__contrail_ifmap_usr__': '%s' %(self.control_ip),
                         '__contrail_ifmap_paswd__': '%s' %(self.control_ip),
                         '__contrail_hostname__': self.hostname,
                         '__contrail_host_ip__': self.control_ip,
                         '__contrail_cert_ops__': '%s' %(certdir) if self._args.use_certs else '',
                         '__contrail_collectors__': \
                             ' '.join('%s:%s' %(server, '8086') for server \
                                in self._args.collectors),
                         '__contrail_ifmap_server_url__': '%s' %('https://' + self._args.cfgm_ip + ':8443'),
                        }
        self._template_substitute_write(contrail_control_conf.template,
                                        template_vals, self._temp_dir_name + '/contrail-control.conf')
        local("sudo mv %s/contrail-control.conf /etc/contrail/contrail-control.conf" %(self._temp_dir_name))

    def fixup_contrail_control_nodemgr(self):
        template_vals = {
                         '__contrail_collectors__': \
                             ' '.join('%s:%s' %(server, '8086') for server \
                                in self._args.collectors),
                        }
        self._template_substitute_write(contrail_control_nodemgr_template.template,
                                        template_vals, self._temp_dir_name + '/contrail-control-nodemgr.conf')
        local("sudo mv %s/contrail-control-nodemgr.conf /etc/contrail/contrail-control-nodemgr.conf" %(self._temp_dir_name))

    def fixup_dns(self):
        dns_template_vals = {'__contrail_ifmap_usr__': '%s.dns' %(self.control_ip),
                         '__contrail_ifmap_paswd__': '%s.dns' %(self.control_ip),
                         '__contrail_hostname__': self.hostname,
                         '__contrail_host_ip__': self.control_ip,
                         '__contrail_cert_ops__': '%s' %(certdir) if self._args.use_certs else '',
                         '__contrail_collectors__': \
                             ' '.join('%s:%s' %(server, '8086') for server \
                                in self._args.collectors),
                         '__contrail_ifmap_server_url__': '%s' %('https://' + self._args.cfgm_ip + ':8443'),
                        }
        self._template_substitute_write(dns_conf.template,
                                        dns_template_vals, self._temp_dir_name + '/contrail-dns.conf')
        local("sudo mv %s/contrail-dns.conf /etc/contrail/contrail-dns.conf" %(self._temp_dir_name))
        for confl in 'contrail-rndc contrail-named'.split():
            local("".join(["sed -i 's/secret \"secret123\"",
                           ";/secret \"xvysmOR8lnUQRBcunkC6vg==\";/g'",
                           " /etc/contrail/dns/%s.conf" % confl]))

    def run_services(self):
        local("sudo control-server-setup.sh")

def main(args_str = None):
    control = ControlSetup(args_str)
    control.setup()

if __name__ == "__main__":
    main()
