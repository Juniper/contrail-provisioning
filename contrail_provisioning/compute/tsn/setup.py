#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import socket
import argparse
import ConfigParser

from fabric.api import local, settings

from contrail_provisioning.compute.setup import ComputeSetup
from contrail_provisioning.compute.common import ComputeBaseSetup


class TsnSetup(ComputeBaseSetup):
    def __init__(self, tsn_args, args_str=None):
        super(TsnSetup, self).__init__(tsn_args)
        self.tsn_hostname = socket.gethostname()

    def disable_nova_compute(self):
        # Check if nova-compute is allready running
        # Stop if running on TSN node
        with settings(warn_only=True):
            if local("sudo service nova-compute status | grep running").succeeded:
                # Stop the service
                local("sudo service nova-compute stop")
                if self.pdist in DEBIAN:
                    local('sudo echo "manual" >> /etc/init/nova-compute.override')
                else:
                    local('sudo chkconfig nova-compute off')

    def add_vnc_config(self):
        tsn_ip = self._args.self_ip
        prov_args = "--host_name %s --host_ip %s --api_server_ip %s --oper add "\
                    "--admin_user %s --admin_password %s --admin_tenant_name %s "\
                    "--openstack_ip %s --router_type tor-service-node"\
                    %(self.tsn_hostname, tsn_ip, self._args.cfgm_ip,
                      self._args.keystone_admin_user,
                      self._args.keystone_admin_password,
                      self._args.keystone_admin_tenant_name, self._args.keystone_ip)
        local("python /opt/contrail/utils/provision_vrouter.py %s" %(prov_args))

    def setup(self):
        super(TsnSetup, self).setup()
        self.disable_nova_compute()

def main(args_str=None):
    tsn_args = ComputeSetup(args_str)._args
    tsn = TsnSetup(tsn_args)
    tsn.setup()

if __name__ == "__main__":
    main()
