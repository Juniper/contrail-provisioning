#!/usr/bin/env bash

#restart analytics services based on distribution
if [ -f /etc/lsb-release ] && (egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release); then
    for svc in alarm-gen analytics-api analytics-nodemgr collector query-engine snmp-collector topology; do
            chkconfig contrail-$svc on
            service contrail-$svc restart
    done
else
    #setup script for analytics package under supervisord
    chkconfig supervisor-analytics on
    service supervisor-analytics restart
fi
