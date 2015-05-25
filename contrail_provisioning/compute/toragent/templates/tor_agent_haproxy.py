import string

template = string.Template("""

listen $__tor_proxy_name__ :$__tor_ovs_port__
    mode tcp
    server $__tor_ip__ $__tor_ip__:$__tor_ovs_port__
    server $__standby_ip__ $__standby_ip__:$__standby_port__

""")
