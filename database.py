import os
import urllib.parse as urlparse
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor, Json
import sqlite3
import json
import uuid

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/my_ai_companion_db")

# Parse target database name
url = urlparse.urlparse(DATABASE_URL)
target_db = url.path[1:]

class DatabaseManager:
    def __init__(self):
        self.pool = None
        self.use_sqlite = False
        self.sqlite_db_path = "my_ai_companion.db"

    def setup_pool(self):
        if self.use_sqlite:
            return
        if not self.pool:
            try:
                self.pool = pool.SimpleConnectionPool(
                    1, 20, dsn=DATABASE_URL
                )
                print("Database connection pool initialized.")
            except Exception as e:
                print(f"Error initializing connection pool, falling back to SQLite: {e}")
                self.use_sqlite = True

    def get_conn(self):
        self.setup_pool()
        if self.use_sqlite:
            conn = sqlite3.connect(self.sqlite_db_path)
            conn.row_factory = sqlite3.Row
            return conn
        return self.pool.getconn()

    def put_conn(self, conn):
        if self.use_sqlite:
            if conn:
                conn.close()
            return
        if self.pool and conn:
            self.pool.putconn(conn)

db = DatabaseManager()

def init_db():
    # Try PostgreSQL first
    try:
        # Connect to postgres default db to check/create target database
        postgres_url = DATABASE_URL.replace(f"/{target_db}", "/postgres")
        conn = psycopg2.connect(postgres_url)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
            if not cur.fetchone():
                print(f"Database '{target_db}' does not exist. Creating...")
                cur.execute(f'CREATE DATABASE "{target_db}"')
        conn.close()
        
        # Connect and migrate
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS companion_users (
                    email VARCHAR(255) PRIMARY KEY,
                    display_name VARCHAR(255) NOT NULL,
                    avatar_url TEXT,
                    theme_preference VARCHAR(20) DEFAULT 'system'
                );
            """)
            cur.execute("""
                ALTER TABLE companion_users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id UUID NOT NULL,
                    user_email VARCHAR(255) REFERENCES companion_users(email) ON DELETE CASCADE,
                    role VARCHAR(50) NOT NULL,
                    message_content JSONB NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_session_created 
                ON chat_history (session_id, created_at);
            """)
            print("PostgreSQL database schemas and index initialized successfully.")
        conn.close()
    except Exception as e:
        print(f"PostgreSQL migration failure or offline: {e}. Switching to SQLite fallback.")
        db.use_sqlite = True
        
        # Initialize SQLite database
        conn = sqlite3.connect(db.sqlite_db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS companion_users (
                email TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                avatar_url TEXT,
                theme_preference TEXT DEFAULT 'system'
            );
        """)
        try:
            cur.execute("ALTER TABLE companion_users ADD COLUMN password_hash TEXT;")
            conn.commit()
        except Exception:
            pass
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_email TEXT REFERENCES companion_users(email) ON DELETE CASCADE,
                role TEXT NOT NULL,
                message_content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_session_created 
            ON chat_history (session_id, created_at);
        """)
        conn.commit()
        conn.close()
        print("SQLite fallback database initialized successfully.")

def get_user(email):
    conn = db.get_conn()
    try:
        if db.use_sqlite:
            cur = conn.cursor()
            cur.execute("SELECT * FROM companion_users WHERE email = ?", (email,))
            row = cur.fetchone()
            if row:
                return dict(row)
            return None
        else:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM companion_users WHERE email = %s", (email,))
                return cur.fetchone()
    except Exception as e:
        print(f"Error getting user: {e}")
        return None
    finally:
        db.put_conn(conn)

def upsert_user(email, display_name, avatar_url, theme_preference='system', password_hash=None):
    conn = db.get_conn()
    try:
        if db.use_sqlite:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO companion_users (email, display_name, avatar_url, theme_preference, password_hash)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (email) 
                DO UPDATE SET 
                    display_name = EXCLUDED.display_name,
                    avatar_url = COALESCE(EXCLUDED.avatar_url, companion_users.avatar_url),
                    theme_preference = COALESCE(EXCLUDED.theme_preference, companion_users.theme_preference),
                    password_hash = COALESCE(EXCLUDED.password_hash, companion_users.password_hash);
            """, (email, display_name, avatar_url, theme_preference, password_hash))
            conn.commit()
            
            cur.execute("SELECT * FROM companion_users WHERE email = ?", (email,))
            return dict(cur.fetchone())
        else:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO companion_users (email, display_name, avatar_url, theme_preference, password_hash)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (email) 
                    DO UPDATE SET 
                        display_name = EXCLUDED.display_name,
                        avatar_url = COALESCE(EXCLUDED.avatar_url, companion_users.avatar_url),
                        theme_preference = COALESCE(EXCLUDED.theme_preference, companion_users.theme_preference),
                        password_hash = COALESCE(EXCLUDED.password_hash, companion_users.password_hash)
                    RETURNING *;
                """, (email, display_name, avatar_url, theme_preference, password_hash))
                conn.commit()
                return cur.fetchone()
    except Exception as e:
        print(f"Error upserting user: {e}")
        return None
    finally:
        db.put_conn(conn)

def update_user_theme(email, theme):
    conn = db.get_conn()
    try:
        if db.use_sqlite:
            cur = conn.cursor()
            cur.execute("""
                UPDATE companion_users 
                SET theme_preference = ? 
                WHERE email = ?;
            """, (theme, email))
            conn.commit()
        else:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE companion_users 
                    SET theme_preference = %s 
                    WHERE email = %s;
                """, (theme, email))
                conn.commit()
    except Exception as e:
        print(f"Error updating user theme: {e}")
    finally:
        db.put_conn(conn)

