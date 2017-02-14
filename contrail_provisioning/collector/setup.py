import os
import sys
import argparse
import ConfigParser

from fabric.api import local, settings

from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.collector.templates import contrail_query_engine_conf
from contrail_provisioning.collector.templates import contrail_collector_conf
from contrail_provisioning.collector.templates import contrail_analytics_nodemgr_template
from contrail_provisioning.collector.templates import redis_server_conf_template
from contrail_provisioning.common.templates import contrail_database_template

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
            'keystone_insecure': False,
            'keystone_certfile': None,
            'keystone_keyfile': None,
            'keystone_cafile': None,
            'keystone_auth_port': '35357',
            'keystone_version': 'v2.0',
            'apiserver_insecure': False,
            'apiserver_certfile': None,
            'apiserver_keyfile': None,
            'apiserver_cafile': None,
            'orchestrator' : 'openstack',
            'aaa_mode': 'cloud-admin',
            'collector_ip_list':['127.0.0.1']
        }

        self.parse_args(args_str)
        if self.is_cql_supported():
            cassandra_port = '9042'
        else:
            cassandra_port = '9160'
        self.cassandra_server_list = [(cassandra_server_ip, cassandra_port) for cassandra_server_ip in self._args.cassandra_ip_list]
        self.redis_server_list = ["%s:6379" % collector_ip for collector_ip in self._args.collector_ip_list]
        zookeeper_port = '2181'
        self.zookeeper_server_list = []
        if self._args.zookeeper_ip_list:
            self.zookeeper_server_list = [(zookeeper_server_ip, zookeeper_port) for \
                zookeeper_server_ip in self._args.zookeeper_ip_list]

        self.api_ssl_enabled = False
        if (self._args.apiserver_keyfile and
                self._args.apiserver_certfile and self._args.apiserver_cafile):
            self.api_ssl_enabled = True
        self.keystone_ssl_enabled = False
        if (self._args.keystone_keyfile and
                self._args.keystone_certfile and self._args.keystone_cafile):
            self.keystone_ssl_enabled = True


    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-collector --cassandra_ip_list 10.1.1.1 10.1.1.2
            --zookeeper_ip_list 10.1.1.1 10.1.1.2
            --cfgm_ip 10.1.5.11 --self_collector_ip 10.1.5.11
            --analytics_data_ttl 1 --analytics_syslog_port 3514
            --keystone_ip 10.1.5.11 --collector_ip_list 10.1.5.11 10.1.5.12
        '''

        parser = self._parse_args(args_str)
        parser.add_argument("--cassandra_ip_list", help = "List of IP Addresses of cassandra nodes",
                            nargs='+', type=str)
        parser.add_argument("--zookeeper_ip_list", help = "List of IP Addresses of zookeeper nodes",
                            nargs='+', type=str)
        parser.add_argument("--collector_ip_list", help = "List of IP Addresses of Analytics nodes",
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
        parser.add_argument("--keystone_version", choices=['v2.0', 'v3'],
            help = "Keystone Version")
        parser.add_argument("--keystone_certfile", help="")
        parser.add_argument("--keystone_keyfile", help="")
        parser.add_argument("--keystone_cafile", help="")
        parser.add_argument("--aaa_mode", help="AAA mode",
            choices=['no-auth', 'cloud-admin', 'cloud-admin-only'])
        parser.add_argument("--cloud_admin_role",
            help="Name of cloud-admin role")
        parser.add_argument("--cassandra_user", help="Cassandra user name",
            default= None)
        parser.add_argument("--cassandra_password", help="Cassandra password",
            default= None)
        parser.add_argument("--amqp_ip_list",
            help="List of IP addresses of AMQP servers", nargs="+", type=str)
        parser.add_argument("--amqp_port", help="Port number of AMQP server")
        parser.add_argument("--apiserver_insecure",
            help = "Connect to apiserver in secure or insecure mode if in https mode")
        parser.add_argument("--apiserver_certfile", help="")
        parser.add_argument("--apiserver_keyfile", help="")
        parser.add_argument("--apiserver_cafile", help="")
        parser.add_argument("--orchestrator", help="Orchestrator used by contrail")
        self._args = parser.parse_args(self.remaining_argv)

    def fixup_config_files(self):
        self.fixup_contrail_collector()
        self.fixup_contrail_query_engine()
        self.fixup_contrail_analytics_api()
        self.fixup_contrail_snmp_collector()
        self.fixup_contrail_topology()
        self.fixup_contrail_analytics_nodemgr()
        if not os.path.exists('/etc/contrail/contrail-keystone-auth.conf'):
            self.fixup_keystone_auth_config_file(False)
        self.fixup_vnc_api_lib_ini()
        self.fixup_contrail_alarm_gen()
        self.fixup_cassandra_config()
        self.fixup_ini_files()

    def fixup_analytics_daemon_ini_file(self, daemon_name, conf_files=None):
        dconf_files = []
        if conf_files:
            dconf_files.extend(conf_files)
        daemon_conf_file = '/etc/contrail/' + daemon_name + '.conf'
        dconf_files.append(daemon_conf_file)
        if self._args.cassandra_user:
            database_conf = '/etc/contrail/contrail-database.conf'
            dconf_files.append(database_conf)
        ini_conf_cmd = ''.join([' --conf_file ' + conf_file for \
            conf_file in dconf_files])
        supervisor_dir = '/etc/contrail/supervisord_analytics_files'
        bin_dir = '/usr/bin'
        self.set_config(os.path.join(supervisor_dir, daemon_name + '.ini'),
            'program:' + daemon_name, 'command',
            os.path.join(bin_dir, daemon_name) + ini_conf_cmd)
    # end fixup_analytics_daemon_ini_file

    def fixup_ini_files(self):
        self.fixup_analytics_daemon_ini_file('contrail-collector',
            ['/etc/contrail/contrail-keystone-auth.conf'])
        self.fixup_analytics_daemon_ini_file('contrail-query-engine')
        self.fixup_analytics_daemon_ini_file('contrail-analytics-api',
            ['/etc/contrail/contrail-keystone-auth.conf'])
        self.fixup_analytics_daemon_ini_file('contrail-alarm-gen',
            ['/etc/contrail/contrail-keystone-auth.conf'])
    # end fixup_ini_files

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
    # end fixup_cassandra_config

    def fixup_contrail_alarm_gen(self):
        ALARM_GEN_CONF_FILE = '/etc/contrail/contrail-alarm-gen.conf'
        cnd = os.path.exists(ALARM_GEN_CONF_FILE)
        if not cnd:
            raise RuntimeError('%s does not exist' % ALARM_GEN_CONF_FILE)
        self.set_config(ALARM_GEN_CONF_FILE, 'DEFAULTS', 'host_ip',
                        self._args.self_collector_ip)

        kafka_broker_list = [server[0] + ":9092" for server in self.cassandra_server_list]
        kafka_broker_list_str = ' '.join(map(str, kafka_broker_list))
        self.set_config(ALARM_GEN_CONF_FILE, 'DEFAULTS', 'kafka_broker_list',
                        kafka_broker_list_str)

        #prepare zklist
        zk_list_str = ' '.join('%s:%s' % zookeeper_server
                for zookeeper_server in self.zookeeper_server_list)
        self.set_config(ALARM_GEN_CONF_FILE, 'DEFAULTS', 'zk_list',
                        zk_list_str)
        redis_list_str = ' '.join(self.redis_server_list)
        self.set_config(ALARM_GEN_CONF_FILE, 'REDIS', 'redis_uve_list',
                        redis_list_str)

        if self._args.amqp_ip_list:
            self.set_config(ALARM_GEN_CONF_FILE, 'DEFAULTS', 'rabbitmq_server_list',
                            ','.join(self._args.amqp_ip_list))

        if self._args.amqp_port:
            self.set_config(ALARM_GEN_CONF_FILE, 'DEFAULTS', 'rabbitmq_port',
                            self._args.amqp_port)

        collector_list_str = ' '.join('%s:%s' %(server, '8086')
                for server in self._args.collector_ip_list)
        self.set_config(ALARM_GEN_CONF_FILE, 'DEFAULTS', 'collectors',
                        collector_list_str)
        self.set_config(ALARM_GEN_CONF_FILE, 'DEFAULTS', 'api_server',
                self._args.cfgm_ip+':8082')
 
    def fixup_contrail_snmp_collector(self):
        conf_fl = '/etc/contrail/contrail-snmp-collector.conf'
        with settings(warn_only=True):
            local("mkdir -p /etc/snmp")
            local("echo 'mibs +ALL' > /etc/snmp/snmp.conf")
            local("[ -f %s ] || > %s" % (conf_fl, conf_fl))
        self.set_config(conf_fl, 'DEFAULTS', 'zookeeper',
                ','.join('%s:%s' % zookeeper_server
                    for zookeeper_server in self.zookeeper_server_list))
        self.set_config(conf_fl, 'DEFAULTS', 'collectors',
                        ' '.join('%s:%s' %(server,'8086')
                        for server in self._args.collector_ip_list))
        self.set_config(conf_fl, 'DEFAULTS', 'api_server',
                self._args.cfgm_ip+':8082')
        self.set_config('/etc/contrail/supervisord_analytics_files/' +\
                        'contrail-snmp-collector.ini',
                        'program:contrail-snmp-collector',
                        'command',
                        '/usr/bin/contrail-snmp-collector --conf_file ' + \
                        conf_fl + ' --conf_file ' + \
                        '/etc/contrail/contrail-keystone-auth.conf')

    def fixup_contrail_analytics_nodemgr(self):
        template_vals = {
                         '__contrail_collectors__' : \
                             ' '.join('%s:%s' %(server, '8086') for server \
                             in self._args.collector_ip_list)
                         }
        self._template_substitute_write(contrail_analytics_nodemgr_template.template,
                                        template_vals, self._temp_dir_name + '/contrail-analytics-nodemgr.conf')
        local("sudo mv %s/contrail-analytics-nodemgr.conf /etc/contrail/contrail-analytics-nodemgr.conf" %(self._temp_dir_name))

    def fixup_contrail_topology(self):
        conf_fl = '/etc/contrail/contrail-topology.conf'
        with settings(warn_only=True):
            local("[ -f %s ] || > %s" % (conf_fl, conf_fl))
        self.set_config(conf_fl, 'DEFAULTS', 'zookeeper',
            ','.join('%s:%s' % zookeeper_server
                for zookeeper_server in self.zookeeper_server_list))
        self.set_config(conf_fl, 'DEFAULTS', 'collectors',\
                        ' '.join('%s:%s' %(server,'8086')
                        for server in self._args.collector_ip_list))
        self.set_config(conf_fl, 'DEFAULTS', 'api_server',
                self._args.cfgm_ip+':8082')
        self.set_config('/etc/contrail/supervisord_analytics_files/' +\
                        'contrail-topology.ini',
                        'program:contrail-topology',
                        'command',
                        '/usr/bin/contrail-topology --conf_file ' + \
                        conf_fl + ' --conf_file ' + \
                        '/etc/contrail/contrail-keystone-auth.conf')
        if self._args.internal_vip:
               self.set_config(conf_fl, 'DEFAULTS', 'analytics_api', '%s:8081' %(self._args.internal_vip))

    def fixup_contrail_collector(self):
        ALARM_GEN_CONF_FILE = '/etc/contrail/contrail-alarm-gen.conf'
        COLLECTOR_CONF_FILE = '/etc/contrail/contrail-collector.conf'
        template_vals = {'__contrail_log_file__' : '/var/log/contrail/contrail-collector.log',
                         '__contrail_host_ip__' : self._args.self_collector_ip,
                         '__contrail_listen_port__' : '8086',
                         '__contrail_http_server_port__' : '8089',
                         '__contrail_cassandra_server_list__' : ' '.join('%s:%s' % cassandra_server for cassandra_server in self.cassandra_server_list),
                         '__contrail_zookeeper_server_list__' : '',
                         '__contrail_analytics_data_ttl__' : '#analytics_data_ttl=48',
                         '__contrail_config_audit_ttl__' : '#analytics_config_audit_ttl=2160',
                         '__contrail_statistics_ttl__' : '#analytics_statistics_ttl=24',
                         '__contrail_flow_ttl__' : '#analytics_flow_ttl=2',
                         '__contrail_analytics_syslog_port__' : str(self._args.analytics_syslog_port),
                         '__contrail_redis_password__' : '',
                         '__contrail_kafka_broker_list__':'',
                         '__contrail_api_server_list__' : self._args.cfgm_ip+':8082'
                       }
        if self.zookeeper_server_list:
            template_vals['__contrail_zookeeper_server_list__'] = \
                ','.join('%s:%s' % zookeeper_server for zookeeper_server in \
                self.zookeeper_server_list)
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
        local("sudo mv %s/contrail-collector.conf %s" % \
              (self._temp_dir_name, COLLECTOR_CONF_FILE))

        # pickup the number of partitions from alarmgen conf
        # if it isn't there, collector conf should use defaults too
        try:
            pstr = self.get_config(ALARM_GEN_CONF_FILE, 'DEFAULTS', 'partitions')
            pint = int(pstr)
            self.set_config(COLLECTOR_CONF_FILE, 'DEFAULT', 'partitions', pstr)
        except:
            self.replace_in_file(COLLECTOR_CONF_FILE, 'partitions', '')

    def fixup_contrail_query_engine(self):
        template_vals = {'__contrail_log_file__' : '/var/log/contrail/contrail-query-engine.log',
                         '__contrail_redis_server__': '127.0.0.1',
                         '__contrail_redis_server_port__' : '6379',
                         '__contrail_collectors__' : \
                             ' '.join('%s:%s' %(server,'8086')
                             for server in self._args.collector_ip_list),
                         '__contrail_host_ip__' : self._args.self_collector_ip,
                         '__contrail_http_server_port__' : '8091',
                         '__contrail_cassandra_server_list__' : ' '.join('%s:%s' % cassandra_server for cassandra_server in self.cassandra_server_list),

                         '__contrail_redis_password__' : ''}
        if self._args.redis_password:
            template_vals['__contrail_redis_password__'] = 'password = '+ self._args.redis_password
        self._template_substitute_write(contrail_query_engine_conf.template,
                                        template_vals, self._temp_dir_name + '/contrail-query-engine.conf')
        local("sudo mv %s/contrail-query-engine.conf /etc/contrail/contrail-query-engine.conf" %(self._temp_dir_name))

    def fixup_contrail_analytics_api(self):
        conf_file = '/etc/contrail/contrail-analytics-api.conf'
        ALARM_GEN_CONF_FILE = '/etc/contrail/contrail-alarm-gen.conf'
        with settings(warn_only=True):
            local("[ -f %s ] || > %s" % (conf_file, conf_file))
        rest_api_port = '8081'
        if self._args.internal_vip:
            rest_api_port = '9081'

        config_vals = \
        { 'DEFAULTS' : {
            'log_file' : '/var/log/contrail/contrail-analytics-api.log',
            'log_local': 1,
            'log_category': '',
            'log_level': 'SYS_NOTICE',
            'http_server_port' : 8090,
            'rest_api_port' : rest_api_port,
            'host_ip' : self._args.self_collector_ip,
            'cassandra_server_list' : ' '.join('%s:%s' % cassandra_server for \
                cassandra_server in self.cassandra_server_list),
            'analytics_data_ttl' : self._args.analytics_data_ttl,
            'analytics_config_audit_ttl' : self._args.analytics_config_audit_ttl,
            'analytics_statistics_ttl' : self._args.analytics_statistics_ttl,
            'analytics_flow_ttl' : self._args.analytics_flow_ttl,
            'api_server' : self._args.cfgm_ip + ':8082',
            'api_server_use_ssl': 'True' if self.api_ssl_enabled else 'False',
            'zk_list': ' '.join('%s:%s' % zookeeper_server for \
                zookeeper_server in self.zookeeper_server_list),
            'collectors': ' '.join('%s:%s' %(server, '8086') \
                            for server in self._args.collector_ip_list)
            },
          'REDIS' : {
            'redis_query_port' : 6379,
            'redis_uve_list' : ' '.join(self.redis_server_list),
            },
        }

        if self._args.redis_password:
            config_vals['REDIS']['redis_password'] = self._args.redis_password
        if self._args.cloud_admin_role:
            config_vals['DEFAULTS']['cloud_admin_role'] = self._args.cloud_admin_role
        if self._args.aaa_mode:
            config_vals['DEFAULTS']['aaa_mode'] = self._args.aaa_mode
        for section, parameter_values in config_vals.items():
            for parameter, value in parameter_values.items():
                self.set_config(conf_file, section, parameter, value)

        # pickup the number of partitions from alarmgen conf
        # if it isn't there, analytics-api conf should use defaults too
        try:
            pstr = self.get_config(ALARM_GEN_CONF_FILE, 'DEFAULTS', 'partitions')
            pint = int(pstr)
            self.set_config(conf_file, 'DEFAULTS', 'partitions', pstr)
        except:
            self.replace_in_file(conf_file, 'partitions', '')

    def load_redis_upstart_file(self):
        #copy the redis-server conf to init
        template_vals = {
                        }
        self._template_substitute_write(redis_server_conf_template.template,
                                        template_vals, self._temp_dir_name + '/redis-server.conf')
        local("sudo service redis-server stop")
        local("sudo mv %s/redis-server.conf /etc/init/" %(self._temp_dir_name))
 
        local("sudo update-rc.d redis-server disable")
        local("sudo service redis-server start")

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

#end class CollectorSetup

def main(args_str = None):
    collector = CollectorSetup(args_str)
    collector.setup()

def fix_collector_config(args_str = None):
    collector = CollectorSetup(args_str)
    collector.fixup_config_files()
    collector.restart_collector()

if __name__ == "__main__":
    main()
