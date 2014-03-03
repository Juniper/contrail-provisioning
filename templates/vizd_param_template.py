import string

template = string.Template("""
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#
# Collector configuration options
#

[DEFAULTS]
analytics-data-ttl=$__contrail_analytics_data_ttl__
cassandra-server=$__contrail_cassandra_server_list__
dup=0
hostip=$__contrail_host_ip__ # Retrieved as IPv4 address of `hostname`
http-server-port=8089
listen-port=8086

[DISCOVERY]
port=5998
server=$__contrail_discovery_ip__ # discovery-server IP address

[REDIS]
ip=127.0.0.1
port=6381

[LOG]
category=
file=/var/log/contrail/collector.log
level=SYS_DEBUG
local=1
listen-port=$__contrail_analytics_syslog_port__
""")
