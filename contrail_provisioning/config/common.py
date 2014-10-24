#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#
"""Provision's Contrail Config components."""

import os
from time import sleep

from fabric.state import env
from fabric.api import local
from fabric.context_managers import settings

from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.config.templates import ifmap_log4j
from contrail_provisioning.config.templates import ifmap_authorization
from contrail_provisioning.config.templates import ifmap_basicauthusers
from contrail_provisioning.config.templates import ifmap_publisher
from contrail_provisioning.config.templates import contrail_api_conf
from contrail_provisioning.config.templates import contrail_api_ini
from contrail_provisioning.config.templates import contrail_api_ini_centos
from contrail_provisioning.config.templates import contrail_api_svc
from contrail_provisioning.config.templates import contrail_plugin_ini
from contrail_provisioning.config.templates import contrail_schema_transformer_conf
from contrail_provisioning.config.templates import contrail_svc_monitor_conf
from contrail_provisioning.config.templates import contrail_discovery_conf
from contrail_provisioning.config.templates import contrail_discovery_ini
from contrail_provisioning.config.templates import contrail_discovery_ini_centos
from contrail_provisioning.config.templates import contrail_discovery_svc
from contrail_provisioning.config.templates import vnc_api_lib_ini


class ConfigBaseSetup(ContrailSetup):
    def __init__(self, config_args, args_str=None):
        super(ConfigBaseSetup, self).__init__()
        self._args = config_args

        self.cfgm_ip = self._args.self_ip
        self.cassandra_server_list = [(cassandra_server_ip, '9160') for cassandra_server_ip in self._args.cassandra_ip_list]
        self.zk_servers = ','.join(self._args.zookeeper_ip_list)
        self.zk_servers_ports = ','.join(['%s:2181' %(s) for s in self._args.zookeeper_ip_list])

    def fixup_config_files(self):
        self.fixup_ifmap_config_files()
        self.fixup_contrail_api_config_file()
        self.fixup_contrail_api_supervisor_ini()
        self.fixup_contrail_api_initd()
        self.fixup_schema_transformer_config_file()
        self.fixup_svc_monitor_config_file()
        self.fixup_discovery_config_file()
        self.fixup_discovery_supervisor_ini()
        self.fixup_discovery_initd()
        self.fixup_vnc_api_lib_ini()
        if self._args.use_certs:
            local("sudo setup-pki.sh /etc/contrail/ssl")

    def fixup_ifmap_config_files(self):
        if self.pdist == 'Ubuntu' or self.pdist == 'centos' or self.pdist == 'redhat':
            # log4j.properties
            template_vals = {
                            }
            self._template_substitute_write(ifmap_log4j.template,
                                            template_vals, self._temp_dir_name + '/log4j.properties')
            local("sudo mv %s/log4j.properties /etc/ifmap-server/" %(self._temp_dir_name))
            # authorization.properties
            template_vals = {
                            }
            self._template_substitute_write(ifmap_authorization.template,
                                            template_vals, self._temp_dir_name + '/authorization.properties')
            local("sudo mv %s/authorization.properties /etc/ifmap-server/" %(self._temp_dir_name))
            # basicauthusers.properties
            template_vals = {
                            }
            self._template_substitute_write(ifmap_basicauthusers.template,
                                            template_vals, self._temp_dir_name + '/basicauthusers.properties')
            local("sudo mv %s/basicauthusers.properties /etc/ifmap-server/" %(self._temp_dir_name))
            # publisher.properties
            template_vals = {
                            }
            self._template_substitute_write(ifmap_publisher.template,
                                            template_vals, self._temp_dir_name + '/publisher.properties')
            local("sudo mv %s/publisher.properties /etc/ifmap-server/" %(self._temp_dir_name))

    def fixup_contrail_api_config_file(self):
        self.rabbit_host = self.cfgm_ip
        self.rabbit_port = 5672
        if self._args.internal_vip:
            self.rabbit_host = self._args.internal_vip
            self.rabbit_port = 5673
        # contrail-api.conf
        template_vals = {'__contrail_ifmap_server_ip__': self.cfgm_ip,
                         '__contrail_ifmap_server_port__': '8444' if self._args.use_certs else '8443',
                         '__contrail_ifmap_username__': 'api-server',
                         '__contrail_ifmap_password__': 'api-server',
                         '__contrail_listen_ip_addr__': '0.0.0.0',
                         '__contrail_listen_port__': '8082',
                         '__contrail_use_certs__': self._args.use_certs,
                         '__contrail_keyfile_location__': '/etc/contrail/ssl/private_keys/apiserver_key.pem',
                         '__contrail_certfile_location__': '/etc/contrail/ssl/certs/apiserver.pem',
                         '__contrail_cacertfile_location__': '/etc/contrail/ssl/certs/ca.pem',
                         '__contrail_multi_tenancy__': self._args.multi_tenancy,
                         '__rabbit_server_ip__': self._args.internal_vip or self.rabbit_host,
                         '__rabbit_server_port__': self.rabbit_port,
                         '__contrail_log_file__': '/var/log/contrail/contrail-api.log',
                         '__contrail_cassandra_server_list__' : ' '.join('%s:%s' % cassandra_server for cassandra_server in self.cassandra_server_list),
                         '__contrail_disc_server_ip__': self._args.internal_vip or self.cfgm_ip,
                         '__contrail_disc_server_port__': '5998',
                         '__contrail_zookeeper_server_ip__': self.zk_servers_ports,
                        }
        self._template_substitute_write(contrail_api_conf.template,
                                        template_vals, self._temp_dir_name + '/contrail-api.conf')
        local("sudo mv %s/contrail-api.conf /etc/contrail/" %(self._temp_dir_name))

    def fixup_contrail_api_supervisor_ini(self, config_files=['/etc/contrail/contrail-api.conf']):
        # supervisor contrail-api.ini
        config_file_args = ' --conf_file '.join(config_files)
        template_vals = {'__contrail_api_port_base__': '910', # 910x
                         '__contrail_api_nworkers__': self._args.nworkers,
                         '__contrail_config_file_args__' : config_file_args,
                        }
        if self.pdist == 'Ubuntu':
            tmpl = contrail_api_ini.template
        else:
            tmpl = contrail_api_ini_centos.template

        self._template_substitute_write(tmpl,
                                        template_vals, self._temp_dir_name + '/contrail-api.ini')
        local("sudo mv %s/contrail-api.ini /etc/contrail/supervisord_config_files/" %(self._temp_dir_name))

    def fixup_contrail_api_initd(self):
        # initd script wrapper for contrail-api
            sctl_lines = ''
            for worker_id in range(int(self._args.nworkers)):
                sctl_line = 'supervisorctl -s unix:///tmp/supervisord_config.sock ' + \
                            '${1} `basename ${0}:%s`' %(worker_id)
                sctl_lines = sctl_lines + sctl_line

            template_vals = {'__contrail_supervisorctl_lines__': sctl_lines,
                            }
            self._template_substitute_write(contrail_api_svc.template,
                                            template_vals, self._temp_dir_name + '/contrail-api')
            local("sudo mv %s/contrail-api /etc/init.d/" %(self._temp_dir_name))
            local("sudo chmod a+x /etc/init.d/contrail-api")

    def fixup_schema_transformer_config_file(self):
        # contrail-schema.conf
        template_vals = {'__contrail_ifmap_server_ip__': self.cfgm_ip,
                         '__contrail_ifmap_server_port__': '8444' if self._args.use_certs else '8443',
                         '__contrail_ifmap_username__': 'schema-transformer',
                         '__contrail_ifmap_password__': 'schema-transformer',
                         '__contrail_api_server_ip__': self._args.internal_vip or self.cfgm_ip,
                         '__contrail_api_server_port__': '8082',
                         '__contrail_zookeeper_server_ip__': self.zk_servers_ports,
                         '__contrail_use_certs__': self._args.use_certs,
                         '__contrail_keyfile_location__': '/etc/contrail/ssl/private_keys/schema_xfer_key.pem',
                         '__contrail_certfile_location__': '/etc/contrail/ssl/certs/schema_xfer.pem',
                         '__contrail_cacertfile_location__': '/etc/contrail/ssl/certs/ca.pem',
                         '__contrail_log_file__' : '/var/log/contrail/contrail-schema.log',
                         '__contrail_cassandra_server_list__' : ' '.join('%s:%s' % cassandra_server for cassandra_server in self.cassandra_server_list),
                         '__contrail_disc_server_ip__': self._args.internal_vip or self.cfgm_ip,
                         '__contrail_disc_server_port__': '5998',
                        }
        self._template_substitute_write(contrail_schema_transformer_conf.template,
                                        template_vals, self._temp_dir_name + '/contrail-schema.conf')
        local("sudo mv %s/contrail-schema.conf /etc/contrail/contrail-schema.conf" %(self._temp_dir_name))
        local("sudo chmod a+x /etc/init.d/contrail-schema")

    def fixup_svc_monitor_config_file(self):
        # contrail-svc-monitor.conf
        template_vals = {'__contrail_ifmap_server_ip__': self.cfgm_ip,
                         '__contrail_ifmap_server_port__': '8444' if self._args.use_certs else '8443',
                         '__contrail_ifmap_username__': 'svc-monitor',
                         '__contrail_ifmap_password__': 'svc-monitor',
                         '__contrail_api_server_ip__': self._args.internal_vip or self.cfgm_ip,
                         '__contrail_api_server_port__': '8082',
                         '__contrail_analytics_server_ip__': self._args.internal_vip or self._args.collector_ip,
                         '__contrail_zookeeper_server_ip__': self.zk_servers_ports,
                         '__contrail_use_certs__': self._args.use_certs,
                         '__contrail_keyfile_location__': '/etc/contrail/ssl/private_keys/svc_monitor_key.pem',
                         '__contrail_certfile_location__': '/etc/contrail/ssl/certs/svc_monitor.pem',
                         '__contrail_cacertfile_location__': '/etc/contrail/ssl/certs/ca.pem',
                         '__contrail_log_file__' : '/var/log/contrail/contrail-svc-monitor.log',
                         '__contrail_cassandra_server_list__' : ' '.join('%s:%s' % cassandra_server for cassandra_server in self.cassandra_server_list),
                         '__contrail_disc_server_ip__': self._args.internal_vip or self.cfgm_ip,
                         '__contrail_disc_server_port__': '5998',
                         '__contrail_region_name__': self._args.region_name,
                        }
        self._template_substitute_write(contrail_svc_monitor_conf.template,
                                        template_vals, self._temp_dir_name + '/contrail-svc-monitor.conf')
        local("sudo mv %s/contrail-svc-monitor.conf /etc/contrail/contrail-svc-monitor.conf" %(self._temp_dir_name))

    def fixup_discovery_config_file(self):
        # discovery.conf_
        template_vals = {
                         '__contrail_zk_server_ip__': self.zk_servers,
                         '__contrail_zk_server_port__': '2181',
                         '__contrail_listen_ip_addr__': '0.0.0.0',
                         '__contrail_listen_port__': '5998',
                         '__contrail_log_local__': 'True',
                         '__contrail_log_file__': '/var/log/contrail/discovery.log',
                         '__contrail_healthcheck_interval__': 5,
                         '__contrail_cassandra_server_list__' : ' '.join('%s:%s' % cassandra_server for cassandra_server in self.cassandra_server_list),
                        }
        self._template_substitute_write(contrail_discovery_conf.template,
                                        template_vals, self._temp_dir_name + '/contrail-discovery.conf')
        local("sudo mv %s/contrail-discovery.conf /etc/contrail/" %(self._temp_dir_name))

    def fixup_discovery_supervisor_ini(self):
        # supervisor contrail-discovery.ini
        template_vals = {'__contrail_disc_port_base__': '911', # 911x
                         '__contrail_disc_nworkers__': '1'
                        }
        if self.pdist == 'Ubuntu':
            tmpl = contrail_discovery_ini.template
        else:
            tmpl = contrail_discovery_ini_centos.template

        self._template_substitute_write(tmpl,
                                        template_vals, self._temp_dir_name + '/contrail-discovery.ini')
        local("sudo mv %s/contrail-discovery.ini /etc/contrail/supervisord_config_files/" %(self._temp_dir_name))

    def fixup_discovery_initd(self):
        # initd script wrapper for contrail-discovery
        sctl_lines = ''
        for worker_id in range(int(self._args.nworkers)):
            sctl_line = 'supervisorctl -s unix:///tmp/supervisord_config.sock ' + \
                        '${1} `basename ${0}:%s`' %(worker_id)
            sctl_lines = sctl_lines + sctl_line

        template_vals = {'__contrail_supervisorctl_lines__': sctl_lines,
                        }
        self._template_substitute_write(contrail_discovery_svc.template,
                                        template_vals, self._temp_dir_name + '/contrail-discovery')
        local("sudo mv %s/contrail-discovery /etc/init.d/" %(self._temp_dir_name))
        local("sudo chmod a+x /etc/init.d/contrail-discovery")

    def fixup_vnc_api_lib_ini(self):
        # vnc_api_lib.ini
        template_vals = {
                         '__contrail_keystone_ip__': '127.0.0.1',
                        }
        self._template_substitute_write(vnc_api_lib_ini.template,
                                        template_vals, self._temp_dir_name + '/vnc_api_lib.ini')
        local("sudo mv %s/vnc_api_lib.ini /etc/contrail/" %(self._temp_dir_name))
        # Remove the auth setion from /etc/contrail/vnc_api_lib.ini, will be added by
        # Orchestrator specific setup if required.
        local("sudo openstack-config --del /etc/contrail/vnc_api_lib.ini auth")

    def run_services(self):
        if self._args.internal_vip:
            # Assumption cfgm and openstack in same node.
            # TO DO: When we introduce contrail_vip for cfgm nodes, this needs to be revisited.
            quantum_ip = self._args.internal_vip
        else:
            quantum_ip = self.cfgm_ip
        local("sudo config-server-setup.sh")
        # Wait for supervisor to start contrail-api and rabbitmq
        for i in range(10):
            services_status = {'contrail-api' : 'down', 'rabbitmq-server' : 'down'}
            for service in services_status.keys():
                status = local("sudo service %s status" % service, capture=True)
                if 'running' in status.lower():
                    print "[%s] started by supervisor config." % service
                    services_status[service] = 'running'
            if 'down' in services_status.values():
                print "[contrail-api and rabbitmq] not yet started by supervisor config, Retrying."
                sleep(2)
            else:
                print "[contrail-api and rabbitmq] started by supervisor config, continue to provision."
                break

    def setup(self):
        self.disable_selinux()
        self.disable_iptables()
        self.setup_coredump()
        self.fixup_config_files()
        self.run_services()
