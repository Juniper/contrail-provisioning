import string

template = string.Template("""#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#
# Control-node configuration options
#

[DEFAULTS]
hostip=$__contrail_host_ip__ # Resolved IP of `hostname`
hostname=$__contrail_hostname__ # Retrieved as `hostname`
http-server-port=8083
test-mode=0
xmpp-server-port=5269

[BGP]
config-file=bgp_config.xml
port=179

[COLLECTOR]
port=8086
server= # Provided by discovery server

[DISCOVERY]
port=5998
server=$__contrail_discovery_ip__ # discovery-server IP address

[IFMAP]
certs-store=$__contrail_cert_ops__
password=$__contrail_ifmap_paswd__
server-url=
user=$__contrail_ifmap_usr__

[LOG]
category=
disable=0
file=/var/log/contrail/control-node.log
level=SYS_NOTICE
local=0

""")
