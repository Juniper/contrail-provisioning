#!/bin/bash
#
# Script to be trrigerd by rc.local to bootstrap galera cluster on every reboot of all galera nodes in the cluster.

source /etc/contrail/ha/cmon_param

readonly PROGNAME=$(basename "$0")
readonly LOCKFILE_DIR=/tmp/galera-chk
readonly LOCK_FD=200

LOGFILE=/var/log/galera-bootstrap.log
RETRIES=3
MYSQL_USERNAME="cmon"
MYSQL_PASSWORD="cmon"
MYSQL_BIN="/usr/bin/mysql"
MYIDFILE="/etc/contrail/galeraid"
SST_FILE="/var/lib/mysql/rsync_sst_complete"
GRA_FILE="/var/lib/mysql/grastate.dat"
MYSQL_STOP="service mysql stop"
RETRY_TIMEOUT=60
RETRY_INTERVAL=5
MYSQL_WSREP_STATE="show status like 'wsrep_local_state';"
MYSQL_CLUSTER_STATE="show status like 'wsrep_cluster_status';"
galera_state_file="/tmp/galera-chk/wsrep.state"
cluster_state_file="/tmp/galera-chk/cluster.state"
SYNCED=4
STATUS="Primary"
CMON_MON_STOP="service contrail-hamon stop"
CMON_MON_START="service contrail-hamon start"
CMON_STOP="service cmon stop"
STDERR_FILE="/tmp/mysqlerr.txt"

if [ ! -f "$LOCKFILE_DIR" ] ; then
        mkdir -p $LOCKFILE_DIR
fi

if [ ! -f "$galera_state_file" ] ; then
         touch "$galera_state_file"
fi

if [ ! -f "$cluster_state_file" ] ; then
         touch "$cluster_state_file"
fi

lock() {
    local prefix=$1
    local fd=${2:-$LOCK_FD}
    local lock_file=$LOCKFILE_DIR/$prefix.lock

    # create lock file
    eval "exec $fd>$lock_file"

    # acquier the lock
    flock -n $fd \
        && return 0 \
        || return 1
}

eexit() {
    local error_str="$@"

    echo $error_str
    exit 1
}

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
    
verify_mysql() {
    retry_count=$(($RETRY_TIMEOUT / RETRY_INTERVAL))
    for i in $(eval echo {1..$retry_count}); do
        sleep $RETRY_INTERVAL
        pid=$(pidof mysqld)
        if [ "$pid" == '' ]; then
            echo "$pid"
            return
        fi
        log_info_msg "Checking for consistent mysql PID: $pid."
    done
    echo "$pid"
}

galera_check()
{
 for (( i=0; i<${DIPS_SIZE}; i++ ))
     do
       $MYSQL_BIN -u $MYSQL_USERNAME -p${MYSQL_PASSWORD} -h ${DIPS[i]} -e "$MYSQL_WSREP_STATE" 2> >( cat <() > $STDERR_FILE )
       error=`cat ${STDERR_FILE} | awk '{print $1}'`
       if [[ $error == "ERROR" ]]; then
         checkNKill
       fi
       $MYSQL_BIN -u $MYSQL_USERNAME -p${MYSQL_PASSWORD} -h ${DIPS[i]} -e "$MYSQL_WSREP_STATE" | awk '{print $2}' | sed '1d' > "$galera_state_file" 2> >( cat <() > $STDERR_FILE )
       $MYSQL_BIN -u $MYSQL_USERNAME -p${MYSQL_PASSWORD} -h ${DIPS[i]} -e "$MYSQL_CLUSTER_STATE" | awk '{print $2}' | sed '1d' > "$cluster_state_file" 2> >( cat <() > $STDERR_FILE )
    done
 (exec rm -rf $STDERR_FILE)&
}

verify_wsrepstate()
{
 wsrepstate=`cat $galera_state_file`
 if [[ $wsrepstate == $SYNCED ]]; then
   echo "y"
   return 1
 else
   echo "n"
   return 0
 fi
}

verify_clusterstatus()
{
 clusterstatus=`cat $cluster_state_file`
 if [[ $clusterstatus == $STATUS ]]; then
   echo "y"
   return 1
 else
   echo "n"
   return 0
 fi
}

cleanup_state()
{
wsrepstate_run=$(verify_wsrepstate)
clusterstatus_run=$(verify_clusterstatus)

if [[ $wsrepstate_run == "n" ]] || [[ $clusterstate_run == "n" ]]; then 
   if [ -f $SST_FILE ]; then
     (exec rm -rf "$SST_FILE")&
   fi
   if [ -f $GRA_FILE ]; then
     (exec rm -rf "$GRA_FILE")&
   fi
fi
}

checkNKill()
{
$CMON_MON_STOP

cmonpid=$(pidof cmon)
if [ -n "$cmonpid" ]; then
 $CMON_STOP
 sleep 10
 log_info_msg "CMON is Running. Kill the process: $cmonpid"
 (exec kill -9 $cmonpid)&
fi

mysqlpid=$(pidof mysqld)
if [ -n "$mysqlpid" ]; then
 $MYSQL_STOP
 sleep 10
 log_info_msg "Mysql is Running. Kill the process: $mysqlpid"
 (exec kill -9 $mysqlpid)&
fi
}

bootstrap()
{
# Get the myid of the galera node
if [ -e $MYIDFILE ]; then
    myid=$(cat $MYIDFILE)
    log_info_msg "Galera node ID: $myid"
else
    log_error_msg "Galera node ID not set in $MYIDFILE exiting bootstrap..."
    (exec rm -rf "$galera_state_file")&
    (exec rm -rf "$cluster_state_file")&
    exit 0
fi

wsrepstate_run=$(verify_wsrepstate)
clusterstatus_run=$(verify_clusterstatus)

# Bootstrap galera cluster
log_info_msg "Bootstraping galera cluster."
retry_flag=0
bootstrap_retry_count=$(($RETRY_TIMEOUT / RETRY_INTERVAL))
for i in $(eval echo {1..$bootstrap_retry_count}); do
    mysql_pid=$(verify_mysql)
    if [ "$mysql_pid" == '' ]; then
        log_warn_msg "Mysql stopped, trying to start...."
        if [[ $wsrepstate_run == "n" ]] || [[ $clusterstatus_run == "n" ]] && [[ $myid == 1 ]]; then
            checkNKill
            cleanup_state
            cmd="service mysql start --wsrep_cluster_address=gcomm://"
            log_info_msg "Starting mysql : $cmd"
            $cmd >> $LOGFILE
        else
            if [ $retry_flag == 1 ]; then
               cleanup_state
            fi
            cmd="service mysql start"
            log_info_msg "Starting mysql : $cmd"
            $cmd >> $LOGFILE
        fi
        retry_flag=1
        sleep 5
    else
        log_info_msg "Galera cluster is up and running."
        log_info_msg "Galera bootstrap completed."
        break
    fi
done
}

main() 
{
lock $PROGNAME \
        || eexit "Only one instance of $PROGNAME can run at one time."

galera_check
bootstrap
$CMON_MON_START
(exec rm -rf "$galera_state_file")&
(exec rm -rf "$cluster_state_file")&
}
main
