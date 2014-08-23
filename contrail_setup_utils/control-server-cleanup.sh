#!/usr/bin/env bash
supervisorctl -s unix:///tmp/supervisord_control.sock stop contrail-control
supervisorctl -s unix:///tmp/supervisord_control.sock stop contrail-dns
supervisorctl -s unix:///tmp/supervisord_control.sock stop contrail-named
chkconfig supervisor-control off
service supervisor-control stop
