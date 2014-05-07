#!/usr/bin/env python
'''Provision Static Routes'''
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

__version__ = '1.0'

import re
import sys
import time
import shutil
import os.path
import logging
import platform
import argparse
from netaddr import IPNetwork

logging.basicConfig(format='%(asctime)-15s:: %(funcName)s:%(levelname)s:: %(message)s',
                    level=logging.INFO)
log = logging.getLogger(__name__)
PLATFORM = platform.dist()[0]

class StaticRoute(object):
    '''Base class containing common methods for configuring static routes
    '''
    def __init__(self, **kwargs):
        self.device = kwargs['device']
        self.netw   = kwargs['network']
        self.gw     = kwargs['gw']
        self.mask   = kwargs['netmask']
        self.prefix = 32
        
    def write_network_script(self):
        '''Create an interface config file in network-scripts with given
            config
        '''
        if os.path.isfile(self.nwfile):
            tmpfile = os.path.join(os.path.dirname(self.nwfile), \
                                  'moved-%s' %os.path.basename(self.nwfile))
            log.info('Backup existing file %s to %s' %(self.nwfile, tmpfile))
            shutil.move(self.nwfile, tmpfile)
        # read existing file
        with open(self.nwfile, 'w') as fid:
            fid.write('%s\n' %self.cmd)
            fid.flush()
            log.info('New file %s has ben created' %self.nwfile)

    def restart_service(self):
        '''Restart network service'''
        log.info('Restarting Network Services...')
        os.system('service network restart')
        time.sleep(5)
                                  
    def pre_config(self):
        '''Setup env before static route configuration'''
        self.nwfile = os.path.join(os.path.sep, 'etc', 'sysconfig',
                                  'network-scripts', 'route-%s' %self.device)
        self.cmd = '%s/%s via %s dev %s' %(
               self.netw, self.prefix, self.gw, self.device) 

    def verify_route(self):
        '''verify configured static routes'''
        with os.popen('ip route') as cmd:
            output = cmd.read().split('\n')
        exp_route = r'%s/%s\s+via\s+%s\s+dev\s+%s' %(self.netw, 
                    self.prefix, self.gw, self.device)
        pattern = re.compile(exp_route)
        routes = filter(pattern.match, output)
        if len(routes) == 0:
            print 'INFO: Available Routes :\n%s' %"\n".join(output)
            print 'ERROR: Searched Route Pattern: \n%s' %exp_route
            print 'ERROR: Matched Routes (%s)' %routes
            raise RuntimeError('Seems Routes are not properly configured')
        else:
            print 'ROUTE (%s) configured Sucessfully' %routes

    def post_config(self):
        '''Execute commands after static route configuration'''
        self.restart_service()
        self.verify_route()

    def setup(self):
        '''High level method to call individual methods to configure
            static routes
        '''
        self.prefix = IPNetwork('%s/%s' %(self.netw, self.mask)).prefixlen
        self.pre_config()
        self.write_network_script()
        self.post_config()
        
    
class UbuntuStaticRoute(StaticRoute):
    '''Configure Static Route in Ubuntu'''

    def restart_service(self):
        '''Restart network service for Ubuntu'''
        log.info('Restarting Network Services...')
        os.system('/etc/init.d/networking restart')
        time.sleep(5)

    def remove_lines(self):
        '''Remove existing config related to given route if the same
            needs to be re-configured
        '''
        log.info('Remove Existing Static Route in %s' %self.nwfile)
        newfile = []
        # backup existing file
        bckup = os.path.join(os.path.dirname(self.nwfile), 'org.%s.%s' %(
                    os.path.basename(self.nwfile),time.strftime('%d%m%y%H%M%S')))
        shutil.copy(self.nwfile, bckup)

        # read existing file
        with open(self.nwfile, 'r') as fid:
            cfg_file = fid.read().split('\n')
        # remove config that match with new config
        for line in cfg_file:
            if self.cmd.replace(' ', '') == line.replace(' ', ''):
                log.info('Removing existing Static Route: \n%s' %line)
                continue
            else:
                newfile.append(line)
        # write new file
        with open(self.nwfile, 'w') as fid:
            fid.write('%s\n' %"\n".join(newfile))
            fid.flush()
            log.info('%s file has been updated' %self.nwfile)
        
    def write_network_script(self):
        '''Append new configs to interfaces file'''
        with open(self.nwfile, 'a') as fid:
            fid.write('%s\n' %self.cmd)
            fid.flush()

    def pre_config(self):
        '''Setup env before static route configuration in Ubuntu'''
        self.nwfile = os.path.join(os.path.sep, 'etc', 'network', 'interfaces')
        self.cmd = 'up route add -net %s/%s gw %s dev %s' %(
               self.netw, self.prefix, self.gw, self.device) 
        self.remove_lines()

def parse_cli(args):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', '-v',
                        action='version',
                        version=__version__,
                        help='Display version and exit')
    parser.add_argument('--device', 
                        action='store',
                        help='Interface Name')
    parser.add_argument('--network', 
                        action='store',
                        help='Network address of the Static route')
    parser.add_argument('--netmask', 
                        action='store',
                        help='Netmask of the Static route')
    parser.add_argument('--gw', 
                        action='store',
                        metavar='GATEWAY',
                        help='Gateway Address of the Static route')

    pargs = parser.parse_args(args)
    if len(args) == 0:
        parser.print_help()
        sys.exit(2)
    return dict(pargs._get_kwargs())
    
if __name__ == '__main__':
    pargs = parse_cli(sys.argv[1:])
    if PLATFORM.lower() != 'ubuntu':
        route = StaticRoute(**pargs)
    else:
        route = UbuntuStaticRoute(**pargs)
    route.setup()

