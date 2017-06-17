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
   rpm_mitaka_or_higher=$(is_installed_rpm_greater openstack-neutron "1 8.1.0 1.el7" && echo 1 || echo 0)
   rpm_liberty_or_higher=$(is_installed_rpm_greater openstack-neutron "1 7.0.1 8.el7ost" && echo 1 || echo 0)
   neutron_api_paste=/usr/share/neutron/api-paste.ini
fi

if [ -f /etc/lsb-release ] && egrep -q 'DISTRIB_ID.*Ubuntu' /etc/lsb-release; then
   is_ubuntu=1
   is_redhat=0
   web_svc=apache2
   mysql_svc=mysql
   neutron_api_paste=/etc/neutron/api-paste.ini
fi

msg_svc=rabbitmq-server

# Make sure mysql service is enabled
update_services "action=enable" $mysql_svc

source /etc/contrail/ctrl-details

# Check if ADMIN/SERVICE Password has been set
ADMIN_TOKEN=${ADMIN_TOKEN:-contrail123}
SERVICE_TOKEN=${SERVICE_TOKEN:-$(cat $CONF_DIR/service.token)}
OPENSTACK_INDEX=${OPENSTACK_INDEX:-0}
INTERNAL_VIP=${INTERNAL_VIP:-none}
CONTRAIL_INTERNAL_VIP=${CONTRAIL_INTERNAL_VIP:-none}

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

# Update all config files with service username and password
if [ -d /etc/neutron ]; then
    net_svc_name='neutron'
else
    net_svc_name='quantum'
fi

for svc in $net_svc_name; do
    openstack-config --set /etc/$svc/$svc.conf DEFAULT bind_port $QUANTUM_PORT
    openstack-config --set /etc/$svc/$svc.conf DEFAULT auth_strategy  keystone
    openstack-config --set /etc/$svc/$svc.conf DEFAULT allow_overlapping_ips True
    openstack-config --set /etc/$svc/$svc.conf DEFAULT dhcp_agent_notification False
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken auth_uri $AUTH_PROTOCOL://$CONTROLLER:35357/$KEYSTONE_VERSION/
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken identity_uri $AUTH_PROTOCOL://$CONTROLLER:5000
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_tenant_name $SERVICE_TENANT
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_user $svc
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_password $NEUTRON_PASSWORD
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken auth_host $CONTROLLER
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken admin_token $SERVICE_TOKEN
    openstack-config --set /etc/$svc/$svc.conf keystone_authtoken auth_protocol $AUTH_PROTOCOL
    if [ "$AUTH_PROTOCOL" == "https" ]; then
        openstack-config --set /etc/$svc/$svc.conf keystone_authtoken certfile $KEYSTONE_CERTFILE
        openstack-config --set /etc/$svc/$svc.conf keystone_authtoken keyfile $KEYSTONE_KEYFILE
        openstack-config --set /etc/$svc/$svc.conf keystone_authtoken cafile $KEYSTONE_CAFILE
    fi
    # Additional configs from Centos7/Mitaka onwards
    if [[ $rpm_mitaka_or_higher -eq 1 ]]; then
        openstack-config --set /etc/$svc/$svc.conf keystone_authtoken username $svc
        openstack-config --set /etc/$svc/$svc.conf keystone_authtoken password $NEUTRON_PASSWORD
    fi
done

openstack-config --set /etc/$net_svc_name/$net_svc_name.conf quotas quota_driver neutron_plugin_contrail.plugins.opencontrail.quota.driver.QuotaDriver
openstack-config --set /etc/$net_svc_name/$net_svc_name.conf QUOTAS quota_network -1
openstack-config --set /etc/$net_svc_name/$net_svc_name.conf QUOTAS quota_subnet -1
openstack-config --set /etc/$net_svc_name/$net_svc_name.conf QUOTAS quota_port -1

