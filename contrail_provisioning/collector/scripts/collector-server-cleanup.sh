#!/usr/bin/env bash

#cleanup script for analytics package under supervisord

for svc in contrail-collector contrail-analytics-api ; do
    service $svc stop
done

if [ -f /etc/lsb-release ] && !(egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release); then
    chkconfig supervisor-analytics off
    service supervisor-analytics stop
fi
