import os
from psycopg2 import pool, OperationalError, InterfaceError
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
        db_sslmode = os.getenv("DB_SSLMODE", "require")
        self.db_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_password,

            # Comment code below for dev
            # sslmode="require",
            # connect_timeout=10,
            # keepalives=1,
            # keepalives_idle=30,
            # keepalives_interval=10,
            # keepalives_count=3,
            # options="-c statement_timeout=60000 -c idle_in_transaction_session_timeout=60000"
        )


    def initialiaze_database(self):
        for command in DATABASE_INIT_COMMANDS:
            self.execute(command)

    @contextmanager
    def get_cursor(self):
        conn = self._get_healthy_conn()
        try:
            with conn.cursor() as cur:
                yield cur, conn
        finally:
            # Only return healthy connections to the pool
            try:
                if conn and conn.closed == 0:
                    self.db_pool.putconn(conn)
                else:
                    self.db_pool.putconn(conn, close=True)
            except Exception:
                # If we can't even return it, force-close it
                try:
                    self.db_pool.putconn(conn, close=True)
                except Exception:
                    pass

    def _get_healthy_conn(self):
        # Grab a conn, ping it; if bad, evict and try once more
        for _ in range(2):
            conn = self.db_pool.getconn()
            try:
                if conn.closed != 0:
                    raise InterfaceError("connection already closed")
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return conn
            except (OperationalError, InterfaceError):
                # Evict broken connection
                self.db_pool.putconn(conn, close=True)
            except Exception:
                # Unknown error — don't lose the conn silently
                self.db_pool.putconn(conn)
                raise
        # Could not obtain a healthy connection
        raise OperationalError("Unable to obtain a healthy DB connection")



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
                result = cur.fetchall() if fetch else None
                conn.commit()
                return result
            except (OperationalError, InterfaceError) as e:
                # Drop this connection and try once with a fresh one
                try:
                    conn.rollback()
                except Exception:
                    pass
                self.db_pool.putconn(conn, close=True)

                with self.get_cursor() as (cur2, conn2):
                    cur2.execute(query, params)
                    result = cur2.fetchall() if fetch else None
                    conn2.commit()
                    return result
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                # Return as unhealthy so it doesn’t recirculate
                self.db_pool.putconn(conn, close=True)
                raise

    def close_all(self):
        """
        Closes all connections in the pool.
        """
        self.db_pool.closeall()