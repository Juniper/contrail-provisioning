import string

template = string.Template("""
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#
# Dns configuration options
#

[DEFAULTS]
dns-config-file=dns_config.xml
hostip=$__contrail_host_ip__ # Resolved IP of `hostname`
http-server-port=8092

[COLLECTOR]
port=8086
server= # Provided by discovery server

[DISCOVERY]
port=5998
server=$__contrail_discovery_ip__ # discovery-server IP address

[LOG]
category=
disable=0
file=/var/log/contrail/dns.log
level=SYS_NOTICE
local=0

[IFMAP]
certs-store=$__contrail_cert_ops__
password=$__contrail_ifmap_paswd__
user=$__contrail_ifmap_usr__

""")
