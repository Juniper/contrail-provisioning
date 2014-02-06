import string

template = string.Template("""#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#
# Vrouter configuration options
#

[DEFAULTS]
eth-port=$__eth_port__
dns-server= # Provided by discovery server
hostname= # Retrieved as `hostname`
mgmt-ip=$__mgmt_ip__
http-server-port=8085
tunnel-type=MPLSoGRE
xmpp-server=$__xmpp_servers__

[COLLECTOR]
port=8086
server= # Provided by discovery server

[DISCOVERY]
port=5998
server=$__discovery_server__
control-instances=$__control_instances__

[GATEWAY]
interface=
ip-prefix=
virtual-network=

[HYPERVISOR]
mode=kvm
xen-ll-ip-prefix=
xen-ll-port=

[LOG]
category=
file=<stdout>
level=SYS_DEBUG
local=0

[KERNEL]
create-vhost=0
no-packet-services=0
no-services=0
no-sync=0

[VHOST]
name=vhost0
ip-prefix=$__vhost_ip_prefix__
gateway=$__vhost_gateway__

DISCOVERY=$__contrail_discovery_ip__
""")
