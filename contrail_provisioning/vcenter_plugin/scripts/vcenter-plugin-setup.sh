#!/usr/bin/env bash

#setup script for vcenter plugin package under supervisord
chkconfig contrail-vcenter-plugin on
service contrail-vcenter-plugin restart

