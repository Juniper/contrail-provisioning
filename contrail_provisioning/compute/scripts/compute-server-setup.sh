#!/usr/bin/env bash

source /opt/contrail/bin/contrail-lib.sh
set -x

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
   rpm_mitaka_or_higher=$(is_installed_rpm_greater openstack-nova-compute "1 13.0.0 1.el7" && echo 1 || echo 0)
   rpm_liberty_or_higher=$(is_installed_rpm_greater openstack-nova-compute "1 12.0.0 1.el7" && echo 1 || echo 0)
   rpm_kilo_or_higher=$(is_installed_rpm_greater openstack-nova-compute "0 2015.1.1 1.el7" && echo 1 || echo 0)
   rpm_juno_or_higher=$(is_installed_rpm_greater openstack-nova-compute "0 2014.2.2 1.el7" && echo 1 || echo 0)
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

INTERNAL_VIP=${INTERNAL_VIP:-none}
CONTRAIL_INTERNAL_VIP=${CONTRAIL_INTERNAL_VIP:-none}
EXTERNAL_VIP=${EXTERNAL_VIP:-$INTERNAL_VIP}

if [ $CONTROLLER != $COMPUTE ] ; then
    openstack-config --del /etc/nova/nova.conf database connection
    openstack-config --set /etc/nova/nova.conf DEFAULT auth_strategy keystone
    openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_nonblocking True
    openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_inject_partition -1
    openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_host $AMQP_SERVER
    openstack-config --set /etc/nova/nova.conf DEFAULT glance_host $CONTROLLER
    openstack-config --set /etc/nova/nova.conf DEFAULT $TENANT_NAME $SERVICE_TENANT_NAME
    openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_USER $OS_NET
    openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_PASSWD $NEUTRON_PASSWORD
    openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_AUTH_URL $AUTH_PROTOCOL://$CONTROLLER:35357/$KEYSTONE_VERSION/
    openstack-config --set /etc/nova/nova.conf DEFAULT $OS_URL ${QUANTUM_PROTOCOL}://$QUANTUM:9696/
    openstack-config --set /etc/nova/nova.conf DEFAULT $OS_URL_TIMEOUT 300
    if [ $is_ubuntu -eq 1 ] ; then
        openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova.network.${OS_NET}v2.api.API
        openstack-config --set /etc/nova/nova.conf DEFAULT compute_driver libvirt.LibvirtDriver
        if [[ $nova_compute_version == *":"* ]]; then
            nova_compute_version_without_epoch=`echo $nova_compute_version | cut -d':' -f2 | cut -d'-' -f1`
            nova_compute_top_ver=`echo $nova_compute_version | cut -d':' -f1`
        else
            nova_compute_version_without_epoch=`echo $nova_compute_version`
        fi

        kilo_or_above=0
        liberty_or_above=0
        mitaka_or_above=0
        # for juno and kilo versions
        if [ "$nova_compute_top_ver" -eq "1" ]; then
            # for kilo
            dpkg --compare-versions $nova_compute_version_without_epoch ge 2015
            if [ $? -eq 0 ]; then
                kilo_or_above=1
            fi
        else
            #Starting liberty the package versioning has changed to x.y.z format
            dpkg --compare-versions $nova_compute_version_without_epoch ge 12.0.0
            if [ $? -eq 0 ]; then
                kilo_or_above=1
            fi
            dpkg --compare-versions $nova_compute_version_without_epoch ge 12.0.1
            if [ $? -eq 0 ]; then
                liberty_or_above=1
            fi
            #For mitaka, the nova-compute version is 13.y.z
            dpkg --compare-versions $nova_compute_version_without_epoch ge 13.0.0
            if [ $? -eq 0 ]; then
                mitaka_or_above=1
            fi
        fi

        if [ $kilo_or_above -eq 1 ] ; then
            if [ $mitaka_or_above -eq 1 ] ; then
                NEUTRON_AUTH_URL_FIELD=auth_url
            else
                NEUTRON_AUTH_URL_FIELD=admin_auth_url
            fi
            if [ "$CONTRAIL_INTERNAL_VIP" != "none" ]; then
                openstack-config --set /etc/nova/nova.conf neutron url ${QUANTUM_PROTOCOL}://$CONTRAIL_INTERNAL_VIP:9696/
                if [ "$INTERNAL_VIP" != "none" ]; then
                    openstack-config --set /etc/nova/nova.conf neutron $NEUTRON_AUTH_URL_FIELD ${AUTH_PROTOCOL}://$INTERNAL_VIP:35357/$KEYSTONE_VERSION/
                else
                    openstack-config --set /etc/nova/nova.conf neutron $NEUTRON_AUTH_URL_FIELD ${AUTH_PROTOCOL}://$CONTROLLER:35357/$KEYSTONE_VERSION/
                fi
            elif [ "$INTERNAL_VIP" != "none" ]; then
                openstack-config --set /etc/nova/nova.conf neutron url ${QUANTUM_PROTOCOL}://$INTERNAL_VIP:9696/
                openstack-config --set /etc/nova/nova.conf neutron $NEUTRON_AUTH_URL_FIELD ${AUTH_PROTOCOL}://$INTERNAL_VIP:35357/$KEYSTONE_VERSION/
            else
                openstack-config --set /etc/nova/nova.conf neutron url ${QUANTUM_PROTOCOL}://$QUANTUM:9696/
                openstack-config --set /etc/nova/nova.conf neutron $NEUTRON_AUTH_URL_FIELD ${AUTH_PROTOCOL}://$CONTROLLER:35357/$KEYSTONE_VERSION/
            fi
            openstack-config --set /etc/nova/nova.conf neutron admin_username $OS_NET
            openstack-config --set /etc/nova/nova.conf neutron admin_password $ADMIN_TOKEN
            openstack-config --set /etc/nova/nova.conf neutron admin_tenant_name service
            openstack-config --set /etc/nova/nova.conf neutron url_timeout 300
            openstack-config --set /etc/nova/nova.conf neutron service_metadata_proxy True
            openstack-config --set /etc/nova/nova.conf compute compute_driver libvirt.LibvirtDriver
            openstack-config --set /etc/nova/nova.conf glance host $CONTROLLER
            if [ $AUTH_PROTOCOL == "https" ]; then
                openstack-config --set /etc/nova/nova.conf neutron insecure True
            fi
        fi

        if [ $mitaka_or_above -eq 1 ]; then
            openstack-config --set /etc/nova/nova.conf neutron auth_type password
            openstack-config --set /etc/nova/nova.conf neutron project_name service
            openstack-config --set /etc/nova/nova.conf neutron username $OS_NET
            openstack-config --set /etc/nova/nova.conf neutron password $ADMIN_TOKEN
            contrail-config --set /etc/nova/nova.conf DEFAULT use_neutron True
        fi
    else
        if [ ${nova_compute_ver%%.*} -ge 2014 ]; then
            openstack-config --set /etc/nova/nova.conf DEFAULT compute_driver libvirt.LibvirtDriver
            openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova.network.${OS_NET}v2.api.API
            openstack-config --set /etc/nova/nova.conf DEFAULT state_path /var/lib/nova
            openstack-config --set /etc/nova/nova.conf DEFAULT lock_path /var/lib/nova/tmp
            openstack-config --set /etc/nova/nova.conf DEFAULT instaces_path /var/lib/nova/instances
        fi

        if [ $is_redhat -eq 1 ]; then
            if [[ $rpm_juno_or_higher -eq 1 ]]; then
                openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova_contrail_vif.contrailvif.ContrailNetworkAPI
            fi

            if [ $rpm_mitaka_or_higher -eq 1 ] ; then
                NEUTRON_AUTH_URL_FIELD=auth_url
            else
                NEUTRON_AUTH_URL_FIELD=admin_auth_url
            fi

            if [[ $rpm_kilo_or_higher -eq 1 ]]; then
                # Neutron section in nova.conf
                if [ "$CONTRAIL_INTERNAL_VIP" != "none" ]; then
                    openstack-config --set /etc/nova/nova.conf neutron url ${QUANTUM_PROTOCOL}://$CONTRAIL_INTERNAL_VIP:9696/
                    if [ "$INTERNAL_VIP" != "none" ]; then
                        openstack-config --set /etc/nova/nova.conf neutron $NEUTRON_AUTH_URL_FIELD ${AUTH_PROTOCOL}://$INTERNAL_VIP:35357/$KEYSTONE_VERSION/
                    else
                        openstack-config --set /etc/nova/nova.conf neutron $NEUTRON_AUTH_URL_FIELD ${AUTH_PROTOCOL}://$CONTROLLER:35357/$KEYSTONE_VERSION/
                    fi
                elif [ "$INTERNAL_VIP" != "none" ]; then
                    openstack-config --set /etc/nova/nova.conf neutron url ${QUANTUM_PROTOCOL}://$INTERNAL_VIP:9696/
                    openstack-config --set /etc/nova/nova.conf neutron $NEUTRON_AUTH_URL_FIELD ${AUTH_PROTOCOL}://$INTERNAL_VIP:35357/$KEYSTONE_VERSION/
                else
                    openstack-config --set /etc/nova/nova.conf neutron url ${QUANTUM_PROTOCOL}://$QUANTUM:9696/
                    openstack-config --set /etc/nova/nova.conf neutron $NEUTRON_AUTH_URL_FIELD ${AUTH_PROTOCOL}://$CONTROLLER:35357/$KEYSTONE_VERSION/
                fi
                openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova.network.neutronv2.api.API
                openstack-config --set /etc/nova/nova.conf neutron admin_tenant_name $SERVICE_TENANT_NAME
                openstack-config --set /etc/nova/nova.conf neutron auth_strategy keystone
                openstack-config --set /etc/nova/nova.conf neutron admin_username neutron
                openstack-config --set /etc/nova/nova.conf neutron admin_password $NEUTRON_PASSWORD
                openstack-config --set /etc/nova/nova.conf neutron service_metadata_proxy True
                if [ $AUTH_PROTOCOL == "https" ]; then
                    openstack-config --set /etc/nova/nova.conf neutron insecure True
                fi
                openstack-config --set /etc/nova/nova.conf compute compute_driver libvirt.LibvirtDriver
                openstack-config --set /etc/nova/nova.conf glance host $CONTROLLER

                # New configs in keystone section
                openstack-config --set /etc/nova/nova.conf keystone_authtoken username nova
                openstack-config --set /etc/nova/nova.conf keystone_authtoken password $NOVA_PASSWORD
            fi

            if [[ $rpm_mitaka_or_higher -eq 1 ]]; then
                contrail-config --set /etc/nova/nova.conf DEFAULT rpc_backend rabbit
                contrail-config --set /etc/nova/nova.conf DEFAULT use_neutron True
                contrail-config --set /etc/nova/nova.conf keystone_authtoken auth_uri ${AUTH_PROTOCOL}://$CONTROLLER:5000
                contrail-config --set /etc/nova/nova.conf keystone_authtoken auth_url ${AUTH_PROTOCOL}://$CONTROLLER:35357
                contrail-config --set /etc/nova/nova.conf keystone_authtoken memcached_servers $CONTROLLER:11211
                contrail-config --set /etc/nova/nova.conf keystone_authtoken auth_type password
                contrail-config --set /etc/nova/nova.conf keystone_authtoken project_domain_name default
                contrail-config --set /etc/nova/nova.conf keystone_authtoken user_domain_name default
                contrail-config --set /etc/nova/nova.conf keystone_authtoken project_name $SERVICE_TENANT_NAME
                contrail-config --set /etc/nova/nova.conf keystone_authtoken username nova
                contrail-config --set /etc/nova/nova.conf keystone_authtoken password $NOVA_PASSWORD
                contrail-config --set /etc/nova/nova.conf glance api_servers http://$CONTROLLER:9292
                contrail-config --set /etc/nova/nova.conf oslo_concurrency lock_path /var/lib/nova/tmp
                contrail-config --set /etc/nova/nova.conf vnc enabled True
                contrail-config --set /etc/nova/nova.conf vnc vncserver_listen 0.0.0.0

                # Needs to updated
                # contrail-config --set /etc/nova/nova.conf DEFAULT my_ip MGMT_IP_ADDRESS_OF_CONTROLLER
                # contrail-config --set /etc/nova/nova.conf oslo_messaging_rabbit rabbit_userid openstack
                # contrail-config --set /etc/nova/nova.conf oslo_messaging_rabbit rabbit_password RABBIT_PASSWD
                # contrail-config --set /etc/nova/nova.conf vnc vncserver_proxyclient_address MGMT_IP_ADDRESS_OF_CONTROLLER

                contrail-config --set /etc/nova/nova.conf neutron auth_url ${AUTH_PROTOCOL}://$CONTROLLER:35357/$KEYSTONE_VERSION/
                contrail-config --set /etc/nova/nova.conf neutron auth_type password
                contrail-config --set /etc/nova/nova.conf neutron region_name $REGION_NAME
                contrail-config --set /etc/nova/nova.conf neutron project_name $SERVICE_TENANT_NAME
                contrail-config --set /etc/nova/nova.conf neutron username neutron
                contrail-config --set /etc/nova/nova.conf neutron password $NEUTRON_PASSWORD

                # virt_type
                hw_acceleration=$(egrep -c '(vmx|svm)' /proc/cpuinfo)
                if [[ $hw_acceleration -eq 0 ]]; then
                    contrail-config --set /etc/nova/nova.conf libvirt virt_type qemu
                fi
            fi
        fi

    fi
    openstack-config --set /etc/nova/nova.conf keystone_authtoken admin_tenant_name $SERVICE_TENANT_NAME
    openstack-config --set /etc/nova/nova.conf keystone_authtoken admin_user nova
    openstack-config --set /etc/nova/nova.conf keystone_authtoken admin_password $NOVA_PASSWORD
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_host $CONTROLLER
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_protocol http
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_port 35357
    openstack-config --set /etc/nova/nova.conf keystone_authtoken signing_dir /tmp/keystone-signing-nova
