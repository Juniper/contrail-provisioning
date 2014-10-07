#!/usr/bin/env bash

#cleanup script for webui package under supervisord

for svc in contrail-webui contrail-webui-middleware; do
    supervisorctl -s unix:///tmp/supervisord_webui.sock stop $svc
done

chkconfig supervisor-webui off
service supervisor-webui stop
