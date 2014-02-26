#!/usr/bin/env bash

CONFIG_FILE="/etc/contrail/collector.conf"
SIGNATURE="Collectror configuration options, generated from vizd_param"

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

(
cat << EOF
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#
# $SIGNATURE
#

[DEFAULTS]
analytics-data-ttl=0
cassandra-server=$CASSANDRA_SERVER_LIST
dup=0
hostip=$HOST_IP # Retrieved as IPv4 address of `hostname`
http-server-port=$HTTP_SERVER_PORT
listen-port=$LISTEN_PORT

[DISCOVERY]
port=5998
server=$DISCOVERY # discovery-server IP address

[REDIS]
ip=127.0.0.1
port=6381

[LOG]
category=
file=$LOG_FILE
level=SYS_DEBUG
local=1
listen-port=$ANALYTICS_SYSLOG_PORT

EOF
) > $CONFIG_FILE
