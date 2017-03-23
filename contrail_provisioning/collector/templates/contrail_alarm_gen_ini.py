import string

template = string.Template("""
[program:contrail-alarm-gen]
command=/usr/bin/contrail-alarm-gen --conf_file $__contrail_alarm_gen_conf__
priority=440
autostart=true
killasgroup=true
stopsignal=KILL
stdout_capture_maxbytes=1MB
redirect_stderr=true
stdout_logfile=/var/log/contrail/contrail-alarm-gen-stdout.log
stderr_logfile=/var/log/contrail/contrail-alarm-gen-stderr.log
startsecs=5
exitcodes=0                   ; 'expected' exit codes for process (default 0,2)
user=contrail
""")
