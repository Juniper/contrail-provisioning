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
   mysql_svc=mysqld
fi

if [ -f /etc/lsb-release ] && egrep -q 'DISTRIB_ID.*Ubuntu' /etc/lsb-release; then
   is_ubuntu=1
   is_redhat=0
   is_xenial=0
   ubuntu_mitaka_or_above=0
   web_svc=apache2
   mysql_svc=mysql
   barbican_api_ver=`dpkg -l | grep 'ii' | grep barbican-api | awk '{print $3}'`
   echo $barbican_api_ver
   if [ -f /etc/lsb-release ] && egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release; then
      is_xenial=1
   fi
   keystone_version=`dpkg -l keystone | grep 'ii' | grep -v python | awk '{print $3}'`
   if [[ $keystone_version == *":"* ]]; then
       keystone_version_without_epoch=`echo $keystone_version | cut -d':' -f2 | cut -d'-' -f1`
       keystone_top_ver=`echo $keystone_version | cut -d':' -f1`
   else
       keystone_version_without_epoch=`echo $keystone_version`
   fi
   if [ $keystone_top_ver -gt 1 ]; then
       dpkg --compare-versions $keystone_version_without_epoch ge 9.0.0
       if [ $? -eq 0 ]; then
           ubuntu_mitaka_or_above=1
       fi
   fi
fi

function error_exit
{
    echo "${PROGNAME}: ${1:-''} ${2:-'Unknown Error'}" 1>&2
    exit ${3:-1}
}

chkconfig $mysql_svc 2>/dev/null
ret=$?
if [ $ret -ne 0 ]; then
    echo "MySQL is not enabled, enabling ..."
    chkconfig $mysql_svc on 2>/dev/null
fi

mysql_status=`service $mysql_svc status 2>/dev/null`
if [[ $mysql_status != *running* ]]; then
    echo "MySQL is not active, starting ..."
    service $mysql_svc restart 2>/dev/null
fi


# Use MYSQL_ROOT_PW from the environment or generate a new password
if [ ! -f $CONF_DIR/mysql.token ]; then
    if [ -n "$MYSQL_ROOT_PW" ]; then
        MYSQL_TOKEN=$MYSQL_ROOT_PW
    else
        MYSQL_TOKEN=$(openssl rand -hex 10)
    fi
    echo $MYSQL_TOKEN > $CONF_DIR/mysql.token
    chmod 400 $CONF_DIR/mysql.token
    echo show databases |mysql -u root &> /dev/null
    if [ $? -eq 0 ] ; then
        mysqladmin password $MYSQL_TOKEN
    else
        error_exit ${LINENO} "MySQL root password unknown, reset and retry"
    fi
else
    MYSQL_TOKEN=$(cat $CONF_DIR/mysql.token)
fi

source /etc/contrail/ctrl-details

# Check if ADMIN/SERVICE Password has been set
ADMIN_TOKEN=${ADMIN_TOKEN:-contrail123}
SERVICE_TOKEN=${SERVICE_TOKEN:-$(cat $CONF_DIR/service.token)}
OPENSTACK_INDEX=${OPENSTACK_INDEX:-0}
INTERNAL_VIP=${INTERNAL_VIP:-none}
AUTH_PROTOCOL=${AUTH_PROTOCOL:-http}
KEYSTONE_INSECURE=${KEYSTONE_INSECURE:-False}
AMQP_PORT=5672
if [ "$CONTRAIL_INTERNAL_VIP" == "$AMQP_SERVER" ] || [ "$INTERNAL_VIP" == "$AMQP_SERVER" ]; then
    AMQP_PORT=5673
fi

keystone_ip=$KEYSTONE_SERVER

if [ "$KEYSTONE_VERSION" == "v3" ]; then
cat > $CONF_DIR/openstackrc_v3 <<EOF
export OS_AUTH_URL=${AUTH_PROTOCOL}://$keystone_ip:5000/v3
export OS_USER_DOMAIN_NAME="Default"
export OS_PROJECT_DOMAIN_NAME="Default"
export OS_DOMAIN_NAME=Default
export OS_IDENTITY_API_VERSION="3"
export OS_USERNAME=admin
export OS_PASSWORD=$ADMIN_TOKEN
export OS_NO_CACHE=1
EOF
fi
cat > $CONF_DIR/openstackrc <<EOF
export OS_USERNAME=admin
export OS_PASSWORD=$ADMIN_TOKEN
export OS_TENANT_NAME=admin
export OS_AUTH_URL=$AUTH_PROTOCOL://$keystone_ip:5000/v2.0/
export OS_NO_CACHE=1
EOF

