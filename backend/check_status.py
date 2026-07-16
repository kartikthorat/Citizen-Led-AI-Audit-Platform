import pandas as pd
from src.database import get_connection

# Check pending records
query = "SELECT id, status FROM reports WHERE status = 'Pending' LIMIT 5"
df = pd.read_sql_query(query, get_connection())
print('Pending records in database:')
print(df.to_string())

# Check status distribution
df_all = pd.read_sql_query('SELECT status, COUNT(*) as count FROM reports GROUP BY status', get_connection())
print('\nStatus distribution:')
print(df_all.to_string())
