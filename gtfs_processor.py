import pandas as pd
from psycopg2 import sql
from io import StringIO
from database import get_db_connection, execute_query

import pandas as pd
import numpy as np
from datetime import time

VALID_GTFS_FILES = {
    'agency.txt', 'stops.txt', 'routes.txt', 'trips.txt', 'stop_times.txt',
    'calendar.txt', 'calendar_dates.txt', 'shapes.txt', 'frequencies.txt',
    'transfers.txt', 'feed_info.txt'
}

GTFS_COLUMN_TYPES = {
    'agency': {
        'agency_id': str,
        'agency_name': str,
        'agency_url': str,
        'agency_timezone': str,
        'agency_lang': str,
        'agency_phone': str,
        'agency_fare_url': str,
        'agency_email': str
    },
    'stops': {
        'stop_id': str,
        'stop_code': str,
        'stop_name': str,
        'stop_desc': str,
        'stop_lat': float,
        'stop_lon': float,
        'zone_id': str,
        'stop_url': str,
        'location_type': int,
        'parent_station': str,
        'stop_timezone': str,
        'wheelchair_boarding': int,
        'level_id': str,
        'platform_code': str
    },
    'routes': {
        'route_id': str,
        'agency_id': str,
        'route_short_name': str,
        'route_long_name': str,
        'route_desc': str,
        'route_type': int,
        'route_url': str,
        'route_color': str,
        'route_text_color': str,
        'route_sort_order': int,
        'continuous_pickup': int,
        'continuous_drop_off': int
    },
    'trips': {
        'route_id': str,
        'service_id': str,
        'trip_id': str,
        'trip_headsign': str,
        'trip_short_name': str,
        'direction_id': int,
        'block_id': str,
        'shape_id': str,
        'wheelchair_accessible': int,
        'bikes_allowed': int
    },
    'stop_times': {
        'trip_id': str,
        'arrival_time': str,  # We'll convert this to timedelta later
        'departure_time': str,  # We'll convert this to timedelta later
        'stop_id': str,
        'stop_sequence': int,
        'stop_headsign': str,
        'pickup_type': int,
        'drop_off_type': int,
        'continuous_pickup': int,
        'continuous_drop_off': int,
        'shape_dist_traveled': float,
        'timepoint': int
    },
    'calendar': {
        'service_id': str,
        'monday': int,
        'tuesday': int,
        'wednesday': int,
        'thursday': int,
        'friday': int,
        'saturday': int,
        'sunday': int,
        'start_date': str,  # We'll convert this to datetime later
        'end_date': str  # We'll convert this to datetime later
    },
    'calendar_dates': {
        'service_id': str,
        'date': str,  # We'll convert this to datetime later
        'exception_type': int
    },
    'shapes': {
        'shape_id': str,
        'shape_pt_lat': float,
        'shape_pt_lon': float,
        'shape_pt_sequence': int,
        'shape_dist_traveled': float
    },
    'frequencies': {
        'trip_id': str,
        'start_time': str,  # We'll convert this to timedelta later
        'end_time': str,  # We'll convert this to timedelta later
        'headway_secs': int,
        'exact_times': int
    },
    'transfers': {
        'from_stop_id': str,
        'to_stop_id': str,
        'transfer_type': int,
        'min_transfer_time': int
    },
    'feed_info': {
        'feed_publisher_name': str,
        'feed_publisher_url': str,
        'feed_lang': str,
        'default_lang': str,
        'feed_start_date': str,  # We'll convert this to datetime later
        'feed_end_date': str,  # We'll convert this to datetime later
        'feed_version': str,
        'feed_contact_email': str,
        'feed_contact_url': str
    }
}

