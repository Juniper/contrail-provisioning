#!/usr/bin/python
#
# Copyright (c) 2015 Juniper Networks, Inc. All rights reserved.
#
"""Upgrade's Contrail Webui components."""

from setup import WebuiSetup
from contrail_provisioning.common.upgrade import ContrailUpgrade

from fabric.api import local


class WebuiUpgrade(ContrailUpgrade, WebuiSetup):
    def __init__(self, args_str = None):
        ContrailUpgrade.__init__(self)
        WebuiSetup.__init__(self)

        self.update_upgrade_data()

    def update_upgrade_data(self):
        self.upgrade_data['upgrade'] = self._args.packages

        self.upgrade_data['restore'].append(
                                '/etc/contrail/config.global.js')
        self.upgrade_data['restore'].append(
                                '/etc/contrail/contrail-webui-userauth.js')

    def restart(self):
        local('service supervisor-webui restart')

    def upgrade(self):
        self._upgrade()
        self.upgrade_python_pkgs()
        #Disable redis server persistence since that is not used by and webui in r2.20
        #bug-1463749
        if self._args.to_rel >= 2.2:
            self.fix_redis()
        self.restart()


def main():
    webui = WebuiUpgrade()
    webui.upgrade()

if __name__ == "__main__":
    main()
