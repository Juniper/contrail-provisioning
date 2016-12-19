import string

template = string.Template("""
Defaults:root !requiretty

Defaults:contrail !requiretty

Cmnd_Alias CONFIGRESTART = $__service_bin_path__ supervisor-config restart

contrail ALL = (root) NOPASSWD:CONFIGRESTART 
""")
