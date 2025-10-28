import logging
import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from qc_application.utils.database_connection import establish_connection

def query_database(query: str, retries=3, delay=5) -> pd.DataFrame:
    """
    Executes a SQL query using SQLAlchemy and returns results as a pandas DataFrame.
    Automatically establishes a connection if one is not available.
    """
    conn = establish_connection(retries=retries, delay=delay)
    if conn is None:
        logging.error("Failed to establish a database connection. Returning empty DataFrame.")
        return pd.DataFrame()

    try:
        df = pd.read_sql(text(query), conn)
        return df
    except SQLAlchemyError as e:
        logging.error(f"Error executing query: {e}")
        return pd.DataFrame()
    finally:
        conn.close()
