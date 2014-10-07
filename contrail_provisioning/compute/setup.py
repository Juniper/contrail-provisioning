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


class ComputeSetup(ContrailSetup, ComputeNetworkSetup):
    def __init__(self, args_str = None):
        super(ComputeSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.global_defaults = {
            'cfgm_ip': '127.0.0.1',
            'cfgm_user': 'root',
            'cfgm_passwd': 'c0ntrail123',
            'keystone_ip': '127.0.0.1',
            'openstack_mgmt_ip': None,
            'service_token': '',
            'self_ip': '127.0.0.1',
            'ncontrols': '2',
            'non_mgmt_ip': None,
            'non_mgmt_gw': None,
            'public_subnet': None,
            'public_vn_name': None,
            'vgw_intf': None,
            'gateway_routes': None,
            'haproxy': False,
            'keystone_auth_protocol':'http',
            'keystone_auth_port':'35357',
            'keystone_admin_user':'admin',
            'keystone_admin_passwd':'admin',
            'keystone_admin_tenant_name':'admin',
            'amqp_server_ip':'127.0.0.1',
            'quantum_service_protocol':'http',
            'vmware': None,
            'vmware_username': 'root',
            'vmware_passwd': 'c0ntrail123',
            'vmware_vmpg_vswitch': 'c0ntrail123',
            'no_contrail_openstack': False,
        }

        self.parse_args(args_str)

    def parse_args(self, args_str):
        '''
        Eg. setup-vnc-vrouter --cfgm_ip 10.1.5.11 --keystone_ip 10.1.5.12
                   --self_ip 10.1.5.12 --service_token 'c0ntrail123' --ncontrols 1
                   --haproxy --internal_vip 10.1.5.200
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--cfgm_ip", help = "IP Address of the config node")
        parser.add_argument("--cfgm_user", help = "Sudo User in the config node")
        parser.add_argument("--cfgm_passwd", help = "Password of the Sudo user in the config node")
        parser.add_argument("--keystone_ip", help = "IP Address of the keystone node")
        parser.add_argument("--openstack_mgmt_ip", help = "Mgmt IP Address of the openstack node if it is different from openstack_IP")
        parser.add_argument("--service_token", help = "The service password to access keystone")
        parser.add_argument("--self_ip", help = "IP Address of this(compute) node")
        parser.add_argument("--mgmt_self_ip", help = "Management IP Address of this system")
        parser.add_argument("--ncontrols", help = "Number of control-nodes in the system")
        parser.add_argument("--non_mgmt_ip", help = "IP Address of non-management interface(fabric network) on the compute  node")
        parser.add_argument("--non_mgmt_gw", help = "Gateway Address of the non-management interface(fabric network) on the compute node")
        parser.add_argument("--public_subnet", help = "Subnet of the virtual network used for public access")
        parser.add_argument("--physical_interface", help = "Name of the physical interface to use")
        parser.add_argument("--vgw_intf", help = "Virtual gateway intreface name")
        parser.add_argument("--vgw_public_subnet", help = "Subnet of the virtual network used for public access")
        parser.add_argument("--vgw_public_vn_name", help = "Fully-qualified domain name (FQDN) of the routing-instance that needs public access")
        parser.add_argument("--vgw_intf_list", help = "List of virtual getway intreface")
        parser.add_argument("--vgw_gateway_routes", help = "Static route to be configured in agent configuration for VGW")
        parser.add_argument("--public_vn_name", help = "Fully-qualified domain name (FQDN) of the routing-instance that needs public access")
        parser.add_argument("--gateway_routes", help = "List of route need to be added in agent configuration for virtual gateway")
        parser.add_argument("--haproxy", help = "Enable haproxy", action="store_true")
        parser.add_argument("--keystone_auth_protocol", help = "Auth protocol used to talk to keystone")
        parser.add_argument("--keystone_auth_port", help = "Port of Keystone to talk to")
        parser.add_argument("--keystone_admin_user", help = "Keystone admin tenants user name")
        parser.add_argument("--keystone_admin_password", help = "Keystone admin user's password")
        parser.add_argument("--keystone_admin_tenant_name", help = "Keystone admin tenant name")
        parser.add_argument("--quantum_service_protocol", help = "Protocol of neutron for nova to use")
        parser.add_argument("--quantum_port", help = "Quantum server port")
        parser.add_argument("--amqp_server_ip", help = "IP of the AMQP server to be used for openstack")
        parser.add_argument("--vmware", help = "The Vmware ESXI IP")
        parser.add_argument("--vmware_username", help = "The Vmware ESXI username")
        parser.add_argument("--vmware_passwd", help = "The Vmware ESXI password")
        parser.add_argument("--vmware_vmpg_vswitch", help = "The Vmware VMPG vswitch name")
        parser.add_argument("--internal_vip", help = "Internal VIP Address of openstack nodes")
        parser.add_argument("--external_vip", help = "External VIP Address of openstack nodes")
        parser.add_argument("--contrail_internal_vip", help = "VIP Address of config  nodes")
        parser.add_argument("--no_contrail_openstack", help = "Do not provision contrail Openstack in compute node.", action="store_true")
        parser.add_argument("--metadata_secret", help = "Metadata Proxy secret from openstack node")

        self._args = parser.parse_args(self.remaining_argv)

    def enable_kernel_core(self): 
        self.enable_kernel_core()
        local ('for s in abrt-vmcore abrtd kdump; do chkconfig ${s} on; done')

    def fixup_config_files(self):
        self.fixup_nova_conf()
        self.add_dev_tun_in_cgroup_device_acl()
        self.fixup_vrouter_nodemgr_param()
        self.fixup_contrail_vrouter_agent()

    def fixup_nova_conf(self):
        with settings(warn_only = True):
            if self.pdist in ['Ubuntu']:
                cmd = "dpkg -l | grep 'ii' | grep nova-compute | grep -v vif | grep -v nova-compute-kvm | awk '{print $3}'"
                nova_compute_version = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
                if (nova_compute_version != "2:2013.1.3-0ubuntu1"):
                    local("openstack-config --set /etc/nova/nova.conf DEFAULT neutron_admin_auth_url http://%s:5000/v2.0" % self._args.keystone_ip)

        nova_conf_file = "/etc/nova/nova.conf"
        if os.path.exists(nova_conf_file):
            local("sudo sed -i 's/rpc_backend = nova.openstack.common.rpc.impl_qpid/#rpc_backend = nova.openstack.common.rpc.impl_qpid/g' %s" \
                   % (nova_conf_file))

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
            if self._args.vmware:
                vmware_dev = self.get_secondary_device(self.dev)
                hypervisor_type = "vmware"
            vnswad_conf_template_vals = {'__contrail_vhost_ip__': cidr,
                '__contrail_vhost_gateway__': self.gateway,
                '__contrail_discovery_ip__': discovery_ip,
                '__contrail_discovery_ncontrol__': ncontrols,
                '__contrail_physical_intf__': self.dev,
                '__contrail_control_ip__': compute_ip,
                '__hypervisor_type__': hypervisor_type,
                '__vmware_physical_interface__': vmware_dev,
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
                           metadata_proxy_secret %s" % (temp_dir_name, self._args.metadata_secret))

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

        if self.pdist in ['Ubuntu']:
            self._rewrite_net_interfaces_file(self.dev, self.mac, self.vhost_ip, self.netmask, self.gateway)
        # end self.pdist == ubuntu

        else: # of if self.dev and self.dev != 'vhost0'
            if not os.path.isfile("/etc/contrail/contrail-vrouter-agent.conf"):
                if os.path.isfile("/opt/contrail/contrail_installer/contrail_config_templates/agent_xml2ini.py"):
                    local("sudo python /opt/contrail/contrail_installer/contrail_config_templates/agent_xml2ini.py")
        #end if self.dev and self.dev != 'vhost0' :

    def build_ctrl_details(self):
        ctrl_infos = []
        ctrl_details = "%s/ctrl-details" % self._temp_dir_name
        ctrl_infos.append('SERVICE_TOKEN=%s' % self._args.service_token)
        ctrl_infos.append('AUTH_PROTOCOL=%s' % self._args.keystone_auth_protocol)
        ctrl_infos.append('QUANTUM_PROTOCOL=%s' % self._args.quantum_service_protocol)
        ctrl_infos.append('ADMIN_TOKEN=%s' % self._args.keystone_admin_password)
        ctrl_infos.append('CONTROLLER=%s' % self._args.keystone_ip)
        ctrl_infos.append('AMQP_SERVER=%s' % self._args.amqp_server_ip)
        if self._args.haproxy:
            ctrl_infos.append('QUANTUM=127.0.0.1')
        else:
            ctrl_infos.append('QUANTUM=%s' % self._args.cfgm_ip)
        ctrl_infos.append('QUANTUM_PORT=%s' % self._args.quantum_port)

        ctrl_infos.append('COMPUTE=%s' % self._args.self_ip)
        ctrl_infos.append('CONTROLLER_MGMT=%s' % self._args.openstack_mgmt_ip)
        if self._args.vmware:
            ctrl_infos.append('VMWARE_IP=%s' % self._args.vmware)
            ctrl_infos.append('VMWARE_USERNAME=%s' % self._args.vmware_username)
            ctrl_infos.append('VMWARE_PASSWD=%s' % self._args.vmware_passwd)
            ctrl_infos.append('VMWARE_VMPG_VSWITCH=%s' % self._args.vmware_vmpg_vswitch)
        self.update_vips_in_ctrl_details(ctrl_infos)

        for ctrl_info in ctrl_infos:
            local ("sudo echo %s >> %s" % (ctrl_info, ctrl_details))
        local("sudo cp %s /etc/contrail/ctrl-details" % ctrl_details)
        local("sudo rm %s/ctrl-details" %(self._temp_dir_name))

    def run_services(self):
        contrail_openstack = not(getattr(self._args, 'no_contrail_openstack', False))
        if contrail_openstack:
            if self._fixed_qemu_conf:
                if self.pdist in ['centos', 'fedora', 'redhat']:
                    local("sudo service libvirtd restart")
                if self.pdist in ['Ubuntu']:
                    local("sudo service libvirt-bin restart")

            # running compute-server-setup.sh on cfgm sets nova.conf's
            # sql access from ip instead of localhost, causing privilege
            # degradation for nova tables
            local("sudo compute-server-setup.sh")
        else:
            #use contrail specific vif driver
            local('openstack-config --set /etc/nova/nova.conf DEFAULT libvirt_vif_driver nova_contrail_vif.contrailvif.VRouterVIFDriver')
            # Use noopdriver for firewall
            local('openstack-config --set /etc/nova/nova.conf DEFAULT firewall_driver nova.virt.firewall.NoopFirewallDriver')
            network_api = 'quantum'
            with(open('/etc/nova/nova.conf', 'r+')) as nova_conf:
                if 'neutron_url' in nova_conf.read():
                    network_api = 'neutron'
            local('openstack-config --set /etc/nova/nova.conf DEFAULT %s_connection_host %s' % (network_api, self._args.cfgm_ip))
            local('openstack-config --set /etc/nova/nova.conf DEFAULT %s_url http://%s:9696' % (network_api, self._args.cfgm_ip))
            local('openstack-config --set /etc/nova/nova.conf DEFAULT %s_admin_password %s' % (network_api, self._args.service_token))

        for svc in ['openstack-nova-compute', 'supervisor-vrouter']:
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
                          self._args.keystone_admin_tenant_name, self._args.openstack_mgmt_ip)
            run("python /opt/contrail/utils/provision_vrouter.py %s" %(prov_args))

    def setup(self):
        self.disable_selinux()
        self.disable_iptables()
        self.setup_coredump()
        self.fixup_config_files()
        self.build_ctrl_details()
        self.run_services()
        self.add_vnc_config()

def main(args_str = None):
    compute = ComputeSetup(args_str)
    compute.setup()

if __name__ == "__main__":
   main() 
