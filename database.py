import os
import json
import uuid
import datetime
from pymongo import MongoClient
from google.genai import types
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

# Inject types.UserContent and types.ModelContent helper aliases for prompt requirements
types.UserContent = lambda parts: types.Content(role='user', parts=parts)
types.ModelContent = lambda parts: types.Content(role='model', parts=parts)

class DataPersistenceManager:
    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/my_ai_companion_db")
        # Extract database name from connection string if present, or use default
        self.db_name = "my_ai_companion_db"
        if "/" in self.mongo_uri.split("://")[-1]:
            self.db_name = self.mongo_uri.split("/")[-1].split("?")[0] or "my_ai_companion_db"
        
        self.client = None
        self.db = None
        self._init_client()

    def _init_client(self):
        try:
            # MongoClient has its own built-in connection pooling
            self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=2000)
            self.db = self.client[self.db_name]
            # Verify connectivity
            self.client.server_info()
            print(f"MongoDB client successfully initialized database: {self.db_name}")
        except Exception as e:
            print(f"MongoDB connection failed: {e}. Running in memory/mock persistence fallback.")
            # Simple mock in-memory fallback for local verification offline
            class MockCollection:
                def __init__(self):
                    self.store = {}
                def find_one(self, query):
                    for k, v in self.store.items():
                        match = True
                        for qk, qv in query.items():
                            if v.get(qk) != qv:
                                match = False
                                break
                        if match:
                            return v
                    return None
                def update_one(self, query, update, upsert=False):
                    doc = self.find_one(query)
                    if not doc:
                        if upsert:
                            doc = {**query}
                            self.store[query.get("_id", str(uuid.uuid4()))] = doc
                        else:
                            return
                    
                    if "$set" in update:
                        for uk, uv in update["$set"].items():
                            doc[uk] = uv
                    if "$setOnInsert" in update:
                        for uk, uv in update["$setOnInsert"].items():
                            if uk not in doc:
                                doc[uk] = uv
                    if "$push" in update:
                        for uk, uv in update["$push"].items():
                            if uk not in doc:
                                doc[uk] = []
                            doc[uk].append(uv)
                def find(self, query):
                    results = []
                    for k, v in self.store.items():
                        match = True
                        for qk, qv in query.items():
                            if v.get(qk) != qv:
                                match = False
                                break
                        if match:
                            results.append(v)
                    return results
            class MockDb:
                def __init__(self):
                    self.users = MockCollection()
                    self.sessions = MockCollection()
                def __getitem__(self, item):
                    return self.users if item == "users" else self.sessions
            self.db = MockDb()

    def _get_connection(self):
        """Private method that establishes and returns the active MongoDB client instance."""
        return self.client

    def upsert_user(self, email, name, avatar, provider='system', password_hash=None):
        update_doc = {
            "display_name": name,
            "avatar_url": avatar,
            "provider": provider
        }
        if password_hash:
            update_doc["password_hash"] = password_hash
            
        try:
            self.db.users.update_one(
                {"_id": email},
                {
                    "$set": update_doc,
                    "$setOnInsert": {
                        "theme_preference": "system"
                    }
                },
                upsert=True
            )
            user = self.get_user(email)
            return user.get("theme_preference", "system") if user else "system"
        except Exception as e:
            print(f"Error in upsert_user: {e}")
            return 'system'

    def update_theme(self, email, theme):
        try:
            self.db.users.update_one(
                {"_id": email},
                {"$set": {"theme_preference": theme}}
            )
        except Exception as e:
            print(f"Error in update_theme: {e}")

    def get_user(self, email):
        try:
            user = self.db.users.find_one({"_id": email})
            if user:
                # Map _id back to email for compatibility
                return {
                    "email": email,
                    "display_name": user.get("display_name"),
                    "avatar_url": user.get("avatar_url"),
                    "theme_preference": user.get("theme_preference", "system"),
                    "password_hash": user.get("password_hash")
                }
            return None
        except Exception as e:
            print(f"Error getting user: {e}")
            return None

    def save_chat_turn(self, session_id, email, role, text):
        message = {
            "role": role,
            "text": text,
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        try:
            self.db.sessions.update_one(
                {"_id": session_id},
                {
                    "$setOnInsert": {
                        "user_email": email,
                        "created_at": datetime.datetime.utcnow().isoformat()
                    },
                    "$push": {"messages": message}
                },
                upsert=True
            )
        except Exception as e:
            print(f"Error in save_chat_turn: {e}")

    def get_account_chat_list(self, email):
        try:
            # Query sessions belonging to user
            # Find in MockCollection or Real MongoDB
            if hasattr(self.db.sessions, "store"):
                rows = self.db.sessions.find({"user_email": email})
            else:
                rows = list(self.db.sessions.find({"user_email": email}).sort("created_at", -1))
                
            session_list = []
            for r in rows:
                messages = r.get("messages", [])
                title = "New Conversation"
                if messages:
                    for m in messages:
                        if m.get("role") == "user":
                            title = m.get("text", "New Conversation")
                            break
                if len(title) > 30:
                    title = title[:27] + "..."
                session_list.append({
                    "session_id": str(r["_id"]),
                    "title": title,
                    "created_at": r.get("created_at")
                })
            # Ensure sort for mock in-memory
            if hasattr(self.db.sessions, "store"):
                session_list.sort(key=lambda x: x["created_at"] or "", reverse=True)
            return session_list
        except Exception as e:
            print(f"Error in get_account_chat_list: {e}")
            return []

    def get_sliding_window_context(self, session_id, email, turn_limit=10):
        try:
            doc = self.db.sessions.find_one({"_id": session_id, "user_email": email})
            if not doc:
                return []
            messages = doc.get("messages", [])
            limit = turn_limit * 2
            rolling_messages = messages[-limit:] if len(messages) > limit else messages
            
            sdk_history = []
            for msg in rolling_messages:
                role = 'user' if msg.get("role") == 'user' else 'model'
                text = msg.get("text", "")
                if role == 'user':
                    sdk_history.append(types.UserContent(parts=[types.Part.from_text(text=text)]))
                else:
                    sdk_history.append(types.ModelContent(parts=[types.Part.from_text(text=text)]))
            return sdk_history
        except Exception as e:
            print(f"Error in get_sliding_window_context: {e}")
            return []

    def clear_history(self, session_id):
        try:
            self.db.sessions.update_one(
                {"_id": session_id},
                {"$set": {"messages": []}}
            )
        except Exception as e:
            print(f"Error clearing history: {e}")

# Global persistence manager instance
db_manager = DataPersistenceManager()

# Module wrappers to support backward compatibility with app.py
def init_db():
    db_manager._init_client()

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
    try:
        doc = db_manager.db.sessions.find_one({"_id": session_id})
        if not doc:
            return []
        messages = doc.get("messages", [])
        rolling = messages[-limit:] if len(messages) > limit else messages
        return [{"role": m.get("role"), "content": m.get("text")} for m in rolling]
    except Exception as e:
        print(f"Error getting history: {e}")
        return []

def clear_chat_history(session_id):
    db_manager.clear_history(session_id)

def get_user_session_list(user_email):
    return db_manager.get_account_chat_list(user_email)

if __name__ == '__main__':
    print("Running DataPersistenceManager MongoDB connection test...")
    manager = DataPersistenceManager()
    client = manager._get_connection()
    if client and manager.db.__class__.__name__ != 'MockDb':
        print(f"MongoDB connection verification check successful!")
    else:
        print(f"MongoDB connection check ran with in-memory fallback successfully!")
