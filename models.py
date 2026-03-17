import sqlite3
import json
from config import Config

def get_db_connection():
    '''create and return a database connection'''
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    '''create all tables'''
    conn = get_db_connection()
    cursor = conn.cursor()#to execute sql commands 

    #table 1: Polls
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS polls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            start_time datetime,
            end_time datetime,
            user_id INTEGER, 
            created_at TIMESTAMP,
            created_id INTEGER(10),
            status TINYINT DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    #table 2: Votes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS votes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id INTEGER(10),
            selected_option_id INTEGER(10),
            created_at TIMESTAMP,
            created_id INTEGER(10),
            FOREIGN KEY (poll_id) REFERENCES polls (id),
            FOREIGN KEY (selected_option_id) REFERENCES options (id)
        )
    """)

    #table 3: Vote Identity
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vote_identity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vote_id INTEGER(10),
            encrypted_identifier TEXT NOT NULL,
            created_at TIMESTAMP,
            created_id INTEGER(10),
            browser VARCHAR(100),
            FOREIGN KEY (vote_id) REFERENCES votes (id)
        )
    """)

    #table 4: users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name varchar(100),
            last_name varchar(100),
            email varchar(100),
            password varchar(100) NOT NULL,
            created_at TIMESTAMP,
            created_id INTEGER(10),
            status TINYINT
        ) 
     """)
    #table 5:
    cursor.execute(""" CREATE TABLE IF NOT EXISTS options(id INTEGER PRIMARY KEY AUTOINCREMENT,
                                            poll_id INTEGER(10),
                                            option TEXT,
                                            status TINYINT,
                                            created_at TIMESTAMP,
                                            created_id INTEGER(10),
                                            FOREIGN KEY (poll_id) REFERENCES polls (id))"""
                   )

    conn.commit()#to save changes to the database
    conn.close()
    print("Database initialized successfully.")