#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import ConfigParser
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


class ConfigSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(ConfigSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.global_defaults = {
            'self_ip': '127.0.0.1',
            'collector_ip': '127.0.0.1',
            'keystone_ip': '127.0.0.1',
            'keystone_admin_user': 'admin',
            'keystone_admin_passwd': 'contrail123',
            'keystone_admin_tenant_name': 'admin',
            'service_token': '',
            'use_certs': False,
            'multi_tenancy': True,
            'nworkers': '1',
            'haproxy': False,
            'region_name': None,
            'keystone_auth_protocol': 'http',
            'keystone_auth_port': '35357',
            'amqp_server_ip': '127.0.0.1',
            'quantum_port': '9696',
            'quantum_service_protocol': 'http',
            'manage_neutron': 'yes',
        }
        self.parse_args(args_str)

        self.cfgm_ip = self._args.self_ip
        self.cassandra_server_list = [(cassandra_server_ip, '9160') for cassandra_server_ip in self._args.cassandra_ip_list]
        self.zk_servers = ','.join(self._args.zookeeper_ip_list)
        self.zk_servers_ports = ','.join(['%s:2181' %(s) for s in self._args.zookeeper_ip_list])

    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-cfgm --self_ip 10.1.5.11 --keystone_ip 10.1.5.12 
            --collector_ip 10.1.5.12 --service_token contrail123
            --cassandra_ip_list 10.1.5.11 10.1.5.12 
            --zookeeper_ip_list 10.1.5.11 10.1.5.12
            --nworkers 1
            optional: --use_certs, --multi_tenancy --haproxy
                      --region_name <name> --internal_vip 10.1.5.100
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--self_ip", help = "IP Address of this system")
        parser.add_argument("--collector_ip", help = "IP Address of collector node")
        parser.add_argument("--keystone_ip", help = "IP Address of keystone node")
        parser.add_argument("--keystone_admin_user", help = "Keystone admin tenant user.")
        parser.add_argument("--keystone_admin_passwd", help = "Keystone admin user's password.")
        parser.add_argument("--keystone_admin_tenant_name", help = "Keystone admin tenant name.")
        parser.add_argument("--service_token", help = "The service password to access keystone")
        parser.add_argument("--use_certs", help = "Use certificates for authentication (irond)",
            action="store_true")
        parser.add_argument("--multi_tenancy", help = "(Deprecated, defaults to True) Enforce resource permissions (implies token validation)",
            action="store_true")
        parser.add_argument("--cassandra_ip_list", help = "List of IP Addresses of cassandra nodes",
                            nargs='+', type=str)
        parser.add_argument("--zookeeper_ip_list", help = "List of IP Addresses of zookeeper servers",
                            nargs='+', type=str)
        parser.add_argument("--quantum_port", help = "Quantum Server port")
        parser.add_argument("--quantum_service_protocol", help = "Protocol of quantum/neutron for nova to use ")
        parser.add_argument("--keystone_auth_protocol", 
            help = "Auth protocol used to talk to keystone")
        parser.add_argument("--keystone_auth_port", help = "Port of Keystone to talk to",
            default = '35357')
        parser.add_argument("--keystone_admin_token", 
            help = "admin_token value in keystone.conf")
        parser.add_argument("--keystone_insecure", 
            help = "Connect to keystone in secure or insecure mode if in https mode",
            default = 'False')

        parser.add_argument("--nworkers",
            help = "Number of worker processes for api and discovery services",
            default = '1')
        parser.add_argument("--haproxy", help = "Enable haproxy", action="store_true")
        parser.add_argument("--region_name", help = "The Region name for the openstack")
        parser.add_argument("--amqp_server_ip",
            help = "IP of the AMQP server to be used for neutron and api server")
        parser.add_argument("--manage_neutron", help = "Provision neutron user/role in Keystone.")
        parser.add_argument("--internal_vip", help = "VIP Address of openstack  nodes")
        parser.add_argument("--external_vip", help = "External VIP Address of HA Openstack Nodes")
        parser.add_argument("--contrail_internal_vip", help = "Internal VIP Address of HA config Nodes")
  
        self._args = parser.parse_args(self.remaining_argv)

    def fixup_config_files(self):
        self.fixup_ifmap_config_files()
        self.fixup_contrail_api_config_file()
        self.fixup_contrail_api_supervisor_ini()
        self.fixup_contrail_api_initd()
        self.fixup_contrail_plugin_ini()
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
                         '__contrail_keystone_ip__': self._args.keystone_ip,
                         '__rabbit_server_ip__': self._args.internal_vip or self.rabbit_host,
                         '__rabbit_server_port__': self.rabbit_port,
                         '__contrail_admin_user__': self._args.keystone_admin_user,
                         '__contrail_admin_password__': self._args.keystone_admin_passwd,
                         '__contrail_admin_tenant_name__': self._args.keystone_admin_tenant_name,
                         '__contrail_admin_token__': self._args.keystone_admin_token,
                         '__contrail_ks_auth_protocol__': self._args.keystone_auth_protocol,
                         '__contrail_ks_auth_port__': self._args.keystone_auth_port,
                         '__keystone_insecure_flag__': self._args.keystone_insecure,
                         '__contrail_memcached_opt__': 'memcache_servers=127.0.0.1:11211' if self._args.multi_tenancy else '',
                         '__contrail_log_file__': '/var/log/contrail/contrail-api.log',
                         '__contrail_cassandra_server_list__' : ' '.join('%s:%s' % cassandra_server for cassandra_server in self.cassandra_server_list),
                         '__contrail_disc_server_ip__': self._args.internal_vip or self.cfgm_ip,
                         '__contrail_disc_server_port__': '5998',
                         '__contrail_zookeeper_server_ip__': self.zk_servers_ports,
                        }
        self._template_substitute_write(contrail_api_conf.template,
                                        template_vals, self._temp_dir_name + '/contrail-api.conf')
        local("sudo mv %s/contrail-api.conf /etc/contrail/" %(self._temp_dir_name))

    def fixup_contrail_api_supervisor_ini(self):
        # supervisor contrail-api.ini
        template_vals = {'__contrail_api_port_base__': '910', # 910x
                         '__contrail_api_nworkers__': self._args.nworkers,
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

    def fixup_contrail_plugin_ini(self):
        # quantum/neutron plugin
        template_vals = {'__contrail_api_server_ip__': self._args.internal_vip or self._args.self_ip,
                         '__contrail_api_server_port__': '8082',
                         '__contrail_multi_tenancy__': self._args.multi_tenancy,
                         '__contrail_keystone_ip__': self._args.keystone_ip,
                         '__contrail_admin_token__': self._args.keystone_admin_token,
                         '__contrail_ks_auth_protocol__': self._args.keystone_auth_protocol,
                         '__contrail_ks_auth_port__': self._args.keystone_auth_port,
                         '__contrail_admin_user__': self._args.keystone_admin_user,
                         '__contrail_admin_password__': self._args.keystone_admin_passwd,
                         '__contrail_admin_tenant_name__': self._args.keystone_admin_tenant_name,
                    }
        self._template_substitute_write(contrail_plugin_ini.template,
                                        template_vals, self._temp_dir_name + '/contrail_plugin.ini')
        if os.path.exists("/etc/neutron"):
            local("sudo mkdir -p /etc/neutron/plugins/opencontrail")
            local("sudo mv %s/contrail_plugin.ini /etc/neutron/plugins/opencontrail/ContrailPlugin.ini" %(self._temp_dir_name))
        else:
            local("sudo mv %s/contrail_plugin.ini /etc/quantum/plugins/contrail/contrail_plugin.ini" %(self._temp_dir_name))

        if self.pdist == 'Ubuntu':
            neutron_def_file = "/etc/default/neutron-server"
            if os.path.exists(neutron_def_file):
                local("sudo sed -i 's/NEUTRON_PLUGIN_CONFIG=.*/NEUTRON_PLUGIN_CONFIG=\"\/etc\/neutron\/plugins\/opencontrail\/ContrailPlugin.ini\"/g' %s" %(neutron_def_file))

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
                         '__contrail_admin_user__': self._args.keystone_admin_user,
                         '__contrail_admin_password__': self._args.keystone_admin_passwd,
                         '__contrail_admin_tenant_name__': self._args.keystone_admin_tenant_name,
                         '__contrail_admin_token__': self._args.keystone_admin_token,
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
                         '__contrail_keystone_ip__': self._args.keystone_ip,
                         '__contrail_ks_auth_protocol__': self._args.keystone_auth_protocol,
                         '__contrail_ks_auth_port__': self._args.keystone_auth_port,
                         '__keystone_insecure_flag__': self._args.keystone_insecure,
                         '__contrail_zookeeper_server_ip__': self.zk_servers_ports,
                         '__contrail_use_certs__': self._args.use_certs,
                         '__contrail_keyfile_location__': '/etc/contrail/ssl/private_keys/svc_monitor_key.pem',
                         '__contrail_certfile_location__': '/etc/contrail/ssl/certs/svc_monitor.pem',
                         '__contrail_cacertfile_location__': '/etc/contrail/ssl/certs/ca.pem',
                         '__contrail_admin_user__': self._args.keystone_admin_user,
                         '__contrail_admin_password__': self._args.keystone_admin_passwd,
                         '__contrail_admin_tenant_name__': self._args.keystone_admin_tenant_name,
                         '__contrail_admin_token__': self._args.keystone_admin_token,
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
                         '__contrail_keystone_ip__': self._args.keystone_ip,
                        }
        self._template_substitute_write(vnc_api_lib_ini.template,
                                        template_vals, self._temp_dir_name + '/vnc_api_lib.ini')
        local("sudo mv %s/vnc_api_lib.ini /etc/contrail/" %(self._temp_dir_name))

    def build_ctrl_details(self):
        ctrl_infos = []
        ctrl_details = "%s/ctrl-details" % self._temp_dir_name
        ctrl_infos.append('SERVICE_TOKEN=%s' % self._args.service_token)
        ctrl_infos.append('AUTH_PROTOCOL=%s' % self._args.keystone_auth_protocol)
        ctrl_infos.append('QUANTUM_PROTOCOL=%s' % self._args.quantum_service_protocol)
        ctrl_infos.append('ADMIN_TOKEN=%s' % self._args.keystone_admin_passwd)
        ctrl_infos.append('CONTROLLER=%s' % self._args.keystone_ip)
        ctrl_infos.append('AMQP_SERVER=%s' % self._args.amqp_server_ip)
        if self._args.haproxy:
            ctrl_infos.append('QUANTUM=127.0.0.1')
        else:
            ctrl_infos.append('QUANTUM=%s' % self.cfgm_ip)
        ctrl_infos.append('QUANTUM_PORT=%s' % self._args.quantum_port)

        self.update_vips_in_ctrl_details(ctrl_infos)

        for ctrl_info in ctrl_infos:
            local ("sudo echo %s >> %s" % (ctrl_info, ctrl_details))
        local("sudo cp %s /etc/contrail/ctrl-details" % ctrl_details)
        local("sudo rm %s/ctrl-details" %(self._temp_dir_name))

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
                print "[contrail-api and rabbitmq] started by supervisor config, continue to provision neutron/quantum."
                break
        local("sudo quantum-server-setup.sh")
        quant_args = "--ks_server_ip %s --quant_server_ip %s --tenant %s --user %s --password %s --svc_password %s --root_password %s" \
                      %(self._args.keystone_ip, quantum_ip, self._args.keystone_admin_tenant_name, self._args.keystone_admin_user, self._args.keystone_admin_passwd, self._args.service_token,
                        env.password)
        if self._args.region_name:
            quant_args += " --region_name %s" %(self._args.region_name)
        if self._args.manage_neutron:
            local("setup-quantum-in-keystone %s" %(quant_args))

    def setup(self):
        self.disable_selinux()
        self.disable_iptables()
        self.setup_coredump()
        self.fixup_config_files()
        self.build_ctrl_details()
        self.run_services()

def main(args_str = None):
    config = ConfigSetup(args_str)
    config.setup()

if __name__ == "__main__":
    main() 
