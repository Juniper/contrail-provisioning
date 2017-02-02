#!/usr/bin/env bash
if [ -f /etc/lsb-release ] && (egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release); then
    for svc in control control-nodemgr dns named; do
        chkconfig contrail-$svc off
        service contrail-$svc stop
    done
else
    chkconfig supervisor-control off
    service supervisor-control stop
fi
