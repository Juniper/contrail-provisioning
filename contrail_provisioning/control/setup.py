#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import ConfigParser

from fabric.api import local

from contrail_provisioning.common import DEBIAN, RHEL
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
            'collector_ip': '127.0.0.1',
            'discovery_ip': '127.0.0.1',
            'self_ip': '127.0.0.1',
            'use_certs': False,
            'puppet_server': None,
        }

        self.parse_args(args_str)
        self.control_ip = self._args.self_ip

    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-control --cfgm_ip 10.1.5.11 --collector_ip 10.1.5.11
                                        --discovery_ip 10.1.5.11 --self_ip 10.1.5.12
                --use_certs --puppet_server a3s19.contrail.juniper.net
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--cfgm_ip", help = "IP Address of the openstack controller")
        parser.add_argument("--collector_ip", help = "IP Address of the VNC collector")
        parser.add_argument("--discovery_ip", help = "IP Address of the VNC discovery server")
        parser.add_argument("--self_ip", help = "IP Address of the VNC control node")
        parser.add_argument("--use_certs", help = "Use certificates for authentication",
            action="store_true")
        parser.add_argument("--puppet_server", help = "FQDN of Puppet Master")

        self._args = parser.parse_args(self.remaining_argv)


    def fixup_config_files(self): 
        self.remove_override('supervisor-control.override')
        self.remove_override('supervisor-dns.override')
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
                         '__contrail_discovery_ip__': self._args.cfgm_ip,
                         '__contrail_hostname__': self.hostname,
                         '__contrail_host_ip__': self.control_ip,
                         '__contrail_cert_ops__': '%s' %(certdir) if self._args.use_certs else '',
                        }
        self._template_substitute_write(contrail_control_conf.template,
                                        template_vals, self._temp_dir_name + '/contrail-control.conf')
        local("sudo mv %s/contrail-control.conf /etc/contrail/contrail-control.conf" %(self._temp_dir_name))

    def fixup_contrail_control_nodemgr(self):
        template_vals = {'__contrail_discovery_ip__' : self._args.cfgm_ip,
                         '__contrail_discovery_port__': '5998'
                       }
        self._template_substitute_write(contrail_control_nodemgr_template.template,
                                        template_vals, self._temp_dir_name + '/contrail-control-nodemgr.conf')
        local("sudo mv %s/contrail-control-nodemgr.conf /etc/contrail/contrail-control-nodemgr.conf" %(self._temp_dir_name))

    def fixup_dns(self):
        dns_template_vals = {'__contrail_ifmap_usr__': '%s.dns' %(self.control_ip),
                         '__contrail_ifmap_paswd__': '%s.dns' %(self.control_ip),
                         '__contrail_discovery_ip__': self._args.cfgm_ip,
                         '__contrail_hostname__': self.hostname,
                         '__contrail_host_ip__': self.control_ip,
                         '__contrail_cert_ops__': '%s' %(certdir) if self._args.use_certs else '',
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
        if self.pdist in RHEL:
            local("service contrail-control restart")

    def setup(self):
        self.increase_limits()
        super(ControlSetup, self).setup()

    def verify(self):
        self.verify_service("supervisor-control")
        self.verify_service("contrail-control")
        self.verify_service("contrail-dns")
        self.verify_service("contrail-named")

def main(args_str = None):
    control = ControlSetup(args_str)
    control.setup()
    control.verify()

if __name__ == "__main__":
    main()
