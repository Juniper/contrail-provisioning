#!/usr/bin/env bash

#CONTROLLER=10.1.5.12
#SERVICE_TOKEN=ded4dd496c91df8eb61b

source /etc/contrail/ctrl-details
if [ $CONTROLLER != $COMPUTE ] ; then
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

openstack-config --set /etc/nova/nova.conf DEFAULT novncproxy_base_url http://$CONTROLLER_MGMT:5999/vnc_auto.html
openstack-config --set /etc/nova/nova.conf DEFAULT vncserver_enabled true
openstack-config --set /etc/nova/nova.conf DEFAULT vncserver_listen $COMPUTE
openstack-config --set /etc/nova/nova.conf DEFAULT vncserver_proxyclient_address $COMPUTE
openstack-config --set /etc/nova/nova.conf DEFAULT security_group_api quantum

openstack-config --set /etc/nova/nova.conf DEFAULT heal_instance_info_cache_interval  0
openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_cpu_mode none

for svc in openstack-nova-compute supervisor-vrouter; do
    chkconfig $svc on
done

#for svc in openstack-nova-compute; do
#    service $svc restart
#done
