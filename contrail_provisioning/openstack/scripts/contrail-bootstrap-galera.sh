#!/bin/bash
#
# Script to be trrigerd by rc.local to bootstrap galera cluster on every reboot of all galera nodes in the cluster.

source /etc/contrail/ha/cmon_param

readonly PROGNAME=$(basename "$0")
readonly LOCKFILE_DIR=/tmp/galera-chk
readonly LOCK_FD=200

readonly boot=$1

LOGFILE=/var/log/galera-bootstrap.log
RETRIES=3
MYSQL_USERNAME="cmon"
MYSQL_PASSWORD="cmon"
MYSQL_BIN="/usr/bin/mysql"
MYIDFILE="/etc/contrail/galeraid"
MYIDFILE="/etc/contrail/galeraid"
SST_FILE="/var/lib/mysql/rsync_sst_complete"
GRA_FILE="/var/lib/mysql/grastate.dat"
MYSQL_STOP="service mysql stop"
GTID_DIR="/tmp/galera"
GTID_FILE="/tmp/galera/gtid"
DONOR="DONOR"

MYSQL_WSREP_STATE="show status like 'wsrep_local_state';"
MYSQL_CLUSTER_STATE="show status like 'wsrep_cluster_status';"
SYNCED=4
STATUS="Primary"
CMON_MON_STOP="service contrail-hamon stop"
CMON_MON_START="service contrail-hamon start"
CMON_STOP="service cmon stop"
STDERR_FILE="/tmp/mysqlerr.txt"

if [ ! -f "$LOCKFILE_DIR" ] ; then
    mkdir -p $LOCKFILE_DIR
fi

if [ ! -f "$GTID_DIR" ] ; then
    mkdir -p $GTID_DIR
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
    date
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
    
galera_check()
{
  $MYSQL_BIN -u $MYSQL_USERNAME -p${MYSQL_PASSWORD} -e "$MYSQL_WSREP_STATE" 2> >( cat <() > $STDERR_FILE )
  error=`cat ${STDERR_FILE} | awk '{print $1}'`
  if [[ $error == "ERROR" ]]; then
    checkNKill
  fi
 (exec rm -rf $STDERR_FILE)&
  for (( i=0; i<${DIPS_SIZE}; i++ ))
   do
     wval=$($MYSQL_BIN -u $MYSQL_USERNAME -p${MYSQL_PASSWORD} -h ${DIPS[i]} -e "$MYSQL_WSREP_STATE" | awk '{print $2}' | sed '1d')
     cval=$($MYSQL_BIN -u $MYSQL_USERNAME -p${MYSQL_PASSWORD} -h ${DIPS[i]} -e "$MYSQL_CLUSTER_STATE" | awk '{print $2}' | sed '1d')
     if [[ $wval == $SYNCED ]] & [[ $cval == $STATUS ]]; then
        ret="y"
        break
     else
        ret="n"
     fi
   done
   echo $ret
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

checkNKillMysql()
{
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
if [ -e $MYIDFILE ]; then
    myid=$(cat $MYIDFILE)
    log_info_msg "Galera node ID: $myid"
else
    log_error_msg "Galera node ID not set in $MYIDFILE exiting bootstrap..."
    exit 0
fi

checkNKill
log_info_msg "Bootstraping galera cluster."

    mysql_pid=$(pidof mysqld)
    if [ "$mysql_pid" == '' ]; then
        log_warn_msg "Mysql stopped on local, trying to start...."
        galchk=$(galera_check)
        if [[ $galchk == "n" ]]; then
            cmd="service mysql start --wsrep_recover"
            log_info_msg "Starting mysql recovery: $cmd"
            setsid $cmd >> $LOGFILE
            if [ -f $GRA_FILE ]; then
              uuid=$(cat $GRA_FILE | grep uuid | awk '{print $2}')
              gtid=$(grep "Recovered position: $uuid" /var/log/mysql/error.log | awk '{print $7}' | cut -d ":" -f 2 | tail -1)
              echo $gtid > $GTID_FILE
            else
              log_info_msg "$GRA_FILE not found. Recover mysql without grastate"
              gtid=$(grep "Recovered position: " /var/log/mysql/error.log | awk '{print $7}' | cut -d ":" -f 2 | tail -1)
              echo $gtid > $GTID_FILE
            fi
        fi
        if [[ $galchk == "y" ]]; then
           log_info_msg "One of the galera cluster node is up. Cluster monitor will initialize the galera cluster."
        fi
    else
        log_info_msg "Galera bootstrap completed."
    fi
}

main()
{
lock $PROGNAME \
    || eexit "Only one instance of $PROGNAME can run at one time."
if [[ $boot == $DONOR ]]; then
    checkNKillMysql
    log_info_msg "bootstrapping this instance of mysql as DONOR based on the GTID"
    cmd="service mysql start --wsrep_cluster_address=gcomm://"
    setsid $cmd >> $LOGFILE
    (ssh -o StrictHostKeyChecking=no $VIP "$CMON_STOP")&
else
    bootstrap
    $CMON_MON_START
fi

if [ -f $SST_FILE ]; then
    (exec rm -rf "$SST_FILE")&
fi

if [ -f $GRA_FILE ]; then
    (exec rm -rf "$GRA_FILE")&
fi
}

main
