#!/usr/bin/env bash

if [ -f /etc/redhat-release ]; then
   is_redhat=1
   is_ubuntu=0
   MSG_HOST=qpid_hostname
   OS_NET=quantum
   TENANT_NAME=quantum_admin_tenant_name
   ADMIN_USER=quantum_admin_username
   ADMIN_PASSWD=quantum_admin_password
   ADMIN_AUTH_URL=quantum_admin_auth_url
   OS_URL=quantum_url
   OS_URL_TIMEOUT=quantum_url_timeout
fi

if [ -f /etc/lsb-release ]; then
   is_ubuntu=1
   is_redhat=0
   MSG_HOST=rabbit_host
   OS_NET=neutron
   TENANT_NAME=nuetron_admin_tenant_name
   ADMIN_USER=neutron_admin_username
   ADMIN_PASSWD=neutron_admin_password
   ADMIN_AUTH_URL=neutron_admin_auth_url
   OS_URL=neutron_url
   OS_URL_TIMEOUT=neutron_url_timeout
fi

#CONTROLLER=10.1.5.12
#SERVICE_TOKEN=ded4dd496c91df8eb61b

source /etc/contrail/ctrl-details
if [ $CONTROLLER != $COMPUTE ] ; then
    openstack-config --set /etc/nova/nova.conf DEFAULT sql_connection mysql://nova:nova@$CONTROLLER/nova
    openstack-config --set /etc/nova/nova.conf DEFAULT $MSG_HOST $CONTROLLER
    openstack-config --set /etc/nova/nova.conf DEFAULT glance_host $CONTROLLER
    openstack-config --set /etc/nova/nova.conf DEFAULT $TENANT_NAME service
    openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_USER $OS_NET
    openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_PASSWD $SERVICE_TOKEN
    openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_AUTH_URL http://$CONTROLLER:35357/v2.0/
    openstack-config --set /etc/nova/nova.conf DEFAULT $OS_URL http://$QUANTUM:9696/
    openstack-config --set /etc/nova/nova.conf DEFAULT $OS_URL_TIMEOUT 300
    openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova.network.neutronv2.api.API
	
    openstack-config --set /etc/nova/nova.conf keystone_authtoken admin_tenant_name service
    openstack-config --set /etc/nova/nova.conf keystone_authtoken admin_user nova
    openstack-config --set /etc/nova/nova.conf keystone_authtoken admin_password $SERVICE_TOKEN
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_host $CONTROLLER
fi
openstack-config --set /etc/nova/nova.conf DEFAULT ec2_private_dns_show_ip False
openstack-config --set /etc/nova/nova.conf DEFAULT novncproxy_base_url http://$CONTROLLER_MGMT:5999/vnc_auto.html
openstack-config --set /etc/nova/nova.conf DEFAULT vncserver_enabled true
openstack-config --set /etc/nova/nova.conf DEFAULT vncserver_listen $COMPUTE
openstack-config --set /etc/nova/nova.conf DEFAULT vncserver_proxyclient_address $COMPUTE
openstack-config --set /etc/nova/nova.conf DEFAULT security_group_api $OS_NET

openstack-config --set /etc/nova/nova.conf DEFAULT heal_instance_info_cache_interval  0
openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_cpu_mode none
openstack-config --set /etc/nova/nova.conf DEFAULT image_cache_manager_interval 0

#use contrail specific vif driver
openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_vif_driver nova_contrail_vif.contrailvif.VRouterVIFDriver

for svc in openstack-nova-compute supervisor-vrouter; do
    chkconfig $svc on
done

#for svc in openstack-nova-compute; do
#    service $svc restart
#done
