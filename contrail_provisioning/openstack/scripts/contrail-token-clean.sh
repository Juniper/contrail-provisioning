#!/bin/bash

# Purpose of the script is to clean up the tokens that are being generated to 
# validated the request.
# Author - Sanju Abraham

source /etc/contrail/ha/cmon_param

LOGFILE=/var/log/contrail/ha/token-cleanup.log
MYIPS=$(ip addr show | sed -ne '/127.0.0.1/!{s/^[ \t]*inet[ \t]*\([0-9.]\+\)\/.*$/\1/p}')
viponme=0
mysql_user=keystone
mysql_password=keystone
mysql_host=$VIP
mysql_port=33306
mysql=$(which mysql)
cmon_user_pass=cmon
cmon_stats_purge="call sp_cmon_purge_history;"

timestamp() {
    date +"%T"
}
    
log_error_msg() {
    msg=$1
    echo "$(timestamp): ERROR: $msg" >> $LOGFILE
}

log_warn_msg() {
    msg=$1
    echo "$(timestamp): WARNING: $msg" >> $LOGFILE
}

log_info_msg() {
    msg=$1
    echo "$(timestamp): INFO: $msg" >> $LOGFILE
}

log_info_msg "keystone-cleaner::Starting token cleanup"

    mysql -u${mysql_user} -p${mysql_password} -h${mysql_host} -P${mysql_port} -e "USE keystone ; DELETE FROM token where expires <= convert_tz(now(),@@session.time_zone,'+01:00');"
    valid_token=$($mysql -u${mysql_user} -p${mysql_password} -h${mysql_host} -P${mysql_port} -e "USE keystone ; SELECT count(*) FROM token;")
    valid_token=$(echo $valid_token | awk '{print $2}')

log_info_msg "keystone-cleaner::Finishing token cleanup, there are $valid_token valid tokens..."

for myip in $MYIPS
 do
  if [ $myip == $VIP ]; then
     viponme=1
     break
  fi
 done

if [ $viponme -eq 1 ]; then
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table cmon_log;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table memory_usage_history;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table cpu_stats_history;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table ram_stats_history;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table disk_stats_history;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table diskdata_history;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table mysql_global_statistics_history;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table mysql_statistics_history;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table mysql_advisor_history;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table expression_result_history;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table mysql_performance_results;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table net_stats_history;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table cmon_job;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table cmon_job_message;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table cluster_log;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table backup_log;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table restore_log;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table backup;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table restore;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table alarm_log;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table mysql_query_histogram;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table mysql_slow_queries;"
    log_info_msg "Purged cmon stats history"
fi

find /var/log/contrail/ha/ -size +10240k -exec rm -f {} \;
find /var/log/cmon.log -size +10240k -exec rm -f {} \;

exit 0
