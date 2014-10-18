
import string

template = string.Template("""
vrrp_sync_group INTERNAL_EXTERNAL_SYNC_GROUP {
   group {
       $__internal_vip_str__
       $__external_vip_str__
   }
}
""")
