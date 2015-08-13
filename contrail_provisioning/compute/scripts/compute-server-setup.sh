#!/usr/bin/env bash

if [ -f /etc/redhat-release ]; then
   is_redhat=1
   is_ubuntu=0
   nova_compute_ver=`rpm -q --qf  "%{VERSION}\n" openstack-nova-compute`
   if [ "$nova_compute_ver" == "2013.1" ]; then
   	OS_NET=quantum
   	TENANT_NAME=quantum_admin_tenant_name
   	ADMIN_USER=quantum_admin_username
   	ADMIN_PASSWD=quantum_admin_password
   	ADMIN_AUTH_URL=quantum_admin_auth_url
   	OS_URL=quantum_url
   	OS_URL_TIMEOUT=quantum_url_timeout
   else
   	OS_NET=neutron
   	TENANT_NAME=neutron_admin_tenant_name
   	ADMIN_USER=neutron_admin_username
   	ADMIN_PASSWD=neutron_admin_password
   	ADMIN_AUTH_URL=neutron_admin_auth_url
   	OS_URL=neutron_url
   	OS_URL_TIMEOUT=neutron_url_timeout
   fi
fi

if [ -f /etc/lsb-release ] && egrep -q 'DISTRIB_ID.*Ubuntu' /etc/lsb-release; then
   is_ubuntu=1
   is_redhat=0
   nova_compute_version=`dpkg -l | grep 'ii' | grep nova-compute | grep -v vif | grep -v nova-compute-kvm | grep -v nova-compute-libvirt | awk '{print $3}'`
   echo $nova_compute_version
   if [ "$nova_compute_version" == "2:2013.1.3-0ubuntu1" ]; then
   	OS_NET=quantum
   	TENANT_NAME=quantum_admin_tenant_name
   	ADMIN_USER=quantum_admin_username
   	ADMIN_PASSWD=quantum_admin_password
   	ADMIN_AUTH_URL=quantum_admin_auth_url
   	OS_URL=quantum_url
   	OS_URL_TIMEOUT=quantum_url_timeout
   else
   	OS_NET=neutron
   	TENANT_NAME=neutron_admin_tenant_name
   	ADMIN_USER=neutron_admin_username
   	ADMIN_PASSWD=neutron_admin_password
   	ADMIN_AUTH_URL=neutron_admin_auth_url
   	OS_URL=neutron_url
   	OS_URL_TIMEOUT=neutron_url_timeout
   fi
fi

#CONTROLLER=10.1.5.12
#SERVICE_TOKEN=ded4dd496c91df8eb61b

if [ $is_ubuntu -eq 1 ] ; then
    lsmod | grep kvm
    if [ $? -ne 0 ]; then
        modprobe -a kvm
        echo "kvm" >> /etc/modules
        VENDOR=`cat /proc/cpuinfo | grep 'vendor_id' | cut -d: -f2 | awk 'NR==1'`
        if [[ "${VENDOR}" == *Intel* ]]; then
            modprobe -a kvm-intel
            echo "kvm-intel" >> /etc/modules
        else
            modprobe -a kvm-amd
            echo "kvm-amd" >> /etc/modules
        fi
    fi
