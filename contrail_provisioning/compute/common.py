#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import re
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

def run_command(cmd):
    # This function can raise ValueError exception.
    # It's the responsibility of the caller to handle it.
    return subprocess.check_output(cmd, shell=True)

def is_ostype_ubuntu():
    if os.path.isfile("/etc/lsb-release"):
        lsb_file = open("/etc/lsb-release", 'r')
        lsb_filetext = lsb_file.read()
        lsb_file.close()
        matches = re.findall('DISTRIB_ID.*Ubuntu', lsb_filetext)
        if matches:
            return True
    return False

def is_xenial_or_above():
    if os.path.isfile("/etc/lsb-release"):
        lsb_file = open("/etc/lsb-release", 'r')
        lsb_filetext = lsb_file.read()
        lsb_file.close()
        matches = re.findall('DISTRIB_RELEASE.*16.04', lsb_filetext)
        if matches:
            return True
    return False

def insert_line_to_file(line,file_name,pattern=None):
    with settings(warn_only = True):
        if pattern:
            local('sed -i \'/%s/d\' %s' %(pattern,file_name))
        local('printf "%s\n" >> %s' %(line, file_name))

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
        template_vals = {
                         '__contrail_collectors__': \
                             ' '.join('%s:%s' %(server, '8086') \
                             for server in self._args.collectors)
                        }
        self._template_substitute_write(vrouter_nodemgr_param.template,
                                        template_vals, self._temp_dir_name + '/vrouter_nodemgr_param')
        local("sudo mv %s/vrouter_nodemgr_param /etc/contrail/vrouter_nodemgr_param" %(self._temp_dir_name))

    def fixup_contrail_vrouter_nodemgr(self):
        template_vals = {
                         '__contrail_collectors__': \
                             ' '.join('%s:%s' %(server, '8086') \
                             for server in self._args.collectors)
                       }
        self._template_substitute_write(contrail_vrouter_nodemgr_template.template,
                                        template_vals, self._temp_dir_name + '/contrail-vrouter-nodemgr.conf')
        local("sudo mv %s/contrail-vrouter-nodemgr.conf /etc/contrail/contrail-vrouter-nodemgr.conf" %(self._temp_dir_name))


    def setup_hugepages_node(self, dpdk_args):
        """Setup hugepages on one or list of nodes
        """
        # How many times DPDK inits hugepages (rte_eal_init())
        # See function map_all_hugepages() in DPDK
        DPDK_HUGEPAGES_INIT_TIMES = 2

        # get required size of hugetlbfs
        factor = int(dpdk_args['huge_pages'])

        print dpdk_args

        if factor == 0:
            factor = 1

        with settings(warn_only = True):
            # set number of huge pages
            memsize = run_command("grep MemTotal /proc/meminfo | tr -s ' ' | cut -d' ' -f 2 | tr -d '\n'")
            pagesize = run_command("grep Hugepagesize /proc/meminfo | tr -s ' ' | cut -d' ' -f 2 | tr -d '\n'")
            reserved = run_command("grep HugePages_Total /proc/meminfo | tr -s ' ' | cut -d' ' -f 2 | tr -d '\n'")

            if (reserved == ""):
                reserved = "0"

            requested = ((int(memsize) * factor) / 100) / int(pagesize)

            if (requested > int(reserved)):
                pattern = "^vm.nr_hugepages ="
                line = "vm.nr_hugepages = %d" %requested
                insert_line_to_file(pattern = pattern, line = line,
                                    file_name = '/etc/sysctl.conf')

            current_max_map_count = local("sysctl -n vm.max_map_count")
            if current_max_map_count == "":
                current_max_map_count = 0

            current_huge_pages = max(int(requested), int(reserved))

            requested_max_map_count = DPDK_HUGEPAGES_INIT_TIMES * int(current_huge_pages)
            if int(requested_max_map_count) > int(current_max_map_count):
                pattern = "^vm.max_map_count ="
                line = "vm.max_map_count = %d" %requested_max_map_count
                insert_line_to_file(pattern = pattern, line = line,
                                    file_name = '/etc/sysctl.conf')

            mounted = local("mount | grep hugetlbfs | cut -d' ' -f 3")
            if (mounted != ""):
                print "hugepages already mounted on %s" %mounted
            else:
                local("mkdir -p /hugepages")
                pattern = "^hugetlbfs"
                line = "hugetlbfs    /hugepages    hugetlbfs defaults      0       0"
                insert_line_to_file(pattern = pattern, line = line,
                                    file_name = '/etc/fstab')
                local("mount -t hugetlbfs hugetlbfs /hugepages")

    def setup_coremask_node(self, dpdk_args):
        """Setup core mask on one or list of nodes
        """
        vrouter_file = '/etc/contrail/supervisord_vrouter_files/contrail-vrouter-dpdk.ini'

        try:
            coremask = dpdk_args['coremask']
        except KeyError:
            raise RuntimeError("Core mask for host %s is not defined." \
                   %(dpdk_args))

        if not coremask:
            raise RuntimeError("Core mask for host %s is not defined." \
                % dpdk_args)

        # if a list of cpus is provided, -c flag must be passed to taskset
        if (',' in coremask) or ('-' in coremask):
            taskset_param = ' -c'
        else:
            taskset_param = ''

        with settings(warn_only = True):
            # supported coremask format: hex: (0x3f); list: (0,3-5), (0,1,2,3,4,5)
            # try taskset on a dummy command
            try:
                run_command('taskset%s %s true' %(taskset_param, coremask))
                run_command('sed -i \'s/command=/command=taskset%s %s /\' %s' \
                    %(taskset_param, coremask, vrouter_file))
            except:
                raise RuntimeError("Error: Core mask %s for host %s is invalid." \
                    %(coremask, dpdk_args))

    def setup_vm_coremask_node(self, q_coremask, dpdk_args):
        """
        Setup CPU affinity for QEMU processes based on vRouter/DPDK core affinity
        on a given node.

        Supported core mask format:
            vRouter/DPDK:   hex (0x3f), list (0,1,2,3,4,5), range (0,3-5)
            QEMU/nova.conf: list (0,1,2,3,4,5), range (0,3-5), exclusion (0-5,^4)

        QEMU needs to be pinned to different cores than vRouter. Because of
        different core mask formats, it is not possible to just set QEMU to
        <not vRouter cores>. This function takes vRouter core mask from testbed,
        changes it to list of cores and removes them from list of all possible
        cores (generated as a list from 0 to N-1, where N = number of cores).
        This is changed back to string and passed to openstack-config.
        """
        vrouter_file = '/etc/contrail/supervisord_vrouter_files/contrail-vrouter-dpdk.ini'

        try:
            vr_coremask = dpdk_args['coremask']
        except KeyError:
            raise RuntimeError("vRouter core mask for host %s is not defined." \
                %(dpdk_args))

        if not vr_coremask:
            raise RuntimeError("vRouter core mask for host %s is not defined." \
                % dpdk_args)

        if not q_coremask:
            try:
                cpu_count = int(run_command('grep -c processor /proc/cpuinfo'))
            except ValueError:
                print "Cannot count CPUs on host %s. VM core mask cannot be computed." \
                    %(dpdk_args)
                raise

            if not cpu_count or cpu_count == -1:
                raise ValueError("Cannot count CPUs on host %s. VM core mask cannot be computed." \
                    %(dpdk_args))

            all_cores = [x for x in xrange(cpu_count)]

            if 'x' in vr_coremask:  # String containing hexadecimal mask.
                vr_coremask = int(vr_coremask, 16)

                """
                Convert hexmask to a string with numbers of cores to be used, eg.
                0x19 -> 11001 -> 10011 -> [(0,1), (1,0), (2,0), (3,1), (4,1)] -> '0,3,4'
                """
                vr_coremask = [x[0] for x in enumerate(reversed(bin(vr_coremask)[2:])) if x[1] == '1']
            elif (',' in vr_coremask) or ('-' in vr_coremask):  # Range or list of cores.
                vr_coremask = vr_coremask.split(',')  # Get list of core numbers and/or core ranges.

                # Expand ranges like 0-4 to 0, 1, 2, 3, 4.
                vr_coremask_expanded = []
                for rng in vr_coremask:
                    if '-' in rng:  # If it's a range - expand it.
                        a, b = rng.split('-')
                        vr_coremask_expanded += range(int(a), int(b)+1)
                    else:  # If not, just add to the list.
                        vr_coremask_expanded.append(int(rng))

                vr_coremask = vr_coremask_expanded
            else:  # A single core.
                try:
                    single_core = int(vr_coremask)
                except ValueError:
                    print "Error: vRouter core mask %s for host %s is invalid." \
                        %(vr_coremask, dpdk_args)
                    raise

                vr_coremask = []
                vr_coremask.append(single_core)

            # From list of all cores remove list of vRouter cores and stringify.
            diff = set(all_cores) - set(vr_coremask)
            q_coremask = ','.join(str(x) for x in diff)

            # If we have no spare cores for VMs
            if not q_coremask:
                raise RuntimeError("Setting QEMU core mask for host %s failed - empty string." \
                    %(dpdk_args))

        with settings(warn_only = True):
            # This can fail eg. because openstack-config is not present.
            # There's no sanity check in openstack-config.
            try:
                run_command("openstack-config --set /etc/nova/nova.conf DEFAULT vcpu_pin_set %s" \
                % q_coremask)
                print "QEMU coremask on host %s set to %s." \
                    %(dpdk_args, q_coremask)
            except ValueError:
                raise RuntimeError("Error: setting QEMU core mask %s for host %s failed." \
                    %(vr_coremask, dpdk_args))

    def setup_uio_driver(self, dpdk_args):
        """Setup UIO driver to use for DPDK (igb_uio, uio_pci_generic or vfio-pci)
        """
        vrouter_agent_file = '/etc/contrail/contrail-vrouter-agent.conf'

        if 'uio_driver' in dpdk_args:
            uio_driver = dpdk_args['uio_driver']
        else:
            print "No UIO driver defined for host, skipping..."
            return

        with settings(warn_only = True):
            try:
                run_command('modprobe %s' %(uio_driver))
                print "Setting UIO driver to %s for host..." % uio_driver
                run_command('sed -i.bak \'s/physical_uio_driver=.*/physical_uio_driver=%s/\' %s' \
                    %(uio_driver, vrouter_agent_file))
            except ValueError:
                raise RuntimeError("Error: invalid UIO driver %s for host"
                    % (uio_driver))

    def dpdk_increase_vrouter_limit(self, vrouter_module_params_args):
        """Increase the maximum number of mpls label and nexthop on tsn node"""
        vrouter_file = '/etc/contrail/supervisord_vrouter_files/contrail-vrouter-dpdk.ini'
        cmd = "--vr_mpls_labels %s " % vrouter_module_params_args.setdefault('mpls_labels', '5120')
        cmd += "--vr_nexthops %s " % vrouter_module_params_args.setdefault('nexthops', '65536')
        cmd += "--vr_vrfs %s " % vrouter_module_params_args.setdefault('vrfs', '5120')
        cmd += "--vr_bridge_entries %s " % vrouter_module_params_args.setdefault('macs', '262144')
        with settings(warn_only=True):
            run_command('sed -i \'s#\(^command=.*$\)#\\1 %s#\' %s'\
                  %(cmd, vrouter_file))

    def fixup_contrail_vrouter_agent(self):
        keystone_ip = self._args.keystone_ip
        compute_ip = self._args.self_ip
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
                dpdk_args = dict(u.split("=") for u in self._args.dpdk.split(","))
                print dpdk_args
                platform_mode = "dpdk"
                iface = self.dev
                if self.is_interface_vlan(self.dev):
                    iface = self.get_physical_interface_of_vlan(self.dev)
                pci_dev = local("/opt/contrail/bin/dpdk_nic_bind.py --status | grep -w %s | cut -d' ' -f 1" %(iface), capture=True)
                # If there is no PCI address, the device is a bond.
                # Bond interface in DPDK has zero PCI address.
                if not pci_dev:
                    pci_dev = "0000:00:00.0"

                self.setup_hugepages_node(dpdk_args)
                self.setup_coremask_node(dpdk_args)
                self.setup_vm_coremask_node(False, dpdk_args)

                if self._args.vrouter_module_params:
                    vrouter_module_params_args = dict(u.split("=") for u in self._args.vrouter_module_params.split(","))
                    self.dpdk_increase_vrouter_limit(vrouter_module_params_args)

                if is_ostype_ubuntu():
                    with settings(warn_only=True):
                        if not is_xenial_or_above():
                            run_command('rm -f /etc/init/supervisor-vrouter.override')
                        # Fix /dev/vhost-net permissions. It is required for
                        # multiqueue operation
                        run_command('echo \'KERNEL=="vhost-net", GROUP="kvm", MODE="0660"\' > /etc/udev/rules.d/vhost-net.rules')
                        # The vhost-net module has to be loaded at startup to
                        # ensure the correct permissions while the qemu is being
                        # launched
                        run_command('echo "vhost-net" >> /etc/modules')

                self.setup_uio_driver(dpdk_args)

            vnswad_conf_template_vals = {'__contrail_vhost_ip__': cidr,
                '__contrail_vhost_gateway__': self.gateway,
                '__contrail_physical_intf__': self.dev,
                '__contrail_control_ip__': compute_ip,
                '__hypervisor_type__': hypervisor_type,
                '__hypervisor_mode__': mode,
                '__vmware_physical_interface__': vmware_dev,
                '__contrail_work_mode__': platform_mode,
                '__pci_dev__': pci_dev,
                '__physical_interface_mac__': self.mac,
                '__gateway_mode__': gateway_mode,
                '__contrail_control_node_list__' : \
                     ' '.join('%s:%s' %(server, '5269') for server \
                     in self._args.control_nodes),
                '__contrail_dns_node_list__' : \
                     ' '.join('%s:%s' %(server, '53') for server \
                     in self._args.control_nodes),
                '__contrail_collectors__' : \
                     ' '.join('%s:%s' %(server, '8086') for server \
                     in self._args.collectors)
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

