import string
template = string.Template("""
CREATE USER $__cassandra_user__ WITH PASSWORD '$__cassandra_password__';
""")
