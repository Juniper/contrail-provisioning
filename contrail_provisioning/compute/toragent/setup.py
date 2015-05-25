#!/usr/bin/python
#
# Copyright (c) 2014 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import itertools
import ConfigParser
from fabric.api import local
from fabric.context_managers import settings

from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.compute.toragent.templates import tor_agent_conf
from contrail_provisioning.compute.toragent.templates import tor_agent_ini

class TorAgentBaseSetup(ContrailSetup):
    def __init__(self, tor_agent_args, args_str=None):
        super(TorAgentBaseSetup, self).__init__()
        self._args = tor_agent_args
        nargs_count = len(self._args.tor_names)
        self.toragent_nargs = [
                               self._args.tor_name,
                               self._args.tor_vendor_names,
                               self._args.tor_tunnel_ips,
                               self._args.tsn_names,
                               self._args.tor_mgmt_ips,
                               self._args.http_server_ports,
                               self._args.tor_ips,
                               self._args.tor_ids,
                               self._args.tor_ovs_ports,
                               self._args.tsn_ips,
                               self._args.tor_ovs_protocols,
                              ]
        if self._args.tor_agent_names:
            self.toragent_nargs.append(self._args.tor_agent_names)
        err_msg = ''
        for narg in self.toragent_nargs:
            if len(narg) != nargs_count:
                err_msg += '\n\t Mismatch in the number of args for %s'
        if err_msg:
            raise RuntimeError(err_msg)

        # Add to toragent_nargs, itertools.izip_longest will
        # populate the empty list with None
        # and thus the code path will determine the agent name
        if not self._args.tor_agent_names:
            self.toragent_nargs.append(self._args.tor_agent_names)

    def copy_ssl_certs(self):
        """ Copies the ssl certs from active node to this node using RPC call"""
        rpc = connect(self.args_active_tor)
        interval = 5
        while not rpc.is_toragent_ssl_certs_created:
            print "Waiting (%s) secs to get the ssl certs created in active toragent node." % interval
            sleep(interval)
        rpc.get_toragent_ssl_certs(self.ssl_cert)
        rpc.get_toragent_ssl_certs(self.ssl_privkey)

    def create_ssl_certs(self):
        self.ssl_cert = '/etc/contrail/ssl/certs/tor.' + self.args_tor_id + '.cert.pem'
        self.ssl_privkey = '/etc/contrail/ssl/private/tor.' + self.args_tor_id + '.privkey.pem'
        # Create certificates if this is a active toragent node
        if self.args_tor_ovs_protocol.lower() == 'pssl' and not self.args_active_tor:
            # Create ssl certs once
            if not os.path.exists(self.ssl_cert) or not os.path.exists(self.ssl_privkey):
                domain_name = local("domainname -f", capture=True)
                ssl_cmd = "openssl req -new -x509 -sha256 -newkey rsa:4096 -nodes -subj \"/C=US/ST=Global/L="
                ssl_cmd += self.args_tor_name + "/O=" + self._args.tor_vendor_name + "/CN=" + domain_name + "\""
                ssl_cmd += " -keyout " + self.ssl_privkey + " -out " + self.ssl_cert
                local(ssl_cmd)
        elif self.args_active_tor:
            # Copy ssl certs once
            if not os.path.exists(self.ssl_cert) or not os.path.exists(self.ssl_privkey):
                self.copy_ssl_certs()

    def fixup_tor_agent(self):
        self.ssl_cacert = ''
        if self.args_tor_ovs_protocol.lower() == 'pssl':
            self.ssl_cacert = '/etc/contrail/ssl/certs/cacert.pem'

        template_vals = {'__contrail_control_ip__':self._args.self_ip,
                         '__contrail_agent_name__':self.agent_name,
                         '__contrail_http_server_port__':self.args_http_server_port,
                         '__contrail_discovery_ip__':self._args.discovery_ip,
                         '__contrail_tor_ip__':self.args_tor_ip,
                         '__contrail_tor_id__':self.args_tor_id,
                         '__contrail_tsn_ovs_port__':self.args_tor_ovs_port,
                         '__contrail_tsn_ip__':self.args_tsn_ip,
                         '__contrail_tor_ovs_protocol__':self.args_tor_ovs_protocol,
                         '__contrail_tor_ssl_cert__':self.ssl_cert,
                         '__contrail_tor_ssl_privkey__':self.ssl_privkey,
                         '__contrail_tor_ssl_cacert__':self.ssl_cacert,
                        }
        self._template_substitute_write(tor_agent_conf.template,
                                        template_vals, self._temp_dir_name + '/tor_agent_conf')
        self.tor_file_name = 'contrail-tor-agent-' + self.args_tor_id + '.conf'
        local("sudo mv %s/tor_agent_conf /etc/contrail/%s" %(self._temp_dir_name,self.tor_file_name))

    def fixup_tor_ini(self):
        self.tor_process_name = 'contrail-tor-agent-' + self.args_tor_id
        self.tor_log_file_name = self.tor_process_name + '-stdout.log'

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
        cmd += " --host_name %s" % self.agent_name
        cmd += " --host_ip %s" % self._args.self_ip
        cmd += " --api_server_ip %s" % self._args.cfgm_ip
        cmd += " --admin_user %s" % self._args.admin_user
        cmd += " --admin_password %s"  % self._args.admin_password
        cmd += " --admin_tenant_name %s" % self._args.admin_tenant
        cmd += " --openstack_ip %s" % self._args.authserver_ip
        cmd += " --router_type tor-agent"
        cmd += " --oper add "
        with settings(warn_only=True):
            local(cmd)

    def add_tor_vendor(self):
        cmd = "sudo python /opt/contrail/utils/provision_physical_device.py"
        cmd += " --device_name %s" % self.args_tor_name
        cmd += " --vendor_name %s" % self.args_tor_vendor_name
        cmd += " --device_mgmt_ip %s" % self.args_tor_mgmt_ip
        cmd += " --device_tunnel_ip %s" % self.args_tor_tunnel_ip
        cmd += " --device_tor_agent %s" % self.agent_name
        cmd += " --device_tsn %s" % self.args_tsn_name
        cmd += " --api_server_ip %s" % self._args.cfgm_ip
        cmd += " --admin_user %s"  % self._args.admin_user
        cmd += " --admin_password %s" % self._args.admin_password
        cmd += " --admin_tenant_name %s" % self._args.admin_tenant
        cmd += " --openstack_ip %s" % self._args.authserver_ip
        cmd += " --oper add"
        with settings(warn_only=True):
            local(cmd)

    def run_services(self):
        if self._args.restart:
            local("sudo supervisorctl -c /etc/contrail/supervisord_vrouter.conf update")

    def setup(self):
        for (self.args_tor_name, self.args_tor_agent_name,
             self.args_tor_vendor_name, self.args_tor_tunnel_ip,
             self.args_tsn_name, self.args.tor_mgmt_ip,
             self.args_http_server_port, self.args_tor_ip,
             self.args_tor_id, self.args_tor_ovs_port,
             self.args_tsn_ip, self.args_tor_ovs_protocol)\
            in itertools.izip_longest(*self.toragent_nargs):

            if (self.args_tor_agent_name == 'NULL' or
                not self.args_tor_agent_name):
                self.agent_name = local("hostname", capture=True) +\
                                  '-' + self.args_tor_id
            else:
                self.agent_name = self.args_tor_agent_name
            self.create_ssl_certs()
            self.fixup_tor_agent()
            self.fixup_tor_ini()
            self.create_init_file()
            self.add_vnc_config()
            self.add_tor_vendor()
        self.run_services()


class TorAgentSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(TorAgentSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.global_defaults = {
            'cfgm_ip': '127.0.0.1',
            'authserver_ip': '127.0.0.1',
            'admin_user':None,
            'admin_passwd':None,
            'admin_tenant_name':'admin',
            'restart':False
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
        parser.add_argument("--discovery_ip", help = "IP Address of the config node")
        parser.add_argument("--authserver_ip", help = "IP Address of the authserver(keystone) node")
        parser.add_argument("--admin_user", help = "Authserver admin tenants user name")
        parser.add_argument("--admin_password", help = "AuthServer admin user's password")
        parser.add_argument("--admin_tenant_name", help = "AuthServer admin tenant name")
        parser.add_argument("--tor_names", help = "Name list of the TOR's",
                            nargs='+', type=str)
        parser.add_argument("--tor_agent_names", help = "Name list of the TORi agents",
                            nargs='+', type=str)
        parser.add_argument("--tor_vendor_names", help = "Name list of the TOR vendors",
                            nargs='+', type=str)
        parser.add_argument("--tor_tunnel_ips", help = "List of Tor device tunnel Ipaddress",
                            nargs='+', type=str)
        parser.add_argument("--tsn_names", help = "List of Tsn name",
                            nargs='+', type=str)
        parser.add_argument("--tor_mgmt_ips" , help = "List of Tor device management ipaddress",
                            nargs='+', type=str)
        parser.add_argument("--http_server_ports", help = "List of Port number for the HTTP server.",
                            nargs='+', type=str)
        parser.add_argument("--tor_ips", help = "List of TOR Switch IP",
                            nargs='+', type=str)
        parser.add_argument("--tor_ids", help = "List of Unique ID for the TOR",
                            nargs='+', type=str)
        parser.add_argument("--tor_ovs_ports", help = "List of OVS Port Number",
                            nargs='+', type=str)
        parser.add_argument("--tsn_ips", help = "List of TSN Node IP",
                            nargs='+', type=str)
        parser.add_argument("--tor_ovs_protocols", help = "List of TOR OVS Protocol.",
                            nargs='+', type=str)
        parser.add_argument("--restart", help="Restart the toragent services.", action="store_true")

        self._args = parser.parse_args(self.remaining_argv)


def main(args_str = None):
    tor_agent_args = TorAgentSetup(args_str)._args
    tor_agent = TorAgentBaseSetup(tor_agent_args)
    tor_agent.setup()

if __name__ == "__main__":
    main()
