#!/usr/bin/env bash

#setup script for analytics package under supervisord
echo "======= Enabling the services ======"

#for svc in supervisor-database contrail-database; do
if [ -f /etc/lsb-release ] && egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release; then
    for svc in contrail-database; do
        chkconfig $svc on
    done
else
    for svc in supervisor-database contrail-database; do
        chkconfig $svc on
    done
fi

echo "======= Starting the services ======"

#for svc in supervisor-database contrail-database; do
if [ -f /etc/lsb-release ] && egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release; then
    for svc in contrail-database; do
        service $svc restart
    done
else
    for svc in supervisor-database contrail-database; do
        service $svc restart
    done
fi
