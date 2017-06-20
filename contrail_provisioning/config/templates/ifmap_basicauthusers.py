import string

template = string.Template("""
api-server:$__ifmap_password__
schema-transformer:$__ifmap_password__
svc-monitor:$__ifmap_password__
visual:$__ifmap_password__

$__contrail_control_node_users__
$__contrail_control_node_dns_users__

""")
