import string

template = string.Template("""
[DEFAULT]
hostip=$__contrail_config_database_ip__
minimum_diskGB=$__contrail_config_minimum_disk__

[DISCOVERY]
server=$__contrail_discovery_ip__
port=$__contrail_discovery_port__

[COLLECTOR]
#server_list=ip1:port1 ip2:port2
""")
