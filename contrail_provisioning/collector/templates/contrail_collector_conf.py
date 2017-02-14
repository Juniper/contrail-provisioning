import string

template = string.Template("""#
# Copyright (c) 2014 Juniper Networks, Inc. All rights reserved.
#
# Collector configuration options
#

[DEFAULT]
# Everything in this section is optional

# Time-to-live in hours of the various data stored by collector into
# cassandra
$__contrail_analytics_data_ttl__
$__contrail_config_audit_ttl__
$__contrail_statistics_ttl__
$__contrail_flow_ttl__

# IP address and port to be used to connect to cassandra.
# Multiple IP:port strings separated by space can be provided
cassandra_server_list=$__contrail_cassandra_server_list__

# IP address and port to be used to connect to zookeeper.
# Multiple IP:port are specified as single string separated by comma
zookeeper_server_list=$__contrail_zookeeper_server_list__

# IP address and port to be used to connect to kafka.
# Multiple IP:port strings separated by space can be provided
kafka_broker_list=$__contrail_kafka_broker_list__

# IP address of analytics node. Resolved IP of 'hostname'
hostip=$__contrail_host_ip__

# Hostname of analytics node. If this is not configured value from `hostname`
# will be taken
# hostname=

# Http server port for inspecting collector state (useful for debugging)
http_server_port=$__contrail_http_server_port__

# Category for logging. Default value is '*'
# log_category=

# Local log file name
log_file=$__contrail_log_file__

# Maximum log file rollover index
# log_files_count=10

# Maximum log file size
# log_file_size=1048576 # 1MB

# Log severity levels. Possible values are SYS_EMERG, SYS_ALERT, SYS_CRIT,
# SYS_ERR, SYS_WARN, SYS_NOTICE, SYS_INFO and SYS_DEBUG. Default is SYS_DEBUG
log_level=SYS_NOTICE

# Enable/Disable local file logging. Possible values are 0 (disable) and
# 1 (enable)
log_local=1

# TCP and UDP ports to listen on for receiving syslog messages. -1 to disable.
syslog_port=$__contrail_analytics_syslog_port__

# UDP port to listen on for receiving sFlow messages. -1 to disable.
# sflow_port=6343

# UDP port to listen on for receiving ipfix messages. -1 to disable.
# ipfix_port=4739

# List of ApiServers specified as ip:port separated by space
api_server=$__contrail_api_server_list__

[COLLECTOR]
# Everything in this section is optional

# Port to listen on for receiving Sandesh messages
port=$__contrail_listen_port__

# IP address to bind to for listening
# server=0.0.0.0

# UDP port to listen on for receiving Google Protocol Buffer messages
# protobuf_port=3333

[REDIS]
# Port to connect to for communicating with redis-server
port=6379

# IP address of redis-server
server=127.0.0.1
$__contrail_redis_password__

""")
