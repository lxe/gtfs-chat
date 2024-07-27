import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
import time

# Global connection variable
conn = None
max_retries = 3
retry_delay = 5  # seconds

def get_db_connection():
    global conn
    
    for attempt in range(max_retries):
        try:
            if conn is None or conn.closed:
                # Connection is not established or has been closed
                conn = psycopg2.connect(
                    dbname="postgres",
                    user="postgres",
                    password="mysecretpassword",
                    host="localhost",
                    port="5432"
                )
                conn.autocommit = True
                cursor = conn.cursor()
                cursor.execute("CREATE TEMPORARY TABLE IF NOT EXISTS spatial_ref_sys (LIKE spatial_ref_sys INCLUDING ALL)")
                cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
            else:
                # Test the connection
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                
            return conn

        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            if attempt < max_retries - 1:
                print(f"Connection attempt {attempt + 1} failed. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                conn = None  # Reset the connection to force a new connection attempt
            else:
                print("Failed to establish a database connection after multiple attempts.")
                raise

    return conn

def init_db():
    cursor = get_db_connection().cursor()
    # PostGIS is already initialized when the extension is created
    pass

def execute_query(query, params=None):
    cursor = get_db_connection().cursor()
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)
    return cursor

def query_to_dict(query, params=None):
    cursor = get_db_connection().cursor(cursor_factory=RealDictCursor)
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)
    return cursor.fetchall()