else
    if [[ $is_redhat -eq 1 ]]; then
        if [[ $rpm_juno_or_higher -eq 1 ]]; then
            openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova_contrail_vif.contrailvif.ContrailNetworkAPI
        fi

        if [[ $rpm_kilo_or_higher -eq 1 ]]; then
            # Neutron section in nova.conf
            openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova.network.neutronv2.api.API
            openstack-config --set /etc/nova/nova.conf neutron url ${QUANTUM_PROTOCOL}://$QUANTUM:9696/
            openstack-config --set /etc/nova/nova.conf neutron admin_tenant_name $SERVICE_TENANT_NAME
            openstack-config --set /etc/nova/nova.conf neutron auth_strategy keystone
            openstack-config --set /etc/nova/nova.conf neutron admin_auth_url ${AUTH_PROTOCOL}://$CONTROLLER:35357/$KEYSTONE_VERSION/
            openstack-config --set /etc/nova/nova.conf neutron admin_username neutron
            openstack-config --set /etc/nova/nova.conf neutron admin_password $NEUTRON_PASSWORD
            openstack-config --set /etc/nova/nova.conf neutron service_metadata_proxy True
            openstack-config --set /etc/nova/nova.conf compute compute_driver libvirt.LibvirtDriver
            openstack-config --set /etc/nova/nova.conf glance host $CONTROLLER

            # New configs in keystone section
            openstack-config --set /etc/nova/nova.conf keystone_authtoken username nova
            openstack-config --set /etc/nova/nova.conf keystone_authtoken password $NOVA_PASSWORD
        fi

        if [[ $rpm_mitaka_or_higher -eq 1 ]]; then
            contrail-config --set /etc/nova/nova.conf DEFAULT rpc_backend rabbit
            contrail-config --set /etc/nova/nova.conf DEFAULT use_neutron True
            contrail-config --set /etc/nova/nova.conf keystone_authtoken auth_uri ${AUTH_PROTOCOL}://$CONTROLLER:5000
            contrail-config --set /etc/nova/nova.conf keystone_authtoken auth_url ${AUTH_PROTOCOL}://$CONTROLLER:35357
            contrail-config --set /etc/nova/nova.conf keystone_authtoken memcached_servers $CONTROLLER:11211
            contrail-config --set /etc/nova/nova.conf keystone_authtoken auth_type password
            contrail-config --set /etc/nova/nova.conf keystone_authtoken project_domain_name default
            contrail-config --set /etc/nova/nova.conf keystone_authtoken user_domain_name default
            contrail-config --set /etc/nova/nova.conf keystone_authtoken project_name $SERVICE_TENANT_NAME
            contrail-config --set /etc/nova/nova.conf keystone_authtoken username nova
            contrail-config --set /etc/nova/nova.conf keystone_authtoken password $NOVA_PASSWORD
            contrail-config --set /etc/nova/nova.conf glance api_servers http://$CONTROLLER:9292
            contrail-config --set /etc/nova/nova.conf oslo_concurrency lock_path /var/lib/nova/tmp
            contrail-config --set /etc/nova/nova.conf vnc enabled True
            contrail-config --set /etc/nova/nova.conf vnc vncserver_listen 0.0.0.0

            # Needs to updated
            # contrail-config --set /etc/nova/nova.conf DEFAULT my_ip MGMT_IP_ADDRESS_OF_CONTROLLER
            # contrail-config --set /etc/nova/nova.conf oslo_messaging_rabbit rabbit_userid openstack
            # contrail-config --set /etc/nova/nova.conf oslo_messaging_rabbit rabbit_password RABBIT_PASSWD
            # contrail-config --set /etc/nova/nova.conf vnc vncserver_proxyclient_address MGMT_IP_ADDRESS_OF_CONTROLLER

            contrail-config --set /etc/nova/nova.conf neutron auth_url ${AUTH_PROTOCOL}://$CONTROLLER:35357/$KEYSTONE_VERSION/
            contrail-config --set /etc/nova/nova.conf neutron auth_type password
            contrail-config --set /etc/nova/nova.conf neutron region_name $REGION_NAME
            contrail-config --set /etc/nova/nova.conf neutron project_name $SERVICE_TENANT_NAME
            contrail-config --set /etc/nova/nova.conf neutron username neutron
            contrail-config --set /etc/nova/nova.conf neutron password $NEUTRON_PASSWORD

            # virt_type
            hw_acceleration=$(egrep -c '(vmx|svm)' /proc/cpuinfo)
            if [[ $hw_acceleration -eq 0 ]]; then
                contrail-config --set /etc/nova/nova.conf libvirt virt_type qemu
            fi
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

