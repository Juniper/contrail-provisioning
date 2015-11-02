#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import ConfigParser
import re
import time
import subprocess

from fabric.api import *

from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.database.templates import contrail_database_nodemgr_template
from contrail_provisioning.database.templates import database_nodemgr_param_template
from contrail_provisioning.database.templates import cassandra_create_user_template
 
class DatabaseSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(DatabaseSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.global_defaults = {
            'dir' : '/usr/share/cassandra',
            'database_listen_ip' : '127.0.0.1',
            'cfgm_ip': '127.0.0.1',
            'minimum_diskGB': '256',
        }
        self.parse_args(args_str)

        self.database_listen_ip = self._args.self_ip
        self.database_seed_list = self._args.seed_list
        self.database_dir = self._args.dir

    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-database
            --self_ip 10.84.13.23
            --dir /usr/share/cassandra
            --initial_token 0 --seed_list 10.84.13.23 10.84.13.24
            --data_dir /home/cassandra
            --zookeeper_ip_list 10.1.5.11 10.1.5.12
            --database_index 1
            --node_to_delete 10.1.5.11
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--self_ip", help = "IP Address of this database node")
        parser.add_argument("--cfgm_ip", help = "IP Address of the config node")
        if self.pdist in ['fedora', 'centos', 'redhat']:
            parser.add_argument("--dir", help = "Directory where database binary exists", default = '/usr/share/cassandra')
        if self.pdist in ['Ubuntu']:
            parser.add_argument("--dir", help = "Directory where database binary exists", default = '/etc/cassandra')
        parser.add_argument("--initial_token", help = "Initial token for database node")
        parser.add_argument("--seed_list", help = "List of seed nodes for database", nargs='+')
        parser.add_argument("--data_dir", help = "Directory where database stores data")
        parser.add_argument("--analytics_data_dir", help = "Directory where database stores analytics data")
        parser.add_argument("--ssd_data_dir", help = "SSD directory that database stores data")
        parser.add_argument("--zookeeper_ip_list", help = "List of IP Addresses of zookeeper servers",
                            nargs='+', type=str)
        parser.add_argument("--database_index", help = "The index of this databse node")
        parser.add_argument("--minimum_diskGB", help = "Required minimum disk space for contrail database")
        parser.add_argument("--kafka_broker_id", help = "The broker id of the database node")
        parser.add_argument("--node_to_delete", help = "The DB node to remove from the cluster")
        parser.add_argument("--cassandra_user", help = "Cassandra user name if provided")
        parser.add_argument("--cassandra_password", help = "Cassandra password if provided")
        self._args = parser.parse_args(self.remaining_argv)

    def fixup_config_files(self):
        # Put hostname/ip mapping into /etc/hosts to avoid DNS resolution failing at bootup (Cassandra can fail)
        hosts_entry = '%s %s' %(self.database_listen_ip, self.hostname)
        with settings( warn_only= True) :
            local('grep -q \'%s\' /etc/hosts || echo \'%s\' >> /etc/hosts' %(self.database_listen_ip, hosts_entry))

        if self.pdist == 'fedora' or self.pdist == 'centos' or self.pdist == 'redhat':
            CASSANDRA_CONF = '/etc/cassandra/conf'
            CASSANDRA_CONF_FILE = 'cassandra.yaml'
            CASSANDRA_ENV_FILE = 'cassandra-env.sh'
        if self.pdist == 'Ubuntu':
            CASSANDRA_CONF = '/etc/cassandra/'
            CASSANDRA_CONF_FILE = 'cassandra.yaml'
            CASSANDRA_ENV_FILE = 'cassandra-env.sh'
        listen_ip = self.database_listen_ip
        cassandra_dir = self.database_dir
        initial_token = self._args.initial_token
        seed_list = self.database_seed_list
        data_dir = self._args.data_dir
        analytics_data_dir = self._args.analytics_data_dir
        ssd_data_dir = self._args.ssd_data_dir
        if not cassandra_dir:
            raise RuntimeError('Undefined cassandra directory')
        conf_dir = CASSANDRA_CONF
        cnd = os.path.exists(conf_dir)
        conf_file = os.path.join(conf_dir, CASSANDRA_CONF_FILE)
        cnd = cnd and os.path.exists(conf_file)
        if not cnd:
            raise RuntimeError('%s does not appear to be a cassandra source directory' % cassandra_dir)

        self.replace_in_file(conf_file, 'listen_address: ', 'listen_address: ' + listen_ip)
        self.replace_in_file(conf_file, 'cluster_name: ', 'cluster_name: \'Contrail\'')
        self.replace_in_file(conf_file, 'rpc_address: ', 'rpc_address: ' + listen_ip)
        self.replace_in_file(conf_file, '# num_tokens: 256', 'num_tokens: 256')
        self.replace_in_file(conf_file, 'initial_token:', '# initial_token:')
        if self._args.cassandra_user is not None:
            self.replace_in_file(conf_file,'authenticator: AllowAllAuthenticator','authenticator: PasswordAuthenticator')
        if data_dir:
            saved_cache_dir = os.path.join(data_dir, 'saved_caches')
            self.replace_in_file(conf_file, 'saved_caches_directory:', 'saved_caches_directory: ' + saved_cache_dir)
            commit_log_dir = os.path.join(data_dir, 'commitlog')
            self.replace_in_file(conf_file, 'commitlog_directory:', 'commitlog_directory: ' + commit_log_dir)
            cass_data_dir = os.path.join(data_dir, 'data')
            self.replace_in_file(conf_file, '    - /var/lib/cassandra/data', '    - ' + cass_data_dir)
        if ssd_data_dir:
            commit_log_dir = os.path.join(ssd_data_dir, 'commitlog')
            self.replace_in_file(conf_file, 'commitlog_directory:', 'commitlog_directory: ' + commit_log_dir)
            if not os.path.exists(ssd_data_dir):
                local("sudo mkdir -p %s" % (ssd_data_dir))
                local("sudo chown -R cassandra: %s" % (ssd_data_dir))
        if analytics_data_dir:
            if not data_dir:
                data_dir = '/var/lib/cassandra'
                cass_data_dir = os.path.join(data_dir, 'data')
            else:
                cass_data_dir = data_dir
            analytics_dir_link = os.path.join(cass_data_dir, 'ContrailAnalytics')
            analytics_dir = os.path.join(analytics_data_dir, 'ContrailAnalytics')
            if not os.path.exists(analytics_dir_link):
                if not os.path.exists(data_dir):
                    local("sudo mkdir -p %s" % (data_dir))
                    local("sudo chown -R cassandra: %s" % (data_dir))
                if not os.path.exists(cass_data_dir):
                    local("sudo mkdir -p %s" % (cass_data_dir))
                    local("sudo chown -R cassandra: %s" % (cass_data_dir))
                if not os.path.exists(analytics_dir):
                    local("sudo mkdir -p %s" % (analytics_dir))
                    local("sudo chown -R cassandra: %s" % (analytics_dir))
                local("sudo ln -s %s %s" % (analytics_dir, analytics_dir_link))
                local("sudo chown -h cassandra: %s" % (analytics_dir_link))
        else:
            if not data_dir:
                data_dir = '/var/lib/cassandra'
                cass_data_dir = os.path.join(data_dir, 'data')
            else:
                cass_data_dir = data_dir
            analytics_dir = os.path.join(cass_data_dir, 'ContrailAnalytics')
            if not os.path.exists(analytics_dir):
                if not os.path.exists(data_dir):
                    local("sudo mkdir -p %s" % (data_dir))
                    local("sudo chown -R cassandra: %s" % (data_dir))
                if not os.path.exists(cass_data_dir):
                    local("sudo mkdir -p %s" % (cass_data_dir))
                    local("sudo chown -R cassandra: %s" % (cass_data_dir))
                local("sudo mkdir -p %s" % (analytics_dir))
                local("sudo chown -R cassandra: %s" % (analytics_dir))

        disk_cmd = "df -Pk " + analytics_dir + " | grep % | awk '{print $2}'"
        total_disk = local(disk_cmd, capture = True).strip()
        if (int(total_disk)/(1024*1024) < int(self._args.minimum_diskGB)):
            raise RuntimeError('Minimum disk space for analytics db is not met')

        if seed_list:
            self.replace_in_file(conf_file, '          - seeds: ', '          - seeds: "' + ", ".join(seed_list) + '"')

        env_file = os.path.join(conf_dir, CASSANDRA_ENV_FILE)
        cnd = os.path.exists(env_file)
        if not cnd:
            raise RuntimeError('%s does not appear to be a cassandra source directory' % cassandra_dir)

        local("sudo sed -i 's/# JVM_OPTS=\"\$JVM_OPTS -XX:+PrintGCDetails\"/JVM_OPTS=\"\$JVM_OPTS -XX:+PrintGCDetails\"/g' %s" \
              % (env_file))
        if  (self.pdist == 'centos' and self.pdistversion >= '6.5') or self.pdist == 'redhat':
            local("sudo sed -i 's/JVM_OPTS=\"\$JVM_OPTS -Xss180k\"/JVM_OPTS=\"\$JVM_OPTS -Xss228k\"/g' %s" \
              % (env_file))
        else:
            local("sudo sed -i 's/JVM_OPTS=\"\$JVM_OPTS -Xss180k\"/JVM_OPTS=\"\$JVM_OPTS -Xss512k\"/g' %s" \
              % (env_file))
        local("sudo sed -i 's/# JVM_OPTS=\"\$JVM_OPTS -XX:+PrintGCDateStamps\"/JVM_OPTS=\"\$JVM_OPTS -XX:+PrintGCDateStamps\"/g' %s" \
              % (env_file))
        local("sudo sed -i 's/# JVM_OPTS=\"\$JVM_OPTS -XX:+PrintHeapAtGC\"/JVM_OPTS=\"\$JVM_OPTS -XX:+PrintHeapAtGC\"/g' %s" \
              % (env_file))
        local("sudo sed -i 's/# JVM_OPTS=\"\$JVM_OPTS -XX:+PrintTenuringDistribution\"/JVM_OPTS=\"\$JVM_OPTS -XX:+PrintTenuringDistribution\"/g' %s" \
              % (env_file))
        local("sudo sed -i 's/# JVM_OPTS=\"\$JVM_OPTS -XX:+PrintGCApplicationStoppedTime\"/JVM_OPTS=\"\$JVM_OPTS -XX:+PrintGCApplicationStoppedTime\"/g' %s" \
              % (env_file))
        local("sudo sed -i 's/# JVM_OPTS=\"\$JVM_OPTS -XX:+PrintPromotionFailure\"/JVM_OPTS=\"\$JVM_OPTS -XX:+PrintPromotionFailure\"/g' %s" \
              % (env_file))
        local("sudo sed -i 's/# JVM_OPTS=\"\$JVM_OPTS -XX:PrintFLSStatistics=1\"/JVM_OPTS=\"\$JVM_OPTS -XX:PrintFLSStatistics=1\"/g' %s" \
              % (env_file))
        local("sudo sed -i 's/# JVM_OPTS=\"\$JVM_OPTS -Xloggc:\/var\/log\/cassandra\/gc-`date +%%s`.log\"/JVM_OPTS=\"\$JVM_OPTS -Xloggc:\/var\/log\/cassandra\/gc-`date +%%s`.log\"/g' %s" \
              % (env_file))
        local("sudo sed -i 's/MaxTenuringThreshold=1/MaxTenuringThreshold=30/g' %s" % (env_file))

        self.fixup_contrail_database_nodemgr()

        # set high session timeout to survive glance led disk activity
        local('sudo echo "maxSessionTimeout=120000" >> /etc/zookeeper/conf/zoo.cfg')
        local('sudo echo "autopurge.purgeInterval=3" >> /etc/zookeeper/conf/zoo.cfg')
        local("sudo sed 's/^#log4j.appender.ROLLINGFILE.MaxBackupIndex=/log4j.appender.ROLLINGFILE.MaxBackupIndex=/g' /etc/zookeeper/conf/log4j.properties > log4j.properties.new")
        local("sudo mv log4j.properties.new /etc/zookeeper/conf/log4j.properties")
        if self.pdist == 'fedora' or self.pdist == 'centos' or self.pdist == 'redhat':
            local('echo export ZOO_LOG4J_PROP="INFO,CONSOLE,ROLLINGFILE" >> /usr/lib/zookeeper/bin/zkEnv.sh')
        if self.pdist == 'Ubuntu':
            local('echo ZOO_LOG4J_PROP="INFO,CONSOLE,ROLLINGFILE" >> /etc/zookeeper/conf/environment')

        self.fix_zookeeper_servers_config()
        self.fixup_kafka_server_properties(listen_ip)

    def fixup_kafka_server_properties(self, listen_ip):
        #Update the broker id of the /usr/share/kafka/config/server.properties
        KAFKA_SERVER_PROPERTIES='/usr/share/kafka/config/server.properties'
        cnd = os.path.exists(KAFKA_SERVER_PROPERTIES)
        if not cnd:
            raise RuntimeError('%s does not appear to be a kafka config directory' % KAFKA_SERVER_PROPERTIES)
        if self._args.kafka_broker_id is not None:
            self.replace_in_file(KAFKA_SERVER_PROPERTIES, 'broker.id=', 'broker.id='+self._args.kafka_broker_id)

        #Handling for Kafka-0.8.3
        self.replace_in_file(KAFKA_SERVER_PROPERTIES, '#port=9092', 'port=9092')
        self.replace_in_file(KAFKA_SERVER_PROPERTIES, \
                'listeners=PLAINTEXT://:9092','#listeners=PLAINTEXT://:9092')

        #Add all the zoo keeper server address to the server.properties file
        zk_list = [server + ":2181" for server in self._args.zookeeper_ip_list]
        zk_list_str = ','.join(map(str, zk_list))
        self.replace_in_file(KAFKA_SERVER_PROPERTIES, 'zookeeper.connect=*', 'zookeeper.connect='+zk_list_str)
        self.replace_in_file(KAFKA_SERVER_PROPERTIES, '#advertised.host.name=<hostname routable by clients>',\
                'advertised.host.name='+listen_ip)
        #Set replication factor to 2 if more than one kafka broker is available
        if (len(zk_list)>1):
            if not self.file_pattern_check(KAFKA_SERVER_PROPERTIES, 'default.replication.factor'):
                local('sudo echo "default.replication.factor=2" >> %s' % (KAFKA_SERVER_PROPERTIES))
        KAFKA_LOG4J_PROPERTIES='/usr/share/kafka/config/log4j.properties'
        cnd = os.path.exists(KAFKA_LOG4J_PROPERTIES)
        if not cnd:
            raise RuntimeError('%s does not appear to be a kafka logs config' % KAFKA_LOG4J_PROPERTIES)
        local("sudo sed -i 's/DailyRollingFileAppender/RollingFileAppender/g' %s" % KAFKA_LOG4J_PROPERTIES)
        local("sudo sed -i \"s/DatePattern='.'yyyy-MM-dd-HH/MaxBackupIndex=10/g\" %s" % KAFKA_LOG4J_PROPERTIES)

    def fixup_contrail_database_nodemgr(self):
        template_vals = {
                        '__contrail_discovery_ip__': self._args.cfgm_ip,
                        '__contrail_discovery_port__': '5998',
                        '__minimum_diskGB__': self._args.minimum_diskGB,
                        '__hostip__': self.database_listen_ip,
                        }
        self._template_substitute_write(contrail_database_nodemgr_template.template,
                                        template_vals, self._temp_dir_name + '/contrail-database-nodemgr.conf')
        local("sudo mv %s/contrail-database-nodemgr.conf /etc/contrail/contrail-database-nodemgr.conf" %(self._temp_dir_name))

    def create_cassandra_user(self):
        template_vals = {
                        '__cassandra_user__': self._args.cassandra_user,
                        '__cassandra_password__': self._args.cassandra_password,
                        }
        self._template_substitute_write(cassandra_create_user_template.template,
                                        template_vals, self._temp_dir_name + '/cassandra_create_user')
        local("sudo mv %s/cassandra_create_user /etc/contrail/cassandra_create_user" %(self._temp_dir_name))

        connected=False
        retry_threshold = 10
        retry = 1
        while connected == False and retry < retry_threshold:
            #create account using cql
            status = subprocess.Popen('sudo cqlsh %s  -u cassandra -p cassandra -f /etc/contrail/cassandra_create_user' % self.database_listen_ip, shell=True,stderr = subprocess.PIPE,stdout=subprocess.PIPE).stderr.read()
            if 'already exists' in status or not status:
                print 'connection made'
                connected = True
            else:
                print status
                retry = retry + 1
                time.sleep(5)
        return connected

    def run_services(self):
        local("sudo database-server-setup.sh %s" % (self.database_listen_ip))
        #If user name and passwd provided setit up in cassandra before starting the database service
        if self._args.cassandra_user is not None:
            assert(self.create_cassandra_user())

    #Checks if a pattern is present in the file or not
    def file_pattern_check(self, file_name, regexp):
        rs = re.compile(regexp)
        with open(file_name, 'r') as f:
            for line in f:
                match = rs.search(line)
                if match:
                    return True
        return False

    def fix_zookeeper_servers_config(self):
        zk_index = 1
        # Instead of inserting/deleting config, remove all the zoo keeper servers
        # and re-generate.
        local("sudo sed -i '/server.[1-9]*=/d' /etc/zookeeper/conf/zoo.cfg")

        for zk_ip in self._args.zookeeper_ip_list:
            local('sudo echo "server.%d=%s:2888:3888" >> /etc/zookeeper/conf/zoo.cfg' %(zk_index, zk_ip))
            zk_index = zk_index + 1

        #put cluster-unique zookeeper's instance id in myid
        local('sudo echo "%s" > /var/lib/zookeeper/myid' %(self._args.database_index))

    def restart_zookeeper(self):
        local('sudo service zookeeper restart')

    def update_seed_list(self):
        if self.pdist == 'fedora' or self.pdist == 'centos' or self.pdist == 'redhat':
            CASSANDRA_CONF = '/etc/cassandra/conf'
            CASSANDRA_CONF_FILE = 'cassandra.yaml'
            CASSANDRA_ENV_FILE = 'cassandra-env.sh'
        if self.pdist == 'Ubuntu':
            CASSANDRA_CONF = '/etc/cassandra/'
            CASSANDRA_CONF_FILE = 'cassandra.yaml'
            CASSANDRA_ENV_FILE = 'cassandra-env.sh'
        conf_dir = CASSANDRA_CONF
        cnd = os.path.exists(conf_dir)
        conf_file = os.path.join(conf_dir, CASSANDRA_CONF_FILE)

        if self._args.seed_list:
            self.replace_in_file(conf_file, '          - seeds:*', '          - seeds: "' + ", ".join(self._args.seed_list) + '"')

        local("sudo service contrail-database restart")

    def decommission_db_node(self):
        print "Decommissioning node %s from cluster. This might take a long time" % self._args.self_ip
        local("nodetool decommission")
        is_decommissioned = local('nodetool netstats | grep "Mode: DECOMMISSIONED"').succeeded
        if not is_decommissioned:
            raise RuntimeError("Error while decommissioning %s from the DB cluster", del_db_node)

        local("service supervisor-database stop")

    def remove_db_node(self):
        print "Removing node %s from cluster. This might take a long time" % self._args.node_to_delete
        with settings(warn_only = True):
            node_uuid = local('nodetool status | grep %s | awk \'{print $7}\'' % self._args.node_to_delete, capture = True) 

        if node_uuid:
            local("nodetool removenode %s" % node_uuid)
        else:
            print "Node %s was never part of the cluster", self._args.node_to_delete
            return

        with settings(warn_only = True):
            is_removed = local('nodetool status | grep %s' % self._args.node_to_delete).failed

        if not is_removed:
            raise RuntimeError("Error while removed node %s from the DB cluster", self._args.node_to_delete)

def main(args_str = None):
    database = DatabaseSetup(args_str)
    database.setup()

def update_zookeeper_servers(args_str = None):
    database = DatabaseSetup(args_str)
    database.fix_zookeeper_servers_config()
    database.fixup_kafka_server_properties()

def restart_zookeeper_server(args_str = None):
    database = DatabaseSetup(args_str)
    database.restart_zookeeper()

def readjust_seed_list(args_str = None):
    database = DatabaseSetup(args_str)
    database.update_seed_list()

def decommission_cassandra_node(args_str = None):
    database = DatabaseSetup(args_str)
    database.decommission_db_node()

def remove_cassandra_node(args_str = None):
    database = DatabaseSetup(args_str)
    database.remove_db_node()

if __name__ == "__main__":
    main()
