import string

template = string.Template("""
test:test
test2:test2
test3:test3
dhcp:dhcp
visual:visual
sensor:sensor

# compliance testsuite users
mapclient:mapclient
helper:mapclient

# This is a read-only MAPC
reader:reader
""")