export ADMIN_TOKEN
export SERVICE_TOKEN

openstack-config --set /etc/barbican/barbican.conf DEFAULT sql_connection sqlite:////var/lib/barbican/barbican.sqlite 
openstack-config --set /etc/barbican/barbican-api-paste.ini composite:main /v1 barbican-api-keystone
openstack-config --set /etc/barbican/barbican-api-paste.ini filter:keystone_authtoken identity_uri $AUTH_PROTOCOL://localhost:35357
openstack-config --set /etc/barbican/barbican-api-paste.ini filter:keystone_authtoken admin_tenant_name service
openstack-config --set /etc/barbican/barbican-api-paste.ini filter:keystone_authtoken admin_user barbican
openstack-config --set /etc/barbican/barbican-api-paste.ini filter:keystone_authtoken admin_password $ADMIN_TOKEN
openstack-config --set /etc/barbican/barbican-api-paste.ini filter:keystone_authtoken auth_version $KEYSTONE_VERSION
openstack-config --set /etc/barbican/barbican.conf DEFAULT host_href http://$CONTROLLER:9311
openstack-config --set /etc/barbican/barbican.conf DEFAULT rabbit_hosts $AMQP_SERVER:$AMQP_PORT

if [ "$INTERNAL_VIP" != "none" ]; then
     openstack-config --set /etc/barbican/barbican-api-paste.ini filter:keystone_authtoken identity_uri $AUTH_PROTOCOL://$INTERNAL_VIP:35357
     openstack-config --set /etc/barbican/barbican.conf DEFAULT host_href http://$INTERNAL_VIP:9311
     openstack-config --set /etc/barbican/barbican.conf database idle_timeout 180
     openstack-config --set /etc/barbican/barbican.conf database min_pool_size 100
     openstack-config --set /etc/barbican/barbican.conf database max_pool_size 350
     openstack-config --set /etc/barbican/barbican.conf database max_overflow 700
     openstack-config --set /etc/barbican/barbican.conf database retry_interval 5
     openstack-config --set /etc/barbican/barbican.conf database max_retries -1
     openstack-config --set /etc/barbican/barbican.conf database db_max_retries 3
     openstack-config --set /etc/barbican/barbican.conf database db_retry_interval 1
     openstack-config --set /etc/barbican/barbican.conf database connection_debug 10
     openstack-config --set /etc/barbican/barbican.conf database pool_timeout 120

     openstack-config --set /etc/barbican/barbican.conf DEFAULT rabbit_retry_interval 10
     openstack-config --set /etc/barbican/barbican.conf DEFAULT rabbit_retry_backoff 5
     openstack-config --set /etc/barbican/barbican.conf DEFAULT rabbit_max_retries 0
     openstack-config --set /etc/barbican/barbican.conf DEFAULT rabbit_ha_queues True

     openstack-config --set /etc/barbican/barbican.conf DEFAULT bind_port 9322
fi

echo "======= Enabling the services ======"

for svc in $web_svc memcached; do
    chkconfig $svc on
done

if [ $is_xenial -ne 1 ] ; then
    for svc in supervisor-openstack; do
        chkconfig $svc on
    done
fi

echo "======= Starting the services ======"

for svc in $web_svc memcached; do
    service $svc restart
done

# Listen at supervisor-openstack port
if [ $is_xenial -ne 1 ] ; then
    status=$(service supervisor-openstack status | grep -s -i running >/dev/null 2>&1  && echo "running" || echo "stopped")
    if [ $status == 'stopped' ]; then
        service supervisor-openstack start
        sleep 5
        if [ -e /tmp/supervisord_openstack.sock ]; then
            supervisorctl -s unix:///tmp/supervisord_openstack.sock stop all
        else
            supervisorctl -s unix:///var/run/supervisord_openstack.sock stop all
        fi
    fi
fi

# Start barbican services
if [[ $is_xenial -eq 1 ]] || [[ $ubuntu_mitaka_or_above -eq 1 ]]; then
    svc='apache2'
else
    svc='barbican-api barbican-worker'
fi

for s in "$svc"; do
    service $s restart
done

