import string

template = string.Template("""
[DISCOVERY]
server=$__contrail_discovery_ip__
port=$__contrail_discovery_port__

[COLLECTOR]
#server_list=ip1:port1 ip2:port2
""")