fi
source /etc/contrail/ctrl-details
HYPERVISOR=${HYPERVISOR:-"libvirt"}
if [ $CONTROLLER != $COMPUTE ] ; then
    openstack-config --del /etc/nova/nova.conf DEFAULT sql_connection
    openstack-config --set /etc/nova/nova.conf DEFAULT auth_strategy keystone
    openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_nonblocking True
    openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_inject_partition -1
    openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_host $AMQP_SERVER
    openstack-config --set /etc/nova/nova.conf DEFAULT glance_host $CONTROLLER
    openstack-config --set /etc/nova/nova.conf DEFAULT $TENANT_NAME $SERVICE_TENANT_NAME
    openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_USER $OS_NET
    openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_PASSWD $NEUTRON_PASSWORD
    openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_AUTH_URL $AUTH_PROTOCOL://$CONTROLLER:35357/v2.0/
    openstack-config --set /etc/nova/nova.conf DEFAULT $OS_URL ${QUANTUM_PROTOCOL}://$QUANTUM:9696/
    openstack-config --set /etc/nova/nova.conf DEFAULT $OS_URL_TIMEOUT 300
    if [ $is_ubuntu -eq 1 ] ; then
        openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova.network.${OS_NET}v2.api.API
        openstack-config --set /etc/nova/nova.conf DEFAULT compute_driver libvirt.LibvirtDriver
        if [[ $nova_compute_version == *":"* ]]; then
            nova_compute_version_without_epoch=`echo $nova_compute_version | cut -d':' -f2`
        else
            nova_compute_version_without_epoch=`echo $nova_compute_version`
        fi

        dpkg --compare-versions $nova_compute_version_without_epoch ge 2015
        if [ $? -eq 0 ]; then
            openstack-config --set /etc/nova/nova.conf neutron admin_auth_url ${AUTH_PROTOCOL}://$CONTROLLER:35357/v2.0/
            openstack-config --set /etc/nova/nova.conf neutron admin_username $OS_NET
            openstack-config --set /etc/nova/nova.conf neutron admin_password $ADMIN_TOKEN
            openstack-config --set /etc/nova/nova.conf neutron admin_tenant_name service
            openstack-config --set /etc/nova/nova.conf neutron url ${QUANTUM_PROTOCOL}://$QUANTUM:9696/
            openstack-config --set /etc/nova/nova.conf neutron url_timeout 300
            openstack-config --set /etc/nova/nova.conf neutron service_metadata_proxy True
            openstack-config --set /etc/nova/nova.conf compute compute_driver libvirt.LibvirtDriver
            openstack-config --set /etc/nova/nova.conf glance host $CONTROLLER
        fi
    else
        if [ ${nova_compute_ver%%.*} -ge 2014 ]; then
            openstack-config --set /etc/nova/nova.conf DEFAULT compute_driver libvirt.LibvirtDriver
            openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova.network.${OS_NET}v2.api.API
            openstack-config --set /etc/nova/nova.conf DEFAULT state_path /var/lib/nova
            openstack-config --set /etc/nova/nova.conf DEFAULT lock_path /var/lib/nova/tmp
            openstack-config --set /etc/nova/nova.conf DEFAULT instaces_path /var/lib/nova/instances
        fi

        # For Juno, set network_api_class as nova_contrail_vif.contrailvif.ContrailNetworkAPI
        is_juno=$(python -c "from distutils.version import LooseVersion; \
                  print LooseVersion('$nova_compute_ver') == LooseVersion('2014.2.2')")
        if [ "$is_juno" == "True" ]; then
            openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova_contrail_vif.contrailvif.ContrailNetworkAPI
        fi
    fi
    openstack-config --set /etc/nova/nova.conf keystone_authtoken admin_tenant_name $SERVICE_TENANT_NAME
    openstack-config --set /etc/nova/nova.conf keystone_authtoken admin_user nova
    openstack-config --set /etc/nova/nova.conf keystone_authtoken admin_password $NOVA_PASSWORD
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_host $CONTROLLER
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_protocol http
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_port 35357
    openstack-config --set /etc/nova/nova.conf keystone_authtoken signing_dir /tmp/keystone-signing-nova
else:
    # For Juno, set network_api_class as nova_contrail_vif.contrailvif.ContrailNetworkAPI even
    # if controller node is compute node so the VIF_TYPE=vrouter is available
    if [ $is_redhat -eq 1 ]; then
        # For Juno, set network_api_class as nova_contrail_vif.contrailvif.ContrailNetworkAPI
        is_juno=$(python -c "from distutils.version import LooseVersion; \
                  print LooseVersion('$nova_compute_ver') == LooseVersion('2014.2.2')")
        if [ "$is_juno" == "True" ]; then
            openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova_contrail_vif.contrailvif.ContrailNetworkAPI
        fi
    fi
fi

if [ $VMWARE_IP ]; then
    openstack-config --del /etc/nova/nova.conf DEFAULT compute_driver
    openstack-config --set /etc/nova/nova.conf DEFAULT compute_driver vmwareapi.ContrailESXDriver
    if [ -f /etc/nova/nova-compute.conf ]; then
        openstack-config --del /etc/nova/nova-compute.conf DEFAULT compute_driver
        openstack-config --set /etc/nova/nova-compute.conf DEFAULT compute_driver vmwareapi.ContrailESXDriver
    fi
