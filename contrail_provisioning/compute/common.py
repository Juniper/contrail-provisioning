#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import socket
import netaddr
import argparse
import netifaces
import subprocess
import ConfigParser

from fabric.api import local, run
from fabric.state import env
from fabric.context_managers import settings, lcd

from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.compute.network import ComputeNetworkSetup
from contrail_provisioning.compute.templates import vrouter_nodemgr_param
from contrail_provisioning.compute.templates import contrail_vrouter_agent_conf


class ExtList (list):
    def findex (self, fun):
        for i, x in enumerate (self):
            if fun (x):
                return i
        raise LookupError, 'No matching element in list'


class ComputeBaseSetup(ContrailSetup, ComputeNetworkSetup):
    def __init__(self, compute_args, args_str=None):
        super(ComputeBaseSetup, self).__init__()
        self._args = compute_args

    def enable_kernel_core(self): 
        self.enable_kernel_core()
        local ('for s in abrt-vmcore abrtd kdump; do chkconfig ${s} on; done')

    def fixup_config_files(self):
        self.add_dev_tun_in_cgroup_device_acl()
        self.fixup_vrouter_nodemgr_param()
        self.fixup_contrail_vrouter_agent()

    def setup_lbaas_prereq(self):
        if self.pdist in ['centos']:
           local('groupadd -f nogroup')
           local("sed -i s/'Defaults    requiretty'/'#Defaults    requiretty'/g /etc/sudoers")

    def add_dev_tun_in_cgroup_device_acl(self):
        # add /dev/net/tun in cgroup_device_acl needed for type=ethernet interfaces
        with settings(warn_only = True):
            ret = local("sudo grep -q '^cgroup_device_acl' /etc/libvirt/qemu.conf")
            if ret.return_code == 1:
                if  self.pdist in ['centos', 'redhat']:
                    local('sudo echo "clear_emulator_capabilities = 1" >> /etc/libvirt/qemu.conf')
                    local('sudo echo \'user = "root"\' >> /etc/libvirt/qemu.conf')
                    local('sudo echo \'group = "root"\' >> /etc/libvirt/qemu.conf')
                local('sudo echo \'cgroup_device_acl = [\' >> /etc/libvirt/qemu.conf')
                local('sudo echo \'    "/dev/null", "/dev/full", "/dev/zero",\' >> /etc/libvirt/qemu.conf')
                local('sudo echo \'    "/dev/random", "/dev/urandom",\' >> /etc/libvirt/qemu.conf')
                local('sudo echo \'    "/dev/ptmx", "/dev/kvm", "/dev/kqemu",\' >> /etc/libvirt/qemu.conf')
                local('sudo echo \'    "/dev/rtc", "/dev/hpet","/dev/net/tun",\' >> /etc/libvirt/qemu.conf')
                local('sudo echo \']\' >> /etc/libvirt/qemu.conf')
                self._fixed_qemu_conf = True
            # add "alias bridge off" in /etc/modprobe.conf for Centos
            if  self.pdist in ['centos', 'redhat']:
                local('sudo echo "alias bridge off" > /etc/modprobe.conf')

    def fixup_vrouter_nodemgr_param(self):
        template_vals = {'__contrail_discovery_ip__': self._args.contrail_internal_vip or self._args.cfgm_ip
                        }
        self._template_substitute_write(vrouter_nodemgr_param.template,
                                        template_vals, self._temp_dir_name + '/vrouter_nodemgr_param')
        local("sudo mv %s/vrouter_nodemgr_param /etc/contrail/vrouter_nodemgr_param" %(self._temp_dir_name))

    def fixup_contrail_vrouter_agent(self):
        keystone_ip = self._args.keystone_ip
        compute_ip = self._args.self_ip
        discovery_ip = self._args.contrail_internal_vip or self._args.cfgm_ip
        ncontrols = self._args.ncontrols
        physical_interface = self._args.physical_interface
        non_mgmt_ip = self._args.non_mgmt_ip
        non_mgmt_gw = self._args.non_mgmt_gw
        self.vhost_ip = compute_ip
        vgw_public_subnet = self._args.vgw_public_subnet
        vgw_public_vn_name = self._args.vgw_public_vn_name
        vgw_intf_list = self._args.vgw_intf_list
        vgw_gateway_routes = self._args.vgw_gateway_routes
        self.multi_net= False
        if non_mgmt_ip :
            self.multi_net= True
            self.vhost_ip= non_mgmt_ip

        self.dev = None
        compute_dev = None
        if physical_interface:
            if physical_interface in netifaces.interfaces ():
                self.dev = physical_interface
            else:
                 raise KeyError, 'Interface %s in present' % (
                         physical_interface)
        else:
            # deduce the phy interface from ip, if configured
            self.dev = self.get_device_by_ip (self.vhost_ip)
            if self.multi_net:
                compute_dev = self.get_device_by_ip (compute_ip)

        self.mac = None
        if self.dev and self.dev != 'vhost0' :
            self.mac = netifaces.ifaddresses (self.dev)[netifaces.AF_LINK][0][
                        'addr']
            if self.mac:
                with open ('%s/default_pmac' % self._temp_dir_name, 'w') as f:
                    f.write (self.mac)
                with settings(warn_only = True):
                    local("sudo mv %s/default_pmac /etc/contrail/default_pmac" % (self._temp_dir_name))
            else:
                raise KeyError, 'Interface %s Mac %s' % (str (self.dev), str (self.mac))
            self.netmask = netifaces.ifaddresses(self.dev)[netifaces.AF_INET][0][
                            'netmask']
            if self.multi_net:
                self.gateway= non_mgmt_gw
            else:
                self.gateway = self.find_gateway(self.dev)
            cidr = str (netaddr.IPNetwork('%s/%s' % (self.vhost_ip, self.netmask)))

            if vgw_public_subnet:
                with lcd(self._temp_dir_name):
                    # Manipulating the string to use in agent_param
                    vgw_public_subnet_str=[]
                    for i in vgw_public_subnet[1:-1].split(";"):
                        j=i[1:-1].split(",")
                        j=";".join(j)
                        vgw_public_subnet_str.append(j)
                    vgw_public_subnet_str=str(tuple(vgw_public_subnet_str)).replace("'","")
                    vgw_public_subnet_str=vgw_public_subnet_str.replace(" ","")
                    vgw_intf_list_str=str(tuple(vgw_intf_list[1:-1].split(";"))).replace(" ","")

                    local("sudo sed 's@dev=.*@dev=%s@g;s@vgw_subnet_ip=.*@vgw_subnet_ip=%s@g;s@vgw_intf=.*@vgw_intf=%s@g' /etc/contrail/agent_param.tmpl > agent_param.new" % 
                          (self.dev,vgw_public_subnet_str,vgw_intf_list_str))
                    local("sudo mv agent_param.new /etc/contrail/agent_param")
                    local("openstack-config --set /etc/nova/nova.conf DEFAULT firewall_driver nova.virt.firewall.NoopFirewallDriver")
            else:
                with lcd(self._temp_dir_name):
                    local("sudo sed 's/dev=.*/dev=%s/g' /etc/contrail/agent_param.tmpl > agent_param.new" % self.dev)
                    local("sudo mv agent_param.new /etc/contrail/agent_param")
            vmware_dev = ""
            hypervisor_type = "kvm"
            mode=""
            if self._args.orchestrator == 'vcenter':
                mode="vcenter"
                vmware_dev = "eth1"
                hypervisor_type = "vmware"
            if self._args.vmware:
                vmware_dev = self.get_secondary_device(self.dev)
                hypervisor_type = "vmware"

            # Set template options for DPDK mode
            pci_dev = ""
            platform_mode = "default"
            if self._args.dpdk:
                platform_mode = "dpdk"
                pci_dev = local("/opt/contrail/bin/dpdk_nic_bind.py --status | grep %s | cut -d' ' -f 1" %(self.dev), capture=True)

            vnswad_conf_template_vals = {'__contrail_vhost_ip__': cidr,
                '__contrail_vhost_gateway__': self.gateway,
                '__contrail_discovery_ip__': discovery_ip,
                '__contrail_discovery_ncontrol__': ncontrols,
                '__contrail_physical_intf__': self.dev,
                '__contrail_control_ip__': compute_ip,
                '__hypervisor_type__': hypervisor_type,
                '__hypervisor_mode__': mode,
                '__vmware_physical_interface__': vmware_dev,
                '__contrail_work_mode__': platform_mode,
                '__pci_dev__': pci_dev,
                '__physical_interface_mac__': self.mac,
            }
            self._template_substitute_write(contrail_vrouter_agent_conf.template,
                    vnswad_conf_template_vals, self._temp_dir_name + '/vnswad.conf')

            if vgw_public_vn_name and vgw_public_subnet:
                vgw_public_vn_name = vgw_public_vn_name[1:-1].split(';')
                vgw_public_subnet = vgw_public_subnet[1:-1].split(';')
                vgw_intf_list = vgw_intf_list[1:-1].split(';')
                gateway_str = ""
                if vgw_gateway_routes != None:
                    vgw_gateway_routes = vgw_gateway_routes[1:-1].split(';')
                for i in range(len(vgw_public_vn_name)):
                    gateway_str += '\n[%s%d]\n' %("GATEWAY-", i)
                    gateway_str += "# Name of the routing_instance for which the gateway is being configured\n"
                    gateway_str += "routing_instance=" + vgw_public_vn_name[i] + "\n\n"
                    gateway_str += "# Gateway interface name\n"
                    gateway_str += "interface=" + vgw_intf_list[i] + "\n\n"
                    gateway_str += "# Virtual network ip blocks for which gateway service is required. Each IP\n"
                    gateway_str += "# block is represented as ip/prefix. Multiple IP blocks are represented by\n"
                    gateway_str += "# separating each with a space\n"
                    gateway_str += "ip_blocks="

                    if vgw_public_subnet[i].find("[") !=-1:
                        for ele in vgw_public_subnet[i][1:-1].split(","):
                            gateway_str += ele[1:-1] + " "
                    else:
                        gateway_str += vgw_public_subnet[i]
                    gateway_str += "\n\n"
                    if vgw_gateway_routes != None and i < len(vgw_gateway_routes):
                        if  vgw_gateway_routes[i] != '[]':
                            gateway_str += "# Routes to be exported in routing_instance. Each route is represented as\n"
                            gateway_str += "# ip/prefix. Multiple routes are represented by separating each with a space\n"
                            gateway_str += "routes="
                            if vgw_gateway_routes[i].find("[") !=-1:
                                for ele in vgw_gateway_routes[i][1:-1].split(","):
                                    gateway_str += ele[1:-1] + " "
                            else:
                                gateway_str += vgw_gateway_routes[i]
                            gateway_str += "\n"
                filename = self._temp_dir_name + "/vnswad.conf"
                with open(filename, "a") as f:
                    f.write(gateway_str)

            if self._args.metadata_secret:
                local("sudo openstack-config --set %s/vnswad.conf METADATA \
                       metadata_proxy_secret %s" % (self._temp_dir_name, self._args.metadata_secret))

            local("sudo cp %s/vnswad.conf /etc/contrail/contrail-vrouter-agent.conf" %(self._temp_dir_name))
            local("sudo rm %s/vnswad.conf*" %(self._temp_dir_name))

            self.fixup_vhost0_interface_configs()

    def fixup_vhost0_interface_configs(self):
        if self.pdist in ['centos', 'fedora', 'redhat']:
            ## make ifcfg-vhost0
            with open ('%s/ifcfg-vhost0' % self._temp_dir_name, 'w') as f:
                f.write ('''#Contrail vhost0
DEVICE=vhost0
ONBOOT=yes
BOOTPROTO=none
IPV6INIT=no
USERCTL=yes
IPADDR=%s
NETMASK=%s
NM_CONTROLLED=no
#NETWORK MANAGER BUG WORKAROUND
SUBCHANNELS=1,2,3
''' % (self.vhost_ip, self.netmask ))
                # Don't set gateway and DNS on vhost0 if on non-mgmt network
                if not self.multi_net:
                    if self.gateway:
                        f.write('GATEWAY=%s\n' %( self.gateway ) )
                    dns_list = self.get_dns_servers(self.dev)
                    for i, dns in enumerate(dns_list):
                        f.write('DNS%d=%s\n' % (i+1, dns))
                    domain_list = self.get_domain_search_list()
                    if domain_list:
                        f.write('DOMAIN="%s"\n'% domain_list)

                prsv_cfg = []
                mtu = self.get_if_mtu (self.dev)
                if mtu:
                    dcfg = 'MTU=%s' % str(mtu)
                    f.write(dcfg+'\n')
                    prsv_cfg.append (dcfg)
                f.flush ()
            if self.dev != 'vhost0':
                with settings(warn_only = True):
                    local("sudo mv %s/ifcfg-vhost0 /etc/sysconfig/network-scripts/ifcfg-vhost0" % (self._temp_dir_name))
                    local("sync")
                ## make ifcfg-$dev
                if not os.path.isfile (
                        '/etc/sysconfig/network-scripts/ifcfg-%s.rpmsave' % self.dev):
                    with settings(warn_only = True):
                        local("sudo cp /etc/sysconfig/network-scripts/ifcfg-%s /etc/sysconfig/network-scripts/ifcfg-%s.rpmsave" % (self.dev, self.dev))
                self._rewrite_ifcfg_file('%s/ifcfg-%s' % (self._temp_dir_name, self.dev), self.dev, prsv_cfg)

                if self.multi_net :
                    self.migrate_routes(self.dev)

                with settings(warn_only = True):
                    local("sudo mv %s/ifcfg-%s /etc/contrail/" % (self._temp_dir_name, self.dev))

                    local("sudo chkconfig network on")
                    local("sudo chkconfig supervisor-vrouter on")
        # end self.pdist == centos | fedora | redhat
        # setup lbaas prereqs
        self.setup_lbaas_prereq()

        if self.pdist in ['Ubuntu']:
            self._rewrite_net_interfaces_file(self.dev, self.mac, self.vhost_ip, self.netmask, self.gateway,
                        self._args.vmware, self._args.vmware_vmpg_vswitch_mtu,
                        self._args.vmware_datanic_mtu)
        # end self.pdist == ubuntu

        else: # of if self.dev and self.dev != 'vhost0'
            if not os.path.isfile("/etc/contrail/contrail-vrouter-agent.conf"):
                if os.path.isfile("/opt/contrail/contrail_installer/contrail_config_templates/agent_xml2ini.py"):
                    local("sudo python /opt/contrail/contrail_installer/contrail_config_templates/agent_xml2ini.py")
        #end if self.dev and self.dev != 'vhost0' :

    def run_services(self):
        for svc in ['supervisor-vrouter']:
            local('chkconfig %s on' % svc)

    def add_vnc_config(self):
        compute_ip = self._args.self_ip
        compute_hostname = socket.gethostname()
        with settings(host_string = '%s@%s' %(self._args.cfgm_user, self._args.cfgm_ip), password=self._args.cfgm_passwd):
            prov_args = "--host_name %s --host_ip %s --api_server_ip %s --oper add " \
                        "--admin_user %s --admin_password %s --admin_tenant_name %s --openstack_ip %s" \
                        %(compute_hostname, compute_ip, self._args.cfgm_ip, 
                          self._args.keystone_admin_user,
                          self._args.keystone_admin_password,
                          self._args.keystone_admin_tenant_name, self._args.keystone_ip)
            run("python /opt/contrail/utils/provision_vrouter.py %s" %(prov_args))

    def setup(self):
        self.disable_selinux()
        self.disable_iptables()
        self.setup_coredump()
        self.fixup_config_files()
        self.run_services()
        self.add_vnc_config()
