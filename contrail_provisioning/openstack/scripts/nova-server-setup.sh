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
source /opt/contrail/bin/contrail-openstack-lib.sh

CONF_DIR=/etc/contrail
set -x

if [ -f /etc/redhat-release ]; then
   is_redhat=1
   is_ubuntu=0
   web_svc=httpd
   mysql_svc=$(get_mysql_service_name)
   nova_api_ver=`rpm -q --qf  "%{VERSION}\n" openstack-nova-api`
   echo $nova_api_ver
   rpm_mitaka_or_higher=$(is_installed_rpm_greater openstack-nova-api "1 13.0.0 1.el7" && echo 1 || echo 0)
   rpm_liberty_or_higher=$(is_installed_rpm_greater openstack-nova-api "1 8.0.1 1.el7" && echo 1 || echo 0)
   rpm_icehouse_or_higher=$(is_installed_rpm_greater openstack-nova-api "0 2014.1.1 1.el7" && echo 1 || echo 0)
   rpm_kilo_or_higher=$(is_installed_rpm_greater openstack-nova-api "0 2015.1.1 1.el7" && echo 1 || echo 0)
   rpm_juno_or_higher=$(is_installed_rpm_greater openstack-nova-api "0 2014.2.1 1.el7" && echo 1 || echo 0)
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
        # remove quantum related configs if any in the nova.conf
        openstack-config --del /etc/nova/nova.conf DEFAULT quantum_admin_tenant_name
        openstack-config --del /etc/nova/nova.conf DEFAULT quantum_admin_username
        openstack-config --del /etc/nova/nova.conf DEFAULT quantum_admin_password
        openstack-config --del /etc/nova/nova.conf DEFAULT quantum_admin_auth_url
        openstack-config --del /etc/nova/nova.conf DEFAULT quantum_auth_strategy
        openstack-config --del /etc/nova/nova.conf DEFAULT quantum_url
   fi
   openstack_services_contrail=''
   openstack_services_nova='openstack-nova-api openstack-nova-cert
                            openstack-nova-conductor openstack-nova-consoleauth
                            openstack-nova-console openstack-nova-novncproxy
                            openstack-nova-objectstore openstack-nova-scheduler'
fi

if [ -f /etc/lsb-release ] && egrep -q 'DISTRIB_ID.*Ubuntu' /etc/lsb-release; then
   is_ubuntu=1
   is_redhat=0
   web_svc=apache2
   mysql_svc=mysql
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
        # remove quantum related configs if any in the nova.conf
        openstack-config --del /etc/nova/nova.conf DEFAULT quantum_admin_tenant_name
        openstack-config --del /etc/nova/nova.conf DEFAULT quantum_admin_username
        openstack-config --del /etc/nova/nova.conf DEFAULT quantum_admin_password
        openstack-config --del /etc/nova/nova.conf DEFAULT quantum_admin_auth_url
        openstack-config --del /etc/nova/nova.conf DEFAULT quantum_auth_strategy
        openstack-config --del /etc/nova/nova.conf DEFAULT quantum_url
   fi
   openstack_services_contrail='supervisor-openstack'
   openstack_services_nova='nova-api nova-scheduler
                            nova-console nova-consoleauth
                            nova-novncproxy nova-conductor'
fi

is_liberty_or_above=0
is_mitaka_or_above=0
nova_version=`echo $nova_api_version | cut -d':' -f2 | cut -d'-' -f1`
nova_top_ver=`echo $nova_api_version | cut -d':' -f1`
if [ $is_ubuntu -eq 1 ]; then
    if [ $nova_top_ver -gt 1 ]; then
        is_liberty_or_above=1
        dpkg --compare-versions $nova_version eq 13.0.0
        if [ $? -eq 0 ]; then
            is_mitaka_or_above=1
        fi
    fi
fi

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
CONTRAIL_INTERNAL_VIP=${CONTRAIL_INTERNAL_VIP:-none}
AUTH_PROTOCOL=${AUTH_PROTOCOL:-http}
KEYSTONE_INSECURE=${KEYSTONE_INSECURE:-False}
AMQP_PORT=5672
if [ "$CONTRAIL_INTERNAL_VIP" == "$AMQP_SERVER" ] || [ "$INTERNAL_VIP" == "$AMQP_SERVER" ]; then
    AMQP_PORT=5673
fi

controller_ip=$CONTROLLER
if [ "$INTERNAL_VIP" != "none" ]; then
    controller_ip=$INTERNAL_VIP
fi

