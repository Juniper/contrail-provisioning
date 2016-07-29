import string

template = string.Template("""
#!/bin/bash

vconfig set_egress_map $__interface__ 0 0
vconfig set_egress_map $__interface__ 1 1
vconfig set_egress_map $__interface__ 2 2
vconfig set_egress_map $__interface__ 3 3
vconfig set_egress_map $__interface__ 4 4
vconfig set_egress_map $__interface__ 5 5
vconfig set_egress_map $__interface__ 6 6
vconfig set_egress_map $__interface__ 7 7

""")
