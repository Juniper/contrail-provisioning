import string

template = string.Template("""
[DEFAULT]
hostip=$__hostip__
minimum_diskGB=$__minimum_diskGB__

[COLLECTOR]
server_list=$__contrail_collectors__
""")

