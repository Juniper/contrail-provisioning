#!/usr/bin/env bash

#setup script for webui package under supervisord
if [ -f /etc/lsb-release ] && (egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release); then
    for svc in webui webui-middleware; do
        chkconfig contrail-$svc on
        service contrail-$svc restart
    done
else
    chkconfig supervisor-webui on
    service supervisor-webui restart
fi
