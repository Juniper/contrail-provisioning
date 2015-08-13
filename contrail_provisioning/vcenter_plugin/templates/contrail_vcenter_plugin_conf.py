import string

template = string.Template("""#
# Copyright (c) 2014 Juniper Networks, Inc. All rights reserved.
#
# Vcenter Plugin  configuration options
#

[DEFAULT]
# Everything in this section is optional

# Vcenter plugin URL
vcenter.url=$__contrail_vcenter_url__

#Vcenter credentials
vcenter.username=$__contrail_vcenter_username__
vcenter.password=$__contrail_vcenter_password__

vcenter.datacenter=$__contrail_vcenter_datacenter__
vcenter.dvswitch=$__contrail_vcenter_dvswitch__
vcenter.ipfabricpg=$__contrail_vcenter_ipfabricpg__

mode=$__contrail_vcenter_compute__

# IP address and port to be used to connect to api server.
api.hostname=$__contrail_api_hostname__
api.port=$__contrail_api_port__

zookeeper.serverlist=$__contrail_zookeeper_serverlist__

""")
