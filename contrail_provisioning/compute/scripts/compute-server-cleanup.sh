#!/usr/bin/env bash

if [ -f /etc/lsb-release ] && !(egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release); then
    for svc in openstack-nova-compute supervisor-vrouter; do
        chkconfig $svc off
    done

    for svc in openstack-nova-compute supervisor-vrouter; do
        service $svc stop
    done
fi