get_pci_whitelist_addresses() {
    orig_ifs=$IFS
    IFS=' '

    # Function arguments
    dpdk_iface=$1
    sriov_iface=$2

    ## check for VLANs
    _vlan_file="/proc/net/vlan/${dpdk_iface}"
    if [ -f "${_vlan_file}" ]; then
        dpdk_vlan_dev=`cat ${_vlan_file} | grep "Device:" | head -1 | awk '{print $2}'`
        if [ -n "${dpdk_vlan_dev}" ]; then
            ## use raw device and pass VLAN ID as a parameter
            dpdk_iface="${dpdk_vlan_dev}"
        fi
    fi

    ## check for Bonding
    bond_dir="/sys/class/net/${dpdk_iface}/bonding"
    if [ -d ${bond_dir} ]; then
        dpdk_ifaces=`cat ${bond_dir}/slaves | tr ' ' '\n' | sort | tr '\n' ' '`
    else
        dpdk_ifaces=(${dpdk_iface% })
    fi

    for dpdk_iface in $dpdk_ifaces; do
        # If the DPDK vRouter is not a virtual function, there is nothing to do
        if [ ! -e "/sys/class/net/${dpdk_iface}/device/physfn" ]; then
           continue
        fi

        # Also, if the physical parent interface of the VF used by the DPDK vRouter
        # is different than the SRIOV interface, there is nothing to do
        dpdk_parent=$(basename /sys/class/net/${dpdk_iface}/device/physfn/net/*)
        if [ $dpdk_parent != $sriov_iface ]; then
            continue
        fi

        # Get the PCI address of the DPDK vRouter interface
        dpdk_pci=$(basename $(readlink /sys/class/net/${dpdk_iface}/device))

        # Loop through the VFs of the SRIOV interface and whitelist all but the one
        # used by the DPDK vRouter
        IFS=$'\n'
        pci_to_whitelist=()
        pcis=($(readlink /sys/class/net/${sriov_iface}/device/virtfn*))
        for pci in ${pcis[@]}; do
            if [ $dpdk_pci != ${pci##*/} ]; then
                pci_to_whitelist[${#pci_to_whitelist[@]}]="${pci##*/}"
            fi
        done
        IFS=' '
    done

    echo ${pci_to_whitelist[@]}

    IFS=$orig_ifs
}

openstack-config --del /etc/nova/nova.conf DEFAULT pci_passthrough_whitelist
if [ ! -z $SRIOV_INTERFACES ] ; then
    OLD_IFS=$IFS
    IFS=','
    intf_list=($SRIOV_INTERFACES)
    physnet_list=($SRIOV_PHYSNETS)
    search_pattern=""
    i=0
    IFS='%'
    for intf in ${intf_list[@]}; do
        physnets=${physnet_list[$i]}
        i=$((i+1))
        phys=($physnets)
        for physnet_name in ${phys[@]}; do
            pci_addresses=$(get_pci_whitelist_addresses $DPDK_INTERFACE $intf)
            if [ -z $pci_addresses ]; then
                wl_list=("{ \"devname\": \"$intf\", \"physical_network\": \"$physnet_name\"}")
            else
                wl_list=()
                orig_ifs=$IFS
                IFS=' '
                for pci in $pci_addresses; do
                    wl_list[${#wl_list[@]}]="{ \"address\": \"$pci\", \"physical_network\": \"$physnet_name\" }"
                done
                IFS=$orig_ifs
            fi

            for wl in ${wl_list[@]}; do
                if [ $search_pattern ]; then
                    pci_wl="pci_passthrough_whitelist = $wl"
                    sed -i "/$search_pattern/a \
                           $pci_wl" /etc/nova/nova.conf
                else
                    openstack-config --set /etc/nova/nova.conf DEFAULT pci_passthrough_whitelist $wl
                fi
                search_pattern=$wl
            done
        done
    done
    IFS=$OLD_IFS
fi

if [ $VCENTER_IP ]; then
    openstack-config --set /etc/nova/nova.conf vmware host_ip $VCENTER_IP 
    openstack-config --set /etc/nova/nova.conf vmware host_username $VCENTER_USERNAME 
    openstack-config --set /etc/nova/nova.conf vmware host_password $VCENTER_PASSWORD 

    openstack-config --del /etc/nova/nova.conf vmware cluster_name
    cluster_list=$(echo $VCENTER_CLUSTER | tr "," "\n")
    for cluster in $cluster_list
    do
        echo "cluster_name = " $cluster >> /etc/nova/nova.conf
    done
    openstack-config --set /etc/nova/nova.conf vmware vcenter_dvswitch $VCENTER_DVSWITCH 
    openstack-config --set /etc/nova/nova.conf vmware insecure True
    openstack-config --del /etc/nova/nova.conf DEFAULT compute_driver
    openstack-config --set /etc/nova/nova.conf DEFAULT compute_driver nova.virt.vmwareapi.contrailVCDriver
    if [ -f /etc/nova/nova-compute.conf ]; then
        openstack-config --set /etc/nova/nova-compute.conf DEFAULT compute_driver nova.virt.vmwareapi.contrailVCDriver
        openstack-config --set /etc/nova/nova-compute.conf libvirt virt_type vmwareapi
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
    openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_AUTH_URL http://$INTERNAL_VIP:5000/$KEYSTONE_VERSION/
    openstack-config --set /etc/nova/nova.conf DEFAULT $OS_URL http://$CONTRAIL_INTERNAL_VIP:9696/
    openstack-config --set /etc/nova/nova.conf DEFAULT novncproxy_base_url http://$EXTERNAL_VIP:6080/vnc_auto.html
# Contrail HA.
elif [ "$INTERNAL_VIP" == "none" ] && [ "$CONTRAIL_INTERNAL_VIP" != "none" ]; then
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_host $CONTROLLER
    openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_AUTH_URL http://$CONTROLLER:5000/$KEYSTONE_VERSION/
    openstack-config --set /etc/nova/nova.conf DEFAULT $OS_URL http://$CONTRAIL_INTERNAL_VIP:9696/
    openstack-config --set /etc/nova/nova.conf DEFAULT novncproxy_base_url http://$CONTROLLER_MGMT:5999/vnc_auto.html
    openstack-config --set /etc/nova/nova.conf DEFAULT novncproxy_port 5999
# Openstack and Contrail in same nodes.
elif [ "$INTERNAL_VIP" != "none" ] && [ "$CONTRAIL_INTERNAL_VIP" == "none" ]; then
    openstack-config --set /etc/nova/nova.conf keystone_authtoken auth_host $INTERNAL_VIP
    openstack-config --set /etc/nova/nova.conf DEFAULT $ADMIN_AUTH_URL http://$INTERNAL_VIP:5000/$KEYSTONE_VERSION/
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

if [ $is_ubuntu -eq 1 ]; then
    if (egrep -q 'DISTRIB_RELEASE.*16.04' /etc/lsb-release); then
        for svc in nova-compute contrail-vrouter-agent contrail-vrouter-nodemgr; do
            chkconfig $svc on
        done
    else
        for svc in nova-compute supervisor-vrouter; do
            chkconfig $svc on
        done
    fi
else
    for svc in openstack-nova-compute supervisor-vrouter; do
        chkconfig $svc on
    done
fi
