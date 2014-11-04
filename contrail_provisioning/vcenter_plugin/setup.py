import os
import sys
import argparse
import ConfigParser

from fabric.api import local

from contrail_provisioning.common.base import ContrailSetup
from contrail_provisioning.vcenter_plugin.templates import contrail_vcenter_plugin_conf


class VcenterPluginSetup(ContrailSetup):
    def __init__(self, args_str = None):
        super(VcenterPluginSetup, self).__init__()
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])

        self.global_defaults = {
            'vcenter_url': 'https://127.0.0.1/sdk',
            'api_hostname': '127.0.0.1',
            'api_port': 8082,
        }

        self.parse_args(args_str)

    def parse_args(self, args_str):
        '''
        Eg. setup-vcenter-plugin --vcenter_url https://10.84.24.111/sdk 
            --api_port 8082 --api_hostname 10.1.5.11 
        '''

        parser = self._parse_args(args_str)
        parser.add_argument("--vcenter_url", help = "URL of vcenter node",
                            nargs='+', type=str)
        parser.add_argument("--vcenter_username", help = "vcenter login username")
        parser.add_argument("--vcenter_password", help = "vcenter login password")
        parser.add_argument("--api_hostname", help = "IP Address of the config node")
        parser.add_argument("--api_port", help = "Listen port for api server", type = int)
        self._args = parser.parse_args(self.remaining_argv)

    def fixup_config_files(self):
        self.fixup_contrail_vcenter_plugin()

    def fixup_contrail_vcenter_plugin(self):
        template_vals = {'__contrail_vcenter_url__' : self._args.vcenter_url,
                         '__contrail_vcenter_username__' : self._args.vcenter_username,
                         '__contrail_vcenter_password__' : self._args.vcenter_password,
                         '__contrail_api_hostname__' : self._args.api_hostname,
                         '__contrail_api_port__' : self._args.api_port
                         }
        self._template_substitute_write(contrail_vcenter_plugin_conf.template,
                                   template_vals, self._temp_dir_name + '/contrail-vcenter-plugin.conf')
        local("sudo mv %s/contrail-vcenter-plugin.conf /etc/contrail/contrail-vcenter-plugin.conf" %(self._temp_dir_name))

    def run_services(self):
        local("sudo vcenter-plugin-setup.sh")

    def setup(self):
        self.fixup_contrail_vcenter_plugin()        
        self.run_services()        

#end class VcenterPluginSetup
def main(args_str = None):
    vcenterplugin = VcenterPluginSetup(args_str)
    vcenterplugin.setup()

if __name__ == "__main__":
    main()
