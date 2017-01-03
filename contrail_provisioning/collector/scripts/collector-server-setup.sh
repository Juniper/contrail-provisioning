#!/usr/bin/env bash

#setup script for analytics package under supervisord
if [ -f /etc/lsb-release ] && !(egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release); then
    chkconfig supervisor-analytics on
    service supervisor-analytics restart
fi

