#!/usr/bin/env bash

if [ -f /etc/lsb-release ]; then
    if (egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release); then
        for svc in nova-compute contrail-vrouter-agent contrail-vrouter-nodemgr; do
            chkconfig $svc off
            service $svc stop
        done
    else
        for svc in nova-compute supervisor-vrouter; do
            chkconfig $svc off
            service $svc stop
        done
    fi
else
    for svc in openstack-nova-compute supervisor-vrouter; do
        chkconfig $svc off
        service $svc stop
    done
fi
