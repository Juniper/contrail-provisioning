import string

template = string.Template("""
description "redis server memory database"
author contrail

# run when the local FS becomes available
start on local-filesystems
stop on shutdown

# The default redis conf has `daemonize = yes` and will naiively fork itself.
expect fork

# Respawn unless redis dies 10 times in 5 seconds
respawn
respawn limit 10 5

# run redis as the correct user
setuid redis
setgid redis

# run redis with the correct config file for this instance
exec /usr/bin/redis-server /etc/redis/redis.conf
""")
