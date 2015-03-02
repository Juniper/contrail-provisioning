import string

template = string.Template("""
[DEFAULT]
hostip=$__hostip__
minimum_diskGB=$__minimum_diskGB__

[DISCOVERY]
server=$__contrail_discovery_ip__
""")

