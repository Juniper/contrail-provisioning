#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#

from templates import openstack_haproxy

class OpenstackHaproxyConfig(object):
    def __init__(self, args):
        self._args = args

    def create(self):
        haproxy_config = ''

        # if this openstack is also config, skip quantum stanza
        # as that would have been generated in config context
        q_stanza = ''
        if self._args.self_ip not in self._args.cfgm_ip_list:
            # generate a quantum stanza
            q_server_lines = ''
            for host_ip in self._args.cfgm_ip_list:
                q_server_lines = q_server_lines + \
                '    server %s %s:9696 check\n' %(host_ip, host_ip)

                q_stanza = q_stanza_template.safe_substitute({
                    '__contrail_quantum_frontend__': q_frontend,
                    '__contrail_quantum_servers__': q_server_lines,
                    })

        with settings(host_string=host_ip):
            # chop old settings including pesky default from pkg...
            haproxy_fname = "/etc/haproxy/haproxy.cfg"
            with settings(warn_only=True):
                local("sed -i -e '/^#contrail-openstack-marker-start/,/^#contrail-openstack-marker-end/d' %s"\
                       %(haproxy_fname))
                local("sed -i -e 's/*:5000/*:5001/' %s" %(haproxy_fname))
                local("sed -i -e 's/ssl-relay 0.0.0.0:8443/ssl-relay 0.0.0.0:5002/' %s" %(haproxy_fname))
            # ...generate new ones
            openstack_haproxy = openstack_haproxy.template.safe_substitute({
                '__contrail_hap_user__': 'haproxy',
                '__contrail_hap_passwd__': 'contrail123',
                '__contrail_quantum_stanza__': q_stanza,
                })
            with open(haproxy_fname, 'a') as cfg_file:
                cfg_file.write(openstack_haproxy)

    def start(self):
        with settings(warn_only=True):
            sudo("chkconfig haproxy on")
            sudo("service haproxy restart")
