#!/usr/bin/env bash

# Copyright 2012 OpenStack LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


CONF_DIR=/etc/contrail
set -x

if [ -f /etc/redhat-release ]; then
   is_redhat=1
   is_ubuntu=0
   web_svc=httpd
fi

if [ -f /etc/lsb-release ] && egrep -q 'DISTRIB_ID.*Ubuntu' /etc/lsb-release; then
   is_ubuntu=1
   is_redhat=0
   web_svc=apache2
fi

# Create link /usr/bin/nodejs to /usr/bin/node
if [ ! -f /usr/bin/nodejs ]; then 
    ln -s /usr/bin/node /usr/bin/nodejs
fi

echo "======= Enabling the services ======"

for svc in rabbitmq-server $web_svc memcached; do
    chkconfig $svc on
done

if [ $is_ubuntu -eq 1 ] && (egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release); then
    for svc in api config-nodemgr device-manager discovery schema svc-monitor; do
        chkconfig contrail-$svc on
    done 
    for svc in ifmap; do
        chkconfig $svc on
    done 
else
    for svc in supervisor-support-service supervisor-config; do
        chkconfig $svc on
    done
fi

echo "======= Starting the services ======"

for svc in rabbitmq-server $web_svc memcached; do
    service $svc restart
done

# TODO: move dependency to service script
# wait for ifmap server to start
if [ -f /etc/lsb-release ] && !(egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release); then
tries=0
while [ $tries -lt 10 ]; do
    wget -O- http://localhost:8443 >/dev/null 2>&1
    if [ $? -eq 0 ]; then break; fi
    tries=$(($tries + 1))
    sleep 1
done
fi

if [ $is_ubuntu -eq 1 ] && (egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release); then
    for svc in api config-nodemgr device-manager discovery schema svc-monitor; do
        service contrail-$svc restart
    done 
    for svc in ifmap; do
        service $svc restart
    done
else
    for svc in supervisor-config; do
        service $svc restart
    done
fi

