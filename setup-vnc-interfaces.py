#!/usr/bin/env python
'''Provision Interface and Configure Bond Interface'''
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

__version__ = '1.0'

import os
import re
import sys
import argparse
import shutil
import socket
import fcntl
import struct
import logging
import platform
import time
from netaddr import IPNetwork

logging.basicConfig(format='%(asctime)-15s:: %(funcName)s:%(levelname)s::\
                            %(message)s',
                    level=logging.INFO)
log = logging.getLogger(__name__)
PLATFORM = platform.dist()[0]

class BaseInterface(object):
    '''Base class containing common methods for configuring interface
    '''
    def __init__(self, **kwargs):
        self.device     = kwargs['device']
        self.members    = kwargs.get('members', [])
        self.mode       = kwargs.get('mode', 'balance-xor')
        self.ip         = kwargs.get('ip', None)
        self.gw         = kwargs.get('gw', None)
        self.type       = kwargs.get('type', 'Ethernet')
        self.ipaddr     = None
        self.netmask    = None

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
            shutil.move(nwfile, tmpfile)
        with open(nwfile, 'w') as fid:
            fid.write('\n'.join(['%s=%s' %(key, value) \
                          for key, value in cfg.items()]))
            fid.write('\n')
            fid.flush()

    def get_mac_addr(self, iface):
        '''Retrieve mac address for the given interface in the system'''
        macaddr = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            macinfo = fcntl.ioctl(sock.fileno(), 0x8927,  struct.pack('256s', iface[:15]))
            macaddr = ''.join(['%02x:' % ord(each) for each in macinfo[18:24]])[:-1]
        except IOError, err:
            log.warn('Seems there is no such interface (%s)' %iface)
        return macaddr

    def create_bond_members(self, master):
        '''Create interface config for each bond members'''
        # create slave interface
        for each in self.members:
            log.info('Creating bond member: %s' %each)
            cfg = {}
            mac = self.get_mac_addr(each)
            cfg = {'DEVICE'        : each,
                   'MASTER'        : master,
                   'SLAVE'         : 'yes',
                   'TYPE'          : self.type,
                   'NM_CONTROLLED' : 'no',
                   'IPADDR'        : '',
                   'NETMASK'       : '',
                   'HWADDR'        : mac}
            self.write_network_script(each, cfg)
        time.sleep(2)
              
    def create_bonding_interface(self):
        '''Create interface config for bond master'''
        # create slave interface
        self.create_bond_members(self.device)
        log.info('Creating bond master: %s' %self.device)
        cfg = {'DEVICE'        : self.device,
               'ONBOOT'        : 'yes',
               'NM_CONTROLLED' : 'no',
               'BONDING_MASTER': 'yes',
               'BONDING_OPTS'  : 'mode=%s' %self.mode,
               'BOOTPROTO'     : 'none',
               'NETMASK'       : self.netmask,
               'IPADDR'        : self.ipaddr}
        self.write_network_script(self.device, cfg)

    def create_interface(self):
        '''Create interface config for normal interface'''
        log.info('Creating Interface: %s' %self.device)
        mac = self.get_mac_addr(self.device)
        cfg = {'DEVICE'        : self.device,
               'ONBOOT'        : 'yes',
               'NM_CONTROLLED' : 'no',
               'BOOTPROTO'     : 'none',
               'NETMASK'       : self.netmask,
               'IPADDR'        : self.ipaddr,
               'HWADDR'        : mac}
        self.write_network_script(self.device, cfg)
    
    def restart_service(self):
        '''Restart network service'''
        log.info('Restarting Network Services...')
        os.system('service network restart')
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
        self.pre_conf()
        if self.ip:
            ip = IPNetwork(self.ip)
            self.ipaddr = str(ip.ip)
            self.netmask = str(ip.netmask)
        if re.match(r'^bond', self.device):
            self.create_bonding_interface()
        else:
            self.create_interface()
        self.post_conf()

