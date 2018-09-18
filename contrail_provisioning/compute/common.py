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
from contrail_provisioning.compute.templates import contrail_vrouter_nodemgr_template
from contrail_provisioning.compute.templates import contrail_lbaas_auth_conf


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

        self.multi_net = False
        if self._args.non_mgmt_ip:
            self.multi_net = True
            self.vhost_ip = self._args.non_mgmt_ip
        else:
            self.vhost_ip = self._args.self_ip

        self.dev = None
        if self._args.physical_interface:
            if self._args.physical_interface in netifaces.interfaces():
                self.dev = self._args.physical_interface
            else:
                raise KeyError, 'Interface %s in present' % (
                        self._args.physical_interface)
        else:
            # Deduce the phy interface from ip, if configured
            self.dev = self.get_device_by_ip(self.vhost_ip)
        self.config_nova = not(getattr(self._args, 'no_nova_config', False))
        self.disc_ssl_enabled = False
        if (self._args.discovery_keyfile and
                self._args.discovery_certfile and self._args.discovery_cafile):
            self.disc_ssl_enabled = True

    def enable_kernel_core(self): 
        self.enable_kernel_core()
        local ('for s in abrt-vmcore abrtd kdump; do chkconfig ${s} on; done')

    def fixup_config_files(self):
        self.add_dev_tun_in_cgroup_device_acl()
        self.fixup_vrouter_nodemgr_param()
        self.fixup_contrail_vrouter_agent()
        self.fixup_contrail_vrouter_nodemgr()
        self.fixup_contrail_lbaas()

    def setup_lbaas_prereq(self):
        if self.pdist in ['centos', 'redhat']:
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

    def fixup_contrail_vrouter_nodemgr(self):
        template_vals = {'__contrail_discovery_ip__' : self._args.cfgm_ip,
                         '__contrail_discovery_port__': '5998'
                       }
        self._template_substitute_write(contrail_vrouter_nodemgr_template.template,
                                        template_vals, self._temp_dir_name + '/contrail-vrouter-nodemgr.conf')
        local("sudo mv %s/contrail-vrouter-nodemgr.conf /etc/contrail/contrail-vrouter-nodemgr.conf" %(self._temp_dir_name))
        conf_file = '/etc/contrail/contrail-vrouter-nodemgr.conf'
        if self.disc_ssl_enabled:
            certfile, cafile, keyfile = self._get_discovery_certs()
            configs = {'ssl': self.disc_ssl_enabled,
                       'cert': certfile,
                       'key': keyfile,
                       'cacert': cafile}
            for param, value in configs.items():
                self.set_config(conf_file, 'DISCOVERY', param, value)

    def fixup_contrail_vrouter_agent(self):
        keystone_ip = self._args.keystone_ip
        compute_ip = self._args.self_ip
        discovery_ip = self._args.contrail_internal_vip or self._args.cfgm_ip
        ncontrols = self._args.ncontrols
        non_mgmt_gw = self._args.non_mgmt_gw
        vgw_public_subnet = self._args.vgw_public_subnet
        vgw_public_vn_name = self._args.vgw_public_vn_name
        vgw_intf_list = self._args.vgw_intf_list
        vgw_gateway_routes = self._args.vgw_gateway_routes
        gateway_server_list = self._args.gateway_server_list
        qos_logical_queue = self._args.qos_logical_queue
        qos_queue_id_list = self._args.qos_queue_id
        default_hw_queue_qos = self._args.default_hw_queue_qos
        priority_id_list = self._args.priority_id
        priority_scheduling = self._args.priority_scheduling
        priority_bandwidth = self._args.priority_bandwidth

        self.mac = None
        if self.dev and self.dev != 'vhost0' :
            self.mac = netifaces.ifaddresses (self.dev)[netifaces.AF_LINK][0][
                        'addr']
            if not self.mac:
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
                    if self.config_nova:
                        local("openstack-config --set /etc/nova/nova.conf DEFAULT firewall_driver nova.virt.firewall.NoopFirewallDriver")
            else:
                with lcd(self._temp_dir_name):
                    local("sudo sed 's/dev=.*/dev=%s/g' /etc/contrail/agent_param.tmpl > agent_param.new" % self.dev)
                    local("sudo mv agent_param.new /etc/contrail/agent_param")
            vmware_dev = ""
            hypervisor_type = "kvm"
            mode=""
            gateway_mode = ""
            if self._args.mode == 'vcenter':
                mode="vcenter"
                vmware_dev = self.get_secondary_device(self.dev)
                hypervisor_type = "vmware"
            if self._args.vmware:
                vmware_dev = self.get_secondary_device(self.dev)
                hypervisor_type = "vmware"
            if self._args.hypervisor == 'docker':
                hypervisor_type = "docker"
            if compute_ip in gateway_server_list :
                gateway_mode = "server"

            # Set template options for DPDK mode
            pci_dev = ""
            platform_mode = "default"
            if self._args.dpdk:
                platform_mode = "dpdk"
                iface = self.dev
                if self.is_interface_vlan(self.dev):
                    iface = self.get_physical_interface_of_vlan(self.dev)
                pci_dev = local("/opt/contrail/bin/dpdk_nic_bind.py --status | grep -w %s | cut -d' ' -f 1" %(iface), capture=True)
                # If there is no PCI address, the device is a bond.
                # Bond interface in DPDK has zero PCI address.
                if not pci_dev:
                    pci_dev = "0000:00:00.0"

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
                '__gateway_mode__': gateway_mode,
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

            if qos_queue_id_list != None:
                qos_str = ""
                qos_str += "[QOS]\n"
                num_sections = len(qos_logical_queue)
                if(len(qos_logical_queue) == len(qos_queue_id_list) and default_hw_queue_qos):
                    num_sections = num_sections - 1
                for i in range(num_sections):
                    qos_str += '[%s%s]\n' %("QUEUE-", qos_queue_id_list[i])
                    qos_str += "# Logical nic queues for qos config\n"
                    qos_str += "logical_queue=[%s]\n\n" % qos_logical_queue[i].replace(",",", ")

                if (default_hw_queue_qos):
                    qos_str += '[%s%s]\n' %("QUEUE-", qos_queue_id_list[-1])
                    qos_str += "# This is the default hardware queue\n"
                    qos_str += "default_hw_queue= true\n\n"
                    qos_str += "# Logical nic queues for qos config\n"

                    if(len(qos_logical_queue) == len(qos_queue_id_list)):
                        qos_str += "logical_queue=[%s]\n\n" % qos_logical_queue[-1].replace(",",", ")
                    else:
                        qos_str += "logical_queue=[ ]\n\n"
                filename = self._temp_dir_name + "/vnswad.conf"
                with open(filename, "a") as f:
                    f.write(qos_str)

            if priority_id_list != None:
                priority_group_str = ""
                priority_group_str += "[QOS-NIANTIC]\n"
                for i in range(len(priority_id_list)):
                    priority_group_str += '[%s%s]\n' %("PG-", priority_id_list[i])
                    priority_group_str += "# Scheduling algorithm for priority group (strict/rr)\n"
                    priority_group_str += "scheduling=" + priority_scheduling[i] + "\n\n"
                    priority_group_str += "# Total hardware queue bandwidth used by priority group\n"
                    priority_group_str += "bandwidth=" + priority_bandwidth[i] + "\n\n"

                filename = self._temp_dir_name + "/vnswad.conf"
                with open(filename, "a") as f:
                    f.write(priority_group_str)

            if self._args.metadata_secret:
                local("sudo openstack-config --set %s/vnswad.conf METADATA \
                       metadata_proxy_secret %s" % (self._temp_dir_name, self._args.metadata_secret))

            local("sudo cp %s/vnswad.conf /etc/contrail/contrail-vrouter-agent.conf" %(self._temp_dir_name))
            local("sudo rm %s/vnswad.conf*" %(self._temp_dir_name))
            conf_file = '/etc/contrail/contrail-vrouter-agent.conf'
            if self.disc_ssl_enabled:
                certfile, cafile, keyfile = self._get_discovery_certs()
                configs = {'ssl': str(self.disc_ssl_enabled).lower(),
                           'cert': certfile,
                           'key': keyfile,
                           'cacert': cafile}
                for param, value in configs.items():
                    self.set_config(conf_file, 'DISCOVERY', param, value)

            self.fixup_vhost0_interface_configs()

    def fixup_contrail_lbaas(self):
        auth_url = self._args.keystone_auth_protocol + '://' + self._args.keystone_ip
        auth_url += ':' + self._args.keystone_auth_port
        auth_url += '/' + 'v2.0'
        template_vals = {'__admin_tenant_name__' : 'service',
                         '__admin_user__' : 'neutron',
                         '__admin_password__' : self._args.neutron_password,
                         '__auth_url__': auth_url
                       }
        self._template_substitute_write(contrail_lbaas_auth_conf.template,
                                        template_vals, self._temp_dir_name + '/contrail-lbaas-auth.conf')
        local("sudo mv %s/contrail-lbaas-auth.conf /etc/contrail/contrail-lbaas-auth.conf" %(self._temp_dir_name))

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
        use_ssl = False
        if self._args.quantum_service_protocol == 'https':
            use_ssl = True
        prov_args = "--host_name %s --host_ip %s --api_server_ip %s --oper add " \
                    "--admin_user %s --admin_password %s --admin_tenant_name %s " \
                    "--openstack_ip %s --api_server_use_ssl %s" \
                    %(compute_hostname, compute_ip, self._args.cfgm_ip,
                      self._args.keystone_admin_user,
                      self._args.keystone_admin_password,
                      self._args.keystone_admin_tenant_name,
                      self._args.keystone_ip,
                      use_ssl)
        if self._args.dpdk:
            prov_args += " --dpdk_enabled"
        local("python /opt/contrail/utils/provision_vrouter.py %s" %(prov_args))

    def setup(self):
        self.disable_selinux()
        self.disable_iptables()
        self.setup_coredump()
        if not self._args.vcenter_server:
           self.fixup_config_files()
           self.run_services()
           self.add_vnc_config()

