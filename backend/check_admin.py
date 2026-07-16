import pandas as pd
from src.database import get_connection

# Check if admin user exists
query = "SELECT username, password_hash, role FROM users WHERE username = 'admin'"
df = pd.read_sql_query(query, get_connection())
print('Admin user in database:')
print(df.to_string())

# Check total users
query_all = "SELECT username, role FROM users LIMIT 10"
df_all = pd.read_sql_query(query_all, get_connection())
print('\nFirst 10 users:')
print(df_all.to_string())
