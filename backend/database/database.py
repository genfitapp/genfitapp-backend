import os
from psycopg2 import pool
from pathlib import Path
from dotenv import load_dotenv
from contextlib import contextmanager
from .utils import DATABASE_INIT_COMMANDS


# Define the path to the .env file relative to the project root
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

class Database:
    def __init__(self):
        # Read database credentials from environment variables
        db_host = os.getenv("DB_HOST")
        db_name = os.getenv("DB_NAME")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")

        # Create a connection pool with a minimum of 1 and a maximum of 10 connections.
        self.db_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_password
        )

    def initialiaze_database(self):
        for command in DATABASE_INIT_COMMANDS:
            self.execute(command)

    @contextmanager
    def get_cursor(self):
        conn = self.db_pool.getconn()
        try:
            with conn.cursor() as cur:
                yield cur, conn
        finally:
            self.db_pool.putconn(conn)

    def execute(self, query, params=None, fetch=False):
        """
        Executes a given SQL query.
        
        Parameters:
            query (str): The SQL query to execute.
            params (tuple, optional): The parameters to use in the SQL query.
            fetch (bool, optional): If True, fetch and return the query results.
        
        Returns:
            list: Query results if fetch is True, otherwise None.
        """
        with self.get_cursor() as (cur, conn):
            try:
                cur.execute(query, params)
                if fetch:
                    result = cur.fetchall()
                else:
                    result = None
                conn.commit()
                return result
            except Exception as e:
                conn.rollback()
                raise e

    def close_all(self):
        """
        Closes all connections in the pool.
        """
        self.db_pool.closeall()