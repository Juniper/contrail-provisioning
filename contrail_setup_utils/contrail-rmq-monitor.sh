#!/bin/bash

# Purpose of the script is to check the state of RMQ
# Author - Sanju Abraham

source /etc/contrail/ha/cmon_param

LOGFILE=/var/log/contrail/ha/rmq-monitor.log
RMQ_CONSUMERS="rabbitmqctl list_consumers"
NOVA_COMPUTE_RESTART="service nova-compute restart"
RMQ_CHANNEL_CHK="rabbitmqctl list_channels"
RMQ_CHANNEL_OK="...done."
RMQ_RESET="service rabbitmq-server restart"
file="/tmp/rmq-chnl-ok"

if [ ! -f "$file" ] ; then
         touch "$file"
fi

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

verify_chnlstate()
{
 chnlstate=`cat $file`
 if [[ $chnlstate == $RMQ_CHANNEL_OK ]]; then
   echo "y"
   return 1
 else
   echo "n"
   return 0
 fi
}

i=1
while [ $i -lt  12 ]
do
 ($RMQ_CHANNEL_CHK | grep $RMQ_CHANNEL_OK > "$file") & pid=$!
 log_info_msg "pidof pending rmq check $pid"
 sleep 10
 if [[ -n  "$pid" ]] ; then
  (exec kill -9 $pid)&
  i=$[$i+1]
 else
  break
 fi
done

for (( i=0; i<${DIPS_SIZE}; i++ ))
 do 
  sleep 20
  chnlstate_run=$(verify_chnlstate)
  if [ $chnlstate_run == "n" ]; then
     (exec ssh -o StrictHostKeyChecking=no "$COMPUTES_USER@${DIPS[i]}" $RMQ_RESET)&
  fi
done
(exec rm -rf "$file")&
log_info_msg "Resetting RMQ Channels -- Done"

exit 0
