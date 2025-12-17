import mysql.connector
from prometheus_client import start_http_server, Gauge
"""This Module includes functions for connecting and disconnecting to a database"""

def connect_to_DB():
    """
    Connects to the MSSQL database via pyodbc
        Return: Database object to make queries with
    """
    config = {
    'user': 'BotAdmin',
    'password': 'B0tK1ng23',
    'host': 'paulsrv2', # or the IP address or hostname of your MariaDB server
    'database': 'paulbots',
    'port': 3307 # default port for MariaDB, change if yours is different
    }
    print("connected")
    return mysql.connector.connect(**config)


def start_prometheus_server(port):
    """Runs the prometheus server on localhost:8000"""
    start_http_server(port)
    return Gauge('iteration_counter', 'This counter shows how often the main loop is iterating. This should increase every few seconds and if it is not, then the bot may be sleeping or experiencing a timeout')
