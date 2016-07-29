#!/usr/bin/env python
'''Provision Interface'''
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

__version__ = '1.0'

import os
import re
import sys
import glob
import argparse
import socket
import fcntl
import struct
import logging
import platform
import time
import json
import subprocess
from netaddr import IPNetwork
from tempfile import NamedTemporaryFile
from distutils.version import LooseVersion
try:
    import lsb_release
except ImportError:
    pass

from contrail_provisioning.common.templates import vlan_egress_map


logging.basicConfig(format='%(asctime)-15s:: %(funcName)s:%(levelname)s::\
                            %(message)s',
                    level=logging.INFO)
log = logging.getLogger(__name__)
(PLATFORM, VERSION, EXTRA) = platform.linux_distribution()

bond_opts_dict  = {'arp_interval' : 'int',
                   'arp_ip_target': 'ipaddr_list',
                   'arp_validate' : ['none', 'active', 'backup', 'all'],
                   'downdelay'    : 'int',
                   'fail_over_mac': ['none', '0', 'active', '1', 'follow', '2'],
                   'lacp_rate'    : ['slow', 'fast'],
                   'miimon'       : 'int',
                   'mode'         : ['balance-rr', 'active-backup',
                                     'balance-xor', 'broadcast', '802.3ad',
                                     'balance-tlb', 'balance-alb'],
                   'primary'      : 'string',
                   'updelay'      : 'int',
                   'use_carrier'  : 'int',
                   'xmit_hash_policy': ['layer2', 'layer2+3', 'layer3+4']
                  }

