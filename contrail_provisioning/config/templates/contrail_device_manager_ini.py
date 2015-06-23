import string

template = string.Template("""
[program:contrail-device-manager]
command=/usr/bin/contrail-device-manager --conf_file $__contrail_config_file_args__
priority=450
autostart=true
autorestart=true
killasgroup=true
stopsignal=KILL
redirect_stderr=true
stdout_logfile=/var/log/contrail/contrail-device-manager-stdout.log
stderr_logfile=/dev/null
exitcodes=0                   ; 'expected' exit codes for process (default 0,2)
user=contrail
""")
