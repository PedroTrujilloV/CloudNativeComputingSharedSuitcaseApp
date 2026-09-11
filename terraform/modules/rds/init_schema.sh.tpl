# Renders the shell script applied against the shared RDS database.
# host, port, username and database name are interpolated from the
# aws_db_instance attributes; the SQL body is the rendered schema.sql.
# The password is passed via the PGPASSWORD environment variable (never
# interpolated into the script).
PGPASSWORD="$PGPASSWORD" psql \
  -h "${host}" \
  -p "${port}" \
  -U "${db_username}" \
  "dbname='${db_name}'" \
  -v ON_ERROR_STOP=1 <<'SQL'
${render_schema_sql}
SQL