class BaseInterface(object):
    '''Base class containing common methods for configuring interface
    '''
    def __init__(self, **kwargs):
        self.device     = kwargs['device']
        self.members    = kwargs.get('members', [])
        self.ip         = kwargs.get('ip', None)
        self.no_ip      = kwargs.get('no_ip', False)
        self.gw         = kwargs.get('gw', None)
        self.vlan       = kwargs.get('vlan', None)
        self.bond_opts  = {'miimon': '100', 'mode': '802.3ad',
                           'xmit_hash_policy': 'layer3+4'}
        try:
            self.bond_opts.update(json.loads(kwargs.get('bopts', {})))
        except ValueError:
            log.warn("No bonding options specified using default %s",
                                                       self.bond_opts)
        self.bond_opts_str = ''
        self.mac_list = {}
        self.tempfile = NamedTemporaryFile(delete=False)

    def validate_bond_opts(self):
        for key in list(self.bond_opts):
            if not self.is_valid_opts(key, self.bond_opts[key], bond_opts_dict):
                del self.bond_opts[key]
            else:
                self.bond_opts_str += '%s=%s '%(key, self.bond_opts[key])

    def is_valid_mac(self, mac):
        if re.match("[0-9a-f]{2}(:)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", mac.lower()):
            return True
        else:
            return False

    def is_valid_ipaddr_list(p):
        addr_list = ip.split(",")
        for addr in addr_list:
            socket.inet_pton(socket.AF_INET, addr)
        return True

    def is_valid_opts(self, key, value, compare_dict):
        if key in compare_dict:
          try:
            if (not isinstance(value, int) and value in compare_dict[key]) or\
               ('int' in compare_dict[key] and int(value)) or\
               ('macaddr' in compare_dict[key] and self.is_valid_mac(value)) or\
               ('ipaddr_list' in compare_dict[key] and
                                 self.is_valid_ipaddr_list(value)) or\
               ('string' in compare_dict[key] and isinstance(value,basestring)):
                return True
          except:
            log.warn("Caught Exception while processing (%s, %s)" %(key, value))
            log.warn("Supported options for key %s are %s" %(key,
                                                        str(compare_dict[key])))
        return False

    def write_network_script(self, device, cfg):
        '''Create an interface config file in network-scripts with given
            config
        '''
        nw_scripts = os.path.join(os.path.sep, 'etc', 'sysconfig', 
                                  'network-scripts')
        nwfile = os.path.join(nw_scripts, 'ifcfg-%s' %device)
        if os.path.isfile(nwfile):
            tmpfile = os.path.join(os.path.dirname(nwfile), \
                                  'moved-%s' %os.path.basename(nwfile))
            log.info('Backup existing file %s to %s' %(nwfile, tmpfile))
            os.system('sudo mv %s %s' %(nwfile, tmpfile))
        with open(self.tempfile.name, 'w') as fd:
            fd.write('\n'.join(['%s=%s' %(key, value) \
                          for key, value in cfg.items()]))
            fd.write('\n')
            fd.flush()
        os.system('sudo cp -f %s %s'%(self.tempfile.name, nwfile))

    def get_mac_addr(self, iface):
        '''Retrieve mac address for the given interface in the system'''
        macaddr = None
        if self.mac_list.has_key(iface):
            return self.mac_list[iface]
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            macinfo = fcntl.ioctl(sock.fileno(), 0x8927,
                                  struct.pack('256s', iface[:15]))
            macaddr = ''.join(['%02x:' % ord(each) for each in macinfo[18:24]])[:-1]
        except IOError, err:
            raise Exception('Unable to fetch MAC address of interface (%s)' %iface)
        return macaddr

    def create_vlan_interface(self):
        '''Create interface config for vlan sub interface'''
        vlanif = "%s.%s"%(self.device, self.vlan)
        log.info('Creating vlan interface: %s' %vlanif)
        cfg = {'DEVICE'        : vlanif,
               'ONBOOT'        : 'yes',
               'BOOTPROTO'     : 'none',
               'NM_CONTROLLED' : 'no',
               'NETMASK'       : self.netmask,
               'IPADDR'        : self.ipaddr,
               'VLAN'          : 'yes',
               'VLAN_EGRESS_PRIORITY_MAP' : '0:0,1:1,2:2,3:3,4:4,5:5,6:6,7:7',
              }
        if self.gw:
            cfg['GATEWAY'] = self.gw
        self.write_network_script(vlanif, cfg)

    def create_bond_members(self):
        '''Create interface config for each bond members'''
        # create slave interface
        if not self.members:
            log.warn('No slaves are specified for bond interface. Please use --members')
        for each in self.members:
            log.info('Creating bond member: %s' %each)
            mac = self.get_mac_addr(each)
            cfg = {'DEVICE'        : each,
                   'ONBOOT'        : 'yes',
                   'BOOTPROTO'     : 'none',
                   'NM_CONTROLLED' : 'no',
                   'HWADDR'        : mac,
                   'MASTER'        : self.device,
                   'SLAVE'         : 'yes'
                  }
            self.write_network_script(each, cfg)

    def get_mac_from_bond_intf(self):
        output= os.popen("sudo cat /proc/net/bonding/%s"%self.device).read()
        device_list= re.findall('Slave Interface:\s+(\S+)$', output, flags=re.M)
        mac_list= re.findall('HW addr:\s+(\S+)$', output, flags=re.M)
        if len(device_list) == len(mac_list):
            for (device, mac) in zip(device_list, mac_list):
                self.mac_list[device]= mac.lower()

    def create_bonding_interface(self):
        '''Create interface config for bond master'''
        # create slave interface
        self.get_mac_from_bond_intf()
        self.create_bond_members()
        bond_mac = self.get_mac_addr(self.members[0])
        log.info('Creating bond master: %s with Mac Addr: %s' %
                (self.device, bond_mac))
        cfg = {'DEVICE'        : self.device,
               'ONBOOT'        : 'yes',
               'BOOTPROTO'     : 'none',
               'NM_CONTROLLED' : 'no',
               'BONDING_MASTER': 'yes',
               'MACADDR'        : bond_mac,
               'BONDING_OPTS'  : "\"%s\""%self.bond_opts_str.strip(),
               'SUBCHANNELS'   : '1,2,3'
              }
        if not self.vlan:
            cfg.update({'NETMASK'       : self.netmask,
                        'IPADDR'        : self.ipaddr
                       })
            if self.gw:
                cfg['GATEWAY'] = self.gw
        else:
            self.create_vlan_interface()
        self.write_network_script(self.device, cfg)

    def create_interface(self):
        '''Create interface config for normal interface'''
        log.info('Creating Interface: %s' %self.device)
        mac = self.get_mac_addr(self.device)
        cfg = {'DEVICE'        : self.device,
               'ONBOOT'        : 'yes',
               'BOOTPROTO'     : 'none',
               'NM_CONTROLLED' : 'no',
               'HWADDR'        : mac}
        if not self.vlan and not self.no_ip:
            cfg.update({'NETMASK'       : self.netmask,
                        'IPADDR'        : self.ipaddr
                       })
            if self.gw:
                cfg['GATEWAY'] = self.gw
        else:
            self.create_vlan_interface()
        self.write_network_script(self.device, cfg)

    def restart_service(self):
        '''Restart network service'''
        log.info('Restarting Network Services...')
        os.system('sudo service network restart')
        time.sleep(5)

    def post_conf(self):
        '''Execute commands after after interface configuration'''
        self.restart_service()

    def pre_conf(self):
        '''Execute commands before interface configuration'''
        pass

    def setup(self):
        '''High level method to call individual methods to configure
            interface
        '''
        self.validate_bond_opts()
        self.pre_conf()
        if self.ip:
            ip = IPNetwork(self.ip)
            self.ipaddr = str(ip.ip)
            self.netmask = str(ip.netmask)
        elif not self.no_ip:
            raise Exception("IP address/mask is not specified")
        if 'bond' in self.device.lower():
            self.create_bonding_interface()
        else:
            self.create_interface()
        time.sleep(3)
        self.post_conf()

