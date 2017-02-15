import string

template = string.Template("""
[program:ifmap]
command=/usr/bin/ifmap-server
priority=420
autostart=true
autorestart=true
killasgroup=true
stopasgroup=true
stopsignal=TERM
redirect_stderr=true
stdout_logfile=/var/log/contrail/ifmap-stdout.log
stderr_logfile=/dev/null
user=contrail
""")
