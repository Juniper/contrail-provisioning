#!/bin/bash

# Purpose of the script is to clean up the tokens that are being generated to 
# validated the request.
# Author - Sanju Abraham

source /etc/contrail/ha/cmon_param

LOGFILE=/var/log/contrail/ha/token-cleanup.log
mysql_user=$OS_KS_USER
mysql_password=$OS_KS_PASS
mysql_host="localhost"
mysql_port=3306
mysql=$(which mysql)
cmon_user_pass=$CMON_PASS
cmon_stats_purge="call sp_cmon_purge_history;"
token_removed="/tmp/ks_token_remove"
token_clean="keystone-manage -v -d token_flush"
MYIPS=$(ip a s|sed -ne '/127.0.0.1/!{s/^[ \t]*inet[ \t]*\([0-9.]\+\)\/.*$/\1/p}')

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

if [ ! -f "$token_removed" ] ; then
         touch "$token_removed"
fi

get_my_ip() {
flag=false
for ip in $MYIPS
 do
  for (( i=0; i<${DIPS_SIZE}; i++ ))
   do
     if [ $ip == ${DIPS[i]} ]; then
        mysql_host=$ip
        flag=true
        break
     fi
   done
   if [[ "$flag" == true ]]; then
     break
   fi
done
}

cmon_data_purge() {
    log_info_msg "Starting to purged cmon stats history"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table cmon_log;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table memory_usage_history;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table cpu_stats_history;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table ram_stats_history;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table disk_stats_history;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table diskdata_history;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table mysql_global_statistics_history;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table mysql_statistics_history;"
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; truncate table mysql_statistics_tm;"
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
    mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -P${mysql_port} -e "use cmon; ${cmon_stats_purge}"
    log_info_msg "Purged cmon stats history"
}

keystone_token_cleanup() {
    delay=$(cat /etc/contrail/galeraid)
    delay=$(($delay*120))
    sleep $delay

    log_info_msg "keystone-cleaner::Starting token cleanup"

    `$token_clean 2> >( cat <() > $token_removed)`
    tokens_purged=$(cat $token_removed | grep "Total expired tokens" | awk '{print $11}')
    log_info_msg "Number of expired tokens purged in this job: $tokens_purged"

    valid_token=$($mysql -u${mysql_user} -p${mysql_password} -h${mysql_host} -P${mysql_port} -e "USE keystone ; SELECT count(*) FROM token;")
    valid_token=$(echo $valid_token | awk '{print $2}')

    log_info_msg "keystone-cleaner::Finishing token cleanup, there are $valid_token valid tokens..."
}

log_purge() {
find /var/log/contrail/ha/ -size +10240k -exec rm -f {} \;
find /var/log/cmon.log -size +10240k -exec rm -f {} \;
}

main() {
 cmon_data_purge
 keystone_token_cleanup
 log_purge
 exit 0
}

main