def save_chat_message(session_id, user_email, role, message_text):
    conn = db.get_conn()
    msg_id = str(uuid.uuid4())
    content_payload = {"text": message_text}
    try:
        if db.use_sqlite:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO chat_history (id, session_id, user_email, role, message_content)
                VALUES (?, ?, ?, ?, ?);
            """, (msg_id, session_id, user_email, role, json.dumps(content_payload)))
            conn.commit()
        else:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO chat_history (id, session_id, user_email, role, message_content)
                    VALUES (%s, %s, %s, %s, %s);
                """, (msg_id, session_id, user_email, role, Json(content_payload)))
                conn.commit()
    except Exception as e:
        print(f"Error saving chat message: {e}")
    finally:
        db.put_conn(conn)

def get_chat_history(session_id, limit=20):
    conn = db.get_conn()
    try:
        if db.use_sqlite:
            cur = conn.cursor()
            # Fetch last 20 messages matching session_id in chronological order
            cur.execute("""
                SELECT role, message_content
                FROM (
                    SELECT role, message_content, created_at
                    FROM chat_history
                    WHERE session_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ) sub
                ORDER BY created_at ASC;
            """, (session_id, limit))
            rows = cur.fetchall()
            chat_list = []
            for r in rows:
                content = json.loads(r[1])
                chat_list.append({"role": r[0], "content": content["text"]})
            return chat_list
        else:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT role, message_content
                    FROM (
                        SELECT role, message_content, created_at
                        FROM chat_history
                        WHERE session_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                    ) sub
                    ORDER BY created_at ASC;
                """, (session_id, limit))
                rows = cur.fetchall()
                return [{"role": r[0], "content": r[1]["text"]} for r in rows]
    except Exception as e:
        print(f"Error getting chat history: {e}")
        return []
    finally:
        db.put_conn(conn)

def clear_chat_history(session_id):
    conn = db.get_conn()
    try:
        if db.use_sqlite:
            cur = conn.cursor()
            cur.execute("DELETE FROM chat_history WHERE session_id = ?;", (session_id,))
            conn.commit()
        else:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM chat_history WHERE session_id = %s;", (session_id,))
                conn.commit()
    except Exception as e:
        print(f"Error clearing chat history: {e}")
    finally:
        db.put_conn(conn)
