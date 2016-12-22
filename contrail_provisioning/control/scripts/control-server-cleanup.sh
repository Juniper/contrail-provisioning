#!/usr/bin/env bash
service contrail-control stop
service contrail-dns stop
service contrail-named stop
if [ -f /etc/lsb-release ] && !(egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release); then
    chkconfig supervisor-control off
    service supervisor-control stop
fi
