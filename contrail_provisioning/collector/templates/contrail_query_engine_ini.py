import string

template = string.Template("""
[program:contrail-query-engine]
command=/usr/bin/contrail-query-engine --conf_file $__contrail_query_engine_conf__
priority=430
autostart=true
killasgroup=true
stopsignal=KILL
stdout_capture_maxbytes=1MB
redirect_stderr=true
stdout_logfile=/var/log/contrail/contrail-query-engine-stdout.log
stderr_logfile=/dev/null
startsecs=5
exitcodes=0                   ; 'expected' exit codes for process (default 0,2)
user=contrail
""")
