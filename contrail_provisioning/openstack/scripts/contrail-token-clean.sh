#!/bin/bash

# Purpose of the script is to clean up the tokens that are being generated to 
# validated the request.
# Author - Sanju Abraham

LOGFILE=/var/log/contrail/ha/token-cleanup.log
mysql_user=keystone
mysql_password=keystone
mysql_host=localhost
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

log_info_msg "keystone-cleaner::Starting Keystone 'token' table cleanup"

log_info_msg "keystone-cleaner::Starting token cleanup"
mysql -u${mysql_user} -p${mysql_password} -h${mysql_host} -e 'USE keystone ; DELETE FROM token WHERE NOT DATE_SUB(CURDATE(),INTERVAL 1 DAY) <= expires;'
valid_token=$($mysql -u${mysql_user} -p${mysql_password} -h${mysql_host} -e 'USE keystone ; SELECT * FROM token;' | wc -l)
log_info_msg "keystone-cleaner::Finishing token cleanup, there is still $valid_token valid tokens..."

find /var/log/contrail/ha/ -size +10240k -exec rm -f {} \;
find /var/log/cmon.log -size +10240k -exec rm -f {} \;

mysql -u${cmon_user_pass} -p${cmon_user_pass} -h${mysql_host} -e "use cmon; ${cmon_stats_purge}"
log_info_msg "Purged cmon stats history"
exit 0
