#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#

import os
import sys

from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.common.rabbitmq import RabbitMQ


class AmqpSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(AmqpSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.global_defaults = {
            'self_ip' : '127.0.0.1',
            'internal_vip' : None,
            'contrail_internal_vip' : None,
            'role' : 'cfgm',
            'force' : False,
            'amqp' : 'rabbitmq',
        }
        self.parse_args(args_str)

    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-rabbitmq --self_ip 10.1.5.11\
                               --rabbit_hosts cfgm1,cfgm2,cfgm3\
                               --cookie 4438e3a2-529e-42b2-abb7-44a3c5bb64ad\
                               --role config
            Optional args used when role is openstack,
                           --internal_vip 192.168.122.200
                           --contrail_internal_vip 192.168.122.250
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--self_ip", help = "IP Address of this system")
        parser.add_argument("--rabbit_hosts", nargs='+', type=str,
            help = "List of short hostnames(hostname -s) of rabbit nodes")
        parser.add_argument("--cookie", help = "RabbitMQ erlang cookie string.")
        parser.add_argument("--internal_vip", help = "VIP Address of openstack  nodes")
        parser.add_argument("--contrail_internal_vip", help = "Internal VIP Address of HA config Nodes")
        parser.add_argument("--role", help="Contrail role of nodes to be clustered.")
        parser.add_argument("--force", help = "Force cluster again", action="store_true")
        parser.add_argument("--amqp", help="AMQP to be used.")
  
        self._args = parser.parse_args(self.remaining_argv)

def main(args_str = None):
    amqp_args = AmqpSetup(args_str)._args
    if amqp_args.amqp == 'rabbitmq':
        amqp = RabbitMQ(amqp_args)
    # For future AMQP's other rabbitmq,
    # Implement specific amqp setup class and
    # Instantiate it in the else part
    amqp.setup()

if __name__ == "__main__":
    main() 
