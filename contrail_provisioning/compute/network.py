#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import re
import glob
import struct
import socket
import netifaces

from fabric.api import local
from fabric.context_managers import settings

class ComputeNetworkSetup(object):
    def find_gateway (self, dev):
        gateway = ''
        gateway = local("netstat -rn | grep ^\"0.0.0.0\" | head -n 1 | grep %s | awk '{ print $2 }'" % dev,
                capture = True).strip()
        return gateway

    #end find_gateway

    def get_dns_servers (self, dev):
        dns_list = local("grep \"^nameserver\\>\" /etc/resolv.conf | awk  '{print $2}'",
                capture = True)
        return dns_list.split()
    #end get_dns_servers

    def get_domain_search_list (self):
        domain_list = ''
        domain_list = local("grep ^\"search\" /etc/resolv.conf | awk '{$1=\"\";print $0}'", capture = True).strip()
        if not domain_list:
            domain_list = local("grep ^\"domain\" /etc/resolv.conf | awk '{$1=\"\"; print $0}'", capture = True).strip()
        return domain_list

    def get_if_mtu (self, dev):
        mtu = local("ifconfig %s | grep mtu | awk '{ print $NF }'" % dev,
                capture = True).strip ()
        if not mtu:
            # for debian
            mtu = local(
              r"ifconfig %s | grep MTU | sed 's/.*MTU.\([0-9]\+\).*/\1/g'" % dev,
                capture = True).strip ()
        if mtu and mtu != '1500': return mtu
        return ''
    #end if_mtu

    def get_device_by_ip (self, ip):
        for i in netifaces.interfaces ():
            try:
                if i == 'pkt1':
                    continue
                if netifaces.ifaddresses (i).has_key (netifaces.AF_INET):
                    if ip == netifaces.ifaddresses (i)[netifaces.AF_INET][0][
                            'addr']:
                        if i == 'vhost0':
                             print "vhost0 is already present!"
    #                        raise RuntimeError, 'vhost0 already running with %s'%ip
                        return i
            except ValueError,e:
                print "Skipping interface %s" % i
        raise RuntimeError, '%s not configured, rerun w/ --physical_interface' % ip
    #end get_device_by_ip

    def get_secondary_device(self, primary):
        for i in netifaces.interfaces ():
            try:
                if i == 'pkt1':
                    continue
                if i == primary:
                    continue
                if i == 'vhost0':
                    continue
                if not netifaces.ifaddresses (i).has_key (netifaces.AF_INET):
                    return i
            except ValueError,e:
                print "Skipping interface %s" % i
        raise RuntimeError('Secondary interace  not configured,',
                           'rerun w/ --physical_interface')
    #end get_secondary_device

    def get_if_mac(self, dev):
        iface_addr = netifaces.ifaddresses(dev)
        link_info = iface_addr[netifaces.AF_LINK]
        mac_addr = link_info[0]['addr']
        return mac_addr
    #end get_if_mac

    @staticmethod
    def is_interface_vlan(interface):
        with settings(warn_only=True):
            iface = local("ip link show %s | head -1" % interface +
                    "| cut -f2 -d':' | grep '@'", capture=True)
        if iface.succeeded:
            return True
        else:
            return False

    @staticmethod
    def get_physical_interface_of_vlan(interface):
        iface = local("ip link show %s | head -1 | cut -f2 -d':'" % interface +
                "| cut -f2 -d'@'", capture=True)
        return iface

    def _is_string_in_file(self, string, filename):
        f_lines=[]
        if os.path.isfile( filename ):
            fd=open(ifcfg_file)
            f_lines=fd.readlines()
            fd.close()
        #end if  
        found= False
        for line in f_lines:
            if string in line:
                found= True
        return found
    #end _is_string_in_file

    def _rewrite_ifcfg_file(self, filename, dev, prsv_cfg):
        bond = False
        mac = ''
        temp_dir_name = self._temp_dir_name

        vlan = False
        if os.path.isfile ('/proc/net/vlan/%s' % dev):
            vlan_info = open('/proc/net/vlan/config').readlines()
            match = re.search('^%s.*\|\s+(\S+)$'%dev, "\n".join(vlan_info), flags=re.M|re.I)
            if not match:
                raise RuntimeError, 'Configured vlan %s is not found in /proc/net/vlan/config'%dev
            phydev = match.group(1)
            vlan = True

        if os.path.isdir ('/sys/class/net/%s/bonding' % dev):
            bond = True
        # end if os.path.isdir...

        mac = netifaces.ifaddresses(dev)[netifaces.AF_LINK][0]['addr']
        ifcfg_file='/etc/sysconfig/network-scripts/ifcfg-%s' %(dev)
        if not os.path.isfile( ifcfg_file ):
            ifcfg_file = temp_dir_name + 'ifcfg-' + dev
            with open (ifcfg_file, 'w') as f:
                f.write ('''#Contrail %s
TYPE=Ethernet
ONBOOT=yes
DEVICE="%s"
USERCTL=yes
NM_CONTROLLED=no
HWADDR=%s
''' % (dev, dev, mac))
                for dcfg in prsv_cfg:
                    f.write(dcfg+'\n')
                if vlan:
                    f.write('VLAN=yes\n')
        fd=open(ifcfg_file)
        f_lines=fd.readlines()
        fd.close()
        local("sudo rm -f %s" %ifcfg_file)
        new_f_lines=[]
        remove_items=['IPADDR', 'NETMASK', 'PREFIX', 'GATEWAY', 'HWADDR',
                      'DNS1', 'DNS2', 'BOOTPROTO', 'NM_CONTROLLED', '#Contrail']

        remove_items.append('DEVICE')
        new_f_lines.append('#Contrail %s\n' % dev)
        new_f_lines.append('DEVICE=%s\n' % dev)


        for line in f_lines:
            found=False
            for text in remove_items:
                if text in line:
                    found=True
            if not found:
                new_f_lines.append(line)

        new_f_lines.append('NM_CONTROLLED=no\n')
        if bond:
            new_f_lines.append('SUBCHANNELS=1,2,3\n')
        elif not vlan:
            new_f_lines.append('HWADDR=%s\n' % mac)

        fdw=open(filename,'w')
        fdw.writelines(new_f_lines)
        fdw.close()

    def migrate_routes(self, device):
        '''
        Sample output of /proc/net/route :
        Iface   Destination     Gateway         Flags   RefCnt  Use     Metric  Mask            MTU     Window  IRTT
        p4p1    00000000        FED8CC0A        0003    0       0       0       00000000        0       0       0
        '''
        temp_dir_name = self._temp_dir_name
        cfg_file = '/etc/sysconfig/network-scripts/route-vhost0'
        tmp_file = '%s/route-vhost0'%(temp_dir_name)
        with open(tmp_file, 'w') as route_cfg_file:
            for route in open('/proc/net/route', 'r').readlines():
                if route.startswith(device):
                    route_fields = route.split()
                    destination = int(route_fields[1], 16)
                    gateway = int(route_fields[2], 16)
                    flags = int(route_fields[3], 16)
                    mask = int(route_fields[7], 16)
                    if flags & 0x2:
                        if destination != 0:
                            route_cfg_file.write(socket.inet_ntoa(struct.pack('I', destination)))
                            route_cfg_file.write('/' + str(bin(mask).count('1')) + ' ')
                            route_cfg_file.write('via ')
                            route_cfg_file.write(socket.inet_ntoa(struct.pack('I', gateway)) + ' ')
                            route_cfg_file.write('dev vhost0')
                        #end if detination...
                    #end if flags &...
                #end if route.startswith...
            #end for route...
        #end with open...
        local("sudo mv -f %s %s" %(tmp_file, cfg_file))
        #delete the route-dev file
        if os.path.isfile('/etc/sysconfig/network-scripts/route-%s'%device):
            os.unlink('/etc/sysconfig/network-scripts/route-%s'%device)
    #end def migrate_routes

    def get_cfgfile_for_dev(self, iface, cfg_files):
        if not cfg_files:
            return None
        mapped_intf_cfgfile = None
        for file in cfg_files:
            with open(file, 'r') as fd:
                contents = fd.read()
                regex = '(?:^|\n)\s*iface\s+%s\s+'%iface
                if re.search(regex, contents):
                    mapped_intf_cfgfile = file
        return mapped_intf_cfgfile

    def get_sourced_files(self):
        '''Get all sourced config files'''
        files = self.get_valid_files(self.get_source_entries())
        files += self.get_source_directory_files()
        return list(set(files))

    def get_source_directory_files(self):
        '''Get source-directory entry and make list of valid files'''
        regex = '(?:^|\n)\s*source-directory\s+(\S+)'
        files = list()
        with open(self.default_cfg_file, 'r') as fd:
            entries = re.findall(regex, fd.read())
        dirs = [d for d in self.get_valid_files(entries) if os.path.isdir(d)]
        for dir in dirs:
            files.extend([os.path.join(dir, f) for f in os.listdir(dir)\
                          if os.path.isfile(os.path.join(dir, f)) and \
                          re.match('^[a-zA-Z0-9_-]+$', f)])
        return files

    def get_source_entries(self):
        '''Get entries matching source keyword from /etc/network/interfaces file'''
        regex = '(?:^|\n)\s*source\s+(\S+)'
        with open(self.default_cfg_file, 'r') as fd:
            return re.findall(regex, fd.read())

    def get_valid_files(self, entries):
        '''Provided a list of glob'd strings, return matching file names'''
        files = list()
        prepend = os.path.join(os.path.sep, 'etc', 'network') + os.path.sep
        for entry in entries:
            entry = entry.lstrip('./') if entry.startswith('./') else entry
            entry = prepend+entry if not entry.startswith(os.path.sep) else entry
            files.extend(glob.glob(entry))
        return files

    def _rewrite_net_interfaces_file(self, dev, mac, vhost_ip, netmask, gateway_ip, esxi_vm, vmpg_mtu,
                                     datapg_mtu):
        self.default_cfg_file = '/etc/network/interfaces'
        cfg_files = self.get_sourced_files()
        cfg_files.append(self.default_cfg_file)
        intf_cfgfile = self.get_cfgfile_for_dev('vhost0', cfg_files)
        if intf_cfgfile:
            print "Interface vhost0 is already present in /etc/network/interfaces"
            print "Skipping rewrite of this file"
            return
        #endif

        vlan = False
        if os.path.isfile ('/proc/net/vlan/%s' % dev):
            vlan_info = open('/proc/net/vlan/config').readlines()
            match  = re.search('^%s.*\|\s+(\S+)$'%dev, "\n".join(vlan_info), flags=re.M|re.I)
            if not match:
                raise RuntimeError, 'Configured vlan %s is not found in /proc/net/vlan/config'%dev
            phydev = match.group(1)
            vlan = True

        # Replace strings matching dev to vhost0 in ifup and ifdown parts file
        # Any changes to the file/logic with static routes has to be
        # reflected in setup-vnc-static-routes.py too
        ifup_parts_file = os.path.join(os.path.sep, 'etc', 'network', 'if-up.d', 'routes')
        ifdown_parts_file = os.path.join(os.path.sep, 'etc', 'network', 'if-down.d', 'routes')

        if os.path.isfile(ifup_parts_file) and os.path.isfile(ifdown_parts_file):
            with settings(warn_only = True):
                local("sudo sed -i 's/%s/vhost0/g' %s" %(dev, ifup_parts_file))
                local("sudo sed -i 's/%s/vhost0/g' %s" %(dev, ifdown_parts_file))

        dev_cfgfile = self.get_cfgfile_for_dev(dev, cfg_files)
        temp_intf_file = '%s/interfaces' %(self._temp_dir_name)
        local("cp %s %s" %(dev_cfgfile, temp_intf_file))
        with open(dev_cfgfile, 'r') as fd:
            cfg_file = fd.read()

        if not self._args.non_mgmt_ip:
            # remove entry from auto <dev> to auto excluding these pattern
            # then delete specifically auto <dev> 
            local("sed -i '/auto %s/,/auto/{/auto/!d}' %s" %(dev, temp_intf_file))
            local("sed -i '/auto %s/d' %s" %(dev, temp_intf_file))
            # add manual entry for dev
            local("echo 'auto %s' >> %s" %(dev, temp_intf_file))
            local("echo 'iface %s inet manual' >> %s" %(dev, temp_intf_file))
            if vlan:
                local("echo '    post-up ifconfig %s up' >> %s" %(dev, temp_intf_file))
                local("echo '    pre-down ifconfig %s down' >> %s" %(dev, temp_intf_file))
            else: 
                local("echo '    pre-up ifconfig %s up' >> %s" %(dev, temp_intf_file))
                local("echo '    post-down ifconfig %s down' >> %s" %(dev, temp_intf_file))
            if (esxi_vm):
                    local("echo '    pre-up ifconfig %s up mtu %s' >> %s" % (dev, datapg_mtu, temp_intf_file))
                    device_driver = local("ethtool -i %s | grep driver | cut -f 2 -d ' '" %dev, capture=True)
                    if (device_driver == "vmxnet3"):
                        local("echo '    pre-up ethtool --offload %s rx off' >> %s" %(dev, temp_intf_file))
                        local("echo '    pre-up ethtool --offload %s tx off' >> %s" %(dev, temp_intf_file))
            if vlan:
                local("echo '    vlan-raw-device %s' >> %s" %(phydev, temp_intf_file))
            if 'bond' in dev.lower():
                iters = re.finditer('^\s*auto\s', cfg_file, re.M)
                indices = [match.start() for match in iters]
                matches = map(cfg_file.__getslice__, indices, indices[1:] + [len(cfg_file)])
                for each in matches:
                    each = each.strip()
                    if re.match('^auto\s+%s'%dev, each):
                        string = ''
                        for lines in each.splitlines():
                            if 'bond-' in lines:
                                string += lines+os.linesep
                        local("echo '%s' >> %s" %(string, temp_intf_file))
                    else:
                        continue
            local("echo '' >> %s" %(temp_intf_file))
        else:
            #remove ip address and gateway
            with settings(warn_only = True):
                local("sed -i '/iface %s inet static/, +2d' %s" % (dev, temp_intf_file))
                if esxi_vm:
                    local("echo '    pre-up ifconfig %s up mtu %s' >> %s" % (dev, datapg_mtu, temp_intf_file))
                    device_driver = local("ethtool -i %s | grep driver | cut -f 2 -d ' '" %dev, capture=True)
                    if (device_driver == "vmxnet3"):
                        local("echo '    pre-up ethtool --offload %s rx off' >> %s" %(dev, temp_intf_file))
                        local("echo '    pre-up ethtool --offload %s tx off' >> %s" %(dev, temp_intf_file))
                if vlan:
                    local("sed -i '/auto %s/ a\iface %s inet manual\\n    post-up ifconfig %s up\\n    pre-down ifconfig %s down\' %s"% (dev, dev, dev, dev, temp_intf_file))
                else:
                    local("sed -i '/auto %s/ a\iface %s inet manual\\n    pre-up ifconfig %s up\\n    post-down ifconfig %s down\' %s"% (dev, dev, dev, dev, temp_intf_file))
        if esxi_vm and vmpg_mtu:
            intf = self.get_secondary_device(self.dev)
            mac_addr = self.get_if_mac(intf)
            udev_net_file = '/etc/udev/rules.d/70-persistent-net.rules'
            temp_udev_net_file = '%s/70-persistent-net.rules' %(self._temp_dir_name)
            local("touch %s" %(temp_udev_net_file))
            local("cp %s %s" %(udev_net_file, temp_udev_net_file))
            local("echo 'SUBSYSTEM==\"net\", ACTION==\"add\", DRIVERS==\"?*\", ATTR{address}==\"%s\", ATTR{dev_id}==\"0x0\", ATTR{type}==\"1\", KERNEL==\"eth*\", NAME=\"%s\"' >> %s" %(mac_addr, intf, temp_udev_net_file))
            local("sudo mv -f %s %s" %(temp_udev_net_file, udev_net_file))
            local("sed -i '/auto %s/,/down/d' %s" %(intf, temp_intf_file))
            local("echo '\nauto %s' >> %s" %(intf, temp_intf_file))
            local("echo 'iface %s inet manual' >> %s" %(intf, temp_intf_file))
            local("echo '    pre-up ifconfig %s up mtu %s' >> %s" % (intf, vmpg_mtu, temp_intf_file))
            local("echo '    post-down ifconfig %s down' >> %s" %(intf, temp_intf_file))
            local("echo '    pre-up ethtool --offload %s lro off' >> %s" %(intf, temp_intf_file))

        # populte vhost0 as static
        local("echo '' >> %s" %(temp_intf_file))
        local("echo 'auto vhost0' >> %s" %(temp_intf_file))
        local("echo 'iface vhost0 inet static' >> %s" %(temp_intf_file))
        local("echo '    pre-up %s/if-vhost0' >> %s" %(self.contrail_bin_dir, temp_intf_file))
        local("echo '    netmask %s' >> %s" %(netmask, temp_intf_file))
        local("echo '    network_name application' >> %s" %(temp_intf_file))
        if esxi_vm and datapg_mtu:
            local("echo '    mtu %s' >> %s" %(datapg_mtu, temp_intf_file))
        if vhost_ip:
            local("echo '    address %s' >> %s" %(vhost_ip, temp_intf_file))
        if (not self._args.non_mgmt_ip) and gateway_ip:
            local("echo '    gateway %s' >> %s" %(gateway_ip, temp_intf_file))

        domain = self.get_domain_search_list()
        if domain:
            local("echo '    dns-search %s' >> %s" %(domain, temp_intf_file))
        dns_list = self.get_dns_servers(dev)
        if dns_list:
            local("echo -n '    dns-nameservers' >> %s" %(temp_intf_file))
            for dns in dns_list:
                local("echo -n ' %s' >> %s" %(dns, temp_intf_file))
            local("echo '' >> %s" % (temp_intf_file))
        local("echo '    post-up ip link set vhost0 address %s' >> %s" % (mac,
              temp_intf_file))

        # move it to right place
        local("sudo mv -f %s %s" %(temp_intf_file, dev_cfgfile))
