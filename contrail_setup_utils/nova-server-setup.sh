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
   nova_pfx=openstack-nova
   nova_api_ver=`rpm -q --qf  "%{VERSION}\n" openstack-nova-api`
   echo $nova_api_ver
   if [ "$nova_api_ver" == "2013.1" ]; then
   	OS_NET=quantum
   	TENANT_NAME=quantum_admin_tenant_name
   	ADMIN_USER=quantum_admin_username
   	ADMIN_PASSWD=quantum_admin_password
   	ADMIN_AUTH_URL=quantum_admin_auth_url
   	OS_URL=quantum_url
   	OS_URL_TIMEOUT=quantum_url_timeout
   	META_DATA_PROXY=service_quantum_metadata_proxy
   else
   	OS_NET=neutron
   	TENANT_NAME=neutron_admin_tenant_name
   	ADMIN_USER=neutron_admin_username
   	ADMIN_PASSWD=neutron_admin_password
   	ADMIN_AUTH_URL=neutron_admin_auth_url
   	OS_URL=neutron_url
   	OS_URL_TIMEOUT=neutron_url_timeout
   	META_DATA_PROXY=service_neutron_metadata_proxy
   fi
fi

if [ -f /etc/lsb-release ] && egrep -q 'DISTRIB_ID.*Ubuntu' /etc/lsb-release; then
   is_ubuntu=1
   is_redhat=0
   web_svc=apache2
   mysql_svc=mysql
   nova_pfx=nova
   nova_api_version=`dpkg -l | grep 'ii' | grep nova-api | awk '{print $3}'`
   echo $nova_api_version
   if [ "$nova_api_version" == "2:2013.1.3-0ubuntu1" ]; then
   	OS_NET=quantum
   	TENANT_NAME=quantum_admin_tenant_name
   	ADMIN_USER=quantum_admin_username
   	ADMIN_PASSWD=quantum_admin_password
   	ADMIN_AUTH_URL=quantum_admin_auth_url
   	OS_URL=quantum_url
  	OS_URL_TIMEOUT=quantum_url_timeout
   	META_DATA_PROXY=service_quantum_metadata_proxy
   else
   	OS_NET=neutron
   	TENANT_NAME=neutron_admin_tenant_name
   	ADMIN_USER=neutron_admin_username
   	ADMIN_PASSWD=neutron_admin_password
   	ADMIN_AUTH_URL=neutron_admin_auth_url
   	OS_URL=neutron_url
   	OS_URL_TIMEOUT=neutron_url_timeout
   	META_DATA_PROXY=service_neutron_metadata_proxy
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

cat > $CONF_DIR/openstackrc <<EOF
export OS_USERNAME=admin
export OS_PASSWORD=$ADMIN_TOKEN
export OS_TENANT_NAME=admin
export OS_AUTH_URL=${AUTH_PROTOCOL}://$CONTROLLER:5000/v2.0/
export OS_NO_CACHE=1
EOF

# must set SQL connection before running nova-manage
if [ $is_ubuntu -eq 0 ] ; then
    openstack-config --set /etc/nova/nova.conf DEFAULT sql_connection mysql://nova:nova@127.0.0.1/nova
fi
openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_nonblocking True 
openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_inject_partition -1

for APP in nova; do
  openstack-db -y --init --service $APP --rootpw "$MYSQL_TOKEN"
done

export ADMIN_TOKEN
export SERVICE_TOKEN

# Update all config files with service username and password
for svc in nova; do
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_tenant_name service
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_user $svc
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_password $SERVICE_TOKEN
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_protocol http
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_host 127.0.0.1
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_port 35357
    openstack-config --set /etc/nova/nova.conf keystone_authtoken signing_dir /tmp/keystone-signing-nova
    openstack-config --set /etc/nova/nova.conf keystone_authtoken rabbit_host $CONTROLLER
done

openstack-config --set /etc/nova/nova.conf DEFAULT $TENANT_NAME service
openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_USER $OS_NET
openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_PASSWD $SERVICE_TOKEN
openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_AUTH_URL ${AUTH_PROTOCOL}://$CONTROLLER:35357/v2.0/
openstack-config --set /etc/nova/nova.conf DEFAULT $OS_URL ${QUANTUM_PROTOCOL}://$QUANTUM:9696/
openstack-config --set /etc/nova/nova.conf DEFAULT $OS_URL_TIMEOUT 300
openstack-config --set /etc/nova/nova.conf DEFAULT security_group_api $OS_NET
openstack-config --set /etc/nova/nova.conf DEFAULT osapi_compute_workers 40
openstack-config --set /etc/nova/nova.conf DEFAULT $META_DATA_PROXY True
openstack-config --set /etc/nova/nova.conf conductor workers 40

openstack-config --set /etc/nova/nova.conf DEFAULT compute_driver libvirt.LibvirtDriver
openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_vif_driver nova_contrail_vif.contrailvif.VRouterVIFDriver
# Use noopdriver for firewall
openstack-config --set /etc/nova/nova.conf DEFAULT firewall_driver nova.virt.firewall.NoopFirewallDriver

# Hack till we have synchronized time (config node as ntp server). Without this
# utils.py:service_is_up() barfs and instance deletes not fwded to compute node
openstack-config --set /etc/nova/nova.conf DEFAULT service_down_time 100000

openstack-config --set /etc/nova/nova.conf DEFAULT sql_max_retries -1

openstack-config --set /etc/nova/nova.conf DEFAULT novncproxy_port 5999
openstack-config --set /etc/nova/nova.conf DEFAULT novncproxy_host 0.0.0.0

openstack-config --set /etc/nova/nova.conf DEFAULT quota_instances 100000
openstack-config --set /etc/nova/nova.conf DEFAULT quota_cores 100000
openstack-config --set /etc/nova/nova.conf DEFAULT quota_ram 10000000

if [ $is_ubuntu -eq 1 ] ; then
    openstack-config --set /etc/nova/nova.conf DEFAULT auth_strategy keystone
    if [ "$nova_api_version" == "2:2013.1.3-0ubuntu1" ]; then
        openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova.network.quantumv2.api.API
    else
        openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova.network.neutronv2.api.API
    fi
    openstack-config --set /etc/nova/nova.conf DEFAULT ec2_private_dns_show_ip False
fi

echo "======= Enabling the services ======"

for svc in rabbitmq-server $web_svc memcached; do
    chkconfig $svc on
done

for svc in api objectstore scheduler cert consoleauth novncproxy conductor; do
    chkconfig $nova_pfx-$svc on
done

echo "======= Starting the services ======"

for svc in rabbitmq-server $web_svc memcached; do
    service $svc restart
done

for svc in api objectstore scheduler cert consoleauth novncproxy conductor; do
    service $nova_pfx-$svc restart
done
