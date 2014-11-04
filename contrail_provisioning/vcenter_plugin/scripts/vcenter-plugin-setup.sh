#!/usr/bin/env bash

#setup script for vcenter plugin package under supervisord
chkconfig vcenter-plugin on
service vcenter-plugin restart

