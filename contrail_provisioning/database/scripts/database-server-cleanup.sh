#!/usr/bin/env bash

#cleanup script for database package under supervisord
# shutdown all the services
if [ -f /etc/lsb-release ] && egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release; then
    for svc in contrail-database-nodemgr; do
        chkconfig $svc off > /dev/null 2>&1
        service $svc stop > /dev/null 2>&1
    done
else
    for svc in zookeeper supervisor-database; do
        chkconfig $svc off > /dev/null 2>&1
        service $svc stop > /dev/null 2>&1
    done
fi

