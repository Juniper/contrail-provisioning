#!/usr/bin/env bash
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#

CONF_DIR=/etc/contrail
set -x

if [ -f /etc/redhat-release ]; then
   is_redhat=1
   is_ubuntu=0
   ceilometer_services="openstack-ceilometer-compute"
   ceilometer_version=`rpm -q --qf  "%{VERSION}\n" openstack-ceilometer-compute`
fi

if [ -f /etc/lsb-release ] && egrep -q 'DISTRIB_ID.*Ubuntu' /etc/lsb-release; then
   is_ubuntu=1
   is_redhat=0
   ceilometer_services="ceilometer-agent-compute"
   ceilometer_version=`dpkg -l | grep 'ii' | grep ceilometer-agent-compute | awk '{print $3}'`
fi

# Get openstack SKU
is_icehouse_or_latest=$(python -c "from distutils.version import LooseVersion; \
                        print LooseVersion('$ceilometer_version') >= LooseVersion('2014.1.1')")

source $CONF_DIR/ctrl-details

# Check if ADMIN/SERVICE Password has been set
ADMIN_TOKEN=${ADMIN_TOKEN:-contrail123}
SERVICE_TOKEN=${SERVICE_TOKEN:-$(cat $CONF_DIR/service.token)}
OPENSTACK_INDEX=${OPENSTACK_INDEX:-0}
AMQP_PORT=5672

# must set SQL connection before running nova-manage
ceilometer_conf='/etc/ceilometer/ceilometer.conf'
if [ "$OPENSTACK_INDEX" -eq 1 ]; then
    if [ "$is_icehouse_or_latest" == "True" ]; then
        openstack-config --set $ceilometer_conf database connection mongodb://ceilometer:CEILOMETER_DBPASS@$CONTROLLER:27017/ceilometer
    else
        openstack-config --set $ceilometer_conf DEFAULT connection mongodb://ceilometer:CEILOMETER_DBPASS@$CONTROLLER:27017/ceilometer
    fi

    CONFIG_CMD="openstack-config --set $ceilometer_conf"
    $CONFIG_CMD DEFAULT rabbit_host $AMQP_SERVER
    $CONFIG_CMD DEFAULT DEFAULT log_dir /var/log/ceilometer
    if [ "$is_icehouse_or_latest" == "True" ]; then
        $CONFIG_CMD publisher metering_secret $SERVICE_TOKEN
    else
        $CONFIG_CMD DEFAULT DEFAULT metering_secret $SERVICE_TOKEN
    fi
    $CONFIG_CMD DEFAULT auth_strategy keystone

    # set keystone_authtoken section
    CONFIG_CMD="openstack-config --set $ceilometer_conf keystone_authtoken"
    $CONFIG_CMD admin_password CEILOMETER_PASS
    $CONFIG_CMD admin_user ceilometer
    $CONFIG_CMD admin_tenant_name service
    $CONFIG_CMD auth_uri http://$CONTROLLER:5000
    $CONFIG_CMD auth_protocol http
    $CONFIG_CMD auth_port 35357
    $CONFIG_CMD auth_host $CONTROLLER

    # set service_credentials  section
    CONFIG_CMD="openstack-config --set $ceilometer_conf service_credentials"
    $CONFIG_CMD os_password CEILOMETER_PASS
    $CONFIG_CMD os_tenant_name service
    $CONFIG_CMD os_username ceilometer
    $CONFIG_CMD os_auth_url http://$CONTROLLER:5000/v2.0
fi

echo "======= Enabling the services ======"

for svc in $ceilometer_services; do
    chkconfig $svc on
done


echo "======= Starting the services ======"

for svc in $ceilometer_services; do
    service $svc restart
done
