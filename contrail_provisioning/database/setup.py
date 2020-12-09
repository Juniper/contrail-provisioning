#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import re
import time
import subprocess

from fabric.api import *

from contrail_provisioning.database.base import DatabaseCommon
from contrail_provisioning.database.templates import contrail_database_nodemgr_template
from contrail_provisioning.database.templates import cassandra_create_user_template
 
class DatabaseSetup(DatabaseCommon):
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
            'discovery_certfile': None,
            'discovery_keyfile': None,
            'discovery_cafile': None,
        }
        self.parse_args(args_str)

        self.database_listen_ip = self._args.self_ip
        self.database_seed_list = self._args.seed_list
        self.database_dir = self._args.dir
        self.disc_ssl_enabled = False
        if (self._args.discovery_keyfile and
                self._args.discovery_certfile and self._args.discovery_cafile):
            self.disc_ssl_enabled = True

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
        parser.add_argument("--opscenter_ip", help = "IP Address of webui/opscenter node")
        parser.add_argument("--discovery_certfile", help="")
        parser.add_argument("--discovery_keyfile", help="")
        parser.add_argument("--discovery_cafile", help="")
        self._args = parser.parse_args(self.remaining_argv)

    def create_analytics_data_dir(self, data_dir, cass_data_dir,
                                  analytics_dir, analytics_dir_link=None):
        if analytics_dir_link:
            verify_dir = analytics_dir_link
        else:
            verify_dir = analytics_dir
        if not os.path.exists(verify_dir):
            if not os.path.exists(data_dir):
                local("sudo mkdir -p %s" % (data_dir))
                local("sudo chown -R cassandra: %s" % (data_dir))
            if not os.path.exists(cass_data_dir):
                local("sudo mkdir -p %s" % (cass_data_dir))
                local("sudo chown -R cassandra: %s" % (cass_data_dir))
            if not os.path.exists(analytics_dir):
                local("sudo mkdir -p %s" % (analytics_dir))
                local("sudo chown -R cassandra: %s" % (analytics_dir))
            if analytics_dir_link:
                local("sudo ln -s %s %s" % (analytics_dir, analytics_dir_link))
                local("sudo chown -h cassandra: %s" % (analytics_dir_link))

    def setup_analytics_data_dir(self):
        data_dir = self._args.data_dir
        analytics_data_dir = self._args.analytics_data_dir
        if self.is_cql_supported():
            CASSANDRA_ANALYTICS_KEYSPACE = 'ContrailAnalyticsCql'
        else:
            CASSANDRA_ANALYTICS_KEYSPACE = 'ContrailAnalytics'
        if not data_dir:
            data_dir = '/var/lib/cassandra'
            cass_data_dir = os.path.join(data_dir, 'data')
        else:
            cass_data_dir = data_dir
        if analytics_data_dir:
            analytics_dir_link = os.path.join(cass_data_dir,
                                              CASSANDRA_ANALYTICS_KEYSPACE)
            analytics_dir = os.path.join(analytics_data_dir,
                                         CASSANDRA_ANALYTICS_KEYSPACE)
            self.create_analytics_data_dir(data_dir, cass_data_dir,
                                           analytics_dir, analytics_dir_link)
        else:
            analytics_dir = os.path.join(cass_data_dir,
                                         CASSANDRA_ANALYTICS_KEYSPACE)
            self.create_analytics_data_dir(data_dir, cass_data_dir,
                                           analytics_dir)

        disk_cmd = "df -Pk " + analytics_dir + " | grep % | awk '{print $2}'"
        total_disk = local(disk_cmd, capture = True).strip()
        if (int(total_disk)/(1024*1024) < int(self._args.minimum_diskGB)):
            raise RuntimeError('Minimum disk space for analytics db is not met')

    def fixup_config_files(self):
        self.fixup_etc_hosts_file(self.database_listen_ip, self.hostname)
        self.fixup_cassandra_config_file(self.database_listen_ip,
                                         self.database_seed_list,
                                         self._args.data_dir,
                                         self._args.ssd_data_dir,
                                         cluster_name='Contrail',
                                         user=self._args.cassandra_user)
        self.fixup_datastax_config_file(self._args.opscenter_ip)
        self.setup_analytics_data_dir()
        self.fixup_cassandra_env_config()

        self.fixup_contrail_database_nodemgr()

        #self.fixup_zookeeper_configs()
        self.fixup_kafka_server_properties(self.database_listen_ip)

    def fixup_kafka_server_properties(self, listen_ip):
        #Update the broker id of the /usr/share/kafka/config/server.properties
        KAFKA_SERVER_PROPERTIES='/opt/kafka/config/server.properties'
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
        self.replace_in_file(KAFKA_SERVER_PROPERTIES, 'zookeeper.connect=.*', 'zookeeper.connect='+zk_list_str)
        self.replace_in_file(KAFKA_SERVER_PROPERTIES, '#advertised.host.name=<hostname routable by clients>',\
                'advertised.host.name='+listen_ip)

        #Set retention policy
        self.replace_in_file(KAFKA_SERVER_PROPERTIES, '#log.retention.bytes=.*',
                'log.retention.bytes=1073741824')
        self.replace_in_file(KAFKA_SERVER_PROPERTIES, 'log.retention.bytes=.*',
                'log.retention.bytes=268435456')
        self.replace_in_file(KAFKA_SERVER_PROPERTIES, 'log.segment.bytes=.*',
                'log.segment.bytes=268435456')
        self.replace_in_file(KAFKA_SERVER_PROPERTIES, 'log.retention.hours=.*',
                'log.retention.hours=24')
        self.replace_in_file(KAFKA_SERVER_PROPERTIES, 'log.cleanup.policy=.*',
                'log.cleanup.policy=delete')
        self.replace_in_file(KAFKA_SERVER_PROPERTIES, 'log.cleaner.threads=.*',
                'log.cleaner.threads=2')
        self.replace_in_file(KAFKA_SERVER_PROPERTIES, 'log.cleaner.dedupe.buffer.size=.*',
                'log.cleaner.dedupe.buffer.size=250000000')

        # Set log compaction and topic delete options
        self.replace_in_file(KAFKA_SERVER_PROPERTIES, 'log.cleaner.enable=false','log.cleaner.enable=true')
        local ("sudo echo >> %s" % KAFKA_SERVER_PROPERTIES)
        if not self.file_pattern_check(KAFKA_SERVER_PROPERTIES, 'log.cleanup.policy=delete'):
            local('sudo echo "log.cleanup.policy=delete" >> %s' % KAFKA_SERVER_PROPERTIES)
        if not self.file_pattern_check(KAFKA_SERVER_PROPERTIES, 'delete.topic.enable=true'):
            local('sudo echo "delete.topic.enable=true" >> %s' % KAFKA_SERVER_PROPERTIES)
        if not self.file_pattern_check(KAFKA_SERVER_PROPERTIES, 'log.cleaner.threads=2'):
            local('sudo echo "log.cleaner.threads=2" >> %s' % KAFKA_SERVER_PROPERTIES)
        if not self.file_pattern_check(KAFKA_SERVER_PROPERTIES, 'log.cleaner.dedupe.buffer.size=250000000'):
            local('sudo echo "log.cleaner.dedupe.buffer.size=250000000" >> %s' % KAFKA_SERVER_PROPERTIES)

        #Set replication factor to 2 if more than one kafka broker is available
        if (len(self._args.seed_list) > 1 or len(self._args.seed_list[0].split(','))>1):
            if not self.file_pattern_check(KAFKA_SERVER_PROPERTIES, 'default.replication.factor'):
                local('sudo echo "default.replication.factor=2" >> %s' % (KAFKA_SERVER_PROPERTIES))
        KAFKA_LOG4J_PROPERTIES='/usr/share/kafka/config/log4j.properties'
        cnd = os.path.exists(KAFKA_LOG4J_PROPERTIES)
        if not cnd:
            raise RuntimeError('%s does not appear to be a kafka logs config' % KAFKA_LOG4J_PROPERTIES)
        local("sudo sed -i 's/DailyRollingFileAppender/RollingFileAppender/g' %s" % KAFKA_LOG4J_PROPERTIES)
        local("sudo sed -i \"s/DatePattern='.'yyyy-MM-dd-HH/MaxBackupIndex=10/g\" %s" % KAFKA_LOG4J_PROPERTIES)

        # set parameters to limit GC file size
        KAFKA_RUN_FILE='/usr/share/kafka/bin/kafka-run-class.sh'
        cnd = os.path.exists(KAFKA_RUN_FILE)
        if cnd:
            local("sudo sed -i 's/+UseG1GC/+UseG1GC -XX:NumberOfGCLogFiles=10 -XX:GCLogFileSize=100M/g' %s" % KAFKA_RUN_FILE)


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
        conf_file = '/etc/contrail/contrail-database-nodemgr.conf'
        if self.disc_ssl_enabled:
            certfile, cafile, keyfile = self._get_discovery_certs()
            configs = {'ssl': self.disc_ssl_enabled,
                       'cert': certfile,
                       'key': keyfile,
                       'cacert': cafile}
            for param, value in configs.items():
                self.set_config(conf_file, 'DISCOVERY', param, value)

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

    def restart_zookeeper(self):
        local('sudo service zookeeper restart')

    def update_seed_list(self):
        conf_dir = self.cassandra.conf_dif
        conf_file = os.path.join(conf_dir, self.cassandra.conf_file)

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

    def restart(self):
        #local('service zookeeper restart')
        local('service contrail-database restart')
        local('service supervisor-database restart')


def main(args_str = None):
    database = DatabaseSetup(args_str)
    database.setup()

def update_zookeeper_servers(args_str = None):
    database = DatabaseSetup(args_str)
    database.fixup_zookeeper_configs()
    database.fixup_kafka_server_properties(database.database_listen_ip)

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
