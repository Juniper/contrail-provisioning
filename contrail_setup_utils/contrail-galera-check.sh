#!/bin/bash
#
######## This file is managed by Puppet ##########
#
# This script checks if a mysql server is healthy running on localhost. It will
# return:
# "HTTP/1.x 200 OK\r" (if mysql is running smoothly)
# - OR -
# "HTTP/1.x 500 Internal Server Error\r" (else)
#
# The purpose of this script is make haproxy capable of monitoring mysql properly
#
# Author - Sanju Abraham
# Juniper Networks

MYSQL_HOST="localhost"
MYSQL_PORT="3306"
MYSQL_USERNAME="cmon"
MYSQL_PASSWORD="cmon"
MYSQL_BIN="/usr/bin/mysql"
RUN_STATE="isrunning"
mysqlpid=$(pidof mysqld)
CHECK_QUERY="show global status where variable_name='wsrep_local_state'"
CONNECT_TIMEOUT=2
return_ok()
{
    echo -e "HTTP/1.1 200 OK\r\n"
    echo -e "Content-Type: text/html\r\n"
    echo -e "Content-Length: 43\r\n"
    echo -e "\r\n"
    echo -e "<html><body>MySQL is running.</body></html>\r\n"
    echo -e "\r\n"
    exit 0
}
return_fail()
{
    echo -e "HTTP/1.1 503 Service Unavailable\r\n"
    echo -e "Content-Type: text/html\r\n"
    echo -e "Content-Length: 42\r\n"
    echo -e "\r\n"
    echo -e "<html><body>MySQL is *down*.</body></html>\r\n"
    echo -e "\r\n"
    exit 1
}
if [ -z "$mysqlpid" ]; then
   return_fail;
fi
status=$($MYSQL_BIN --connect_timeout $CONNECT_TIMEOUT -h $MYSQL_HOST --port $MYSQL_PORT -u $MYSQL_USERNAME -p${MYSQL_PASSWORD} -e "${CHECK_QUERY}" | awk '{print $2}' | sed '1d')

if [ $status -ne 4 ]; then
   return_fail;
fi

return_ok;
