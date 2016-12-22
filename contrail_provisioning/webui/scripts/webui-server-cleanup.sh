#!/usr/bin/env bash

#cleanup script for webui package under supervisord

for svc in contrail-webui contrail-webui-middleware; do
    service $svc stop
done
if [ -f /etc/lsb-release ] && !(egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release); then
    chkconfig supervisor-webui off
    service supervisor-webui stop
fi
