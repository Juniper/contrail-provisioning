import string

template = string.Template("""
test:test
test2:test2
test3:test3
api-server:api-server
schema-transformer:schema-transformer
svc-monitor:svc-monitor
control-user:control-user-passwd
control-node-1:control-node-1
control-node-2:control-node-2
control-node-3:control-node-3
control-node-4:control-node-4
control-node-5:control-node-5
control-node-6:control-node-6
control-node-7:control-node-7
control-node-8:control-node-8
control-node-9:control-node-9
control-node-10:control-node-10
dhcp:dhcp
visual:visual
sensor:sensor

# compliance testsuite users
mapclient:mapclient
helper:mapclient

# This is a read-only MAPC
reader:reader
$__contrail_control_node_users__
$__contrail_control_node_dns_users__

""")
