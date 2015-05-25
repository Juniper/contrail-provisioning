#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#

from templates import compute_haproxy

class ComputeHaproxyConfig(object):
    def __init__(self, args):
        self._args = args 

    def generate(self):
        haproxy_config = ''

        # if this compute is also config, skip quantum and discovery
        # stanza as they would have been generated in config context
        ds_stanza = ''
        q_stanza = ''
        if self._args.self_ip not in self._args.cfgm_ip_list:
            # generate discovery service stanza
            ds_server_lines = ''
            for host_ip in self._args.cfgm_ip_list:
                ds_server_lines = ds_server_lines + \
                '    server %s %s:5998 check\n' %(host_ip, host_ip)

                ds_stanza = compute_haproxy.ds_stanza_template.safe_substitute({
                    '__contrail_disc_frontend__': ds_frontend,
                    '__contrail_disc_servers__': ds_server_lines,
                    })

            # generate  quantum stanza
            q_server_lines = ''
            for host_ip in self._args.cfgm_ip_list:
                q_server_lines = q_server_lines + \
                '    server %s %s:9696 check\n' %(host_ip, host_ip)

                q_stanza = compute_haproxy.q_stanza_template.safe_substitute({
                    '__contrail_quantum_frontend__': q_frontend,
                    '__contrail_quantum_servers__': q_server_lines,
                    })

        # if this compute is also openstack, skip glance-api stanza
        # as that would have been generated in openstack context
        g_api_stanza = ''
        if self._args.self_ip not in self._args.openstack_ip_list:
            # generate a glance-api stanza
            g_api_server_lines = ''
            for host_ip in self._args.openstack_ip_list:
                g_api_server_lines = g_api_server_lines + \
                '    server %s %s:9292 check\n' %(host_ip, host_ip)

                g_api_stanza = compute_haproxy.g_api_stanza_template.safe_substitute({
                    '__contrail_glance_api_frontend__': g_api_frontend,
                    '__contrail_glance_apis__': g_api_server_lines,
                    })
                # HACK: for now only one openstack
                break

        # chop old settings including pesky default from pkg...
        haproxy_fname = "/etc/haproxy.cfg"
        with settings(warn_only=True):
            local("sed -i -e '/^#contrail-compute-marker-start/,/^#contrail-compute-marker-end/d' %s"\
                   %(haproxy_fname))
            local("sed -i -e 's/*:5000/*:5001/' %s" %(haproxy_fname))
            local("sed -i -e 's/ssl-relay 0.0.0.0:8443/ssl-relay 0.0.0.0:5002/' %s" %(haproxy_fname))
        # ...generate new ones
        compute_haproxy = compute_haproxy.template.safe_substitute({
            '__contrail_hap_user__': 'haproxy',
            '__contrail_hap_passwd__': 'contrail123',
            '__contrail_disc_stanza__': ds_stanza,
            '__contrail_quantum_stanza__': q_stanza,
            '__contrail_glance_api_stanza__': g_api_stanza,
            '__contrail_qpid_stanza__': '',
        })

        with open(haproxy_fname, 'a') as cfg_file:
            cfg_file.write(compute_haproxy)

    def start(self):
        with settings(warn_only=True):
            local("sudo chkconfig haproxy on")
            local("sudo service haproxy restart")
