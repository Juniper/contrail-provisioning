
import string

template = string.Template("""
vrrp_script chk_haproxy_$__vip_str__ {
        script "killall -0 haproxy" # verify if pid exists
        interval 1
        weight 2
        timeout $__timeout__
        rise $__rise__
        fall $__fall__
}

vrrp_instance $__vip_str__ {
        interface $__device__
        state $__state__
        garp_master_delay $__delay__
        advert_int 1
        virtual_router_id $__router_id__
        priority  $__priority__
        authentication {
             auth_type AH
             auth_pass k@l!ve1
        }
        virtual_ipaddress {
                $__virtual_ip__/$__virtual_ip_mask__ dev $__device__
        }
        track_script  {
                chk_haproxy_$__vip_str__
        }
}
""")
