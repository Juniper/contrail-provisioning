#!/usr/bin/env bash

CONFIG_FILE="/etc/contrail/contrail-vrouter-agent.conf"
OLD_AGENT_CONFIG_FILE="/etc/contrail/agent_param"
OLD_VROUTER_NODEMGR_CONFIG_FILE="/etc/contrail/vrouter_nodemgr_param"
OLD_AGENT_XML_CONFIG_FILE="/etc/contrail/agent.conf"
SIGNATURE="contrail-vrouter-agent.conf configuration options, generated from $OLD_AGENT_CONFIG_FILE and $OLD_VROUTER_NODEMGR_CONFIG_FILE"

# Remove old style command line arguments from .ini file.
#perl -ni -e 's/command=.*/command=\/usr\/bin\/control-node/g; print $_;' /etc/contrail/supervisord_control_files/contrail-control.ini

if [ ! -e $OLD_CONFIG_FILE ]; then
    exit
fi

# Ignore if the converted file is already generated once before
if [ -e $CONFIG_FILE ]; then
    grep --quiet "$SIGNATURE" $CONFIG_FILE > /dev/null

    # Exit if configuraiton already converted!
    if [ $? == 0 ]; then
        exit
    fi
fi

source $OLD_AGENT_CONFIG_FILE 2>/dev/null || true
source $OLD_VROUTER_NODEMGR_CONFIG_FILE 2>/dev/null || true

IPADDRESS=$(xmllint --xpath //config/agent/vhost/ip-address $OLD_AGENT_XML_CONFIG_FILE | cut -d'>' -f 2 | cut -d'<' -f 1)
GATEWAY=$(xmllint --xpath //config/agent/vhost/gateway $OLD_AGENT_XML_CONFIG_FILE | cut -d'>' -f 2 | cut -d'<' -f 1)
CONTROL_NETWORK_IP=$(xmllint --xpath xmllint --xpath //config/agent/control/ip-address $OLD_AGENT_XML_CONFIG_FILE | cut -d'>' -f 2 | cut -d'<' -f 1)
MAX_CONTROL_NODES=$(xmllint --xpath //config/agent/discovery-server/control-instances $OLD_AGENT_XML_CONFIG_FILE | cut -d'>' -f 2 | cut -d'<' -f 1)

(
cat << EOF
#
# Vnswad configuration options
#

[CONTROL-NODE]
# IP address to be used to connect to control-node. Maximum of 2 IP addresses
# (separated by a space) can be provided. If no IP is configured then the
# value provided by discovery service will be used. (optional)
# server=10.0.0.1 10.0.0.2

[DEFAULT]
# Everything in this section is optional

# IP address and port to be used to connect to collector. If these are not
# configured, value provided by discovery service will be used. Multiple
# IP:port strings separated by space can be provided
# collectors=127.0.0.1:8086

# Enable/disable debug logging. Possible values are 0 (disable) and 1 (enable)
# debug=0

# Aging time for flow-records in seconds
# flow_cache_timeout=0

# Hostname of compute-node. If this is not configured value from ostname# will be taken
# hostname=

# Http server port for inspecting vnswad state (useful for debugging)
# http_server_port=8085

# Category for logging. Default value is '*'
# log_category=

# Local log file name
# log_file=/var/log/contrail/vrouter.log

# Log severity levels. Possible values are SYS_EMERG, SYS_ALERT, SYS_CRIT,
# SYS_ERR, SYS_WARN, SYS_NOTICE, SYS_INFO and SYS_DEBUG. Default is SYS_DEBUG
# log_level=SYS_DEBUG

# Enable/Disable local file logging. Possible values are 0 (disable) and 1 (enable)
# log_local=0

# Encapsulation type for tunnel. Possible values are MPLSoGRE, MPLSoUDP, VXLAN
# tunnel_type=

# Enable/Disable headless mode for agent. In headless mode agent retains last
# known good configuration from control node when all control nodes are lost.
# Possible values are true(enable) and false(disable)
# headless_mode=

[DISCOVERY]
#If DEFAULT.collectors and/or CONTROL-NODE and/or DNS is not specified this
#section is mandatory. Else this section is optional

# IP address of discovery server
server=$DISCOVERY

# Number of control-nodes info to be provided by Discovery service. Possible
# values are 1 and 2
max_control_nodes=$MAX_CONTROL_NODES

[DNS]
# IP address to be used to connect to dns-node. Maximum of 2 IP addresses
# (separated by a space) can be provided. If no IP is configured then the
# value provided by discovery service will be used. (Optional)
# server=10.0.0.1 10.0.0.2 

[HYPERVISOR]
# Everything in this section is optional

# Hypervisor type. Possible values are kvm, xen and vmware
type=kvm

# Link-local IP address and prefix in ip/prefix_len format (for xen)
# xen_ll_ip=

# Link-local interface name when hypervisor type is Xen
# xen_ll_interface=

# Physical interface name when hypervisor type is vmware
# vmware_physical_interface=

[FLOWS]
# Everything in this section is optional

# Maximum flows allowed per VM (given as % of maximum system flows)
# max_vm_flows=

# Maximum number of link-local flows allowed across all VMs
# max_system_linklocal_flows=4096

# Maximum number of link-local flows allowed per VM
# max_vm_linklocal_flows=1024

[METADATA]
# Shared secret for metadata proxy service (Optional)
# metadata_proxy_secret=contrail


[NETWORKS]
# control-channel IP address used by WEB-UI to connect to vnswad to fetch
# required information (Optional)
control_network_ip=$CONTROL_NETWORK_IP

[VIRTUAL-HOST-INTERFACE]
# Everything in this section is mandatory

# name of virtual host interface
name=$DEVICE

# IP address and prefix in ip/prefix_len format
ip=$IPADDRESS

# Gateway IP address for virtual host
gateway=$GATEWAY

# Physical interface name to which virtual host interface maps to
physical_interface=$dev

# We can have multiple gateway sections with different indices in the
# following format
[GATEWAY-0]
# Name of the routing_instance for which the gateway is being configured
# routing_instance=default-domain:admin:public:public

# Gateway interface name
# interface=vgw

# Virtual network ip blocks for which gateway service is required. Each IP
# block is represented as ip/prefix. Multiple IP blocks are represented by
# separating each with a space
# ip_blocks=1.1.1.1/24

[GATEWAY-1]
# Name of the routing_instance for which the gateway is being configured
# routing_instance=default-domain:admin:public1:public1

# Gateway interface name
# interface=vgw1

# Virtual network ip blocks for which gateway service is required. Each IP
# block is represented as ip/prefix. Multiple IP blocks are represented by
# separating each with a space
# ip_blocks=2.2.1.0/24 2.2.2.0/24

# Routes to be exported in routing_instance. Each route is represented as
# ip/prefix. Multiple routes are represented by separating each with a space
# routes=10.10.10.1/24 11.11.11.1/24

[SERVICE-INSTANCE]
# Path to the script which handles the netns commands
#netns_command=/usr/local/bin/opencontrail-vrouter-netns

# Number of workers that will be used to start netns commands
#netns_workers=1

# Timeout for each netns command, when the timeout is reached, the netns
# command is killed.
#netns_timeout=30
EOF
) > $CONFIG_FILE
