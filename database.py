import os
import json
import psycopg2
import urllib.parse
from psycopg2 import pool
from psycopg2.extras import RealDictCursor, Json
import sqlite3
import uuid
from google.genai import types
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

# Inject types.UserContent and types.ModelContent helper aliases for prompt requirements
types.UserContent = lambda parts: types.Content(role='user', parts=parts)
types.ModelContent = lambda parts: types.Content(role='model', parts=parts)

class DataPersistenceManager:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/my_ai_companion_db")
        self.use_sqlite = False
        self.sqlite_db_path = "my_ai_companion.db"
        self.pool = None
        self._init_pool()

    def _init_pool(self):
        try:
            if "postgresql" not in self.database_url:
                self.use_sqlite = True
                return
            
            # Parse database name to ensure it exists
            url_parsed = urllib.parse.urlparse(self.database_url)
            target_db = url_parsed.path[1:]
            postgres_url = self.database_url.replace(f"/{target_db}", "/postgres")
            
            conn = psycopg2.connect(postgres_url)
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
                if not cur.fetchone():
                    print(f"Database '{target_db}' does not exist. Creating...")
                    cur.execute(f'CREATE DATABASE "{target_db}"')
            conn.close()
            
            # Initialize connection pool
            self.pool = pool.SimpleConnectionPool(1, 20, dsn=self.database_url)
            self._migrate_db()
            print("PostgreSQL connection pool setup successful.")
        except Exception as e:
            print(f"PostgreSQL connection pool setup failed: {e}. Falling back to SQLite.")
            self.use_sqlite = True
            self._migrate_db()

    def _get_connection(self):
        """Private method to get connection from pool or SQLite."""
        if self.use_sqlite:
            conn = sqlite3.connect(self.sqlite_db_path)
            conn.row_factory = sqlite3.Row
            return conn
        
        conn = self.pool.getconn()
        conn.cursor_factory = RealDictCursor
        return conn

    def _put_connection(self, conn):
        if self.use_sqlite:
            if conn:
                conn.close()
        else:
            if self.pool and conn:
                self.pool.putconn(conn)

    def _migrate_db(self):
        conn = self._get_connection()
        try:
            if self.use_sqlite:
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS companion_users (
                        email TEXT PRIMARY KEY,
                        display_name TEXT NOT NULL,
                        avatar_url TEXT,
                        theme_preference TEXT DEFAULT 'system',
                        password_hash TEXT
                    );
                """)
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
                conn.commit()
            else:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS companion_users (
                            email VARCHAR(255) PRIMARY KEY,
                            display_name VARCHAR(255) NOT NULL,
                            avatar_url TEXT,
                            theme_preference VARCHAR(20) DEFAULT 'system',
                            password_hash VARCHAR(255)
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
                    conn.commit()
        except Exception as e:
            print(f"Migration error: {e}")
        finally:
            self._put_connection(conn)

    def upsert_user(self, email, name, avatar, provider='system', password_hash=None):
        conn = self._get_connection()
        try:
            if self.use_sqlite:
                cur = conn.cursor()
                cur.execute("SELECT theme_preference FROM companion_users WHERE email = ?;", (email,))
                row = cur.fetchone()
                if row:
                    theme = row[0]
                    if password_hash:
                        cur.execute("""
                            UPDATE companion_users 
                            SET display_name = ?, avatar_url = ?, password_hash = ?
                            WHERE email = ?;
                        """, (name, avatar, password_hash, email))
                    else:
                        cur.execute("""
                            UPDATE companion_users 
                            SET display_name = ?, avatar_url = ?
                            WHERE email = ?;
                        """, (name, avatar, email))
                else:
                    theme = 'system'
                    cur.execute("""
                        INSERT INTO companion_users (email, display_name, avatar_url, theme_preference, password_hash)
                        VALUES (?, ?, ?, ?, ?);
                    """, (email, name, avatar, theme, password_hash))
                conn.commit()
                return theme
            else:
                with conn.cursor() as cur:
                    if password_hash:
                        cur.execute("""
                            INSERT INTO companion_users (email, display_name, avatar_url, password_hash)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (email) DO UPDATE 
                            SET display_name = EXCLUDED.display_name, 
                                avatar_url = EXCLUDED.avatar_url,
                                password_hash = EXCLUDED.password_hash
                            RETURNING theme_preference;
                        """, (email, name, avatar, password_hash))
                    else:
                        cur.execute("""
                            INSERT INTO companion_users (email, display_name, avatar_url)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (email) DO UPDATE 
                            SET display_name = EXCLUDED.display_name, 
                                avatar_url = EXCLUDED.avatar_url
                            RETURNING theme_preference;
                        """, (email, name, avatar))
                    row = cur.fetchone()
                    conn.commit()
                    return row['theme_preference'] if row else 'system'
        except Exception as e:
            print(f"Error in upsert_user: {e}")
            return 'system'
        finally:
            self._put_connection(conn)

    def update_theme(self, email, theme):
        conn = self._get_connection()
        try:
            if self.use_sqlite:
                cur = conn.cursor()
                cur.execute("UPDATE companion_users SET theme_preference = ? WHERE email = ?;", (theme, email))
                conn.commit()
            else:
                with conn.cursor() as cur:
                    cur.execute("UPDATE companion_users SET theme_preference = %s WHERE email = %s;", (theme, email))
                    conn.commit()
        except Exception as e:
            print(f"Error in update_theme: {e}")
        finally:
            self._put_connection(conn)

    def get_user(self, email):
        conn = self._get_connection()
        try:
            if self.use_sqlite:
                cur = conn.cursor()
                cur.execute("SELECT email, display_name, avatar_url, theme_preference, password_hash FROM companion_users WHERE email = ?;", (email,))
                r = cur.fetchone()
                if r:
                    return {
                        "email": r[0],
                        "display_name": r[1],
                        "avatar_url": r[2],
                        "theme_preference": r[3],
                        "password_hash": r[4]
                    }
                return None
            else:
                with conn.cursor() as cur:
                    cur.execute("SELECT email, display_name, avatar_url, theme_preference, password_hash FROM companion_users WHERE email = %s;", (email,))
                    return cur.fetchone()
        except Exception as e:
            print(f"Error getting user: {e}")
            return None
        finally:
            self._put_connection(conn)

    def save_chat_turn(self, session_id, email, role, text):
        conn = self._get_connection()
        msg_id = str(uuid.uuid4())
        content_payload = {"text": text}
        try:
            if self.use_sqlite:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO chat_history (id, session_id, user_email, role, message_content)
                    VALUES (?, ?, ?, ?, ?);
                """, (msg_id, session_id, email, role, json.dumps(content_payload)))
                conn.commit()
            else:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO chat_history (id, session_id, user_email, role, message_content)
                        VALUES (%s, %s, %s, %s, %s);
                    """, (msg_id, session_id, email, role, Json(content_payload)))
                    conn.commit()
        except Exception as e:
            print(f"Error in save_chat_turn: {e}")
        finally:
            self._put_connection(conn)

    def get_account_chat_list(self, email):
        conn = self._get_connection()
        try:
            if self.use_sqlite:
                cur = conn.cursor()
                cur.execute("""
                    SELECT session_id, message_content, MIN(created_at) as created_at
                    FROM chat_history
                    WHERE user_email = ? AND role = 'user'
                    GROUP BY session_id
                    ORDER BY created_at DESC;
                """, (email,))
                rows = cur.fetchall()
                session_list = []
                for r in rows:
                    try:
                        content = json.loads(r[1])
                        title = content.get("text", "New Conversation")
                    except Exception:
                        title = "New Conversation"
                    if len(title) > 30:
                        title = title[:27] + "..."
                    session_list.append({
                        "session_id": r[0],
                        "title": title,
                        "created_at": r[2]
                    })
                return session_list
            else:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT DISTINCT ON (session_id) session_id, message_content, created_at 
                        FROM chat_history 
                        WHERE user_email = %s AND role = 'user'
                        ORDER BY session_id, created_at DESC;
                    """, (email,))
                    rows = cur.fetchall()
                    session_list = []
                    for r in rows:
                        title = r['message_content'].get("text", "New Conversation")
                        if len(title) > 30:
                            title = title[:27] + "..."
                        session_list.append({
                            "session_id": str(r['session_id']),
                            "title": title,
                            "created_at": r['created_at']
                        })
                    return session_list
        except Exception as e:
            print(f"Error in get_account_chat_list: {e}")
            return []
        finally:
            self._put_connection(conn)

    def get_sliding_window_context(self, session_id, email, turn_limit=10):
        conn = self._get_connection()
        limit = turn_limit * 2
        try:
            if self.use_sqlite:
                cur = conn.cursor()
                cur.execute("""
                    SELECT role, message_content FROM (
                        SELECT role, message_content, created_at, rowid FROM chat_history
                        WHERE session_id = ? AND user_email = ?
                        ORDER BY created_at DESC, rowid DESC LIMIT ?
                    ) AS rolling_window ORDER BY created_at ASC, rowid ASC;
                """, (session_id, email, limit))
                rows = cur.fetchall()
                sdk_history = []
                for r in rows:
                    role = 'user' if r[0] == 'user' else 'model'
                    content = json.loads(r[1])
                    text = content.get("text", "")
                    
                    if role == 'user':
                        sdk_history.append(types.UserContent(parts=[types.Part.from_text(text=text)]))
                    else:
                        sdk_history.append(types.ModelContent(parts=[types.Part.from_text(text=text)]))
                return sdk_history
            else:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT role, message_content FROM (
                            SELECT role, message_content, created_at FROM chat_history
                            WHERE session_id = %s AND user_email = %s
                            ORDER BY created_at DESC LIMIT %s
                        ) AS rolling_window ORDER BY created_at ASC;
                    """, (session_id, email, limit))
                    rows = cur.fetchall()
                    sdk_history = []
                    for r in rows:
                        role = 'user' if r['role'] == 'user' else 'model'
                        text = r['message_content'].get("text", "")
                        
                        if role == 'user':
                            sdk_history.append(types.UserContent(parts=[types.Part.from_text(text=text)]))
                        else:
                            sdk_history.append(types.ModelContent(parts=[types.Part.from_text(text=text)]))
                    return sdk_history
        except Exception as e:
            print(f"Error in get_sliding_window_context: {e}")
            return []
        finally:
            self._put_connection(conn)

    def clear_history(self, session_id):
        conn = self._get_connection()
        try:
            if self.use_sqlite:
                cur = conn.cursor()
                cur.execute("DELETE FROM chat_history WHERE session_id = ?;", (session_id,))
                conn.commit()
            else:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM chat_history WHERE session_id = %s;", (session_id,))
                    conn.commit()
        except Exception as e:
            print(f"Error clearing history: {e}")
        finally:
            self._put_connection(conn)

# Global persistence manager instance
db_manager = DataPersistenceManager()

# Module wrappers to support backward compatibility with app.py
def init_db():
    db_manager._init_pool()

def get_user(email):
    return db_manager.get_user(email)

def upsert_user(email, name, avatar, provider='system', password_hash=None):
    theme = db_manager.upsert_user(email, name, avatar, provider, password_hash)
    return {
        "email": email,
        "display_name": name,
        "avatar_url": avatar,
        "theme_preference": theme
    }

def update_user_theme(email, theme):
    db_manager.update_theme(email, theme)

def save_chat_message(session_id, user_email, role, message_text):
    db_manager.save_chat_turn(session_id, user_email, role, message_text)

def get_chat_history(session_id, limit=20):
    conn = db_manager._get_connection()
    try:
        if db_manager.use_sqlite:
            cur = conn.cursor()
            cur.execute("""
                SELECT role, message_content FROM (
                    SELECT role, message_content, created_at, rowid FROM chat_history
                    WHERE session_id = ?
                    ORDER BY created_at DESC, rowid DESC LIMIT ?
                ) AS sub ORDER BY created_at ASC, rowid ASC;
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
                    SELECT role, message_content FROM (
                        SELECT role, message_content, created_at FROM chat_history
                        WHERE session_id = %s
                        ORDER BY created_at DESC LIMIT %s
                    ) AS sub ORDER BY created_at ASC;
                """, (session_id, limit))
                rows = cur.fetchall()
                return [{"role": r['role'], "content": r['message_content']["text"]} for r in rows]
    except Exception as e:
        print(f"Error getting history: {e}")
        return []
    finally:
        db_manager._put_connection(conn)

def clear_chat_history(session_id):
    db_manager.clear_history(session_id)

def get_user_session_list(user_email):
    return db_manager.get_account_chat_list(user_email)

if __name__ == '__main__':
    print("Running DataPersistenceManager connection test...")
    manager = DataPersistenceManager()
    conn = None
    try:
        conn = manager._get_connection()
        if manager.use_sqlite:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM companion_users;")
            count = cur.fetchone()[0]
            print(f"SQLite connection successful! Total user count: {count}")
        else:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM companion_users;")
                count = cur.fetchone()['count']
                print(f"PostgreSQL connection pool binding successful! Total user count: {count}")
    except Exception as e:
        print(f"DataPersistenceManager verification check failed: {e}")
    finally:
        if conn:
            manager._put_connection(conn)
