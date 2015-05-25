import string

template = string.Template("""

listen $__tor_proxy_name__
    mode tcp
    bind $__tor_ovs_ports__
$__server_lines__
    balance leastconn

""")