if [ "$KEYSTONE_VERSION" == "v3" ]; then
cat > $CONF_DIR/openstackrc_v3 <<EOF
export OS_AUTH_URL=${AUTH_PROTOCOL}://$controller_ip:5000/v3
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
export OS_AUTH_URL=${AUTH_PROTOCOL}://$controller_ip:5000/v2.0/
export OS_NO_CACHE=1
EOF

# must set SQL connection before running nova-manage
openstack-config --set /etc/nova/nova.conf database connection mysql://nova:$SERVICE_DBPASS@127.0.0.1/nova
if [ $is_mitaka_or_above -eq 1 ];then
    openstack-config --set /etc/nova/nova.conf api_database connection mysql://nova:$SERVICE_DBPASS@127.0.0.1/nova_api
fi

# For Centos, from mitaka onwards set connection variable for database and api_database
if [[ $rpm_mitaka_or_higher -eq 1 ]]; then
    contrail-config --set /etc/nova/nova.conf api_database connection mysql+pymysql://nova:$SERVICE_DBPASS@$CONTROLLER/nova_api
    contrail-config --set /etc/nova/nova.conf database connection mysql+pymysql://nova:$SERVICE_DBPASS@$CONTROLLER/nova
fi

openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_nonblocking True 
openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_inject_partition -1
openstack-config --set /etc/nova/nova.conf DEFAULT connection_type libvirt

if [ "$INTERNAL_VIP" != "none" ]; then
    # must set SQL connection before running nova-manage
    openstack-config --set /etc/nova/nova.conf database connection mysql://nova:$SERVICE_DBPASS@$INTERNAL_VIP:33306/nova
    if [ $is_mitaka_or_above -eq 1 ];then
        openstack-config --set /etc/nova/nova.conf api_database connection mysql://nova:$SERVICE_DBPASS@$INTERNAL_VIP:33306/nova_api
    fi
fi

# For Centos7, From Mitaka, Initializing nova_api db
# Also dont use openstack-db to initialize nova db
if [[ $rpm_mitaka_or_higher -eq 1 ]]; then
    if [[ $OPENSTACK_INDEX -eq 1 ]]; then
        contrail_openstack_db "db_user=nova_api; \
                               db_name=api_db; \
                               db_username=nova; \
                               db_root_pw=$(cat /etc/contrail/mysql.token); \
                               db_user_pw=$SERVICE_DBPASS; \
                               db_sync_cmd=nova-manage;"

        contrail_openstack_db "db_user=nova; \
                               db_name=db; \
                               db_username=nova; \
                               db_root_pw=$(cat /etc/contrail/mysql.token); \
                               db_user_pw=$SERVICE_DBPASS; \
                               db_sync_cmd=nova-manage;"
    fi
else
    for APP in nova; do
        # Required only in first openstack node, as the mysql db is replicated using galera.
        if [ "$OPENSTACK_INDEX" -eq 1 ]; then
            openstack-db -y --init --service $APP --password $SERVICE_DBPASS --rootpw "$MYSQL_TOKEN"
        fi
    done
fi

if [ $is_mitaka_or_above -eq 1 ]; then
    openstack-db -y --init --service nova_api --password $SERVICE_DBPASS --rootpw "$MYSQL_TOKEN"
fi

export ADMIN_TOKEN
export SERVICE_TOKEN

# Update all config files with service username and password
for svc in nova; do
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_tenant_name service
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_user $svc
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_password $ADMIN_TOKEN
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken auth_protocol $AUTH_PROTOCOL
    if [ $AUTH_PROTOCOL == "https" ]; then
        openstack-config --set /etc/$svc/$svc.conf keystone_authtoken insecure True
        openstack-config --set /etc/$svc/$svc.conf DEFAULT insecure True
    fi
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken auth_host 127.0.0.1
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken auth_port 35357
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken signing_dir /tmp/keystone-signing-nova
done

openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_host $AMQP_SERVER
openstack-config --set /etc/nova/nova.conf DEFAULT $TENANT_NAME service
openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_USER $OS_NET
openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_PASSWD $ADMIN_TOKEN
openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_AUTH_URL ${AUTH_PROTOCOL}://$CONTROLLER:35357/$KEYSTONE_VERSION/
openstack-config --set /etc/nova/nova.conf DEFAULT $OS_URL ${QUANTUM_PROTOCOL}://$QUANTUM:9696/
openstack-config --set /etc/nova/nova.conf DEFAULT $OS_URL_TIMEOUT 300
openstack-config --set /etc/nova/nova.conf DEFAULT security_group_api $OS_NET
openstack-config --set /etc/nova/nova.conf DEFAULT osapi_compute_workers $OSAPI_COMPUTE_WORKERS
openstack-config --set /etc/nova/nova.conf DEFAULT $META_DATA_PROXY True
openstack-config --set /etc/nova/nova.conf conductor workers $CONDUCTOR_WORKERS

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

