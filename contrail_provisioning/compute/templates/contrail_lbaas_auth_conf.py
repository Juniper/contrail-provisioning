import string

template = string.Template("""
[BARBICAN]
admin_tenant_name=$__admin_tenant_name__
admin_user=$__admin_user__
admin_password=$__admin_password__
auth_url=$__auth_url__
region=RegionOne

""")