class UbuntuInterface(BaseInterface):
    def restart_service(self):
        '''Restart network service for Ubuntu'''
        log.info('Restarting Network Services...')
        os.system('/etc/init.d/networking restart')
        time.sleep(5)

    def remove_lines(self, ifaces, filename):
        '''Remove existing config related to given interface if the same
            needs to be re-configured
        '''
        log.info('Remove Existing Interface configs in %s' %filename)
        # read existing file
        if not filename:
            filename = os.path.join(os.path.sep, 'etc', 'network', 'interfaces')
        with open(filename, 'r') as fid:
            cfg_file = fid.read()

        # get blocks
        keywords = ['allow-', 'auto', 'iface', 'source', 'mapping']
        pattern = '\n\s*' + '|\n\s*'.join(keywords)
        iters = re.finditer(pattern, cfg_file)
        indices = [match.start() for match in iters]
        matches = map(cfg_file.__getslice__, indices, indices[1:] + [len(cfg_file)])

        # backup old file
        bckup = os.path.join(os.path.dirname(filename), 'org.%s.%s' %(
                    os.path.basename(filename),time.strftime('%d%m%y%H%M%S')))
        shutil.copy(filename, bckup)

        # write new file
        fid = open(filename, 'w')
        fid.write('%s\n' %cfg_file[0:indices[0]])
        iface_pattern = '^\s*iface ' + " |^\s*iface ".join(ifaces) + ' '
        auto_pattern = '^\s*auto ' + "|^\s*auto ".join(ifaces)
        for each in matches:
            each = each.strip()
            if re.match(auto_pattern, each) or re.match(iface_pattern, each):
                continue
            else:
                fid.write('%s\n' %each)
            fid.flush()
        fid.close()

    def pre_conf(self):
        '''Execute commands before interface configuration for Ubuntu'''
        filename = os.path.join(os.path.sep, 'etc', 'network', 'interfaces')
        ifaces = [self.device] + self.members
        self.remove_lines(ifaces, filename)

    def write_network_script(self, cfg):
        '''Append new configs to interfaces file'''
        interface_file = os.path.join(os.path.sep, 'etc', 'network', 'interfaces')
        with open(interface_file, 'a') as fid:
            fid.write('\n')
            fid.write('%s\n' %cfg[0])
            fid.write('\n    '.join(cfg[1:]))
            fid.write('\n')
            fid.flush()

    def create_interface(self):
        '''Create interface config for normal interface for Ubuntu'''
        log.info('Creating Interface: %s' %self.device)
        cfg = ['auto %s' %self.device,
               'iface %s inet static' %self.device,
               'address %s' %self.ipaddr,
               'netmask %s' %self.netmask]
        self.write_network_script(cfg)

    def create_bond_members(self, master):
        '''Create interface config for each bond members for Ubuntu'''
        if len(self.members) != 0:
            bprimary = self.members[0]
        for each in self.members:
            log.info('Create Bond Members: %s' %each)
            cfg = ['auto %s' %each,
                   'iface %s inet manual' %each,
                   'bond-master %s' %master,
                   'bond-primary %s' %bprimary]
            self.write_network_script(cfg)

    def create_bonding_interface(self):
        '''Create interface config for bond master'''
        #create slave interfaces
        self.create_bond_members(self.device)
        log.info('Create Bond master: %s' %self.device)
        cfg = ['auto %s' %self.device,
               'iface %s inet static' %self.device,
               'address %s' %self.ipaddr,
               'netmask  %s' %self.netmask,
               'bond-mode %s' %self.mode,
               'bond-miimon 100',
               'bond-slaves %s' %" ".join(self.members)]
        self.write_network_script(cfg)
                   

def parse_cli(args):
    '''Define and Parser arguments for the script'''
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', '-v',
                        action='version',
                        version=__version__,
                        help='Display version and exit')
    parser.add_argument('--device', 
                        action='store', 
                        default='bond0',
                        help='Interface Name')
    parser.add_argument('--members', 
                        action='store',
                        default=[],
                        nargs='+',
                        help='Name of Member interfaces')
    parser.add_argument('--mode',    
                        action='store', 
                        default='balance-xor',
                        help='Mode of Bonding Interface')
    parser.add_argument('--ip', 
                        action='store',
                        help='IP address of the new Interface')
    parser.add_argument('--gw', 
                        action='store',
                        help='Gateway Address of the Interface')
    parser.add_argument('--interface-type', 
                        dest='type', 
                        action='store', 
                        default='Ethernet',
                        help='Specify Interface type')
    pargs = parser.parse_args(args)
    if len(args) == 0:
        parser.print_help()
        sys.exit(2)
    return dict(pargs._get_kwargs())

if __name__ == '__main__':
    pargs = parse_cli(sys.argv[1:])
    if PLATFORM.lower() == 'ubuntu':
        interface = UbuntuInterface(**pargs)
    else:
        interface = BaseInterface(**pargs)
    interface.setup()
