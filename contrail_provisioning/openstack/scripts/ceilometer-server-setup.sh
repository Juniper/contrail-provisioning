#!/usr/bin/env bash
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#

CONF_DIR=/etc/contrail
set -x

function is_keystone_up() {
    for i in {1..36} {
    do
       (source $CONF_DIR/openstackrc;keystone tenant-list)
       if [ $? == 0 ]; then
           return 0
       fi
       echo "Keystone is not up, retrying in 5 secs"
       sleep 5
    done
    return 1
}

if [ -f /etc/redhat-release ]; then
   is_redhat=1
   is_ubuntu=0
   ceilometer_api_ver=`rpm -q --qf  "%{VERSION}\n" openstack-ceilometer-api`
fi

if [ -f /etc/lsb-release ] && egrep -q 'DISTRIB_ID.*Ubuntu' /etc/lsb-release; then
   is_ubuntu=1
   is_redhat=0
   ceilometer_api_ver=`dpkg -l | grep 'ii' | grep ceilometer-api | awk '{print $3}'`
fi

# Get openstack SKU
is_icehouse_or_latest=$(python -c "from distutils.version import LooseVersion; \
                        print LooseVersion('$ceilometer_api_ver') >= LooseVersion('2014.1.1')")

if [ "$is_icehouse_or_latest" == "True" ]; then
    ceilometer_services="ceilometer-agent-central ceilometer-api ceilometer-collector"
else
    ceilometer_services="ceilometer-agent-central ceilometer-agent-notification ceilometer-api ceilometer-collector ceilometer-alarm-evaluator ceilometer-alarm-notifier"
fi

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

    # Verify keystone status
    is_keystone_up
    if [ $? != 0 ]; then
        echo "Keystone is not up, Exiting..."
        exit 1
    fi

    # Create ceilometer user/tenant
    get_ceilometer_user="source $CONF_DIR/openstackrc;keystone user-get ceilometer"
    $get_ceilometer_user 2>/dev/null
    ret=$?
    if [ $ret -ne 0 ]; then
        echo "Creating ceilometer user and tenant ..."
        (source $CONF_DIR/openstackrc;keystone user-create --name=ceilometer --pass=CEILOMETER_PASS --tenant=service --email=ceilometer@example.com)
        (source $CONF_DIR/openstackrc;keystone user-role-add --user=ceilometer --tenant=service --role=admin)
    fi

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

    # Create keystone service and endpoint
    (source $CONF_DIR/openstackrc;keystone service-list | grep ceilometer 2>/dev/null)
    ret=$?
    if [ $ret -ne 0 ]; then
        (source $CONF_DIR/openstackrc;keystone service-create --name=ceilometer --type=metering --description=Telemetry)
        (source $CONF_DIR/openstackrc;keystone endpoint-create --service-id=$(keystone service-list | awk '/ metering / {print $2}') --publicurl=http://$CONTROLLER:8777 --internalurl=http://$CONTROLLER:8777 --adminurl=http://$CONTROLLER:8777 --region=RegionOne)
    fi
fi

echo "======= Enabling the services ======"

for svc in $ceilometer_services; do
    chkconfig $svc on
done


echo "======= Starting the services ======"

for svc in $ceilometer_services; do
    service $svc restart
done