openstack-config --set /etc/nova/nova.conf DEFAULT auth_strategy keystone
if [ $is_ubuntu -eq 1 ] ; then
    if [[ $nova_api_version == *"2013.2"* ]] || [[ $nova_api_version == *"2015"* ]]; then
        openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova.network.neutronv2.api.API
    else
        if [ $is_liberty_or_above -eq 1 ]; then
            openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova.network.neutronv2.api.API
        else 
            if [ $is_mitaka_or_above -eq 1 ]; then
                openstack-config --del /etc/nova/nova.conf DEFAULT network_api_class nova.network.neutronv2.api.API
                openstack-config --set /etc/nova/nova.conf DEFAULT use_neutron True
            else
                openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class contrail_nova_networkapi.api.API
            fi
        fi
    fi
    openstack-config --set /etc/nova/nova.conf DEFAULT ec2_private_dns_show_ip False
    if [[ $nova_api_version == *"2015"* ]] || [[ $is_liberty_or_above -eq 1 ]]; then
        openstack-config --set /etc/nova/nova.conf neutron admin_auth_url ${AUTH_PROTOCOL}://$CONTROLLER:35357/$KEYSTONE_VERSION/
        openstack-config --set /etc/nova/nova.conf neutron admin_username $OS_NET
        openstack-config --set /etc/nova/nova.conf neutron admin_password $ADMIN_TOKEN
        openstack-config --set /etc/nova/nova.conf neutron admin_tenant_name service
        openstack-config --set /etc/nova/nova.conf neutron url ${QUANTUM_PROTOCOL}://$QUANTUM:9696/
        openstack-config --set /etc/nova/nova.conf neutron url_timeout 300
        openstack-config --set /etc/nova/nova.conf neutron service_metadata_proxy True
        if [ $AUTH_PROTOCOL == "https" ]; then
            openstack-config --set /etc/nova/nova.conf neutron insecure True
        fi
        if [ $is_mitaka_or_above -eq 1 ]; then
            openstack-config --set /etc/nova/nova.conf neutron auth_url ${AUTH_PROTOCOL}://$CONTROLLER:35357
            openstack-config --set /etc/nova/nova.conf neutron auth_type password
            openstack-config --set /etc/nova/nova.conf neutron project_name service
            openstack-config --set /etc/nova/nova.conf neutron username $OS_NET
            openstack-config --set /etc/nova/nova.conf neutron password $ADMIN_TOKEN
        fi
        openstack-config --set /etc/nova/nova.conf compute compute_driver libvirt.LibvirtDriver
        openstack-config --set /etc/nova/nova.conf oslo_messaging_rabbit heartbeat_timeout_threshold 0
    fi
