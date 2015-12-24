import os
import sys
import argparse
import ConfigParser

from fabric.api import local, settings

from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.collector.templates import contrail_query_engine_conf
from contrail_provisioning.collector.templates import contrail_collector_conf
from contrail_provisioning.collector.templates import contrail_analytics_api_conf
from contrail_provisioning.collector.templates import contrail_analytics_nodemgr_template
from contrail_provisioning.collector.templates import redis_server_conf_template
from contrail_provisioning.common.templates import contrail_database_template
from contrail_provisioning.collector.templates import contrail_collector_ini
from contrail_provisioning.collector.templates import contrail_query_engine_ini
from contrail_provisioning.collector.templates import contrail_analytics_api_ini

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
            'keystone_ip': '127.0.0.1',
            'keystone_admin_user': 'admin',
            'keystone_admin_passwd': 'contrail123',
            'keystone_admin_tenant_name': 'admin',
            'keystone_service_tenant_name' : 'service',
            'keystone_auth_protocol': 'http',
            'keystone_auth_port': '35357',
            'multi_tenancy': True,
        }

        self.parse_args(args_str)
        self.cassandra_server_list = [(cassandra_server_ip, '9160') for cassandra_server_ip in self._args.cassandra_ip_list]

    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-collector --cassandra_ip_list 10.1.1.1 10.1.1.2
            --cfgm_ip 10.1.5.11 --self_collector_ip 10.1.5.11
            --analytics_data_ttl 1 --analytics_syslog_port 3514
            --keystone_ip 10.1.5.11
        '''

        parser = self._parse_args(args_str)
        parser.add_argument("--cassandra_ip_list", help = "List of IP Addresses of cassandra nodes",
                            nargs='+', type=str)
        parser.add_argument("--cfgm_ip", help = "IP Address of the config node")
        parser.add_argument("--self_collector_ip", help = "IP Address of the collector node")
        parser.add_argument("--num_nodes", help = "Number of collector nodes", type = int)
        parser.add_argument("--analytics_data_ttl", help = "TTL in hours of data stored in cassandra database", type = int)
        parser.add_argument("--analytics_config_audit_ttl", help = "TTL in hours of config audit data stored in cassandra database", type = int)
        parser.add_argument("--analytics_statistics_ttl", help = "TTL in hours of stats data stored in cassandra database", type = int)
        parser.add_argument("--analytics_flow_ttl", help = "TTL in hours of flow data stored in cassandra database", type = int)
        parser.add_argument("--analytics_syslog_port", help = "Listen port for analytics syslog server", type = int)
        parser.add_argument("--internal_vip", help = "Internal VIP Address of openstack nodes")
        parser.add_argument("--redis_password", help = "Redis password")
        # TODO : remove this option : kafka will now stay enabled
        parser.add_argument("--kafka_enabled", help = "kafka enabled flag")
        parser.add_argument("--keystone_ip", help = "IP Address of keystone node")
        parser.add_argument("--keystone_admin_user", help = "Keystone admin tenant user.")
        parser.add_argument("--keystone_admin_passwd", help = "Keystone admin user's password.")
        parser.add_argument("--keystone_admin_tenant_name", help = "Keystone admin tenant name.")
        parser.add_argument("--keystone_auth_protocol",
            help = "Auth protocol used to talk to keystone")
        parser.add_argument("--keystone_auth_port",
                help="Port of Keystone to talk to",
            default = '35357')
        parser.add_argument("--keystone_insecure",
            help = "Connect to keystone in secure or insecure mode if in" + \
                    "https mode",
            default = 'False')
        parser.add_argument("--multi_tenancy", help = "(Deprecated, defaults to True) Enforce resource permissions (implies token validation)",
            action="store_true")
        parser.add_argument("--cassandra_user", help="Cassandra user name",
            default= None)
        parser.add_argument("--cassandra_password", help="Cassandra password",
            default= None)
        self._args = parser.parse_args(self.remaining_argv)

    def fixup_config_files(self):
        self.fixup_contrail_collector()
        self.fixup_contrail_query_engine()
        self.fixup_contrail_analytics_api()
        self.fixup_contrail_snmp_collector()
        self.fixup_contrail_topology()
        self.fixup_contrail_analytics_nodemgr()
        if not os.path.exists('/etc/contrail/contrail-keystone-auth.conf'):
            self.fixup_keystone_auth_config_file()
        self.fixup_contrail_alarm_gen()
        if self._args.cassandra_user is not None:
            self.fixup_cassandra_config()
            self.fixup_ini_files()

    def fixup_ini_files(self):
        collector_conf_files = ['/etc/contrail/contrail-collector.conf','/etc/contrail/contrail-database.conf']
        query_engine_conf_files = ['/etc/contrail/contrail-query-engine.conf','/etc/contrail/contrail-database.conf']
        analytics_api_conf_files = ['/etc/contrail/contrail-analytics-api.conf','/etc/contrail/contrail-database.conf']
        collector_template_vals = {'__contrail_collector_conf__': ' --conf_file '.join(collector_conf_files)}
        query_engine_template_vals = {'__contrail_query_engine_conf__': ' --conf_file '.join(query_engine_conf_files)}
        analytics_api_template_vals = {'__contrail_analytics_api_conf__': ' --conf_file '.join(analytics_api_conf_files)}
        self._template_substitute_write(contrail_collector_ini.template,
                                        collector_template_vals, self._temp_dir_name + '/contrail-collector.ini')
        local("sudo mv %s/contrail-collector.ini /etc/contrail/supervisord_analytics_files/contrail-collector.ini" %(self._temp_dir_name))
        self._template_substitute_write(contrail_query_engine_ini.template,
                                        query_engine_template_vals, self._temp_dir_name + '/contrail-query-engine.ini')
        local("sudo mv %s/contrail-query-engine.ini /etc/contrail/supervisord_analytics_files/contrail-query-engine.ini" %(self._temp_dir_name))
        self._template_substitute_write(contrail_analytics_api_ini.template,
                                        analytics_api_template_vals, self._temp_dir_name + '/contrail-analytics-api.ini')
        local("sudo mv %s/contrail-analytics-api.ini /etc/contrail/supervisord_analytics_files/contrail-analytics-api.ini" %(self._temp_dir_name))


    def fixup_cassandra_config(self):
        if self._args.cassandra_user:
            if os.path.isfile('/etc/contrail/contrail-database.conf') is not True:
                 # Create conf file
                 template_vals = {'__cassandra_user__': self._args.cassandra_user,
                                  '__cassandra_password__': self._args.cassandra_password
                                 }
                 self._template_substitute_write(contrail_database_template.template,
                                        template_vals, self._temp_dir_name + '/contrail-collector-database.conf')
                 local("sudo mv %s/contrail-collector-database.conf /etc/contrail/contrail-database.conf" %(self._temp_dir_name))
 

    def fixup_contrail_alarm_gen(self):
        ALARM_GEN_CONF_FILE = '/etc/contrail/contrail-alarm-gen.conf'
        cnd = os.path.exists(ALARM_GEN_CONF_FILE)
        if not cnd:
            raise RuntimeError('%s does not exist' % ALARM_GEN_CONF_FILE)
        self.replace_in_file(ALARM_GEN_CONF_FILE, '#host_ip',
                             'host_ip = ' + self._args.self_collector_ip)
        kafka_broker_list = [server[0] + ":9092" for server in self.cassandra_server_list]
        kafka_broker_list_str = ' '.join(map(str, kafka_broker_list))
        self.replace_in_file(ALARM_GEN_CONF_FILE, '#kafka_broker_list', 'kafka_broker_list = ' + kafka_broker_list_str)
        #prepare zklist
        zk_list = [server[0] + ":2181" for server in self.cassandra_server_list]
        zk_list_str = ' '.join(map(str, zk_list))
        self.replace_in_file(ALARM_GEN_CONF_FILE, '#zk_list', 'zk_list = ' + zk_list_str)
        #prepare alarm gen conf file
        self.replace_in_file(ALARM_GEN_CONF_FILE, '#disc_server_ip', 'disc_server_ip = ' + self._args.cfgm_ip)
        self.replace_in_file(ALARM_GEN_CONF_FILE, '#disc_server_port', 'disc_server_port = 5998')

    def fixup_contrail_snmp_collector(self):
        conf_fl = '/etc/contrail/contrail-snmp-collector.conf'
        with settings(warn_only=True):
            local("mkdir -p /etc/snmp")
            local("echo 'mibs +ALL' > /etc/snmp/snmp.conf")
            local("[ -f %s ] || > %s" % (conf_fl, conf_fl))
        self.set_config(conf_fl, 'DEFAULTS', 'zookeeper',
                        self.cassandra_server_list[0][0] + ':2181')
        self.set_config(conf_fl, 'DISCOVERY', 'disc_server_ip',
                        self._args.cfgm_ip)
        self.set_config(conf_fl, 'DISCOVERY', 'disc_server_port', '5998')
        self.set_config('/etc/contrail/supervisord_analytics_files/' +\
                        'contrail-snmp-collector.ini',
                        'program:contrail-snmp-collector',
                        'command',
                        '/usr/bin/contrail-snmp-collector --conf_file ' + \
                        conf_fl + ' --conf_file ' + \
                        '/etc/contrail/contrail-keystone-auth.conf')

    def fixup_contrail_analytics_nodemgr(self):
        template_vals = {'__contrail_discovery_ip__' : self._args.cfgm_ip,
                         '__contrail_discovery_port__': '5998'
                       }
        self._template_substitute_write(contrail_analytics_nodemgr_template.template,
                                        template_vals, self._temp_dir_name + '/contrail-analytics-nodemgr.conf')
        local("sudo mv %s/contrail-analytics-nodemgr.conf /etc/contrail/contrail-analytics-nodemgr.conf" %(self._temp_dir_name))

    def fixup_contrail_topology(self):
        conf_fl = '/etc/contrail/contrail-topology.conf'
        with settings(warn_only=True):
            local("[ -f %s ] || > %s" % (conf_fl, conf_fl))
        self.set_config(conf_fl, 'DEFAULTS', 'zookeeper',
                        self.cassandra_server_list[0][0] + ':2181')
        self.set_config(conf_fl, 'DISCOVERY', 'disc_server_ip',
                        self._args.cfgm_ip)
        self.set_config(conf_fl, 'DISCOVERY', 'disc_server_port', '5998')
        self.set_config('/etc/contrail/supervisord_analytics_files/' +\
                        'contrail-topology.ini',
                        'program:contrail-topology',
                        'command',
                        '/usr/bin/contrail-topology --conf_file ' + \
                        conf_fl)

    def fixup_contrail_collector(self):
        template_vals = {'__contrail_log_file__' : '/var/log/contrail/contrail-collector.log',
                         '__contrail_discovery_ip__' : self._args.cfgm_ip,
                         '__contrail_host_ip__' : self._args.self_collector_ip,
                         '__contrail_listen_port__' : '8086',
                         '__contrail_http_server_port__' : '8089',
                         '__contrail_cassandra_server_list__' : ' '.join('%s:%s' % cassandra_server for cassandra_server in self.cassandra_server_list),
                         '__contrail_analytics_data_ttl__' : '#analytics_data_ttl=48',
                         '__contrail_config_audit_ttl__' : '#analytics_config_audit_ttl=2160',
                         '__contrail_statistics_ttl__' : '#analytics_statistics_ttl=24',
                         '__contrail_flow_ttl__' : '#analytics_flow_ttl=2',
                         '__contrail_analytics_syslog_port__' : str(self._args.analytics_syslog_port),
                         '__contrail_redis_password__' : '',
                         '__contrail_kafka_broker_list__':''
                       }
        if self._args.analytics_data_ttl:
            template_vals['__contrail_analytics_data_ttl__'] = 'analytics_data_ttl=%d' % self._args.analytics_data_ttl
        if self._args.analytics_config_audit_ttl:
            template_vals['__contrail_config_audit_ttl__'] = 'analytics_config_audit_ttl=%d' % self._args.analytics_config_audit_ttl
        if self._args.analytics_statistics_ttl:
            template_vals['__contrail_statistics_ttl__'] = 'analytics_statistics_ttl=%d' % self._args.analytics_statistics_ttl
        if self._args.analytics_flow_ttl:
            template_vals['__contrail_flow_ttl__'] = 'analytics_flow_ttl=%d' % self._args.analytics_flow_ttl
        if self._args.redis_password:
            template_vals['__contrail_redis_password__'] = 'password = '+ self._args.redis_password
        kafka_broker_list = [server[0] + ":9092" for server in self.cassandra_server_list]
        kafka_broker_list_str = ' '.join(map(str, kafka_broker_list))
        template_vals['__contrail_kafka_broker_list__'] = kafka_broker_list_str
        self._template_substitute_write(contrail_collector_conf.template,
                                   template_vals, self._temp_dir_name + '/contrail-collector.conf')
        local("sudo mv %s/contrail-collector.conf /etc/contrail/contrail-collector.conf" %(self._temp_dir_name))

    def fixup_contrail_query_engine(self):
        template_vals = {'__contrail_log_file__' : '/var/log/contrail/contrail-query-engine.log',
                         '__contrail_redis_server__': '127.0.0.1',
                         '__contrail_redis_server_port__' : '6379',
                         '__contrail_http_server_port__' : '8091',
                         '__contrail_cassandra_server_list__' : ' '.join('%s:%s' % cassandra_server for cassandra_server in self.cassandra_server_list),
                         '__contrail_discovery_ip__' : self._args.cfgm_ip,
                         '__contrail_redis_password__' : ''}
        if self._args.redis_password:
            template_vals['__contrail_redis_password__'] = 'password = '+ self._args.redis_password
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
                         '__contrail_cassandra_server_list__' : ' '.join('%s:%s' % cassandra_server for cassandra_server in self.cassandra_server_list),
                         '__contrail_analytics_data_ttl__' : self._args.analytics_data_ttl,
                         '__contrail_config_audit_ttl__' : self._args.analytics_config_audit_ttl,
                         '__contrail_statistics_ttl__' : self._args.analytics_statistics_ttl,
                         '__contrail_flow_ttl__' : self._args.analytics_flow_ttl,
                         '__contrail_redis_password__' : ''}
        if self._args.redis_password:
            template_vals['__contrail_redis_password__'] = 'redis_password = '+ self._args.redis_password
        self._template_substitute_write(contrail_analytics_api_conf.template,
                                        template_vals, self._temp_dir_name + '/contrail-analytics-api.conf')
        local("sudo mv %s/contrail-analytics-api.conf /etc/contrail/contrail-analytics-api.conf" %(self._temp_dir_name))

    def load_redis_upstart_file(self):
        #copy the redis-server conf to init
        template_vals = {
                        }
        self._template_substitute_write(redis_server_conf_template.template,
                                        template_vals, self._temp_dir_name + '/redis-server.conf')
        local("sudo mv %s/redis-server.conf /etc/init/" %(self._temp_dir_name))
 
        local("sudo update-rc.d redis-server disable")

    def restart_collector(self):
        local("sudo service supervisor-analytics restart")

    def run_services(self):
        #disable redis from init.d since upstart has been added
        if self.pdist == 'Ubuntu':
            self.load_redis_upstart_file()

        if self._args.num_nodes:
            local("sudo collector-server-setup.sh multinode")
        else:
            local("sudo collector-server-setup.sh")
#end class SetupVncCollector

def main(args_str = None):
    collector = CollectorSetup(args_str)
    collector.setup()

def fix_collector_config(args_str = None):
    collector = CollectorSetup(args_str)
    collector.fixup_config_files()
    collector.restart_collector()

if __name__ == "__main__":
    main()
