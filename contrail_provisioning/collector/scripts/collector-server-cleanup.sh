#!/usr/bin/env bash

#cleanup script for analytics package under supervisord

for svc in contrail-collector contrail-analytics-api ; do
    supervisorctl -s unix:///tmp/supervisord_analytics.sock stop $svc
done
chkconfig supervisor-analytics off
service supervisor-analytics stop
