import string

template = string.Template("""
api-server:api-server
schema-transformer:schema-transformer
svc-monitor:svc-monitor
control-user:control-user-passwd
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
