#!/usr/bin/env bash

#cleanup script for webui package under supervisord

if [ -f /etc/lsb-release ] && (egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release); then
    for svc in webui webui-middleware; do
        chkconfig contrail-$svc off
        service contrail-$svc stop
    done
else
    chkconfig supervisor-webui off
    service supervisor-webui stop
fi