fi

openstack-config --set /etc/nova/nova.conf DEFAULT ec2_private_dns_show_ip False
openstack-config --set /etc/nova/nova.conf DEFAULT novncproxy_base_url http://$CONTROLLER_MGMT:5999/vnc_auto.html
openstack-config --set /etc/nova/nova.conf DEFAULT vncserver_enabled true

openstack-config --set /etc/nova/nova.conf DEFAULT vncserver_listen $COMPUTE
openstack-config --set /etc/nova/nova.conf DEFAULT vncserver_proxyclient_address $COMPUTE
openstack-config --set /etc/nova/nova.conf DEFAULT security_group_api $OS_NET

openstack-config --set /etc/nova/nova.conf DEFAULT heal_instance_info_cache_interval  0

openstack-config --set /etc/nova/nova.conf DEFAULT image_cache_manager_interval 0

if [ "$HYPERVISOR" == "libvirt" ]; then
    # Running DPDK apps inside VMs require more modern cpu model
    if [ "$DPDK_MODE" == "True" ]; then
        openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_cpu_mode host-model
    else
        openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_cpu_mode none
    fi
    #use contrail specific vif driver
    openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_vif_driver nova_contrail_vif.contrailvif.VRouterVIFDriver
elif [ "$HYPERVISOR" == "docker" ]; then
    openstack-config --del /etc/nova/nova.conf DEFAULT libvirt_nonblocking
    openstack-config --del /etc/nova/nova.conf DEFAULT libvirt_inject_partition
    openstack-config --set /etc/nova/nova.conf DEFAULT compute_driver novadocker.virt.docker.DockerDriver
    openstack-config --set /etc/nova/nova-compute.conf DEFAULT compute_driver novadocker.virt.docker.DockerDriver
    openstack-config --set /etc/nova/nova.conf docker vif_driver novadocker.virt.docker.opencontrail.OpenContrailVIFDriver
    openstack-config --set /etc/nova/nova-compute.conf docker vif_driver novadocker.virt.docker.opencontrail.OpenContrailVIFDriver
    openstack-config --del /etc/nova/nova.conf DEFAULT libvirt_use_virtio_for_bridges
    openstack-config --del /etc/nova/nova-compute.conf libvirt
    openstack-config --del /etc/nova/nova-compute.conf DEFAULT network_api_class
fi

# Use noopdriver for firewall
openstack-config --set /etc/nova/nova.conf DEFAULT firewall_driver nova.virt.firewall.NoopFirewallDriver

if [ $VMWARE_IP ]; then
    openstack-config --set /etc/nova/nova.conf vmware host_ip $VMWARE_IP
    openstack-config --set /etc/nova/nova.conf vmware host_username $VMWARE_USERNAME
    openstack-config --set /etc/nova/nova.conf vmware host_password $VMWARE_PASSWD
    openstack-config --set /etc/nova/nova.conf vmware vmpg_vswitch $VMWARE_VMPG_VSWITCH
fi

# Openstack HA specific configs
INTERNAL_VIP=${INTERNAL_VIP:-none}
CONTRAIL_INTERNAL_VIP=${CONTRAIL_INTERNAL_VIP:-none}
EXTERNAL_VIP=${EXTERNAL_VIP:-$INTERNAL_VIP}
AMQP_PORT=5672
if [ "$CONTRAIL_INTERNAL_VIP" == "$AMQP_SERVER" ] || [ "$INTERNAL_VIP" == "$AMQP_SERVER" ]; then
    AMQP_PORT=5673
