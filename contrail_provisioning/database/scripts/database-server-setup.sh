#!/usr/bin/env bash

#setup script for analytics package under supervisord
echo "======= Enabling the services ======"
if [ -f /etc/lsb-release ] && (egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release); then
    for svc in database database-nodemgr; do
        chkconfig contrail-$svc on
        echo "======= Starting the services ======"
        service contrail-$svc restart
    done
else
    for svc in supervisor-database contrail-database; do
        chkconfig $svc on
        echo "======= Starting the services ======"
        service $svc restart
    done
fi
