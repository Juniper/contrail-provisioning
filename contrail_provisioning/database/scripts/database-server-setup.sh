#!/usr/bin/env bash

#setup script for analytics package under supervisord
echo "======= Enabling the services ======"

for svc in zookeeper supervisor-database; do
    chkconfig $svc on
done

echo "======= Starting the services ======"

for svc in zookeeper supervisor-database; do
    service $svc restart
done

