#!/usr/bin/env bash

#cleanup script for webui package under supervisord

for svc in contrail-webui contrail-webui-middleware; do
    service $svc stop
done

chkconfig supervisor-webui off
service supervisor-webui stop
