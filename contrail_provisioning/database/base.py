#!/usr/bin/python
#
# Copyright (c) 2016 Juniper Networks, Inc. All rights reserved.
#

import os

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

    def fixup_cassandra_config_file(self, listen_ip, seed_list, data_dir,
                                    ssd_data_dir, cluster_name='Contrail',
                                    user=None):

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
