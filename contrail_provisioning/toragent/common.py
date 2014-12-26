#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import socket
import netaddr
import argparse
import netifaces
import subprocess
import ConfigParser

from fabric.api import local, run
from fabric.state import env
from fabric.context_managers import settings, lcd

from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.toragent.templates import tor_agent_conf
from contrail_provisioning.toragent.templates import tor_agent_ini

class TorAgentBaseSetup(ContrailSetup):
    def __init__(self, tor_agent_args, args_str=None):
        super(TorAgentBaseSetup, self).__init__()
        self._args = tor_agent_args


    def fixup_tor_agent(self):
        template_vals = {'__contrail_agent_name__':self._args.agent_name,
                         '__contrail_http_server_port__':self._args.http_server_port,
                         '__contrail_discovery_ip__':self._args.discovery_server_ip,
                         '__contrail_tor_ip__':self._args.tor_ip,
                         '__contrail_tor_id__':self._args.tor_id,
                         '__contrail_tsn_ovs_port__':self._args.tor_ovs_port,
                         '__contrail_tsn_ip__':self._args.tsn_ip,
                         '__contrail_tor_ovs_protocol__':self._args.tor_ovs_protocol,
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

    def setup(self):
        self.fixup_tor_agent()
        self.fixup_tor_ini()
        self.create_init_file()
