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

function error_exit
{
    echo "${PROGNAME}: ${1:-''} ${2:-'Unknown Error'}" 1>&2
    exit ${3:-1}
}

chkconfig mysqld 2>/dev/null
ret=$?
if [ $ret -ne 0 ]; then
    echo "MySQL is not enabled, enabling ..."
    chkconfig mysqld on 2>/dev/null
fi

service mysqld status 2>/dev/null
ret=$?
if [ $ret -ne 0 ]; then
    echo "MySQL is not active, starting ..."
    service mysqld restart 2>/dev/null
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

cat > $CONF_DIR/openstackrc <<EOF
export OS_USERNAME=admin
export OS_PASSWORD=$ADMIN_TOKEN
export OS_TENANT_NAME=admin
export OS_AUTH_URL=http://$CONTROLLER:5000/v2.0/
export OS_NO_CACHE=1
EOF

if [ $CONTROLLER != $QUANTUM ] ; then
    openstack-config --set /etc/nova/nova.conf DEFAULT sql_connection mysql://nova:nova@$CONTROLLER/nova
    openstack-config --set /etc/nova/nova.conf DEFAULT qpid_hostname $CONTROLLER
    openstack-config --set /etc/nova/nova.conf DEFAULT glance_host $CONTROLLER
    openstack-config --set /etc/nova/nova.conf DEFAULT quantum_admin_tenant_name service
    openstack-config --set /etc/nova/nova.conf DEFAULT quantum_admin_username quantum
    openstack-config --set /etc/nova/nova.conf DEFAULT quantum_admin_password $SERVICE_TOKEN
    openstack-config --set /etc/nova/nova.conf DEFAULT quantum_admin_auth_url http://$CONTROLLER:35357/v2.0/
    openstack-config --set /etc/nova/nova.conf DEFAULT quantum_url http://$QUANTUM:9696/
    openstack-config --set /etc/nova/nova.conf DEFAULT quantum_url_timeout 300

    openstack-config --set /etc/nova/nova.conf keystone_authtoken admin_tenant_name service
    openstack-config --set /etc/nova/nova.conf keystone_authtoken admin_user nova
    openstack-config --set /etc/nova/nova.conf keystone_authtoken admin_password $SERVICE_TOKEN
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_host $CONTROLLER
fi

# Update all config files with service username and password
for svc in quantum; do
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_tenant_name service
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_user $svc
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_password $SERVICE_TOKEN
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken auth_host $CONTROLLER
done

openstack-config --set /etc/quantum/quantum.conf QUOTAS quota_network -1
openstack-config --set /etc/quantum/quantum.conf QUOTAS quota_subnet -1
openstack-config --set /etc/quantum/quantum.conf QUOTAS quota_port -1

openstack-config --set /etc/quantum/quantum.conf DEFAULT core_plugin quantum.plugins.contrail.ContrailPlugin.ContrailPlugin
openstack-config --set /etc/quantum/quantum.conf DEFAULT log_format '%(asctime)s.%(msecs)d %(levelname)8s [%(name)s] %(message)s'

echo "======= Enabling the services ======"

for svc in qpidd httpd memcached; do
    chkconfig $svc on
done

for svc in quantum-server; do
    chkconfig $svc on
done

echo "======= Starting the services ======"

for svc in qpidd httpd memcached; do
    service $svc restart
done

service quantum-server restart

