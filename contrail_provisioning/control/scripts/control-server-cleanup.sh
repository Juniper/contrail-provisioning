#!/usr/bin/env bash
service contrail-control stop
service contrail-dns stop
service contrail-named stop
chkconfig supervisor-control off
service supervisor-control stop
