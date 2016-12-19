#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#

"""Provisions rabbitmq cluster"""

import os
import re
import shutil
import socket
from time import sleep

from fabric.api import local, settings, hide

from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.common.templates import rabbitmq_env_conf,\
    rabbitmq_config, rabbitmq_config_single_node

CTRL = '-ctrl'


class RabbitMQ(ContrailSetup):
    def __init__(self, amqp_args, args_str=None):
        super(RabbitMQ, self).__init__()
        self._args = amqp_args
        self.rabbitmq_svc_status = 'service rabbitmq-server status'
        self.rabbitmq_cluster_status = 'rabbitmqctl cluster_status'

    def local(self, cmd):
        return local(cmd, capture=True)

    def verify_service(self, retry=False):
        """Verifies the rabbitmq service status."""
        svc_status = False
        # Retry a few times, as rabbit-mq can fail intermittently when trying
        # to connect to AMQP server. Total wait time here is atmost a minute.
        for i in range(0, 6):
            with settings(warn_only=True):
                status = self.local(self.rabbitmq_svc_status)
            if 'running' in status.lower():
                svc_status = True
                break
            elif not retry:
                svc_status = False
                break
            sleep(10)
        return svc_status

    def get_clustered_nodes(self, retry=False):
        """Finds the clustered nodes."""
        cluster_status = False
        # Retry a few times, as rabbit-mq can fail intermittently when trying
        # to connect to AMQP server. Total wait time here is atmost a minute.
        for i in range(0, 6):
            with settings(warn_only=True):
                output = self.local(self.rabbitmq_cluster_status)
            running_nodes = re.compile(r"running_nodes,\[([^\]]*)")
            match = running_nodes.search(output)
            if match:
                cluster_status = True
                break
            elif not retry:
                cluster_status = False
                break
            sleep(10)

        clustered_nodes = None
        if cluster_status:
            clustered_nodes = match.group(1).split(',')
            clustered_nodes = [node.strip(' \n\r\'')\
                               for node in clustered_nodes]
        return clustered_nodes

    def verify(self, retry=False):
        """Verifies the rabbitmq cluster status"""
        rabbitmq_status = False
        # Verify rabbit service status
        svc_status = self.verify_service(retry)
        if not svc_status:
            return rabbitmq_status

        # Get clustered nodes.
        clustered_nodes = self.get_clustered_nodes(retry)
        if not clustered_nodes:
            return rabbitmq_status

        rabbit_nodes = []
        for rabbit_host in self._args.rabbit_hosts:
            rabbit_nodes.append('rabbit@%s' % rabbit_host + CTRL)

        rabbitmq_status = True
        print "Clustered nodes: %s" % clustered_nodes
        for rabbit_node in rabbit_nodes:
            if rabbit_node not in clustered_nodes:
                print "RabbitMQ cluster doesnt list %s"\
                      " in running_nodes" % rabbit_node
                rabbitmq_status = False
        return rabbitmq_status

    def listen_at_supervisor_support_port(self):
        is_running = "service supervisor-support-service status | grep running"
        if local(is_running).failed:
            local("service supervisor-support-service start")
            sock = "unix:///tmp/supervisord_support_service.sock"
            stop_all = "supervisorctl -s %s stop all" % sock
            local(stop_all)

    def remove_mnesia_database(self):
         with settings(warn_only=True):
             local("service rabbitmq-server stop")
             if 'Killed' not in self.local("epmd -kill"):
                 local("pkill -9  beam")
                 local("pkill -9 epmd")
             if 'beam' in self.local("netstat -anp | grep beam"):
                 local("pkill -9  beam")
             local("rm -rf /var/lib/rabbitmq/mnesia")

    def verfiy_and_update_hosts(self):
        # Need to have the alias created to map to the hostname
        # this is required for erlang node to cluster using
        # the same interface that is used for rabbitMQ TCP listener
        for rabbit_host in self._args.rabbit_hosts:
            with settings(hide('stderr'), warn_only=True):
                if local('grep %s /etc/hosts' % (rabbit_host+CTRL)).failed:
                    host_ip = socket.gethostbyname(rabbit_host)
                    local("echo '%s     %s     %s' >> /etc/hosts" %
                          (host_ip, rabbit_host, rabbit_host+CTRL))

    def allow_rabbitmq_port(self):
        self.disable_iptables()

    def fixup_rabbitmq_env_conf(self):
        rabbit_env_conf = '/etc/rabbitmq/rabbitmq-env.conf'
        host_name = self.local('hostname -s') + CTRL
        erl_node_name = "rabbit@%s" % (host_name)
        template_vals = {
                '__erl_node_ip__' : socket.gethostbyname(host_name),
                '__erl_node_name__' : erl_node_name,
                }
        tmp_fname = "/tmp/rabbitmq-env-%s.conf" % host_name
        data = self._template_substitute(rabbitmq_env_conf.template,
                                         template_vals)
        with open(tmp_fname, 'w') as fp:
            fp.write(data)
        shutil.move(tmp_fname, rabbit_env_conf)


    def fixup_rabbitmq_config(self):
        rabbit_hosts = []
        rabbit_conf = '/etc/rabbitmq/rabbitmq.config'
        host_name = self.local('hostname -s') + CTRL
        if (len(self._args.rabbit_hosts) <= 1 and self.pdist == 'redhat'):
            print "CONFIG_RABBITMQ: Skip creating rabbitmq.config"\
                  " for Single node setup"
            return
        for rabbit_host in self._args.rabbit_hosts:
            rabbit_hosts.append("\'rabbit@%s\'" % rabbit_host + CTRL)
        rabbit_hosts = ', '.join(rabbit_hosts)

        template_vals = { 
               '__control_intf_ip__' : socket.gethostbyname(host_name),
               '__rabbit_hosts__' : rabbit_hosts,
               }

        rabbitmq_config_template = rabbitmq_config
        if len(self._args.rabbit_hosts) == 1:
            rabbitmq_config_template = rabbitmq_config_single_node
        tmp_fname = "/tmp/rabbitmq_%s.config" % host_name
        data = self._template_substitute(rabbitmq_config_template.template,
                                         template_vals)
        with open(tmp_fname, 'w') as fp:
            fp.write(data)
        shutil.move(tmp_fname, rabbit_conf)

    def stop_rabbitmq_and_set_cookie(self):
         with settings(warn_only=True):
             local("service rabbitmq-server stop")
             if 'Killed' not in self.local("epmd -kill"):
                 local("pkill -9  beam")
                 local("pkill -9 epmd")
             if 'beam' in self.local("netstat -anp | grep beam"):
                 local("pkill -9  beam")
             local("rm -rf /var/lib/rabbitmq/mnesia/")
         local("echo '%s' > /var/lib/rabbitmq/.erlang.cookie" % self._args.cookie)
         local("chmod 400 /var/lib/rabbitmq/.erlang.cookie")
         local("chown rabbitmq:rabbitmq /var/lib/rabbitmq/.erlang.cookie")

    def start_rabbitmq(self):
        local("service rabbitmq-server restart")

    def set_ha_policy_in_rabbitmq(self):
        local("rabbitmqctl set_policy HA-all"\
              " \"\" '{\"ha-mode\":\"all\",\"ha-sync-mode\":\"automatic\"}'")

    def set_tcp_keepalive(self):
        sysctl_file = '/etc/sysctl.conf'
        with open(sysctl_file, 'r') as fp:
            sysctl_conf = fp.read()
        tcp_keepalive_vars = {'net.ipv4.tcp_keepalive_time' : 5,
                              'net.ipv4.tcp_keepalive_probes' : 5,
                              'net.ipv4.tcp_keepalive_intvl' : 1,
                             }
        for tcp_param, tcp_value in tcp_keepalive_vars.items():
           if tcp_param in sysctl_conf:
                local("sed -i 's/%s\s\s*/%s = %s/' %s" % (tcp_param, tcp_param,
                                                       tcp_value, sysctl_file))
           else:
                local("echo '%s = %s' >> %s" % (tcp_param, tcp_value,
                                               sysctl_file))

    def setup(self):
        """ Provisions rabbitMQ cluster."""
        if not self._args.force:
            if self.verify(retry=True):
                print "RabbitMQ cluster is up and running in node[%s];"\
                      " No need to cluster again." % self._args.self_ip
                return

        self.listen_at_supervisor_support_port()
        self.remove_mnesia_database()
        self.verfiy_and_update_hosts()
        self.allow_rabbitmq_port()
        self.fixup_rabbitmq_env_conf()
        self.fixup_rabbitmq_config()
        self.stop_rabbitmq_and_set_cookie
        self.start_rabbitmq()
        if (self._args.role == 'openstack' and self._args.internal_vip or
            self._args.role == 'cfgm' and self._args.contrail_internal_vip):
            self.set_ha_policy_in_rabbitmq()
            self.set_tcp_keepalive()
            #self.set_tcp_keepalive_on_compute()
        if not self.verify(retry=True):
            print "Unable to setup RabbitMQ cluster in role[%s]...." %\
                      self._args.role
            exit(1)