else
    # From Icehouse onwards
    if [[ $rpm_icehouse_or_higher -eq 1 ]]; then
        openstack-config --set /etc/nova/nova.conf DEFAULT neutron_auth_strategy keystone
        openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova.network.neutronv2.api.API
        openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_host $AMQP_SERVER
        openstack-config --set /etc/nova/nova.conf DEFAULT lock_path /var/lib/nova/tmp
        openstack-config --set /etc/nova/nova.conf DEFAULT state_path /var/lib/nova
        openstack-config --set /etc/nova/nova.conf DEFAULT instances_path /var/lib/nova/instances
        openstack-config --set /etc/nova/nova.conf conductor rabbit_host $AMQP_SERVER
        chown -R nova:nova /var/lib/nova
    fi

    # From Juno onwards
    if [[ $rpm_juno_or_higher -eq 1 ]]; then
        openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class contrail_nova_networkapi.api.API
    fi


    # From Kilo onwards
    if [[ $rpm_kilo_or_higher -eq 1 ]]; then
        openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova.network.neutronv2.api.API

        # Neutron section in nova.conf
        if [ $AUTH_PROTOCOL == "https" ]; then
            openstack-config --set /etc/nova/nova.conf neutron insecure True
        fi
        openstack-config --set /etc/nova/nova.conf neutron url ${QUANTUM_PROTOCOL}://$QUANTUM:9696/
        openstack-config --set /etc/nova/nova.conf neutron admin_tenant_name $SERVICE_TENANT_NAME
        openstack-config --set /etc/nova/nova.conf neutron auth_strategy keystone
        openstack-config --set /etc/nova/nova.conf neutron admin_auth_url ${AUTH_PROTOCOL}://$CONTROLLER:35357/$KEYSTONE_VERSION/
        openstack-config --set /etc/nova/nova.conf neutron admin_username neutron
        openstack-config --set /etc/nova/nova.conf neutron admin_password $NEUTRON_PASSWORD
        openstack-config --set /etc/nova/nova.conf neutron service_metadata_proxy True
        openstack-config --set /etc/nova/nova.conf compute compute_driver libvirt.LibvirtDriver

        # New configs in keystone section
        openstack-config --set /etc/nova/nova.conf keystone_authtoken username nova
        openstack-config --set /etc/nova/nova.conf keystone_authtoken password $NOVA_PASSWORD
    fi

    # From Mitaka onwards
    if [[ $rpm_mitaka_or_higher -eq 1 ]]; then
        contrail-config --set /etc/nova/nova.conf DEFAULT rpc_backend rabbit
        contrail-config --set /etc/nova/nova.conf DEFAULT use_neutron True
        contrail-config --set /etc/nova/nova.conf keystone_authtoken auth_uri ${AUTH_PROTOCOL}://$CONTROLLER:5000
        contrail-config --set /etc/nova/nova.conf keystone_authtoken auth_url ${AUTH_PROTOCOL}://$CONTROLLER:35357
        contrail-config --set /etc/nova/nova.conf keystone_authtoken memcached_servers $CONTROLLER:11211
        contrail-config --set /etc/nova/nova.conf keystone_authtoken auth_type password
        #contrail-config --set /etc/nova/nova.conf keystone_authtoken project_domain_name default
        #contrail-config --set /etc/nova/nova.conf keystone_authtoken user_domain_name default
        contrail-config --set /etc/nova/nova.conf keystone_authtoken project_name $SERVICE_TENANT_NAME
        contrail-config --set /etc/nova/nova.conf glance api_servers http://$CONTROLLER:9292
        contrail-config --set /etc/nova/nova.conf oslo_concurrency lock_path /var/lib/nova/tmp
        # Needs to updated
        # contrail-config --set /etc/nova/nova.conf DEFAULT my_ip MGMT_IP_ADDRESS_OF_CONTROLLER
        # contrail-config --set /etc/nova/nova.conf oslo_messaging_rabbit rabbit_userid openstack
        # contrail-config --set /etc/nova/nova.conf oslo_messaging_rabbit rabbit_password RABBIT_PASSWD
        # contrail-config --set /etc/nova/nova.conf vnc vncserver_listen MGMT_IP_ADDRESS_OF_CONTROLLER
        # contrail-config --set /etc/nova/nova.conf vnc vncserver_proxyclient_address MGMT_IP_ADDRESS_OF_CONTROLLER

        contrail-config --set /etc/nova/nova.conf neutron auth_url ${AUTH_PROTOCOL}://$CONTROLLER:35357/$KEYSTONE_VERSION/
        contrail-config --set /etc/nova/nova.conf neutron auth_type password
        contrail-config --set /etc/nova/nova.conf neutron region_name $REGION_NAME
        contrail-config --set /etc/nova/nova.conf neutron project_name $SERVICE_TENANT_NAME
        contrail-config --set /etc/nova/nova.conf neutron username neutron
        contrail-config --set /etc/nova/nova.conf neutron password $NEUTRON_PASSWORD

    fi
fi