class UbuntuInterface(BaseInterface):
    def restart_service(self):
        '''Restart network service for Ubuntu'''
        log.info('Restarting Network Services...')
        if LooseVersion(VERSION) < LooseVersion("14.04"):
            subprocess.call('sudo /etc/init.d/networking restart', shell=True)
        else:
            # Avoid bringing down the PF of VF together with the VFs.
            # Otherwise, the addition of the VF to a bond fails (probably due to
            # a bug in the ixgbe driver)
            if self.no_ip:
                subprocess.call('sudo ifdown %s && ifup %s' % (self.device,
                                self.device), shell=True)
            else:
                output = os.popen("sudo ifquery -l --allow=auto").read()
                intfs = output.split()
                lsb_info = lsb_release.get_lsb_information()
                lsb_version = lsb_info['DESCRIPTION'].split()[1]
                if LooseVersion(lsb_version) >= LooseVersion('14.04.4'):
                    for intf in intfs:
                        subprocess.call('sudo ifdown %s && ifup %s' %
                                        (intf, intf), shell=True)
                    subprocess.call('sudo ifup -a', shell=True)

                else:
                    for intf in intfs:
                        subprocess.call('sudo ifdown %s && ifup -a' % (intf),
                                        shell=True)
        time.sleep(5)

    def remove_lines(self, ifaces, filename):
        '''Remove existing config related to given interface if the same
            needs to be re-configured
        '''
        log.info('Remove Existing Interface configs in %s' %filename)
        # read existing file
        with open(filename, 'r') as fd:
            cfg_file = fd.read()

        # get blocks
        keywords = ['allow-', 'auto', 'iface', 'source', 'mapping']
        pattern = '(?:^|\n)\s*(?:{})'.format('|'.join(map(re.escape, keywords)))
        iters = re.finditer(pattern, cfg_file)
        indices = [match.start() for match in iters]
        if not indices:
            return
        matches = map(cfg_file.__getslice__, indices, indices[1:] + [len(cfg_file)])

        # backup old file
        bckup = os.path.join(os.path.dirname(filename), 'orig.%s.%s' %(
                    os.path.basename(filename),time.strftime('%d%m%y%H%M%S')))
        os.system('sudo cp %s %s' %(filename, bckup))
        os.system('sudo cp %s %s' %(filename, self.tempfile.name))

        iface_pattern = '^\s*iface ' + " |^\s*iface ".join(ifaces) + ' '
        auto_pattern = '^\s*auto ' + "|^\s*auto ".join(ifaces)
        allow_pattern = '^\s*allow-hotplug ' + "|^\s*allow-hotplug ".join(ifaces)
        # write new file
        with open(self.tempfile.name, 'w') as fd:
            fd.write('%s\n' %cfg_file[0:indices[0]])
            for each in matches:
                each = each.strip()
                if re.match(auto_pattern, each) or\
                   re.match(iface_pattern, each) or\
                   re.match(allow_pattern, each):
                    continue
                else:
                    fd.write('%s\n' %each)
            fd.flush()
        os.system('sudo cp -f %s %s'%(self.tempfile.name, filename))

    def pre_conf(self):
        '''Execute commands before interface configuration for Ubuntu'''
        self.default_cfg_file = os.path.join(os.path.sep, 'etc',
                                             'network', 'interfaces')

        # Build self.mac_list[bond_member_name] = bond_member_mac
        self.get_mac_from_bond_intf()
        # Build a list of bond members from both self.mac_list and passed with
        # --members, without duplicates
        bond_members = list(set(self.members) | set(self.mac_list.keys()))

        # These interfaces will be removed from cfg_file
        ifaces = [self.device] + bond_members
        if self.vlan:
            ifaces += [self.device + '.' + self.vlan, 'vlan'+self.vlan]

        # Get matching files from 'source' keyword and create a dict
        sourced_files = self.get_sourced_files()
        sourced_files.append(self.default_cfg_file)
        self.intf_cfgfile_dict = self.map_intf_cfgfile(ifaces, sourced_files)

        # Trim down the to be overwritten interfaces section from all cfg files
        for cfg_file in sourced_files:
            self.remove_lines(ifaces, cfg_file)

    def map_intf_cfgfile(self, ifaces, cfg_files):
        if not cfg_files:
            return None
        mapped_intf_cfgfile = dict()
        for file in cfg_files:
            with open(file, 'r') as fd:
                contents = fd.read()
                for iface in ifaces:
                    regex = '(?:^|\n)\s*iface\s+%s\s+'%iface
                    if re.search(regex, contents):
                        if not iface in mapped_intf_cfgfile.keys():
                            mapped_intf_cfgfile[iface] = list()
                        mapped_intf_cfgfile[iface].append(file)
        for iface in ifaces:
            if not iface in mapped_intf_cfgfile.keys():
                mapped_intf_cfgfile[iface] = [self.default_cfg_file]
            if len(mapped_intf_cfgfile[iface]) != 1:
                raise Exception('Found multiple references for interface %s'
                                ' namely %s' %(iface, mapped_intf_cfgfile[iface]))
        return mapped_intf_cfgfile

    def get_sourced_files(self):
        '''Get config files matching the device and/or members'''
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

    def validate_bond_opts(self):
        self.bond_opts_str = 'bond-slaves none\n'
        for key in list(self.bond_opts):
            if not self.is_valid_opts(key, self.bond_opts[key], bond_opts_dict):
                del self.bond_opts[key]
            else:
                self.bond_opts_str += 'bond-%s %s\n'%(key, self.bond_opts[key])

    def write_network_script(self, device, cfg):
        '''Append new configs to interfaces file'''
        interface_file = self.intf_cfgfile_dict[device][0]
        os.system('sudo cp %s %s' %(interface_file, self.tempfile.name))

        # write new file
        with open(self.tempfile.name, 'a+') as fd:
            fd.write('\n%s\n' %cfg[0])
            fd.write('\n    '.join(cfg[1:]))
            fd.write('\n')
            fd.flush()
        os.system('sudo cp -f %s %s'%(self.tempfile.name, interface_file))

    @staticmethod
    def _dev_is_vf(dev):
        '''Return True if the given device is a PCI virtual function and not
        the physical interface.
        '''
        if os.path.exists('/sys/class/net/%s/device/physfn' % dev):
            return True
        else:
            return False

    @staticmethod
    def _get_mac_of_vf_parent(dev):
        '''Get MAC address of the physical interface the given VF belongs.
        '''
        dir_list = os.listdir('/sys/class/net/%s/device/physfn/net/' % dev)
        if not dir_list:
            return ''

        phys_dev = dir_list[0]
        mac = ''
        with open('/sys/class/net/%s/address' % phys_dev, 'r') as f:
            mac = f.readline()

        return mac

    @staticmethod
    def _get_pf(dev):
        '''Get PF of specified VF
        '''
        dir_list = os.listdir('/sys/class/net/%s/device/physfn/net/' % dev)
        if not dir_list:
            return ''

        return dir_list[0]

    def _get_vf_index(self, dev):
       '''Get index of given VF on its PF, -1 on error
       '''
       pf = self._get_pf(dev)
       if pf:
           str = "/sys/class/net/%s/device/virtfn*" %pf
           vfd = "/sys/class/net/%s/device" % dev
           for file in glob.glob(str):
               if (os.path.realpath(file) == os.path.realpath(vfd)):
                   num = re.search(r'\d+$', file)
                   return num.group()
       return ''

    def _cfg_append_spoof_vlan(self, dev, cfg):
        '''Append a line to the config to turn off spoof check Also add VLAN 0
           to the given VF as ixgbe seems to require it.
        '''
        vfi = self._get_vf_index(dev)
        pf = self._get_pf(dev)
        if (vfi and pf):
            cfg.append('post-up ip link set %s vf %s spoof off'
                       %(pf, vfi))
            if (self.vlan):
                cfg.append('pre-up ip link set %s vf %s vlan 0'
                           %(pf, vfi))
    
    def create_interface(self):
        '''Create interface config for normal interface for Ubuntu'''
        log.info('Creating Interface: %s' % self.device)
        mac = self.get_mac_addr(self.device)
        if not self.vlan and not self.no_ip:
            cfg = ['auto %s' %self.device,
                   'iface %s inet static' %self.device,
                   'address %s' %self.ipaddr,
                   'netmask  %s' %self.netmask]
            if self.gw:
                cfg.append('gateway %s' %self.gw)
        else:
            cfg = ['auto %s' %self.device,
                   'iface %s inet manual' %self.device,
                   'down ip addr flush dev %s' %self.device]

        if self._dev_is_vf(self.device):
            correct_mac = self._get_mac_of_vf_parent(self.device)
            if correct_mac:
                cfg.append('post-up ip link set %s address %s' % (self.device,
                           correct_mac))
            self._cfg_append_spoof_vlan(self.device, cfg)
        elif self.no_ip:
            # Set PF to allow-hotplug instead of auto to distinguish it from
            # interfaces which are brought up and down every time by create_interface
            cfg = ['allow-hotplug %s' %self.device,
                   'iface %s inet manual' %self.device,
                   'down ip addr flush dev %s' %self.device]
        self.write_network_script(self.device, cfg)
        if self.vlan:
            self.create_vlan_interface()

    def create_bond_members(self):
        '''Create interface config for each bond members for Ubuntu'''
        for each in self.members:
            log.info('Create Bond Members: %s' %each)
            mac = self.get_mac_addr(each)
            cfg = ['auto %s' %each,
                   'iface %s inet manual' %each,
                   'down ip addr flush dev %s' %each,
                   'bond-master %s' %self.device]
            if self._dev_is_vf(each):
                self._cfg_append_spoof_vlan(each, cfg)
                # work around a bug with bonding VFs on ixgbe by repeating ifenslave
                cfg.append('post-up ifenslave %s %s > /dev/null 2>&1; ifconfig %s up'
                           %(self.device, each, each))
            self.write_network_script(each, cfg)

    def get_vlan_egress_map_script(self, interface):
        vlan_egress_map_config = \
                vlan_egress_map.template.safe_substitute(
                        {'__interface__' : interface})
        egress_map_script = '/opt/contrail/bin/vconfig-%s' % interface
        with open(egress_map_script, 'w+') as fd:
            fd.write(vlan_egress_map_config)
            fd.flush()
        os.chmod(egress_map_script, 0755)

        return egress_map_script

    def create_vlan_interface(self):
        '''Create interface config for vlan sub interface'''
        interface = "%s.%s"%(self.device, self.vlan)
        cfg = ['auto %s' %interface,
               'iface %s inet static' %interface,
               'address %s' %self.ipaddr,
               'netmask  %s' %self.netmask,
               'vlan-raw-device %s' %self.device,
               'post-up %s' % self.get_vlan_egress_map_script(interface)]
        if self.gw:
            cfg.append('gateway %s' %self.gw)
        self.write_network_script(interface, cfg)

    def create_bonding_interface(self):
        '''Create interface config for bond master'''
        self.get_mac_from_bond_intf()
        self.create_bond_members()
        bond_mac = self.get_mac_addr(self.members[0])
        log.info('Creating bond master: %s with Mac Addr: %s' %
                 (self.device, bond_mac))
        if not self.vlan:
            cfg = ['auto %s' %self.device,
                   'iface %s inet static' %self.device,
                   'address %s' %self.ipaddr,
                   'netmask  %s' %self.netmask,
                   'hwaddress %s' % bond_mac]
            if self.gw:
                cfg.append('gateway %s' %self.gw)
        else:
            cfg = ['auto %s' %self.device,
                   'iface %s inet manual' %self.device,
                   'hwaddress %s' % bond_mac,
                   'down ip addr flush dev %s' %self.device]
        cfg += self.bond_opts_str.split("\n")
        self.write_network_script(self.device, cfg)
        if self.vlan:
            self.create_vlan_interface()

