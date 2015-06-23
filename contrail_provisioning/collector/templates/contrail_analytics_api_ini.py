import string

template = string.Template("""
[program:contrail-analytics-api]
command=/usr/bin/contrail-analytics-api --conf_file $__contrail_analytics_api_conf__
priority=440
autostart=true
killasgroup=true
stopsignal=KILL
stdout_capture_maxbytes=1MB
redirect_stderr=true
stdout_logfile=/var/log/contrail/contrail-analytics-api-stdout.log
stderr_logfile=/var/log/contrail/contrail-analytics-api-stderr.log
startsecs=5
exitcodes=0                   ; 'expected' exit codes for process (default 0,2)
user=contrail
""")
