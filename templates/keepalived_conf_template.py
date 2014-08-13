
import string

template = string.Template("""
vrrp_script chk_haproxy {
        script "killall -0 haproxy" # verify if pid exists
        interval 1
        weight 2
        timeout 2
        rise 1
        fall 2
}

vrrp_instance $__vip_str__ {
        interface $__device__
        state $__state__
        virtual_router_id $__router_id__
        priority  $__priority__
        virtual_ipaddress {
                $__virtual_ip__/$__virtual_ip_mask__ dev $__device__
        }
        track_script  {
                chk_haproxy
        }
}
""")
