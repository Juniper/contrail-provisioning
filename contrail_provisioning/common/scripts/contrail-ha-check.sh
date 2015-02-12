#!/bin/bash

# Purpose of the script is to check the state of galera cluster
# Author - Sanju Abraham

while true; do
    sleep 5
    # Create the sshd empty dir if necessary
    if [ ! -d /var/run/sshd ]; then
        logger "/var/run/sshd deleted, creating it again"
        mkdir /var/run/sshd
        chmod 0755 /var/run/sshd
    fi

    /opt/contrail/bin/contrail-cmon-monitor.sh
done
