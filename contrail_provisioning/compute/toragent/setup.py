#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import ConfigParser
from fabric.api import local, run
from fabric.state import env
from fabric.context_managers import settings, lcd

from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.compute.toragent.templates import tor_agent_conf
from contrail_provisioning.compute.toragent.templates import tor_agent_ini

class TorAgentBaseSetup(ContrailSetup):
    def __init__(self, tor_agent_args, args_str=None):
        super(TorAgentBaseSetup, self).__init__()
        self._args = tor_agent_args
        self.agent_name = local("hostname", capture=True) + '-' + sel._args.tor_id

    def create_ssl_certs(self):
        self.ssl_cert = ''
        self.ssl_privkey = ''
        if self._args.tor_ovs_protocol.lower() == 'pssl':
            domain_name = local("domainname -f", capture=True)
            self.ssl_cert = '/etc/contrail/ssl/certs/tor.' + self._args.tor_id + '.cert.pem'
            self.ssl_privkey = '/etc/contrail/ssl/private/tor.' + self._args.tor_id + '.privkey.pem'
            ssl_cmd = "openssl req -new -x509 -sha256 -newkey rsa:4096 -nodes -subj \"/C=US/ST=Global/L="
            ssl_cmd += self._args.tor_name + "/O=" + self._args.tor_vendor_name + "/CN=" + domain_name + "\""
            ssl_cmd += " -keyout " + self.ssl_privkey + " -out " + self.ssl_cert
            local(ssl_cmd)

    def fixup_tor_agent(self):
        ssl_cacert = ''
        if self._args.tor_ovs_protocol.lower() == 'pssl':
            ssl_cacert = '/etc/contrail/ssl/certs/cacert.pem'

        template_vals = {'__contrail_control_ip__':self._args.self_ip,
                         '__contrail_agent_name__':self.agent_name,
                         '__contrail_http_server_port__':self._args.http_server_port,
                         '__contrail_discovery_ip__':self._args.discovery_server_ip,
                         '__contrail_tor_ip__':self._args.tor_ip,
                         '__contrail_tor_id__':self._args.tor_id,
                         '__contrail_tsn_ovs_port__':self._args.tor_ovs_port,
                         '__contrail_tsn_ip__':self._args.tsn_ip,
                         '__contrail_tor_ovs_protocol__':self._args.tor_ovs_protocol,
                         '__contrail_tor_ssl_cert__':ssl_cert,
                         '__contrail_tor_ssl_privkey__':self.ssl_privkey,
                         '__contrail_tor_ssl_cacert__':self.ssl_cacert,
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
        self._template_substitute_write(tor_agent_ini.template,
                                        template_vals, self._temp_dir_name + '/tor_agent_ini')
        self.tor_ini_file_name=self.tor_process_name + '.ini'
        local("sudo mv %s/tor_agent_ini /etc/contrail/supervisord_vrouter_files/%s" %(self._temp_dir_name,self.tor_ini_file_name))

    def create_init_file(self):
        local("sudo cp /etc/init.d/contrail-vrouter-agent /etc/init.d/%s" %(self.tor_process_name))

    def add_vnc_config(self):
        cmd = "sudo python /opt/contrail/utils/provision_vrouter.py"
        cmd += " --host_name %s" % agent_name
        cmd += " --host_ip %s" % self._args.self_ip
        cmd += " --api_server_ip %s" % self._args.cfgm_ip
        cmd += " --admin_user %s" % self._args.admin_user
        cmd += " --admin_password %s"  % self._args.admin_password
        cmd += " --admin_tenant_name %s" % self._args.admin_tenant
        cmd += " --openstack_ip %s" % self._args.keystone_ip
        cmd += " --router_type tor-agent"
        cmd += " --oper add "
        with settings(warn_only=True):
            local(cmd)

    def add_tor_vendor(self):
        cmd = "sudo python /opt/contrail/utils/provision_physical_device.py"
        cmd += " --device_name %s" % self._args.tor_name
        cmd += " --vendor_name %s" % self._args.tor_vendor_name
        cmd += " --device_mgmt_ip %s" % self._args.tor_mgmt_ip
        cmd += " --device_tunnel_ip %s" % self._args.tor_tunnel_ip
        cmd += " --device_tor_agent %s" % self.args.agent_name
        cmd += " --device_tsn %s" % self._args.tsn_name
        cmd += " --api_server_ip %s" % self._args.cfgm_ip
        cmd += " --admin_user %s"  % self._args.admin_user
        cmd += " --admin_password %s" % self._args.admin_password
        cmd += " --admin_tenant_name %s" % self._args.admin_tenant
        cmd += " --openstack_ip %s" % self._args.keystone_ip
        cmd += " --oper add"
        with settings(warn_only=True):
            local(cmd)

    def setup(self):
        self.create_ssl_certs()
        self.fixup_tor_agent()
        self.fixup_tor_ini()
        self.create_init_file()
        self.add_vnc_config()
        self.add_tor_vendor()


class TorAgentSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(TorAgentSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.global_defaults = {
            'cfgm_ip': '127.0.0.1',
            'keystone_ip': '127.0.0.1',
            'admin_user':None,
            'admin_passwd':None,
            'admin_tenant_name':'admin',
        }

        self.parse_args(args_str)

    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-tor-agent --tor_name contrail-tor-1 --http_server_port 9090
            --discovery_server_ip 10.204.217.39 --tor_id 1 --tor_ip 10.204.221.35
            --tor_ovs_port 9999 --tsn_ip 10.204.221.33 --tor_ovs_protocol tcp
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--self_ip", help = "IP Address of this(compute) node")
        parser.add_argument("--cfgm_ip", help = "IP Address of the config node")
        parser.add_argument("--keystone_ip", help = "IP Address of the keystone node")
        parser.add_argument("--keystone_admin_user", help = "Keystone admin tenants user name")
        parser.add_argument("--admin_password", help = "AuthServer admin user's password")
        parser.add_argument("--admin_tenant_name", help = "AuthServer admin tenant name")
        parser.add_argument("--tor_name", help = "Name of the TOR")
        parser.add_argument("--tor_vendor_name", help = "Name of the TOR vendor")
        parser.add_argument("--tor_tunnel_ip", help = "Tor device tunnel Ipaddress")
        parser.add_argument("--tsn_name", help = "Tsn name")
        parser.add_argument("--tor_mgmt_ip" , help = "Tor device management ipaddress")
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