if [ -d /etc/neutron ]; then
    PYDIST=$(python -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")
    openstack-config --set /etc/neutron/neutron.conf DEFAULT core_plugin neutron_plugin_contrail.plugins.opencontrail.contrail_plugin.NeutronPluginContrailCoreV2
    openstack-config --set /etc/neutron/neutron.conf DEFAULT rabbit_hosts $AMQP_SERVER

    is_liberty_or_latest=0
    if [ $is_ubuntu -eq 1 ] ; then
        neutron_server_top_ver=`dpkg -l | grep 'ii' | grep neutron-server | awk '{print $3}'  | cut -d ":" -f 1`
        if [ "$neutron_server_top_ver" -gt "1" ]; then
            is_liberty_or_latest=1
        fi
    fi

    if [ $is_liberty_or_latest -eq 1 ] || [[ $rpm_liberty_or_higher -eq 1 ]]; then
        # for liberty loadbalanacer plugin would be V2 by default and
        # neutron_lbaas extensions would be needed in api_extensions_path
        openstack-config --set /etc/neutron/neutron.conf DEFAULT api_extensions_path extensions:${PYDIST}/neutron_plugin_contrail/extensions:${PYDIST}/neutron_lbaas/extensions
        openstack-config --set /etc/neutron/neutron.conf DEFAULT service_plugins neutron_plugin_contrail.plugins.opencontrail.loadbalancer.v2.plugin.LoadBalancerPluginV2
    else
        openstack-config --set /etc/neutron/neutron.conf DEFAULT api_extensions_path extensions:${PYDIST}/neutron_plugin_contrail/extensions
        openstack-config --set /etc/neutron/neutron.conf DEFAULT service_plugins neutron_plugin_contrail.plugins.opencontrail.loadbalancer.plugin.LoadBalancerPlugin
    fi 

    openstack-config --del /etc/neutron/neutron.conf service_providers service_provider
    openstack-config --set /etc/neutron/neutron.conf service_providers service_provider LOADBALANCER:Opencontrail:neutron_plugin_contrail.plugins.opencontrail.loadbalancer.driver.OpencontrailLoadbalancerDriver:default

    ret_val=`grep "keystone = user_token" $neutron_api_paste > /dev/null;echo $?`
    if [ "$AAA_MODE" == "rbac" ] && [ $ret_val == 1 ]; then
        sed -i 's/keystone =/keystone = user_token/' $neutron_api_paste
        openstack-config --set $neutron_api_paste filter:user_token paste.filter_factory neutron_plugin_contrail.plugins.opencontrail.neutron_middleware:token_factory
    elif [ "$AAA_MODE" != "rbac" ] && [ $ret_val != 1 ]; then
        sed -i 's/keystone = user_token/keystone =/'$neutron_api_paste 
    fi
else
    openstack-config --set /etc/quantum/quantum.conf DEFAULT core_plugin quantum.plugins.contrail.ContrailPlugin.ContrailPlugin

    openstack-config --set /etc/neutron/neutron.conf DEFAULT max_header_line 65536
fi

if [ -f /usr/share/neutron/neutron-dist.conf ]; then
    openstack-config --del /usr/share/neutron/neutron-dist.conf service_providers
fi

openstack-config --set /etc/$net_svc_name/$net_svc_name.conf DEFAULT log_format '%(asctime)s.%(msecs)d %(levelname)8s [%(name)s] %(message)s'

if [ "$INTERNAL_VIP" != "none" ] || [ "$CONTRAIL_INTERNAL_VIP" != "none" ]; then
    # Openstack HA specific config
    openstack-config --set /etc/$net_svc_name/$net_svc_name.conf DEFAULT rabbit_hosts $AMQP_SERVER
    openstack-config --set /etc/$net_svc_name/$net_svc_name.conf DEFAULT rabbit_retry_interval 1
    openstack-config --set /etc/$net_svc_name/$net_svc_name.conf DEFAULT rabbit_retry_backoff 2
    openstack-config --set /etc/$net_svc_name/$net_svc_name.conf DEFAULT rabbit_max_retries 0
    openstack-config --set /etc/$net_svc_name/$net_svc_name.conf DEFAULT rabbit_ha_queues True
    openstack-config --set /etc/$net_svc_name/$net_svc_name.conf DEFAULT rpc_cast_timeout 30
    openstack-config --set /etc/$net_svc_name/$net_svc_name.conf DEFAULT rpc_conn_pool_size 40
    openstack-config --set /etc/$net_svc_name/$net_svc_name.conf DEFAULT rpc_response_timeout 60
    openstack-config --set /etc/$net_svc_name/$net_svc_name.conf DEFAULT rpc_thread_pool_size 70
fi

# Add respawn in nova-compute upstart script
net_svc_upstart='/etc/init/$net_svc_name-server.conf'
if [ -f $net_svc_upstart ]; then
    ret_val=`grep "^respawn" $net_svc_upstart > /dev/null;echo $?`
    if [ $ret_val == 1 ]; then
      sed -i 's/pre-start script/respawn\n&/' $net_svc_upstart
      sed -i 's/pre-start script/respawn limit 10 90\n&/' $net_svc_upstart
    fi
fi

echo "======= Enabling the services ======"
update_services "action=enable" $msg_svc $web_svc memcached $net_svc_name-server

echo "======= Starting the services ======"
update_services "action=restart" $msg_svc $web_svc memcached $net_svc_name-server
