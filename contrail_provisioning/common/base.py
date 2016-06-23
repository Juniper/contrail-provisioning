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

    def is_cql_supported(self):
        if self.pdist == 'Ubuntu' and self.pdistversion.find('12.') == 0:
            return False
        elif self.pdist == 'centos' and self.pdistversion.find('6.') == 0:
            return False
        return True

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
        if self.pdistversion == '14.04':
            with settings(warn_only=True):
                local(r"sed -i 's/crashkernel=.*\([ | \"]\)/crashkernel=384M-2G:64M,2G-16G:128M,16G-:256M\1/g' /etc/default/grub.d/kexec-tools.cfg")
                local("[ -f /etc/default/kdump-tools ] && sed -i 's/USE_KDUMP=0/USE_KDUMP=1/' /etc/default/kdump-tools")
        else:
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

    def setup_sriov_grub(self):
        if not self._args.sriov:
            return

        if self.pdist != 'Ubuntu':
            print "Not configuring SRIOV Grub changes for ", self.pdist, " distribution"
            return

        with open ('/etc/default/grub', 'r') as f:
            gcnf = f.read ()
            p = re.compile ('\s*GRUB_CMDLINE_LINUX_DEFAULT')
            el = gcnf.split ('\n')
            for i, x in enumerate (el):
                if not p.match(x):
                    continue
                exec(el[i])
                el[i] = 'GRUB_CMDLINE_LINUX_DEFAULT="%s intel_iommu=on"' % (
                        ' '.join (filter (lambda x: not x.startswith (
                                    'intel_iommu='), GRUB_CMDLINE_LINUX_DEFAULT.split ())))
                exec(el[i])
                el[i] = 'GRUB_CMDLINE_LINUX_DEFAULT="%s iommu=pt"' % (
                        ' '.join (filter (lambda x: not x.startswith (
                                    'iommu='), GRUB_CMDLINE_LINUX_DEFAULT.split ())))
                exec(el[i])
                with open ('%s/grub' % self._temp_dir_name, 'w') as f:
                    f.write ('\n'.join (el))
                    f.flush ()
                local ('sudo mv %s/grub /etc/default/grub' % (self._temp_dir_name))
                local ('sudo /usr/sbin/update-grub')
                break

    def setup_sriov_vfs(self):
        # Set the required number of Virtual Functions for given interfaces
        if self.pdist != 'Ubuntu':
            print "Not configuring VF's for ", self.pdist, " distribution"
            return

        sriov_string = self._args.sriov
        if sriov_string:
            intf_list = sriov_string.split(",")
            for intf_details in intf_list:
                info = intf_details.split(":")
                # Keep this command consistent with provision.py in fabric utils
                str = 'echo %s > /sys/class/net/%s/device/sriov_numvfs; sleep 2; ifup -a' % (info[1], info[0])
                # Do nothing if the entry already present in /etc/rc.local
                with settings(warn_only = True):
                    if local('grep -w \'%s\' /etc/rc.local' % str).succeeded:
                        continue

                sed = 'sudo sed -i \'/^\s*exit/i ' + str + '\' /etc/rc.local' 
                with settings(warn_only = True):
                    local(sed)


    def disable_iptables(self):
        # Disable iptables
        with settings(warn_only = True):
            local("sudo chkconfig iptables off")
            local("sudo iptables --flush")
            if self.pdist == 'redhat' or \
               self.pdist == 'centos' and self.pdistversion.startswith('7'):
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
        template_vals = {
                         '__contrail_keystone_ip__': self._args.keystone_ip,
                         '__contrail_admin_user__': self._args.keystone_admin_user,
                         '__contrail_admin_password__': self._args.keystone_admin_passwd,
                         '__contrail_admin_tenant_name__': self._args.keystone_admin_tenant_name,
                         '__contrail_ks_auth_protocol__': self._args.keystone_auth_protocol,
                         '__contrail_ks_auth_port__': self._args.keystone_auth_port,
                         '__keystone_insecure_flag__': self._args.keystone_insecure,
                         '__contrail_memcached_opt__': 'memcache_servers=127.0.0.1:11211' if self._args.multi_tenancy else '',
                        }
        self._template_substitute_write(contrail_keystone_auth_conf.template,
                                        template_vals, self._temp_dir_name + '/contrail-keystone-auth.conf')
        local("sudo mv %s/contrail-keystone-auth.conf /etc/contrail/" %(self._temp_dir_name))

    def set_config(self, fl, sec, var, val=''):
        with settings(warn_only=True):
            local("openstack-config --set %s %s %s '%s'" % (
                        fl, sec, var, val))

    def del_config(self, fl, sec, var):
        with settings(warn_only=True):
            local("openstack-config --del %s %s %s" % (
                        fl, sec, var))

    def get_config(self, fl, sec, var):
        with settings(warn_only=True):
            output = local("openstack-config --get %s %s %s" % (
                fl, sec, var), capture=True)
        return output

    def setup(self):
        self.disable_selinux()
        self.disable_iptables()
        self.setup_coredump()
        self.fixup_config_files()
        self.run_services()
