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


source /opt/contrail/bin/contrail-lib.sh
CONF_DIR=/etc/contrail
set -x

if [ -f /etc/redhat-release ]; then
   is_redhat=1
   is_ubuntu=0
   web_svc=httpd
   mysql_svc=$(get_mysql_service_name)
   os_cinder=$(rpm -q --queryformat="%{VERSION}" openstack-cinder)
   is_kilo_or_above=$(python -c "from distutils.version import LooseVersion; \
                  print LooseVersion('$os_cinder') >= LooseVersion('2015.1.1')")
   openstack_services_contrail=''
   openstack_services_cinder='openstack-cinder-api openstack-cinder-scheduler'
fi

if [ -f /etc/lsb-release ] && egrep -q 'DISTRIB_ID.*Ubuntu' /etc/lsb-release; then
   is_ubuntu=1
   is_redhat=0
   web_svc=apache2
   mysql_svc=mysql
   os_cinder=$(dpkg-query -W -f='${Version}' cinder-api)
   is_kilo_or_above=$(python -c "from distutils.version import LooseVersion; \
                  print LooseVersion('$os_cinder') >= LooseVersion('1:2015.1.1')")
   openstack_services_contrail='supervisor-openstack'
   openstack_services_cinder='cinder-api cinder-scheduler'
fi
echo "$0: Openstack Cinder Version: ( $os_cinder )"

# Make sure mysql service is enabled
update_services "action=enable" $mysql_svc
mysql_status=`service $mysql_svc status 2>/dev/null`
if [[ "$mysql_status" != *running* ]]; then
    echo "Service ( $mysql_svc ) is not active. Restarting..."
    update_services "action=restart" $mysql_svc
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

controller_ip=$CONTROLLER
if [ "$INTERNAL_VIP" != "none" ]; then
    controller_ip=$INTERNAL_VIP
fi

if [ "$KEYSTONE_VERSION" == "v3" ]; then
cat > $CONF_DIR/openstackrc_v3 <<EOF
export OS_AUTH_URL=${AUTH_PROTOCOL}://$controller_ip:5000/v3
export OS_TENANT_NAME=admin
export OS_PROJECT_NAME="admin"
export OS_DOMAIN_NAME="Default"
export OS_USER_DOMAIN_NAME="Default"
export OS_PROJECT_DOMAIN_NAME="Default"
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
export OS_AUTH_URL=${AUTH_PROTOCOL}://$controller_ip:5000/v2.0/
export OS_NO_CACHE=1
EOF

for APP in cinder; do
    # Required only in first openstack node, as the mysql db is replicated using galera.
    if [ "$OPENSTACK_INDEX" -eq 1 ]; then
        openstack-db -y --init --service $APP --password $SERVICE_DBPASS --rootpw "$MYSQL_TOKEN"
    fi
done

export ADMIN_TOKEN
export SERVICE_TOKEN



# Update all config files with service username and password
for svc in cinder; do

    # If cinder is Kilo based, need additional settings
    if [ "$is_kilo_or_above" == "True" ]; then
        openstack-config --set /etc/$svc/$svc.conf keystone_authtoken \
                               auth_uri $AUTH_PROTOCOL://${controller_ip}:5000/$KEYSTONE_VERSION
        openstack-config --set /etc/$svc/$svc.conf keystone_authtoken \
                               identity_uri $AUTH_PROTOCOL://${controller_ip}:35357
        admin_user='cinderv2'
    else
        admin_user='cinder'
    fi

    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_tenant_name service
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_user $admin_user
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_password $ADMIN_TOKEN
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken auth_protocol $AUTH_PROTOCOL
    if [ $KEYSTONE_INSECURE == "True" ]; then
        openstack-config --set /etc/$svc/$svc.conf keystone_authtoken insecure $KEYSTONE_INSECURE
    fi
    if [ "$INTERNAL_VIP" != "none" ]; then
        openstack-config --set /etc/$svc/$svc.conf keystone_authtoken auth_host $INTERNAL_VIP
        openstack-config --set /etc/$svc/$svc.conf keystone_authtoken auth_port 5000
        openstack-config --set /etc/$svc/$svc.conf DEFAULT osapi_volume_listen_port 9776
        openstack-config --set /etc/$svc/$svc.conf database idle_timeout 180
        openstack-config --set /etc/$svc/$svc.conf database min_pool_size 100
        openstack-config --set /etc/$svc/$svc.conf database max_pool_size 700
        openstack-config --set /etc/$svc/$svc.conf database max_overflow 100
        openstack-config --set /etc/$svc/$svc.conf database retry_interval 5
        openstack-config --set /etc/$svc/$svc.conf database max_retries -1
        openstack-config --set /etc/$svc/$svc.conf database db_max_retries 3
        openstack-config --set /etc/$svc/$svc.conf database db_retry_interval 1
        openstack-config --set /etc/$svc/$svc.conf database connection_debug 10
        openstack-config --set /etc/$svc/$svc.conf database pool_timeout 120
    fi
done

echo "======= Enabling the services ======"
update_services "action=enable" $web_svc memcached $openstack_services_contrail $openstack_services_cinder

echo "======= Starting the services ======"
update_services "action=restart" $web_svc memcached

# Listen at supervisor-openstack port
listen_on_supervisor_openstack_port

# Start cinder services
update_services "action=restart" $openstack_services_cinder
