#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import ConfigParser

from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.common.templates import keepalived_conf_template


class KeepalivedSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(KeepalivedSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])
        self.parse_args(args_str)

    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-keepalived --self_ip 10.1.5.11 --mgmt_self_ip 11.1.5.11
                   --self_index 1 --internal_vip 10.1.5.13 --external_vip 11.1.5.13
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--role", help = "Role of the node")
        parser.add_argument("--self_ip", help = "IP Address of this system")
        parser.add_argument("--mgmt_self_ip", help = "Management IP Address of this system")
        parser.add_argument("--internal_vip", help = "Internal(private) Virtual IP Addresses of HA nodes"),
        parser.add_argument("--external_vip", help = "External(public) Virtual IP Addresses of HA nodes"),
        parser.add_argument("--self_index", help = "The index of this HA node")
        parser.add_argument("--num_nodes", help = "Number of available HA node")
        self._args = parser.parse_args(remaining_argv)

    def fixup_config_files(self):
        vip_for_ips = [(self._args.internal_vip, self._args.self_ip, 'INTERNAL')]
        if self._args.external_vip:
            vip_for_ips.append((self._args.external_vip, self._args.mgmt_self_ip, 'EXTERNAL'))
        for vip, ip, vip_name in vip_for_ips:
            # keepalived.conf
            device = self.get_device_by_ip(ip)
            netmask = netifaces.ifaddresses(device)[netifaces.AF_INET][0]['netmask']
            prefix = netaddr.IPNetwork('%s/%s' % (ip, netmask)).prefixlen
            state = 'BACKUP'
            delay = 1
            preempt_delay = 1
            timeout = 1
            rise = 1
            fall = 1
            garp_master_repeat = 3
            garp_master_refresh = 1
            if self._args.self_index == 1:
                state = 'MASTER'
                delay = 5
                preempt_delay = 7
                timeout = 3
                rise = 2
                fall = 2
            if vip_name == 'INTERNAL':
                router_id = 101
                if 'openstack' in self._args.role:
                    router_id = 100
            else:
                router_id = 201
                if 'openstack' in self._args.role:
                    router_id = 200
            priority = router_id - (self._args.self_index - 1)
            if self._args.num_nodes > 2 and self._args.self_index == 2:
                state = 'BACKUP'
            vip_str = '_'.join([vip_name] + vip.split('.'))
            template_vals = {'__device__': device,
                             '__router_id__' : router_id,
                             '__state__' : state,
                             '__delay__' : delay,
                             '__garp_master_repeat__' : garp_master_repeat,
                             '__garp_master_refresh__' : garp_master_refresh,
                             '__preempt_delay__' : preempt_delay,
                             '__priority__' : priority,
                             '__virtual_ip__' : vip,
                             '__virtual_ip_mask__' : prefix,
                             '__vip_str__' : vip_str,
                             '__timeout__' : timeout,
                             '__rise__' : rise,
                             '__fall__' : fall,
                            }
            data = self._template_substitute(keepalived_conf_template.template,
                                      template_vals)
            with open(self._temp_dir_name + '/keepalived.conf', 'a+') as fp:
                fp.write(data)
        local("sudo mv %s/keepalived.conf /etc/keepalived/" %(self._temp_dir_name))

    def run_services(self):
        local("service keepalived restart")

def main(args_str = None):
    keepalived = KeepalivedSetup(args_str)
    keepalived.setup()

if __name__ == "__main__":
    main() 
