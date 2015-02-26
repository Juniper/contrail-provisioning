#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#
"""Base Contrail Provisioning module."""

import os
import re
import sys
import shutil
import socket
import argparse
import tempfile
import platform
import ConfigParser

from fabric.api import *
from contrail_provisioning.common.templates import contrail_keystone_auth_conf

class ContrailSetup(object):
    def __init__(self):
        (self.pdist, self.pdistversion, self.pdistrelease) = platform.dist()
        self.hostname = socket.gethostname()
        if self.pdist == 'Ubuntu':
            local("ln -sf /bin/true /sbin/chkconfig")

        self._temp_dir_name = tempfile.mkdtemp()
        self.contrail_bin_dir = '/opt/contrail/bin'
        self._fixed_qemu_conf = False

        # Parser defaults
        self.global_defaults = {
        }

    def _parse_args(self, args_str):
        '''
            Base parser.
        '''

        # Source any specified config/ini file
        # Turn off help, so we print all options in response to -h
        conf_parser = argparse.ArgumentParser(add_help = False)

        conf_parser.add_argument("-c", "--conf_file",
                                 help="Specify config file", metavar="FILE")
        args, self.remaining_argv = conf_parser.parse_known_args(args_str.split())

        if args.conf_file:
            config = ConfigParser.SafeConfigParser()
            config.read([args.conf_file])
            self.global_defaults.update(dict(config.items("GLOBAL")))

        # Override with CLI options
        # Don't surpress add_help here so it will handle -h
        parser = argparse.ArgumentParser(
            # Inherit options from config_parser
            parents=[conf_parser],
            # print script description with -h/--help
            description=__doc__,
            # Don't mess with format of description
            formatter_class=argparse.RawDescriptionHelpFormatter,
            )

        parser.set_defaults(**self.global_defaults)

        return parser

    def update_vips_in_ctrl_details(self, ctrl_infos):
        if self._args.internal_vip:
            ctrl_infos.append('INTERNAL_VIP=%s' % self._args.internal_vip)
        if self._args.contrail_internal_vip:
            ctrl_infos.append('CONTRAIL_INTERNAL_VIP=%s' % self._args.contrail_internal_vip)
        if self._args.external_vip:
            ctrl_infos.append('EXTERNAL_VIP=%s' % self._args.external_vip)

    def _template_substitute(self, template, vals):
        data = template.safe_substitute(vals)
        return data

    def _template_substitute_write(self, template, vals, filename):
        data = self._template_substitute(template, vals)
        outfile = open(filename, 'w')
        outfile.write(data)
        outfile.close()

    def _replaces_in_file(self, file, replacement_list):
        rs = [ (re.compile(regexp), repl) for (regexp, repl) in replacement_list]
        file_tmp = file + ".tmp"
        with open(file, 'r') as f:
            with open(file_tmp, 'w') as f_tmp:
                for line in f:
                    for r, replace in rs:
                        match = r.search(line)
                        if match:
                            line = replace + "\n"
                    f_tmp.write(line)
        shutil.move(file_tmp, file)

    def replace_in_file(self, file, regexp, replace):
        self._replaces_in_file(file, [(regexp, replace)])

    def setup_crashkernel_params(self):
        local(r"sed -i 's/crashkernel=.*\([ | \"]\)/crashkernel=384M-2G:64M,2G-16G:128M,16G-:256M\1/g' /etc/grub.d/10_linux")
        local("update-grub")

    def enable_kernel_core(self):
        '''
            enable_kernel_core:
                update grub file
                install grub2
                enable services
        '''
        gcnf = ''
        with open ('/etc/default/grub', 'r') as f:
            gcnf = f.read ()
            p = re.compile ('\s*GRUB_CMDLINE_LINUX')
            el = ExtList (gcnf.split ('\n'))
            try:
                i = el.findex (p.match)
                exec (el[i])
                el[i] = 'GRUB_CMDLINE_LINUX="%s crashkernel=128M"' % (
                        ' '.join (filter (lambda x: not x.startswith (
                                    'crashkernel='), GRUB_CMDLINE_LINUX.split ())))
                exec (el[i])
                el[i] = 'GRUB_CMDLINE_LINUX="%s kvm-intel.nested=1"' % (
                        ' '.join (filter (lambda x: not x.startswith (
                                    'kvm-intel.nested='), GRUB_CMDLINE_LINUX.split ())))

                with open ('%s/grub' % self._temp_dir_name, 'w') as f:
                    f.write ('\n'.join (el))
                    f.flush ()
                local ('sudo mv %s/grub /etc/default/grub' % (self._temp_dir_name))
                local ('sudo /usr/sbin/grub2-mkconfig -o /boot/grub2/grub.cfg')
            except LookupError:
                print 'Improper grub file, kernel crash not enabled'

    def disable_selinux(self):
        # Disable selinux
        with lcd(self._temp_dir_name):
            with settings(warn_only = True):
                local("sudo sed 's/SELINUX=.*/SELINUX=disabled/g' /etc/selinux/config > config.new")
                local("sudo mv config.new /etc/selinux/config")
                local("setenforce 0")
                # cleanup in case move had error
                local("rm config.new")

    def disable_iptables(self):
        # Disable iptables
        with settings(warn_only = True):
            local("sudo chkconfig iptables off")
            local("sudo iptables --flush")
            if self.pdist == 'redhat':
                local("sudo service iptables stop")
                local("sudo service ip6tables stop")
                local("sudo systemctl stop firewalld")
                local("sudo systemctl status firewalld")
                local("sudo chkconfig firewalld off")
                local("sudo /usr/libexec/iptables/iptables.init stop")
                local("sudo /usr/libexec/iptables/ip6tables.init stop")
                local("sudo service iptables save")
                local("sudo service ip6tables save")
                local("iptables -L")

    def enable_kdump(self):
        '''Enable kdump for centos based systems'''
        with settings(warn_only=True):
            status = local("chkconfig --list | grep kdump")
            if status.failed:
                print 'WARNING: Seems kexec-tools is not installed. Skipping enable kdump'
                return False
        local("chkconfig kdump on")
        local("service kdump start")
        local("service kdump status")
        local("cat /sys/kernel/kexec_crash_loaded")
        local("cat /proc/iomem | grep Crash")

    def setup_coredump(self):
        # usable core dump
        initf = '/etc/sysconfig/init'
        with settings(warn_only = True):
            local("sudo sed '/DAEMON_COREFILE_LIMIT=.*/d' %s > %s.new" %(initf, initf))
            local("sudo mv %s.new %s" %(initf, initf))

        if self.pdist in ['centos', 'fedora', 'redhat']:
            core_unlim = "echo DAEMON_COREFILE_LIMIT=\"'unlimited'\""
            local("%s >> %s" %(core_unlim, initf))

        #Core pattern
        pattern= 'kernel.core_pattern = /var/crashes/core.%e.%p.%h.%t'
        ip_fwd_setting = 'net.ipv4.ip_forward = 1'
        sysctl_file = '/etc/sysctl.conf'
        print pattern
        with settings( warn_only= True) :
            local('grep -q \'%s\' /etc/sysctl.conf || echo \'%s\' >> /etc/sysctl.conf' %(pattern, pattern))
            local("sudo sed 's/net.ipv4.ip_forward.*/%s/g' %s > /tmp/sysctl.new" %(ip_fwd_setting,sysctl_file))
            local("sudo mv /tmp/sysctl.new %s" %(sysctl_file))
            local("rm /tmp/sysctl.new")
            local('sysctl -p')
            local('mkdir -p /var/crashes')
            local('chmod 777 /var/crashes')

        try:
            if self.pdist in ['fedora', 'centos', 'redhat']:
                self.enable_kernel_core ()
            if self.pdist == 'Ubuntu':
                self.setup_crashkernel_params()
        except Exception as e:
            print "Ignoring failure kernel core dump"

        try:
            if self.pdist in ['fedora', 'centos', 'redhat']:
                self.enable_kdump()
        except Exception as e:
            print "Ignoring failure when enabling kdump"
            print "Exception: %s" % str(e)

    def fixup_keystone_auth_config_file(self):
        # Keystone auth config ini
        if os.path.exist('/etc/contrail/contrail-keystone-auth.conf'):
            return
        template_vals = {
                         '__contrail_keystone_ip__': self._args.keystone_ip,
                         '__contrail_admin_user__': self._args.keystone_admin_user,
                         '__contrail_admin_password__': self._args.keystone_admin_passwd,
                         '__contrail_admin_tenant_name__': self._args.keystone_admin_tenant_name,
                         '__contrail_admin_token__': self._args.keystone_admin_token,
                         '__contrail_ks_auth_protocol__': self._args.keystone_auth_protocol,
                         '__contrail_ks_auth_port__': self._args.keystone_auth_port,
                         '__keystone_insecure_flag__': self._args.keystone_insecure,
                         '__contrail_memcached_opt__': 'memcache_servers=127.0.0.1:11211' if self._args.multi_tenancy else '',
                        }
        self._template_substitute_write(contrail_keystone_auth_conf.template,
                                        template_vals, self._temp_dir_name + '/contrail-keystone-auth.conf')
        local("sudo mv %s/contrail-keystone-auth.conf /etc/contrail/" %(self._temp_dir_name))

    def setup(self):
        self.disable_selinux()
        self.disable_iptables()
        self.setup_coredump()
        self.fixup_config_files()
        self.run_services()
