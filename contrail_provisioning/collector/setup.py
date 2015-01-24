import os
import sys
import argparse
import ConfigParser

from fabric.api import local, settings

from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.collector.templates import contrail_query_engine_conf
from contrail_provisioning.collector.templates import contrail_collector_conf
from contrail_provisioning.collector.templates import contrail_analytics_api_conf


class CollectorSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(CollectorSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.global_defaults = {
            'cfgm_ip': '127.0.0.1',
            'self_collector_ip': '127.0.0.1',
            'analytics_syslog_port': -1,
        }

        self.parse_args(args_str)
        self.cassandra_server_list = [(cassandra_server_ip, '9160') for cassandra_server_ip in self._args.cassandra_ip_list]

    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-collector --cassandra_ip_list 10.1.1.1 10.1.1.2 
            --cfgm_ip 10.1.5.11 --self_collector_ip 10.1.5.11 
            --analytics_data_ttl 1 --analytics_syslog_port 3514
        '''

        parser = self._parse_args(args_str)
        parser.add_argument("--cassandra_ip_list", help = "List of IP Addresses of cassandra nodes",
                            nargs='+', type=str)
        parser.add_argument("--cfgm_ip", help = "IP Address of the config node")
        parser.add_argument("--self_collector_ip", help = "IP Address of the collector node")
        parser.add_argument("--num_nodes", help = "Number of collector nodes", type = int)
        parser.add_argument("--analytics_data_ttl", help = "TTL in hours of data stored in cassandra database", type = int)
        parser.add_argument("--analytics_configaudit_ttl", help = "TTL in hours of config audit data stored in cassandra database", type = int, default = -1)
        parser.add_argument("--analytics_statsdata_ttl", help = "TTL in hours of stats data stored in cassandra database", type = int, default = -1)
        parser.add_argument("--analytics_flowdata_ttl", help = "TTL in hours of flow data stored in cassandra database", type = int, default = -1)
        parser.add_argument("--analytics_syslog_port", help = "Listen port for analytics syslog server", type = int)
        parser.add_argument("--internal_vip", help = "Internal VIP Address of openstack nodes")
        self._args = parser.parse_args(self.remaining_argv)

    def fixup_config_files(self):
        self.fixup_contrail_collector()
        self.fixup_contrail_query_engine()
        self.fixup_contrail_analytics_api()
        self.fixup_contrail_snmp_collector()

    def fixup_contrail_snmp_collector(self):
        with settings(warn_only=True):
            local("echo 'mibs +ALL' > /etc/snmp/snmp.conf")

    def fixup_contrail_collector(self):
        template_vals = {'__contrail_log_file__' : '/var/log/contrail/contrail-collector.log',
                         '__contrail_discovery_ip__' : self._args.cfgm_ip,
                         '__contrail_host_ip__' : self._args.self_collector_ip,
                         '__contrail_listen_port__' : '8086',
                         '__contrail_http_server_port__' : '8089',
                         '__contrail_cassandra_server_list__' : ' '.join('%s:%s' % cassandra_server for cassandra_server in self.cassandra_server_list),
                         '__contrail_analytics_data_ttl__' : self._args.analytics_data_ttl,
                         '__contrail_configaudit_ttl__' : self._args.analytics_configaudit_ttl,
                         '__contrail_statsdata_ttl__' : self._args.analytics_statsdata_ttl,
                         '__contrail_flowdata_ttl__' : self._args.analytics_flowdata_ttl,
                         '__contrail_analytics_syslog_port__' : str(self._args.analytics_syslog_port)}
        self._template_substitute_write(contrail_collector_conf.template,
                                   template_vals, self._temp_dir_name + '/contrail-collector.conf')
        local("sudo mv %s/contrail-collector.conf /etc/contrail/contrail-collector.conf" %(self._temp_dir_name))

    def fixup_contrail_query_engine(self):
        template_vals = {'__contrail_log_file__' : '/var/log/contrail/contrail-query-engine.log',
                         '__contrail_redis_server__': '127.0.0.1',
                         '__contrail_redis_server_port__' : '6379',
                         '__contrail_http_server_port__' : '8091',
                         '__contrail_collector__' : '127.0.0.1',
                         '__contrail_collector_port__' : '8086',
                         '__contrail_cassandra_server_list__' : ' '.join('%s:%s' % cassandra_server for cassandra_server in self.cassandra_server_list)}
        self._template_substitute_write(contrail_query_engine_conf.template,
                                        template_vals, self._temp_dir_name + '/contrail-query-engine.conf')
        local("sudo mv %s/contrail-query-engine.conf /etc/contrail/contrail-query-engine.conf" %(self._temp_dir_name))

    def fixup_contrail_analytics_api(self):
        rest_api_port = '8081'
        if self._args.internal_vip:
            rest_api_port = '9081'
        template_vals = {'__contrail_log_file__' : '/var/log/contrail/contrail-analytics-api.log',
                         '__contrail_log_local__': '1',
                         '__contrail_log_category__': '',
                         '__contrail_log_level__': 'SYS_NOTICE',
                         '__contrail_redis_server_port__' : '6379',
                         '__contrail_redis_query_port__' : '6379',
                         '__contrail_http_server_port__' : '8090',
                         '__contrail_rest_api_port__' : rest_api_port,
                         '__contrail_host_ip__' : self._args.self_collector_ip,
                         '__contrail_discovery_ip__' : self._args.cfgm_ip,
                         '__contrail_discovery_port__' : 5998,
                         '__contrail_collector__': self._args.self_collector_ip,
                         '__contrail_collector_port__': '8086',
                         '__contrail_cassandra_server_list__' : ' '.join('%s:%s' % cassandra_server for cassandra_server in self.cassandra_server_list)}
        self._template_substitute_write(contrail_analytics_api_conf.template,
                                        template_vals, self._temp_dir_name + '/contrail-analytics-api.conf')
        local("sudo mv %s/contrail-analytics-api.conf /etc/contrail/contrail-analytics-api.conf" %(self._temp_dir_name))

    def run_services(self):
        if self._args.num_nodes:
            local("sudo collector-server-setup.sh multinode")
        else:
            local("sudo collector-server-setup.sh")
#end class SetupVncCollector

def main(args_str = None):
    collector = CollectorSetup(args_str)
    collector.setup()

if __name__ == "__main__":
    main()
