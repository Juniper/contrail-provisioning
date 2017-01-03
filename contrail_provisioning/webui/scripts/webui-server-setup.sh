#!/usr/bin/env bash

#setup script for webui package under supervisord
if [ -f /etc/lsb-release ] && !(egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release); then
    chkconfig supervisor-webui on
    service supervisor-webui restart
fi