def parse_cli(args):
    '''Define and Parser arguments for the script'''
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', '-v',
                        action='version',
                        version=__version__,
                        help='Display version and exit')
    parser.add_argument('--device', 
                        action='store', 
                        required=True,
                        help='Interface Name')
    parser.add_argument('--members', 
                        action='store',
                        default=[],
                        nargs='+',
                        help='Name of Member interfaces')
    parser.add_argument('--gw', 
                        action='store',
                        help='Gateway Address of the Interface')
    parser.add_argument('--bond-opts',
                        dest='bopts',
                        action='store',
                        default='',
                        help='Interface Bonding options')
    parser.add_argument('--vlan',
                        action='store',
                        help='vLAN ID')

    ip_group = parser.add_mutually_exclusive_group(required=True)
    ip_group.add_argument('--ip',
                          action='store',
                          help='IP address of the new Interface')
    ip_group.add_argument('--no-ip',
                          action='store_true',
                          help='The interface should NOT have any IP ' +
                               'configured')

    pargs = parser.parse_args(args)
    if len(args) == 0:
        parser.print_help()
        sys.exit(2)
    return dict(pargs._get_kwargs())

def main():
    pargs = parse_cli(sys.argv[1:])
    if PLATFORM.lower() == 'ubuntu':
        interface = UbuntuInterface(**pargs)
    else:
        interface = BaseInterface(**pargs)
    interface.setup()

if __name__ == '__main__':
    main()
