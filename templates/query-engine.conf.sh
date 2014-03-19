#!/usr/bin/env bash

CONFIG_FILE="/etc/contrail/query-engine.conf"
SIGNATURE="Query-Engine configuration options, generated from qe_pram"

# Remove old style command line arguments from .ini file.
perl -ni -e 's/command=.*/command=\/usr\/bin\/vizd/g; print $_;' /etc/contrail/supervisord_control_files/contrail-collector
perl -ni -e 's/command=.*/command=\/usr\/bin\/qed/g; print $_;' /etc/contrail/supervisord_analytics_files/qed.ini

if [ ! -e /etc/contrail/qe_param ]; then
    exit
fi

# Ignore if the converted file is already generated once before
if [ -e $CONFIG_FILE ]; then
    grep --quiet "$SIGNATURE" $CONFIG_FILE > /dev/null

    # Exit if configuraiton already converted!
    if [ $? == 0 ]; then
        exit
    fi
fi

source /etc/contrail/qe_param

if [ -z $ANALYTICS_DATA_TTL]; then
    ANALYTICS_SYSLOG_PORT=48
fi

if [ -z $HTTP_SERVER_PORT]; then
    HTTP_SERVER_PORT=8091
fi

if [ -z $REDIS_SERVER_PORT]; then
    REDIS_SERVER_PORT=6379
fi

(
cat << EOF
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#
# $SIGNATURE
#

[DEFAULT]
  analytics_data_ttl=$ANALYTICS_DATA_TTL
  cassandra_server_list=$CASSANDRA_SERVER_LIST
  collectors=$COLLECTOR:$COLLECTOR_PORT
  hostip= # Resolved IP of `hostname`
# hostname= # Retrieved as `hostname`
  http_server_port=$HTTP_SERVER_PORT
# log_category=
# log_disable=0
  log_file=$LOG_FILE
# log_files_count=10
# log_file_size=1048576 # 1MB
# log_level=SYS_NOTICE
# log_local=0
# test_mode=0

[DISCOVERY]
# port=5998
# server= # discovery_server IP address

[REDIS]
  port=$REDIS_SERVER_PORT
  server=$REDIS_SERVER

EOF
) > $CONFIG_FILE
