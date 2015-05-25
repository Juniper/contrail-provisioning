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
from time import sleep

from fabric.api import *

from contrail_provisioning.common import  DEBIAN, RHEL
from contrail_provisioning.common.templates import contrail_keystone_auth_conf

class ContrailSetup(object):
    def __init__(self):
        (self.pdist, self.pdistversion, self.pdistrelease) = platform.dist()
        self.hostname = socket.gethostname()
        if self.pdist in DEBIAN:
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

        if self.pdist in RHEL:
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
            if self.pdist in RHEL:
                self.enable_kernel_core ()
            if self.pdist in DEBIAN:
                self.setup_crashkernel_params()
        except Exception as e:
            print "Ignoring failure kernel core dump"

        try:
            if self.pdist in RHEL:
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
                         '__contrail_admin_token__': self._args.keystone_admin_token,
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

    def insert_line_to_file(self, file_name, line, pattern=None):
        with settings(warn_only = True):
            if pattern:
                local('sed -i \'/%s/d\' %s' % (pattern,file_name))
            local('printf "%s\n" >> %s' % (line, file_name))

    def increase_limits(self):
        """Increase limits in /etc/security/limits.conf, sysctl.conf and
           /etc/contrail/supervisor*.conf files
        """
        if self.pdist in DEBIAN:
            line = 'root soft nofile 65535\nroot hard nofile 65535'
        else:
            line = 'root soft nproc 65535'

        increase_limits_data = {
            '/etc/security/limits.conf' :
                [('^root\s*soft\s*nproc\s*.*', line),
                 ('^*\s*hard\s*nofile\s*.*', '* hard nofile 65535'),
                 ('^*\s*soft\s*nofile\s*.*', '* soft nofile 65535'),
                 ('^*\s*hard\s*nproc\s*.*', '* hard nproc 65535'),
                 ('^*\s*soft\s*nproc\s*.*', '* soft nofile 65535'),
                ],
            '/etc/sysctl.conf' : [('^fs.file-max.*', 'fs.file-max = 65535')],
        }
        for conf_file, data in increase_limits_data.items():
            for pattern, line in data:
                self.insert_line_to_file(pattern=pattern, line=line, file_name=conf_file)

        with settings(warn_only=True):
            local('sysctl -p')
        local('sed -i \'s/^minfds.*/minfds=10240/\' /etc/contrail/supervisor*.conf')

    def remove_override(self, file_name):
        if self.pdist in DEBIAN:
            with settings(warn_only=True):
                local('rm /etc/init/%s' % file_name)

    def verify_service(self, service):
        for x in xrange(10):
            output = local("service %s status" % service, capture=True)
            if 'running' in output.lower():
                return
            else:
                sleep(20)
        raise SystemExit("Service %s not running." % service)

    def is_package_installed(self, pkg_name):
        if self.pdist in DEBIAN:
            cmd = 'dpkg-query -l "%s" | grep -q ^.i'
        elif self.pdist in RHEL:
            cmd = 'rpm -qi %s '
        cmd = cmd % (pkg_name)
        with settings(warn_only=True):
            result = local("sudo %s" % cmd)
        return result.succeeded

    def add_reserved_ports(self, ports):
        # Exclude ports from the available ephemeral port range
        existing_ports = local("sudo cat /proc/sys/net/ipv4/ip_local_reserved_ports", capture=True)
        local("sudo sysctl -w net.ipv4.ip_local_reserved_ports=%s,%s" % (ports, existing_ports))
        # Make the exclusion of ports persistent
        with settings(warn_only=True):
            not_set = local("sudo grep '^net.ipv4.ip_local_reserved_ports' /etc/sysctl.conf > /dev/null 2>&1").failed
        if not_set:
            local('sudo echo "net.ipv4.ip_local_reserved_ports = %s" >> /etc/sysctl.conf' % ports)
        else:
            local("sudo sed -i 's/net.ipv4.ip_local_reserved_ports\s*=\s*/net.ipv4.ip_local_reserved_ports=%s,/' /etc/sysctl.conf" % ports)

        # Centos returns non zero return code for "sysctl -p".
        # However the ports are reserved properly.
        with settings(warn_only=True):
            local("sudo sysctl -p")

    def enable_haproxy(self):
        """For Ubuntu. Set ENABLE=1 in /etc/default/haproxy."""
        if self.pdist in DEBIAN:
            with settings(warn_only=True):
                local("sudo sed -i 's/ENABLED=.*/ENABLED=1/g' /etc/default/haproxy")

    def fixup_redis_conf(self, bind=True):
        if self.pdist in DEBIAN:
            conf_file = "/etc/redis/redis.conf"
            svc_name = "redis-server"
        elif self.pdist in RHEL:
            conf_file = "/etc/redis.conf"
            svc_name = "redis"
        # we need the redis to be listening on *, comment bind line
        local("sudo service %s stop" % svc_name)
        if bind:
            local("sudo sed -i -e '/^[ ]*bind/s/^/#/' %s" % conf_file)
        # If redis passwd sepcified add that to the conf file
        if self._args.redis_password:
            local("sudo sed -i '/^# requirepass/ c\ requirepass %s' %s"
                  % (self._args.redis_password, conf_file))
        local("sudo chkconfig %s on" % svc_name)
        local("sudo service %s start" % svc_name)
        #check if the redis-server is running, if not, issue start again
        retries = 10
        with settings(warn_only=True):
            while (local("sudo service %s status | grep not" % svc_name).succeeded
                   and retries):
                retries -= 1
                sleep(1)
                local("sudo service %s restart" % svc_name)

    def setup(self):
        self.disable_selinux()
        self.disable_iptables()
        self.setup_coredump()
        self.fixup_config_files()
        self.run_services()