def read_gtfs(table_name, file_content):
    # Read the CSV file
    df = pd.read_csv(StringIO(file_content), dtype=GTFS_COLUMN_TYPES.get(table_name, {}))

    # Convert time fields to timedelta
    if table_name == 'stop_times':
        for col in ['arrival_time', 'departure_time']:
            df[col] = pd.to_timedelta(df[col])
    elif table_name == 'frequencies':
        for col in ['start_time', 'end_time']:
            df[col] = pd.to_timedelta(df[col])

    # Convert date fields to datetime
    if table_name in ['calendar', 'calendar_dates', 'feed_info']:
        date_columns = {
            'calendar': ['start_date', 'end_date'],
            'calendar_dates': ['date'],
            'feed_info': ['feed_start_date', 'feed_end_date']
        }
        for col in date_columns.get(table_name, []):
            df[col] = pd.to_datetime(df[col], format='%Y%m%d')

    return df

def infer_sql_type(py_type):
    if py_type == int:
        return "INTEGER"
    elif py_type == float:
        return "FLOAT"
    elif py_type == str:
        return "TEXT"
    else:
        return "TEXT"  # Default to TEXT for unknown types

def process_gtfs_file(file_content, filename):
    if filename not in VALID_GTFS_FILES:
        raise ValueError(f"Invalid GTFS filename: {filename}")

    table_name = filename.split('.')[0]
    df = read_gtfs(table_name, file_content)
    
    columns = [
        sql.SQL("{} {}").format(
            sql.Identifier(col),
            sql.SQL(infer_sql_type(df[col].dtype))
        )
        for col in df.columns
    ]
    
    create_table_query = sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(
        sql.Identifier(table_name),
        sql.SQL(', ').join(columns)
    )
    execute_query(create_table_query)
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            buffer = StringIO()
            df.to_csv(buffer, index=False, header=False, na_rep='\\N')
            buffer.seek(0)
            cur.copy_from(buffer, table_name, sep=',', null='\\N')
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise Exception(f"Error processing {filename}: {str(e)}")
    finally:
        conn.close()

def cleanup_tables():
    table_names = [file.split('.')[0] for file in VALID_GTFS_FILES]
    for table in table_names:
        query = sql.SQL("DROP TABLE IF EXISTS {} CASCADE;").format(sql.Identifier(table))
        execute_query(query)

def add_spatial_index_to_stops():
    queries = [
        "ALTER TABLE stops ADD COLUMN IF NOT EXISTS geometry geometry(Point, 4326);",
        "UPDATE stops SET geometry = ST_SetSRID(ST_MakePoint(stop_lon::float, stop_lat::float), 4326) WHERE geometry IS NULL;",
        "CREATE INDEX IF NOT EXISTS stops_geometry_idx ON stops USING GIST (geometry);"
    ]
    for query in queries:
        execute_query(query)

def process_gtfs_feed(feed_content):
    cleanup_tables()

    for filename, content in feed_content.items():
        if filename in VALID_GTFS_FILES:
            process_gtfs_file(content, filename)
    
    if 'stops.txt' in feed_content:
        add_spatial_index_to_stops()

def gtfs_schema():
    schema_strings = []
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Get all tables in the public schema
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            tables = [row[0] for row in cur.fetchall()]
            
            # Filter for GTFS tables
            gtfs_tables = [table for table in tables if table in GTFS_COLUMN_TYPES.keys()]

            print(tables, gtfs_tables)
            
            for table in gtfs_tables:
                # Get column information for each table
                cur.execute(sql.SQL("""
                    SELECT column_name, data_type, character_maximum_length
                    FROM information_schema.columns
                    WHERE table_name = {}
                    ORDER BY ordinal_position
                """).format(sql.Literal(table)))
                
                columns = cur.fetchall()
                column_defs = []
                
                for col_name, data_type, max_length in columns:
                    if data_type == 'character varying' and max_length:
                        col_type = f"VARCHAR({max_length})"
                    else:
                        col_type = data_type.upper()
                    
                    column_defs.append(f"{col_name} {col_type}")
                
                schema = ", ".join(column_defs)
                schema_strings.append(f"{table} ({schema});")
    
    finally:
        conn.close()
    
    return '\n'.join(schema_strings)