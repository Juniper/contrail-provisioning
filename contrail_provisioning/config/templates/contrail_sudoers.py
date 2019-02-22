import string

template = string.Template("""
Defaults:contrail !requiretty

Cmnd_Alias CONFIGRESTART = /usr/sbin/service supervisor-config restart
Cmnd_Alias IFMAPRESTART = /usr/sbin/service ifmap restart

contrail ALL = (root) NOPASSWD:CONFIGRESTART,IFMAPRESTART
""")
