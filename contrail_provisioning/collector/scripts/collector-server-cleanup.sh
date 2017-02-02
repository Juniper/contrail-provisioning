#!/usr/bin/env bash

if [ -f /etc/lsb-release ] && (egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release); then
    for svc in alarm-gen analytics-api analytics-nodemgr collector query-engine snmp-collector topology; do
        chkconfig contrail-$svc off
        service contrail-$svc stop
    done
else
    #cleanup script for analytics package under supervisord
    chkconfig supervisor-analytics off
    service supervisor-analytics stop
fi
