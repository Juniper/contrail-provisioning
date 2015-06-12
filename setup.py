#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#
from setuptools import setup, find_packages

def requirements(filename):
    with open(filename) as f:
        lines = f.read().splitlines()
    return lines

setup(
    name='ContrailProvisioning',
    version='0.1dev',
    packages=find_packages(),
    long_description="Contrail VNC Provisioning API Implementation",
    install_requires=requirements('requirements.txt'),
    entry_points = {
        'console_scripts' : [
            # Setup scripts
            'setup-vnc-keepalived = contrail_provisioning.common.keepalived_setup:main',
            'setup-vnc-openstack = contrail_provisioning.openstack.setup:main',
            'setup-vnc-galera = contrail_provisioning.openstack.ha.galera_setup:main',
            'setup-vnc-database = contrail_provisioning.database.setup:main',
            'setup-vnc-config = contrail_provisioning.config.setup:main',
            'setup-vnc-control = contrail_provisioning.control.setup:main',
            'setup-vnc-collector = contrail_provisioning.collector.setup:main',
            'setup-vnc-webui = contrail_provisioning.webui.setup:main',
            'setup-vnc-compute = contrail_provisioning.compute.setup:main',
            'setup-vnc-storage = contrail_provisioning.storage.setup:main',
            'setup-vnc-interfaces = contrail_provisioning.common.interface_setup:main',
            'setup-vnc-static-routes = contrail_provisioning.common.staticroute_setup:main',
            'setup-vnc-livemigration = contrail_provisioning.storage.livemigration_setup:main',
            'setup-vnc-storage-webui = contrail_provisioning.storage.webui_setup:main',
            'setup-vcenter-plugin = contrail_provisioning.vcenter_plugin.setup:main',
            'setup-vnc-tor-agent = contrail_provisioning.compute.toragent.setup:main',
            'add-mysql-perm = contrail_provisioning.openstack.ha.galera_setup:add_mysql_perm',
            'add-galera-config = contrail_provisioning.openstack.ha.galera_setup:add_galera_cluster_config',
            'update-zoo-servers = contrail_provisioning.database.setup:update_zookeeper_servers',
            'restart-zoo-server = contrail_provisioning.database.setup:restart_zookeeper_server',
            'update-cfgm-config = contrail_provisioning.config.setup:fix_cfgm_config_files',
            'update-collector-config = contrail_provisioning.collector.setup:fix_collector_config',
            'update-webui-config = contrail_provisioning.webui.setup:fix_webui_config',
            # Reset scripts
            'reset-vnc-database = contrail_provisioning.database.reset:main',
            # Upgrade scripts
            'upgrade-vnc-openstack = contrail_provisioning.openstack.upgrade:main',
            'upgrade-vnc-database = contrail_provisioning.database.upgrade:main',
            'upgrade-vnc-config = contrail_provisioning.config.upgrade:main',
            'upgrade-vnc-control = contrail_provisioning.control.upgrade:main',
            'upgrade-vnc-collector = contrail_provisioning.collector.upgrade:main',
            'upgrade-vnc-webui = contrail_provisioning.webui.upgrade:main',
            'upgrade-vnc-compute = contrail_provisioning.compute.upgrade:main',
            # Helper scripts
            'setup-quantum-in-keystone = contrail_provisioning.config.quantum_in_keystone_setup:main',
            'storage-fs-setup = contrail_provisioning.storage.storagefs.setup:main',
            'compute-live-migration-setup = contrail_provisioning.storage.compute.livemigration:main',
            'livemnfs-setup = contrail_provisioning.storage.storagefs.livemnfs_setup:main',
            'storage-webui-setup = contrail_provisioning.storage.webui.setup:main',
        ],
    },
    scripts = [
               # Common executables
               'contrail_provisioning/common/scripts/setup-pki.sh',
               'contrail_provisioning/common/scripts/contrail-rmq-monitor.sh',
               'contrail_provisioning/common/scripts/contrail-ha-check.sh',
               # Config executables
               'contrail_provisioning/config/scripts/config-server-setup.sh',
               'contrail_provisioning/config/scripts/config-server-cleanup.sh',
               'contrail_provisioning/config/scripts/quantum-server-setup.sh',
               # Collector executables
               'contrail_provisioning/collector/scripts/collector-server-setup.sh',
               'contrail_provisioning/collector/scripts/collector-server-cleanup.sh',
               # Vcenter Plugin executables
               'contrail_provisioning/vcenter_plugin/scripts/vcenter-plugin-setup.sh',
               # Control executables
               'contrail_provisioning/control/scripts/control-server-setup.sh',
               'contrail_provisioning/control/scripts/control-server-cleanup.sh',
               # Compute executables
               'contrail_provisioning/compute/scripts/compute-server-setup.sh',
               'contrail_provisioning/compute/scripts/compute-server-cleanup.sh',
               # Webui executables
               'contrail_provisioning/webui/scripts/webui-server-setup.sh',
               'contrail_provisioning/webui/scripts/webui-server-cleanup.sh',
               # Database executables
               'contrail_provisioning/database/scripts/database-server-setup.sh',
               'contrail_provisioning/database/scripts/database-server-cleanup.sh',
               # Openstack executables
               'contrail_provisioning/openstack/scripts/cinder-server-setup.sh',
               'contrail_provisioning/openstack/scripts/keystone-server-setup.sh',
               'contrail_provisioning/openstack/scripts/glance-server-setup.sh',
               'contrail_provisioning/openstack/scripts/nova-server-setup.sh',
               'contrail_provisioning/openstack/scripts/heat-server-setup.sh',
               'contrail_provisioning/openstack/scripts/setup-service-token.sh',
               'contrail_provisioning/openstack/scripts/contrail-bootstrap-galera.sh',
               'contrail_provisioning/openstack/scripts/contrail-cmon-monitor.sh',
               'contrail_provisioning/openstack/scripts/contrail-token-clean.sh',
               'contrail_provisioning/openstack/scripts/contrail-keystone-setup.sh',
               'contrail_provisioning/openstack/scripts/chk_ctrldata.sh',
               # Openstack HA executables
               'contrail_provisioning/openstack/ha/scripts/contrail-ha-keystone-setup.sh',
               'contrail_provisioning/openstack/scripts/contrail-galera-check.sh',
               # Config file rewrite executables
               'contrail_provisioning/compute/scripts/vrouter-agent.conf.sh',
               # Tools 
               'tools/openstack-db',
               'tools/openstack-config',
              ]

)
