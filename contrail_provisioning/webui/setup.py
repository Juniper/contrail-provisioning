#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import os
import sys
import argparse
import ConfigParser

from fabric.api import local, env, run, settings

from contrail_provisioning.common.base import ContrailSetup


class WebuiSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(WebuiSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.global_defaults = {
            'cfgm_ip': '127.0.0.1',
            'keystone_ip': '127.0.0.1',
            'openstack_ip': '127.0.0.1',
            'collector_ip' : '127.0.0.1',
            'admin_user': 'admin',
            'admin_password': 'contrail123',
            'admin_tenant_name': 'admin',
            'keystone_version': 'v2.0',
            'keystone_auth_protocol': 'http',
            'apiserver_auth_protocol': 'http',
        }
        self.parse_args(args_str)


    def parse_args(self, args_str):        
        '''
        Eg. setup-vnc-webui --cfgm_ip 10.84.12.11 --keystone_ip 10.84.12.12 
            --openstack_ip 10.84.12.12 --collector_ip 10.84.12.12
            --cassandra_ip_list 10.1.5.11 10.1.5.12 --internal_vip 10.84.12.200
            --contrail_internal_vip 10.84.12.250
        '''
        parser = self._parse_args(args_str)

        parser.add_argument("--cfgm_ip", help = "IP Address of the cfgm node")
        parser.add_argument("--keystone_ip", help = "IP Address of the keystone node")
        parser.add_argument("--openstack_ip", help = "IP Address of the openstack controller")
        parser.add_argument("--collector_ip", help = "IP Address of the Collector node")
        parser.add_argument("--cassandra_ip_list", help = "List of IP Addresses of cassandra nodes",
                            nargs='+', type=str)
        parser.add_argument("--orchestrator", help = "Orchestrator used, example openstack, vcenter")
        parser.add_argument("--internal_vip", help = "VIP Address of openstack  nodes")
        parser.add_argument("--contrail_internal_vip", help = "VIP Address of config  nodes")
        parser.add_argument("--vcenter_ip", help = "vcenter ip to connect to")
        parser.add_argument("--vcenter_port", help = "vcenter port to connect to")
        parser.add_argument("--vcenter_auth", help = "vcenter auth http or https")
        parser.add_argument("--vcenter_datacenter", help = "vcenter datacenter name")
        parser.add_argument("--vcenter_dvswitch", help = "vcenter dvswitch name")
        parser.add_argument("--admin_user",
                            help = "Identity Manager admin user name.")
        parser.add_argument("--admin_password",
                            help = "Identity Manager admin user's password.")
        parser.add_argument("--admin_tenant_name",
                            help = "Identity Manager admin tenant name.")
        parser.add_argument("--redis_password", help = "Redis password")
        parser.add_argument("--keystone_version", choices=['v2.0', 'v3'],
            help = "Keystone Version")
        parser.add_argument("--keystone_auth_protocol",
            help = "Auth protocol used to talk to keystone")
        parser.add_argument("--apiserver_auth_protocol",
            help = "Auth protocol used to talk to apiserver/neutron")
        self._args = parser.parse_args(self.remaining_argv)

    def  fixup_config_files(self):
        self.fixup_config_global_js()

    def fixup_config_global_js(self):
        openstack_ip = self._args.openstack_ip
        keystone_ip = self._args.keystone_ip
        keystone_version = self._args.keystone_version
        internal_vip = self._args.internal_vip
        contrail_internal_vip = self._args.contrail_internal_vip or internal_vip
        admin_user = self._args.admin_user
        admin_password = self._args.admin_password
        admin_tenant_name = self._args.admin_tenant_name
        add_cert_path = False
        keys_path = '/etc/contrail/webui_ssl/'
        keys_re_path = '\/etc\/contrail\/webui_ssl\/'

        #Dynamically create keys
        with settings(warn_only=True):
            server_options = local('cat /etc/contrail/config.global.js | grep config.server_options', capture=True)
            keys_path_specified = local('cat /etc/contrail/config.global.js | grep config.server_options.key_file', capture=True)
            cert_path_specified = local('cat /etc/contrail/config.global.js | grep config.server_options.cert_file', capture=True)
        try:
            if not (keys_path_specified and cert_path_specified):
                local("sudo mkdir -p %s" %(keys_path))
                key_cmd = ('sudo openssl req -new -newkey rsa:2048 -nodes -out %s%s -keyout %s%s -subj "/C=US/ST=CA/L=Sunnyvale/O=Juniper Networks/OU=Juniper CA/CN=ContrailCA"') %(keys_path, 'certrequest.csr', keys_path, 'cs-key.pem')
                local(key_cmd)
                cert_cmd = ('sudo openssl x509 -req -days 730 -in %s%s -signkey %s%s -out %s%s') %(keys_path, 'certrequest.csr', keys_path, 'cs-key.pem', keys_path, 'cs-crt.crt',)
                local(cert_cmd)
                local('sudo cat %s%s %s%s > %s%s' %(keys_path, 'cs-key.pem', keys_path, 'cs-crt.crt', keys_path, 'cs-cert.pem'))
                if os.path.isfile(keys_path + 'cs-key.pem') == True and \
                    os.path.isfile(keys_path + 'cs-cert.pem') == True:
                    add_cert_path = True
        except:
            add_cert_path = False

        local("sudo sed \"s/config.cnfg.server_ip.*/config.cnfg.server_ip = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(contrail_internal_vip or self._args.cfgm_ip))
        local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        local("sudo sed \"s/config.networkManager.ip.*/config.networkManager.ip = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(contrail_internal_vip or self._args.cfgm_ip))
        local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        local("sudo sed \"s/config.imageManager.ip.*/config.imageManager.ip = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(internal_vip or openstack_ip))
        local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        local("sudo sed \"s/config.computeManager.ip.*/config.computeManager.ip = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(internal_vip or openstack_ip))
        local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        local("sudo sed \"s/config.identityManager.ip.*/config.identityManager.ip = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(internal_vip or keystone_ip))
        local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        local("sudo sed -si \"s/^config.identityManager.apiVersion.*/config.identityManager.apiVersion = ['%s'];/g\" /etc/contrail/config.global.js" %(keystone_version))
        local("sudo sed -si \"s/config.identityManager.authProtocol.*/config.identityManager.authProtocol = '%s';/g\" /etc/contrail/config.global.js" % self._args.keystone_auth_protocol)
        local("sudo sed -si \"s/config.networkManager.authProtocol.*/config.networkManager.authProtocol = '%s';/g\" /etc/contrail/config.global.js" % self._args.apiserver_auth_protocol)
        local("sudo sed \"s/config.storageManager.ip.*/config.storageManager.ip = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(internal_vip or openstack_ip))
        local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        if admin_user:
            local("sudo sed \"s/auth.admin_user.*/auth.admin_user = '%s';/g\" /etc/contrail/contrail-webui-userauth.js > contrail-webui-userauth.js.new" %(admin_user))
            local("sudo mv contrail-webui-userauth.js.new /etc/contrail/contrail-webui-userauth.js")
        if admin_password:
            local("sudo sed \"s/auth.admin_password.*/auth.admin_password = '%s';/g\" /etc/contrail/contrail-webui-userauth.js > contrail-webui-userauth.js.new" %(admin_password))
            local("sudo mv contrail-webui-userauth.js.new /etc/contrail/contrail-webui-userauth.js")
        if admin_tenant_name:
            local("sudo sed \"s/auth.admin_tenant_name.*/auth.admin_tenant_name = '%s';/g\" /etc/contrail/contrail-webui-userauth.js > contrail-webui-userauth.js.new" %(admin_tenant_name))
            local("sudo mv contrail-webui-userauth.js.new /etc/contrail/contrail-webui-userauth.js")

        if self._args.collector_ip:
            local("sudo sed \"s/config.analytics.server_ip.*/config.analytics.server_ip = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(contrail_internal_vip or self._args.collector_ip))
            local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        if self._args.cassandra_ip_list:
            local("sudo sed \"s/config.cassandra.server_ips.*/config.cassandra.server_ips = %s;/g\" /etc/contrail/config.global.js > config.global.js.new" %(str(self._args.cassandra_ip_list)))
            local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        if self._args.redis_password:
            local("sudo sed \"s/config.redis_password.*/config.redis_password = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(self._args.redis_password))
            local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        with settings(warn_only=True):
            if add_cert_path == True:
                local("sudo sed \"/config.getDomainsFromApiServer/ a \\\n// server_options\\nconfig.server_options = {};\" /etc/contrail/config.global.js > config.global.js.new")
                local("sudo mv config.global.js.new /etc/contrail/config.global.js")
                local("sudo sed \"/config.server_options/ a \\\n// key_file \\nconfig.server_options.key_file = '" + keys_path + "cs-key.pem';\" /etc/contrail/config.global.js > config.global.js.new")
                local("sudo mv config.global.js.new /etc/contrail/config.global.js")
                local("sudo sed \"/config.server_options.key_file/ a \\\n// cert_file \\nconfig.server_options.cert_file = '" + keys_path + "cs-cert.pem';\" /etc/contrail/config.global.js > config.global.js.new")
                local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        if self._args.vcenter_ip:
            orchestrator = 'vcenter'
            local("sudo sed \"s/config.vcenter.server_ip.*/config.vcenter.server_ip = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(self._args.vcenter_ip))
            local("sudo mv config.global.js.new /etc/contrail/config.global.js")
            local("sudo sed \"s/config.orchestration.Manager.*/config.orchestration.Manager = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(orchestrator))
            local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        if self._args.vcenter_port:
            local("sudo sed \"s/config.vcenter.server_port.*/config.vcenter.server_port = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(self._args.vcenter_port))
            local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        if self._args.vcenter_auth:
            local("sudo sed \"s/config.vcenter.authProtocol.*/config.vcenter.authProtocol= '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(self._args.vcenter_auth))
            local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        if self._args.vcenter_datacenter:
            local("sudo sed \"s/config.vcenter.datacenter.*/config.vcenter.datacenter = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(self._args.vcenter_datacenter))
            local("sudo mv config.global.js.new /etc/contrail/config.global.js")
        if self._args.vcenter_dvswitch:
            local("sudo sed \"s/config.vcenter.dvsswitch.*/config.vcenter.dvsswitch = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(self._args.vcenter_dvswitch))
            local("sudo mv config.global.js.new /etc/contrail/config.global.js")

        if self._args.orchestrator == 'vcenter':
           with settings(warn_only=True):
              mt_enable_variable = local('cat /etc/contrail/config.global.js | grep config.multi_tenancy', capture=True);
           if mt_enable_variable:
              local("sudo sed \"s/config.multi_tenancy.enabled.*/config.multi_tenancy.enabled = false;/g\" /etc/contrail/config.global.js > config.global.js.new")
              local("sudo mv config.global.js.new /etc/contrail/config.global.js")
           else:
              local("sudo sed \"/config.vcenter.wsdl/ a \\\n// multi_tenancy\\nconfig.multi_tenancy = {};\\nconfig.multi_tenancy.enabled = false;\" /etc/contrail/config.global.js > config.global.js.new")
              local("sudo mv config.global.js.new /etc/contrail/config.global.js")
           with settings(warn_only=True):
               static_auth = local('cat /etc/contrail/config.global.js | grep config.staticAuth', capture=True)
           if admin_user and admin_password :
              if static_auth:
                 local("sudo sed \"s/config.staticAuth\[0].username.*/config.staticAuth\[0].username = '" + admin_user + "';/g\" /etc/contrail/config.global.js > config.global.js.new")
                 local("sudo mv config.global.js.new /etc/contrail/config.global.js")
                 local("sudo sed \"s/config.staticAuth\[0].password.*/config.staticAuth\[0].password = '" + admin_password + "';/g\" /etc/contrail/config.global.js > config.global.js.new")
                 local("sudo mv config.global.js.new /etc/contrail/config.global.js")
                 local("sudo sed \"s/config.staticAuth\[0].roles.*/config.staticAuth\[0].roles = ['cloudAdmin'];/g\" /etc/contrail/config.global.js > config.global.js.new")
                 local("sudo mv config.global.js.new /etc/contrail/config.global.js")
              else:
                 local("sudo sed \"/config.multi_tenancy.enable/ a \\\n// staticAuth\\nconfig.staticAuth = [];\\nconfig.staticAuth[0] = {};\\nconfig.staticAuth[0].username = '" + admin_user + "';\\nconfig.staticAuth[0].password = '" + admin_password + "';\\nconfig.staticAuth[0].roles = ['cloudAdmin'];\" /etc/contrail/config.global.js > config.global.js.new")
                 local("sudo mv config.global.js.new /etc/contrail/config.global.js")

        if self._args.orchestrator == 'none':
           local("sudo sed \"s/config.orchestration.Manager.*/config.orchestration.Manager = '%s';/g\" /etc/contrail/config.global.js > config.global.js.new" %(self._args.orchestrator))
           local("sudo mv config.global.js.new /etc/contrail/config.global.js")
           with settings(warn_only=True):
              mt_enable_variable = local('cat /etc/contrail/config.global.js | grep config.multi_tenancy', capture=True);
           if mt_enable_variable:
              local("sudo sed \"s/config.multi_tenancy.enabled.*/config.multi_tenancy.enabled = false;/g\" /etc/contrail/config.global.js > config.global.js.new")
              local("sudo mv config.global.js.new /etc/contrail/config.global.js")
           else:
              local("sudo sed \"/config.orchestration.Manager/ a \\\n// multi_tenancy\\nconfig.multi_tenancy = {};\\nconfig.multi_tenancy.enabled = false;\" /etc/contrail/config.global.js > config.global.js.new")
              local("sudo mv config.global.js.new /etc/contrail/config.global.js")

    def restart_webui(self):
        local("sudo service supervisor-webui restart")

    def run_services(self):
        local("sudo webui-server-setup.sh")

def main(args_str = None):
    webui = WebuiSetup(args_str)
    webui.setup()

def fix_webui_config(args_str = None):
    webui = WebuiSetup(args_str)
    webui.fixup_config_files()
    webui.restart_webui()


if __name__ == "__main__":
    main()
