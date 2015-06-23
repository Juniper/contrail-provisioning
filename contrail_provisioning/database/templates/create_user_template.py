import string
template = string.Template("""
CREATE USER $__cassandra_name__ WITH PASSWORD '$__cassandra_password__';
""")
