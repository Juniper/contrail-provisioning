#!/usr/bin/env bash

CONFIG_FILE="/etc/contrail/control-node.conf"
SIGNATURE="Control-node configuration options, generated from control_param"

# Remove old style command line arguments from .ini file.
perl -ni -e 's/command=.*/command=\/usr\/bin\/control-node/g; print $_;' /etc/contrail/supervisord_control_files/contrail-control.ini

if [ ! -e /etc/contrail/control_param ]; then
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

source /etc/contrail/control_param

(
cat << EOF
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#
# $SIGNATURE
#

[DEFAULT]
# bgp_config_file=bgp_config.xml
# bgp_port=179
  hostip=$HOSTIP # Resolved IP of `hostname`
  hostname=$HOSTNAME # Retrieved as `hostname`
# http_server_port=8083
# log_category=
# log_disable=0
  log_file=$LOGFILE
# log_file_size=10485760 # 10MB
# log_level=SYS_NOTICE
# log_local=0
# xmpp_server_port=5269

[COLLECTOR]
# port=8086
# server= # Provided by discovery server

[DISCOVERY]
# port=5998
  server=$DISCOVERY # discovery-server IP address

[IFMAP]
  certs-store=$CERT_OPTS
  password=$IFMAP_PASWD
# server_url= # Provided by discovery server, e.g. https://127.0.0.1:8443
  user=$IFMAP_USER


EOF
) > $CONFIG_FILE