if [ "$INTERNAL_VIP" != "none" ]; then
    openstack-config --set /etc/nova/nova.conf DEFAULT osapi_compute_listen_port 9774
    openstack-config --set /etc/nova/nova.conf DEFAULT metadata_listen_port 9775
    openstack-config --set /etc/nova/nova.conf DEFAULT metadata_port 9775
    openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_retry_interval 10
    openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_retry_backoff 5
    openstack-config --set /etc/nova/nova.conf DEFAULT kombu_reconnect_delay 10
    openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_max_retries 0
    openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_ha_queues True
    openstack-config --set /etc/nova/nova.conf DEFAULT report_interval 15
    openstack-config --set /etc/nova/nova.conf DEFAULT vncserver_enabled true
    openstack-config --set /etc/nova/nova.conf DEFAULT novncproxy_base_url http://$SELF_MGMT_IP:6999/vnc_auto.html
    openstack-config --set /etc/nova/nova.conf DEFAULT novncproxy_port 6999
    openstack-config --set /etc/nova/nova.conf DEFAULT novncproxy_host $SELF_MGMT_IP
    openstack-config --set /etc/nova/nova.conf DEFAULT memcached_servers $MEMCACHED_SERVERS
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_host $INTERNAL_VIP
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_port 5000
    openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_host $AMQP_SERVER
    openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_port $AMQP_PORT
    openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_AUTH_URL $AUTH_PROTOCOL://$INTERNAL_VIP:5000/$KEYSTONE_VERSION/
    openstack-config --set /etc/nova/nova.conf DEFAULT $OS_URL ${QUANTUM_PROTOCOL}://$INTERNAL_VIP:9696/
    openstack-config --set /etc/nova/nova.conf DEFAULT image_service nova.image.glance.GlanceImageService
    openstack-config --set /etc/nova/nova.conf DEFAULT glance_api_servers $INTERNAL_VIP:9292
    openstack-config --set /etc/nova/nova.conf DEFAULT service_down_time 90
    openstack-config --set /etc/nova/nova.conf DEFAULT scheduler_max_attempts 10
    openstack-config --set /etc/nova/nova.conf database idle_timeout 180
    openstack-config --set /etc/nova/nova.conf database min_pool_size 100
    openstack-config --set /etc/nova/nova.conf database max_pool_size 350
    openstack-config --set /etc/nova/nova.conf database max_overflow 700
    openstack-config --set /etc/nova/nova.conf database retry_interval 5
    openstack-config --set /etc/nova/nova.conf database max_retries -1
    openstack-config --set /etc/nova/nova.conf database db_max_retries 3
    openstack-config --set /etc/nova/nova.conf database db_retry_interval 1
    openstack-config --set /etc/nova/nova.conf database connection_debug 10
    openstack-config --set /etc/nova/nova.conf database pool_timeout 120
    openstack-config --set /etc/nova/nova.conf DEFAULT disable_process_locking True
    openstack-config --set /etc/nova/nova.conf DEFAULT lock_path /var/lib/nova/tmp
    if [[ $nova_api_version == *"2015"* ]] || [[ $is_liberty_or_above -eq 1 ]]; then
         openstack-config --set /etc/nova/nova.conf neutron url ${QUANTUM_PROTOCOL}://$INTERNAL_VIP:9696/
    fi
fi

# Openstack and contrail in different nodes.
if [ "$CONTRAIL_INTERNAL_VIP" != "none" ]; then
    openstack-config --set /etc/nova/nova.conf DEFAULT $OS_URL ${QUANTUM_PROTOCOL}://$CONTRAIL_INTERNAL_VIP:9696/
    openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_port $AMQP_PORT
fi

if [ "$SRIOV_ENABLED" == "True" ] ; then

    openstack-config --del /etc/nova/nova.conf DEFAULT scheduler_default_filters
    openstack-config --del /etc/nova/nova.conf DEFAULT scheduler_available_filters

    if [ $is_liberty_or_above -eq 1 ]; then
        DEFAULT_FILTERS="RetryFilter, AvailabilityZoneFilter, RamFilter, DiskFilter,
                            ComputeFilter, ComputeCapabilitiesFilter, ImagePropertiesFilter,
                            ServerGroupAntiAffinityFilter, ServerGroupAffinityFilter, PciPassthroughFilter"
    else
        DEFAULT_FILTERS="RetryFilter, AvailabilityZoneFilter, RamFilter,
                            ComputeFilter, ComputeCapabilitiesFilter, ImagePropertiesFilter,
                            ServerGroupAntiAffinityFilter, ServerGroupAffinityFilter, PciPassthroughFilter"
    fi

    openstack-config --set /etc/nova/nova.conf DEFAULT scheduler_default_filters "$DEFAULT_FILTERS"

    openstack-config --set /etc/nova/nova.conf DEFAULT scheduler_available_filters nova.scheduler.filters.all_filters
    sed -i "/scheduler_available_filters/a \
           scheduler_available_filters = nova.scheduler.filters.pci_passthrough_filter.PciPassthroughFilter"  /etc/nova/nova.conf
fi

echo "======= Enabling the services ======"
update_services "action=enable" $web_svc memcached $openstack_services_contrail $openstack_services_nova

echo "======= Starting the services ======"
update_services "action=restart" $web_svc memcached

# Listen at supervisor-openstack port
listen_on_supervisor_openstack_port

# Start nova services
update_services "action=restart" $openstack_services_nova
