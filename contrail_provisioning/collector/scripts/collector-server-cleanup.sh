#!/usr/bin/env bash

#cleanup script for analytics package under supervisord

for svc in contrail-collector contrail-analytics-api ; do
    service $svc stop
done
chkconfig supervisor-analytics off
service supervisor-analytics stop
