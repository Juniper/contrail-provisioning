#!/usr/bin/env bash

#cleanup script for database package under supervisord

chkconfig supervisord-contrail-database off
service supervisord-contrail-database stop

