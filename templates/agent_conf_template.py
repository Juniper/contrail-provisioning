import string

template = string.Template("""
<?xml version="1.0" encoding="utf-8"?>
<config>
    <agent>
        <!-- Physical ports connecting to IP Fabric -->
        <vhost>
            <name>vhost0</name>
            <ip-address>$__contrail_box_ip__/$__contrail_box_prefix__</ip-address>
            <gateway>$__contrail_gateway__</gateway>
        </vhost>
        <eth-port>
            <name>$__contrail_eth_if__</name>
        </eth-port>
	<metadata-proxy>
            <shared-secret></shared-secret>
        </metadata-proxy></agent>
        $__contrail_discovery_server__
    </agent>
</config>
""")