fi
if [ "$INTERNAL_VIP" != "none" ] || [ "$CONTRAIL_INTERNAL_VIP" != "none" ]; then
    openstack-config --set /etc/nova/nova.conf DEFAULT glance_port 9292
    openstack-config --set /etc/nova/nova.conf DEFAULT glance_num_retries 10
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_port 5000
    openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_host $AMQP_SERVER
    openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_port $AMQP_PORT
    openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_retry_interval 10
    openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_retry_backoff 5
    openstack-config --set /etc/nova/nova.conf DEFAULT kombu_reconnect_delay 10
    openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_max_retries 0
    openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_ha_queues True
    openstack-config --set /etc/nova/nova.conf DEFAULT rpc_cast_timeout 30
    openstack-config --set /etc/nova/nova.conf DEFAULT rpc_conn_pool_size 40
    openstack-config --set /etc/nova/nova.conf DEFAULT rpc_response_timeout 60
    openstack-config --set /etc/nova/nova.conf DEFAULT rpc_thread_pool_size 70
    openstack-config --set /etc/nova/nova.conf DEFAULT report_interval 15
    openstack-config --set /etc/nova/nova.conf DEFAULT novncproxy_port 6080
    openstack-config --set /etc/nova/nova.conf DEFAULT vnc_port 5900
    openstack-config --set /etc/nova/nova.conf DEFAULT vnc_port_total 100
    openstack-config --set /etc/nova/nova.conf DEFAULT resume_guests_state_on_host_boot True
    openstack-config --set /etc/nova/nova.conf DEFAULT vncserver_listen $SELF_MGMT_IP
    openstack-config --set /etc/nova/nova.conf DEFAULT vncserver_proxyclient_address $SELF_MGMT_IP
    openstack-config --set /etc/nova/nova.conf DEFAULT service_down_time 300
    openstack-config --set /etc/nova/nova.conf DEFAULT periodic_fuzzy_delay 30
    openstack-config --set /etc/nova/nova.conf DEFAULT lock_path /var/lib/nova/tmp
    openstack-config --set /etc/nova/nova.conf DEFAULT disable_process_locking True
fi
# Openstack and Contrail in different nodes.
if [ "$INTERNAL_VIP" != "none" ] && [ "$CONTRAIL_INTERNAL_VIP" != "none" ]; then
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_host $INTERNAL_VIP
    openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_AUTH_URL http://$INTERNAL_VIP:5000/v2.0/
    openstack-config --set /etc/nova/nova.conf DEFAULT $OS_URL http://$CONTRAIL_INTERNAL_VIP:9696/
    openstack-config --set /etc/nova/nova.conf DEFAULT novncproxy_base_url http://$EXTERNAL_VIP:6080/vnc_auto.html
# Contrail HA.
elif [ "$INTERNAL_VIP" == "none" ] && [ "$CONTRAIL_INTERNAL_VIP" != "none" ]; then
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_host $CONTROLLER
    openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_AUTH_URL http://$CONTROLLER:5000/v2.0/
    openstack-config --set /etc/nova/nova.conf DEFAULT $OS_URL http://$CONTRAIL_INTERNAL_VIP:9696/
    openstack-config --set /etc/nova/nova.conf DEFAULT novncproxy_base_url http://$CONTROLLER_MGMT:6080/vnc_auto.html
# Openstack and Contrail in same nodes.
elif [ "$INTERNAL_VIP" != "none" ] && [ "$CONTRAIL_INTERNAL_VIP" == "none" ]; then
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_host $INTERNAL_VIP
    openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_AUTH_URL http://$INTERNAL_VIP:5000/v2.0/
    openstack-config --set /etc/nova/nova.conf DEFAULT $OS_URL http://$INTERNAL_VIP:9696/
    openstack-config --set /etc/nova/nova.conf DEFAULT novncproxy_base_url http://$EXTERNAL_VIP:6080/vnc_auto.html
fi

# Set userspace vhost and hugepages for DPDK vRouter
if [ "$DPDK_MODE" == "True" ]; then
    openstack-config --set /etc/nova/nova.conf CONTRAIL use_userspace_vhost true
    openstack-config --set /etc/nova/nova.conf LIBVIRT use_huge_pages true
fi

# Add respawn in nova-compute upstart script
nova_compute_upstart='/etc/init/nova-compute.conf'
if [ -f $nova_compute_upstart ]; then
    ret_val=`grep "^respawn" $nova_compute_upstart > /dev/null;echo $?`
    if [ $ret_val == 1 ]; then
      sed -i 's/pre-start script/respawn\n&/' $nova_compute_upstart
      sed -i 's/pre-start script/respawn limit 10 90\n&/' $nova_compute_upstart
    fi
fi

for svc in openstack-nova-compute supervisor-vrouter; do
    chkconfig $svc on
done

#for svc in openstack-nova-compute; do
#    service $svc restart
#done
