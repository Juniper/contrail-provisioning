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

if [ -f /etc/lsb-release ]; then
   is_ubuntu=1
   is_redhat=0
   web_svc=apache2
   mysql_svc=mysql
fi

msg_svc=rabbitmq-server
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

# Update all config files with service username and password
if [ -d /etc/neutron ]; then
    net_svc_name='neutron'
else
    net_svc_name='quantum'
fi

for svc in $net_svc_name; do
    openstack-config --set /etc/$svc/$svc.conf DEFAULT bind_port $QUANTUM_PORT
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_tenant_name service
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_user $svc
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_password $SERVICE_TOKEN
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken auth_host $CONTROLLER
done

openstack-config --set /etc/$net_svc_name/$net_svc_name.conf QUOTAS quota_network -1
openstack-config --set /etc/$net_svc_name/$net_svc_name.conf QUOTAS quota_subnet -1
openstack-config --set /etc/$net_svc_name/$net_svc_name.conf QUOTAS quota_port -1

if [ -d /etc/neutron ]; then
    openstack-config --set /etc/neutron/neutron.conf DEFAULT core_plugin neutron.plugins.juniper.contrail.contrailplugin.ContrailPlugin
    openstack-config --set /etc/neutron/neutron.conf DEFAULT rabbit_host $CONTROLLER
else
    openstack-config --set /etc/quantum/quantum.conf DEFAULT core_plugin quantum.plugins.contrail.ContrailPlugin.ContrailPlugin
fi

openstack-config --set /etc/$net_svc_name/$net_svc_name.conf DEFAULT log_format '%(asctime)s.%(msecs)d %(levelname)8s [%(name)s] %(message)s'

echo "======= Enabling the services ======"

for svc in $msg_svc $web_svc memcached; do
    chkconfig $svc on
done

for svc in $net_svc_name-server; do
    chkconfig $svc on
done

echo "======= Starting the services ======"

for svc in $msg_svc $web_svc memcached; do
    service $svc restart
done

service $net_svc_name-server restart

