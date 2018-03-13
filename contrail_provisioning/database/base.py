#!/usr/bin/python
#
# Copyright (c) 2016 Juniper Networks, Inc. All rights reserved.
#

import os
import subprocess
import shutil
from tempfile import NamedTemporaryFile
from fabric.api import local, settings

from contrail_provisioning.common.base import ContrailSetup


class CassandraInfo(object):
    def __init__(self, pdist,
                 conf_file='cassandra.yaml',
                 env_file='cassandra-env.sh',
                 conf_dir=None):
        self.conf_file = conf_file
        self.env_file = env_file
        if not conf_dir:
            if pdist in ['fedora', 'centos', 'redhat']:
                self.conf_dir = '/etc/cassandra/conf'
            elif pdist in ['Ubuntu']:
                self.conf_dir = '/etc/cassandra/'


class DatabaseCommon(ContrailSetup):
    def __init__(self):
        super(DatabaseCommon, self).__init__()
        self.cassandra = CassandraInfo(self.pdist)
        self.zoo_conf_dir = '/etc/zookeeper/conf/'
        if not os.path.isdir(self.zoo_conf_dir):
            self.zoo_conf_dir = '/etc/zookeeper/'

    def create_data_dir(self, data_dir):
        if not os.path.exists(data_dir):
            local("sudo mkdir -p %s" % (data_dir))
            local("sudo chown -R cassandra: %s" % (data_dir))

    def fixup_etc_hosts_file(self, listen_ip, hostname):
        # Put hostname/ip mapping into /etc/hosts to avoid DNS resolution
        # failing at bootup (Cassandra can fail)
        hosts_entry = '%s %s' % (listen_ip, hostname)
        with settings(warn_only=True):
            local('grep -q \'%s\' /etc/hosts || echo \'%s\' >> /etc/hosts' %
                  (listen_ip, hosts_entry))

    def fixup_datastax_config_file(self, opscenter_ip):
        DATASTAX_CONF = '/var/lib/datastax-agent/conf'
        DATASTAX_CONF_FILE = 'address.yaml'
        conf_file = os.path.join(DATASTAX_CONF,DATASTAX_CONF_FILE)
        local("sudo mkdir -p %s" % DATASTAX_CONF)
        local("sudo echo \"stomp_interface: %s\" > %s" % (opscenter_ip,conf_file))
        local("sudo echo \"use_ssl: 0\" >> %s", conf_file)
    
    def fixup_cassandra_config_file(self, listen_ip, seed_list, data_dir,
                                    ssd_data_dir, cluster_name='Contrail',
                                    user=None, cassandra_ssl_options=None):

        if not os.path.exists(self.cassandra.conf_dir):
            raise RuntimeError('%s does not appear to be a cassandra conf',
                               'directory' % self.cassandra.conf_dir)
        conf_file = os.path.join(self.cassandra.conf_dir,
                                 self.cassandra.conf_file)
        if not os.path.exists(conf_file):
            raise RuntimeError('cassandra conf file %s does not exists'
                               % conf_file)

        self.replace_in_file(conf_file, 'listen_address: ',
                             'listen_address: ' + listen_ip)
        self.replace_in_file(conf_file, 'cluster_name: ',
                             'cluster_name: \'%s\'' % cluster_name)
        self.replace_in_file(conf_file, 'rpc_address: ',
                             'rpc_address: ' + listen_ip)
        self.replace_in_file(conf_file, '# num_tokens: 256', 'num_tokens: 256')
        self.replace_in_file(conf_file, 'initial_token:', '# initial_token:')
        self.replace_in_file(conf_file, 'start_rpc: ', 'start_rpc: true')
        self.replace_in_file(conf_file, 'compaction_throughput_mb_per_sec: 16',
                             'compaction_throughput_mb_per_sec: 96')
        if user:
            self.replace_in_file(conf_file,
                                 'authenticator: AllowAllAuthenticator',
                                 'authenticator: PasswordAuthenticator')
        if data_dir:
            saved_cache_dir = os.path.join(data_dir, 'saved_caches')
            self.replace_in_file(conf_file, 'saved_caches_directory:',
                                 'saved_caches_directory: ' + saved_cache_dir)
            commit_log_dir = os.path.join(data_dir, 'commitlog')
            self.replace_in_file(conf_file, 'commitlog_directory:',
                                 'commitlog_directory: ' + commit_log_dir)
            cass_data_dir = os.path.join(data_dir, 'data')
            self.replace_in_file(conf_file, '    - /var/lib/cassandra/data',
                                 '    - ' + cass_data_dir)
        if ssd_data_dir:
            commit_log_dir = os.path.join(ssd_data_dir, 'commitlog')
            self.replace_in_file(conf_file, 'commitlog_directory:',
                                 'commitlog_directory: ' + commit_log_dir)
            if not os.path.exists(ssd_data_dir):
                local("sudo mkdir -p %s" % (ssd_data_dir))
                local("sudo chown -R cassandra: %s" % (ssd_data_dir))

        if seed_list:
            self.replace_in_file(
                    conf_file,
                    '          - seeds: ',
                    '          - seeds: "' + ", ".join(seed_list) + '"')

        if cassandra_ssl_options:
            print 'np_database_1'; import pdb; pdb.set_trace()
            kwords = ['enabled', 'optional', 'keystore',
                      'keystore_password', 'truststore',
                      'truststore_password', 'protocol',
                      'algorithm', 'store_type', 'cipher_suites']
            # work on a copy of cassandra.yaml
            tempfile = NamedTemporaryFile()
            if not os.path.isfile('%s.org' % conf_file):
                local("sudo cp -f %s %s.org" % (conf_file, conf_file))
            local("sudo cp -f %s %s" % (conf_file, tempfile.name))
            with open(tempfile.name, 'r') as fid:
                contents = fid.read().split('\n')
                fid.flush()
            start_index = contents.index('client_encryption_options:')
            end_index = contents[start_index:].index('')
            for index in range(start_index+1, (start_index+end_index)):
                line = contents[index].split(':', 1)
                for kword in kwords:
                    if "%s:" % kword in contents[index]:
                        contents[index] = "%s: %s" % (line[0].replace('# ', ''),
                                                   cassandra_ssl_options[kword])
            with open(tempfile.name, 'w') as fid:
                fid.write("\n".join(contents))
                fid.flush()
            local("sudo cp -f %s %s" % (tempfile.name, conf_file))


    def fixup_cassandra_env_config(self):
        env_file = os.path.join(self.cassandra.conf_dir,
                                self.cassandra.env_file)
        cnd = os.path.exists(env_file)
        if not cnd:
            raise RuntimeError('%s does not appear to be a cassandra source',
                               'directory' % self.cassandra.conf_dir)

        env_file_settings = [('# JVM_OPTS=\"\$JVM_OPTS -XX:+PrintGCDetails\"',
                              'JVM_OPTS=\"\$JVM_OPTS -XX:+PrintGCDetails\"'),
                             ('# JVM_OPTS=\"\$JVM_OPTS -XX:+PrintGCDateStamps\"',
                              'JVM_OPTS=\"\$JVM_OPTS -XX:+PrintGCDateStamps\"'),
                             ('# JVM_OPTS=\"\$JVM_OPTS -XX:+PrintHeapAtGC\"',
                              'JVM_OPTS=\"\$JVM_OPTS -XX:+PrintHeapAtGC\"'),
                             ('# JVM_OPTS=\"\$JVM_OPTS -XX:+PrintTenuringDistribution\"',
                              'JVM_OPTS=\"\$JVM_OPTS -XX:+PrintTenuringDistribution\"'),
                             ('# JVM_OPTS=\"\$JVM_OPTS -XX:+PrintGCApplicationStoppedTime\"',
                              'JVM_OPTS=\"\$JVM_OPTS -XX:+PrintGCApplicationStoppedTime\"'),
                             ('# JVM_OPTS=\"\$JVM_OPTS -XX:+PrintPromotionFailure\"',
                              'JVM_OPTS=\"\$JVM_OPTS -XX:+PrintPromotionFailure\"'),
                             ('# JVM_OPTS=\"\$JVM_OPTS -XX:PrintFLSStatistics=1\"',
                              'JVM_OPTS=\"\$JVM_OPTS -XX:PrintFLSStatistics=1\"'),
                             ('# JVM_OPTS=\"\$JVM_OPTS -Xloggc:\/var\/log\/cassandra\/gc-`date +%%s`.log\"',
                              'JVM_OPTS=\"\$JVM_OPTS -Xloggc:\/var\/log\/cassandra\/gc-`date +%%s`.log\"'),
                             # change < to -lt for numeric comparison
                             ('if \\[ \\\"\\$JVM_VERSION\\\" \\\\< \\\"1.8\\\" \\] && \\[ \\\"\\$JVM_PATCH_VERSION\\\" \\\\< \\\"25\\\" \\] ; then',
                              'if [ \"\\$JVM_VERSION\" \\\\< \"1.8\" ] \\&\\& [ \"\\$JVM_PATCH_VERSION\" -lt \"25\" ] ; then'),
                             ('MaxTenuringThreshold=.*\"', 'MaxTenuringThreshold=30\"'), ]

        if (self.pdist == 'centos' and self.pdistversion >= '6.5') or self.pdist == 'redhat':
            env_file_settings.append(('JVM_OPTS=\"\$JVM_OPTS -Xss.*\"', 'JVM_OPTS=\"\$JVM_OPTS -Xss228k\"'))
        else:
            env_file_settings.append(('JVM_OPTS=\"\$JVM_OPTS -Xss.*\"', 'JVM_OPTS=\"\$JVM_OPTS -Xss512k\"'))

        for pattern_to_match, str_to_replace in env_file_settings:
            local("sudo sed -i 's/%s/%s/g' %s" % (pattern_to_match, str_to_replace, env_file))

    def fix_zookeeper_servers_config(self, zookeeper_ip_list, myid):
        zk_index = 1
        # Instead of inserting/deleting config, remove all the zoo keeper servers
        # and re-generate.
        local("sudo sed -i '/server.[1-9]*=/d' %s/zoo.cfg" % self.zoo_conf_dir)

        for zk_ip in zookeeper_ip_list:
            local('sudo echo "server.%d=%s:2888:3888" >> %s/zoo.cfg' %(zk_index, zk_ip, self.zoo_conf_dir))
            zk_index = zk_index + 1

        #put cluster-unique zookeeper's instance id in myid
        datadir = local('grep -oP "^dataDir=\K.*" %s/zoo.cfg' % self.zoo_conf_dir, capture=True)
        local('sudo echo "%s" > %s/myid' %(myid, datadir))

    def fixup_zookeeper_configs(self, zookeeper_ip_list=None, myid=None):
        if not zookeeper_ip_list:
            zookeeper_ip_list = self._args.zookeeper_ip_list
        if not myid:
            myid = self._args.database_index
        # set high session timeout to survive glance led disk activity
        local('sudo echo "maxSessionTimeout=120000" >> %s/zoo.cfg' % self.zoo_conf_dir)
        local('sudo echo "autopurge.purgeInterval=3" >> %s/zoo.cfg' % self.zoo_conf_dir)
        local("sudo sed 's/^#log4j.appender.ROLLINGFILE.MaxBackupIndex=/log4j.appender.ROLLINGFILE.MaxBackupIndex=/g' %s/log4j.properties > log4j.properties.new" % self.zoo_conf_dir)
        local("sudo mv log4j.properties.new %s/log4j.properties" % self.zoo_conf_dir)
        if self.pdist in ['fedora', 'centos', 'redhat']:
            local('echo export ZOO_LOG4J_PROP="INFO,CONSOLE,ROLLINGFILE" >> /usr/lib/zookeeper/bin/zkEnv.sh')
        if self.pdist == 'Ubuntu':
            local('echo ZOO_LOG4J_PROP="INFO,CONSOLE,ROLLINGFILE" >> %s/environment' % self.zoo_conf_dir)

        self.fix_zookeeper_servers_config(zookeeper_ip_list, myid)

    def check_database_down(self):
        proc = subprocess.Popen('ps auxw | grep -Eq "Dcassandra-pidfile=.*cassandra\.pid"', shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (output, errout) = proc.communicate()
        if proc.returncode == 0:
            return False
        else:
            return True

    def check_database_up(self, database_ip):
        cmds = ["cqlsh ", database_ip, " -e exit"]
        cassandra_cli_cmd = ' '.join(cmds)
        proc = subprocess.Popen(cassandra_cli_cmd, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (output, errout) = proc.communicate()

        nodetool_cmd = "nodetool status"
        nodetool_proc = subprocess.Popen(nodetool_cmd, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (output, errout) = nodetool_proc.communicate()
        if proc.returncode == 0 and nodetool_proc.returncode == 0:
            return True
        else:
            return False
