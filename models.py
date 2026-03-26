import psycopg2
import psycopg2.extras
import bcrypt
from config import Config


def get_db_connection():
    return psycopg2.connect(
        Config.DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor
    )


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # ── Polls ─────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS polls (
            id SERIAL PRIMARY KEY,
            question TEXT NOT NULL,
            start_time TIMESTAMPTZ,
            end_time TIMESTAMPTZ,
            user_id INTEGER,
            poll_type VARCHAR(10) DEFAULT 'single'
                CHECK (poll_type IN ('single','multiple')),
            share_token VARCHAR(40) UNIQUE,
            created_at TIMESTAMP DEFAULT NOW(),
            created_id INTEGER,
            status SMALLINT DEFAULT 1
        )
    """)

    # ── Users ─────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            email VARCHAR(100),
            password VARCHAR(255) NOT NULL,
            role VARCHAR(10) DEFAULT 'user'
                CHECK (role IN ('user','admin')),
            created_at TIMESTAMP DEFAULT NOW(),
            created_id INTEGER,
            status SMALLINT
        )
    """)

    # ── Options ───────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS options (
            id SERIAL PRIMARY KEY,
            poll_id INTEGER,
            option TEXT,
            media_id INTEGER,
            status SMALLINT,
            created_at TIMESTAMP DEFAULT NOW(),
            created_id INTEGER
        )
    """)

    # ── Votes ─────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id SERIAL PRIMARY KEY,
            poll_id INTEGER,
            selected_option_id INTEGER,
            submission_id VARCHAR(40),
            created_at TIMESTAMP DEFAULT NOW(),
            created_id INTEGER
        )
    """)

    # ── Vote Identity ─────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vote_identity (
            id SERIAL PRIMARY KEY,
            vote_id INTEGER,
            encrypted_identifier TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            created_id INTEGER
        )
    """)

    # ── Media ─────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS media (
            id SERIAL PRIMARY KEY,
            file_name VARCHAR(255),
            file_path VARCHAR(500),
            file_type VARCHAR(100),
            file_size INTEGER,
            original_name VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW(),
            created_id INTEGER,
            status SMALLINT DEFAULT 1
        )
    """)

    # ── Create Admin ──────────────────────
    cursor.execute(
        "SELECT id FROM users WHERE role = 'admin'"
    )
    existing_admin = cursor.fetchone()

    if not existing_admin:
        hashed = bcrypt.hashpw(
            'admin@123'.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        cursor.execute("""
            INSERT INTO users (
                first_name, last_name,
                email, password, role,
                created_at, status
            )
            VALUES (%s, %s, %s, %s, 'admin', NOW(), 1)
        """, (
            'Pia',
            'Jalmi',
            'piya.intern@gmail.com',
            hashed
        ))

        print("Admin user created.")

    conn.commit()
    cursor.close()
    conn.close()

    print("Database initialized successfully.")


# import os
# import sqlite3
# import json
# import psycopg2
# import psycopg2.extras
# import bcrypt
# from config import Config

# def get_db_connection():
#     '''create and return a database connection'''
#     conn = psycopg2.connect(
#         Config.DATABASE_URL,
#         cursor_factory=psycopg2.extras.RealDictCursor
#     )
#     return conn

# def init_db():
#     '''create all tables'''
#     conn = get_db_connection()
#     cursor = conn.cursor()#to execute sql commands 

#     #table 1: Polls
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS polls (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             question TEXT NOT NULL,
#             start_time datetime,
#             end_time datetime,
#             user_id INTEGER, 
#             poll_type  VARCHAR(10) DEFAULT 'single'
#                    CHECK(poll_type IN ('single', 'multiple')),
#             share_token VARCHAR(40) UNIQUE,
#             created_at TIMESTAMP,
#             created_id INTEGER,
#             status TINYINT DEFAULT 1,
#             FOREIGN KEY (user_id) REFERENCES users (id)
#         )
#     """)

#     #table 2: Votes
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS votes(
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             poll_id INTEGER,
#             selected_option_id INTEGER,
#             submission_id VARCHAR(40),
#             created_at TIMESTAMP,
#             created_id INTEGER,
#             FOREIGN KEY (poll_id) REFERENCES polls (id),
#             FOREIGN KEY (selected_option_id) REFERENCES options (id)
#         )
#     """)

#     #table 3: Vote Identity
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS vote_identity (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             vote_id INTEGER(10),
#             encrypted_identifier TEXT NOT NULL,
#             created_at TIMESTAMP,
#             created_id INTEGER,
#             FOREIGN KEY (vote_id) REFERENCES votes (id)
#         )
#     """)

#     #table 4: users
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,
#             first_name varchar(100),
#             last_name varchar(100),
#             email varchar(100),
#             password varchar(255) NOT NULL,
#             role VARCHAR(10) DEFAULT 'user'
#                  CHECK(role IN ('user', 'admin')),
#             created_at TIMESTAMP,
#             created_id INTEGER,
#             status TINYINT
#         ) 
#      """)
#     #table 5:
#     cursor.execute(""" CREATE TABLE IF NOT EXISTS options(id INTEGER PRIMARY KEY AUTOINCREMENT,
#                                             poll_id INTEGER,
#                                             option TEXT,
#                                             media_id INTEGER,
#                                             status TINYINT,
#                                             created_at TIMESTAMP,
#                                             created_id INTEGER,
#                                             FOREIGN KEY (poll_id) REFERENCES polls (id),
#                                             FOREIGN KEY (media_id) REFERENCES media(id)
#                                              )
#                                          """) 

#     #table 6:
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS media (
#             id            INTEGER PRIMARY KEY AUTOINCREMENT,
#             file_name     VARCHAR(255),
#             file_path     VARCHAR(500),
#             file_type     VARCHAR(100),
#             file_size     INTEGER,
#             original_name VARCHAR(255),
#             created_at    TIMESTAMP,
#             created_id    INTEGER,
#             status        TINYINT DEFAULT 1,
#             FOREIGN KEY (created_id) REFERENCES users(id)
#         )
#     """)

#     #create admin
#     existing_admin = conn.execute(
#         "SELECT id FROM users WHERE role = 'admin'"
#     ).fetchone()

#     if not existing_admin:
    
#         hashed = bcrypt.hashpw(
#         'admin@123'.encode('utf-8'),
#         bcrypt.gensalt()
#     ).decode('utf-8')
        
#         conn.execute("""
#             INSERT INTO users (first_name, last_name,
#                                email, password, role,
#                                created_at, status)
#             VALUES (%s, %s, %s, %s, 'admin',
#                     NOW(), 1)
#         """, (
#             'Pia',
#             'Jalmi',
#             'piya.intern@gmail.com',
#             hashed
#         ))
#         conn.commit()
#         print("Admin user created successfully.")
#     cursor.close()
#     conn.commit()#to save changes to the database
#     conn.close()
#     print("Database initialized successfully.")