#!/usr/bin/env bash

#setup script for analytics package under supervisord
chkconfig supervisord-contrail-database on
service supervisord-contrail-database restart

