#!/usr/bin/env bash
supervisorctl -s http://localhost:9003 stop contrail-control
chkconfig supervisor-control off
service supervisor-control stop
 
supervisorctl -s http://localhost:9006 stop contrail-dns
supervisorctl -s http://localhost:9006 stop contrail-named
chkconfig supervisor-dns off
service supervisor-dns stop
