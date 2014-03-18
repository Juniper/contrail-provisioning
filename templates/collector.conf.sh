#!/usr/bin/env bash

CONFIG_FILE="/etc/contrail/collector.conf"
SIGNATURE="Collector configuration options, generated from vizd_param"

# Remove old style command line arguments from .ini file.
perl -ni -e 's/command=.*/command=\/usr\/bin\/vizd/g; print $_;' /etc/contrail/supervisord_analytics_files/contrail-collector.ini

if [ ! -e /etc/contrail/vizd_param ]; then
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

source /etc/contrail/vizd_param

if [ -z $ANALYTICS_DATA_TTL]; then
    ANALYTICS_DATA_TTL=48
fi

if [ -z $ANALYTICS_SYSLOG_PORT]; then
    ANALYTICS_SYSLOG_PORT=0
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
# dup=0
  hostip=$HOST_IP # Resolved IP of `hostname`
# hostname= # Retrieved as `hostname`
  http_server_port=$HTTP_SERVER_PORT
# log_category=
# log_disable=0
  log_file=$LOG_FILE
# log_files_count=10
# log_file_size=1048576 # 1MB
# log_level=SYS_NOTICE
# log_local=0
  syslog_port=$ANALYTICS_SYSLOG_PORT
# test_mode=0

[COLLECTOR]
  port=$LISTEN_PORT
# server=0.0.0.0

[DISCOVERY]
# port=5998
  server=$DISCOVERY # discovery_server IP address

[REDIS]
  port=6381
  server=127.0.0.1

EOF
) > $CONFIG_FILE
