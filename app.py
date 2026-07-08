import os
import uuid
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from dotenv import load_dotenv

# Load environment configuration
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "secure-dev-session-key-fallback-18239823")

# Import database module
from database import init_db, get_user, upsert_user, update_user_theme, save_chat_message, get_chat_history, clear_chat_history

# Initialize Database Schema
try:
    init_db()
except Exception as err:
    print(f"Database schema init warning: {err}. Proceeding with app startup.")

# Initialize Google GenAI client
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ai_client = None

if GEMINI_API_KEY and GEMINI_API_KEY != "your_google_ai_studio_api_key_here":
    try:
        from google import genai
        from google.genai import types
        ai_client = genai.Client(api_key=GEMINI_API_KEY)
        print("Google GenAI client initialized successfully.")
    except Exception as e:
        print(f"Error initializing GenAI client: {e}")
else:
    print("Warning: GEMINI_API_KEY not configured. Application will run in Mock Companion mode.")

# Authentication Decorator Shield
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'user_email' in session:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))

@app.route('/auth/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if not email or not password:
            flash('Both email and password inputs are required.', 'error')
            return redirect(url_for('login'))
            
        # Check database or auto-register user for high-fidelity experience
        user = get_user(email)
        if not user:
            # Create user dynamically with premium visual avatar details
            avatar_url = 'https://lh3.googleusercontent.com/aida-public/AB6AXuCSEkmmpfhz2RW-n5NMsFRT7ZMTNaBmoLdT8bxrCGAJP1k2ZnX4ZFuDCkTqINrUNux_1-qJoM_8tTC3hzoPREZj5VtbtgBnHJc7XmySi-wN6f59XG4ybOuqTNGk68K5Lba6hS7ck6HwbmgpGpgXQFFWmlKJnOn4wEtidVeC9GtJUk82zroHKDF9L8eOmQB1fQYcQffx5nnmzBiMvTnuVRO1S3XArBsAee0i3DcCfttZc-vkurpzybcuYSGsoVUQIsrNfNwvim5Cepcf'
            display_name = email.split('@')[0].capitalize()
            user = upsert_user(email, display_name, avatar_url, 'system')
            
        session['user_email'] = user['email']
        session['display_name'] = user['display_name']
        session['avatar_url'] = user['avatar_url']
        
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
            
        return redirect(url_for('chat'))
        
    if 'user_email' in session:
        return redirect(url_for('chat'))
        
    return render_template('login.html', theme_preference='system')

@app.route('/auth/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/chat')
@login_required
def chat():
    user = get_user(session['user_email'])
    theme = user['theme_preference'] if user else 'system'
    history = get_chat_history(session['session_id'], limit=20)
    return render_template('chat.html', history=history, theme_preference=theme)

@app.route('/account')
@login_required
def account():
    user = get_user(session['user_email'])
    theme = user['theme_preference'] if user else 'system'
    return render_template('account.html', user=user, theme_preference=theme)

@app.route('/account/update', methods=['POST'])
@login_required
def account_update():
    name = request.form.get('display_name', '').strip()
    avatar = request.form.get('avatar_url', '').strip()
    if name:
        upsert_user(session['user_email'], name, avatar)
        session['display_name'] = name
        session['avatar_url'] = avatar
        flash('Account details updated successfully.', 'success')
    else:
        flash('Name cannot be empty.', 'error')
    return redirect(url_for('account'))

# API - Theme Sync Route
@app.route('/api/theme', methods=['POST'])
@login_required
def set_theme():
    data = request.get_json() or {}
    theme = data.get('theme', 'system')
    if theme in ('light', 'dark', 'system'):
        update_user_theme(session['user_email'], theme)
        return jsonify({"status": "success"})
    return jsonify({"error": "Invalid theme selection"}), 400

# API - Clear Chat Route
@app.route('/api/clear_chat', methods=['POST'])
@login_required
def clear_chat():
    session_id = session.get('session_id')
    if session_id:
        clear_chat_history(session_id)
        session['session_id'] = str(uuid.uuid4()) # Fresh session token
        return jsonify({"status": "success"})
    return jsonify({"error": "No active session ID"}), 400

# API - Chat Interaction Endpoint
@app.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    data = request.get_json() or {}
    message_text = data.get('message', '').strip()

    # Structural Validation Gate
    if not message_text:
        return jsonify({"error": "Prompt message cannot be empty or blank."}), 400

    session_id = session['session_id']
    user_email = session['user_email']

    # 1. Append active turn to PostgreSQL database
    save_chat_message(session_id, user_email, 'user', message_text)

    # 2. Query the sliding window history (last 20 messages)
    history = get_chat_history(session_id, limit=20)

    # Remove the last message from history if we want to pass it as the new prompt,
    # or pass the history up to the current turn to the Chat session.
    # Typically, the history passed to Chats.create contains the past turns (excluding the latest),
    # and then we call send_message with the latest.
    past_history = history[:-1] if len(history) > 1 else []

    reply_text = ""

    # 3. Generate response using Gemini client or fallback mock
    if ai_client:
        try:
            from google.genai import types
            
            # Format raw database history into Google SDK types
            sdk_history = []
            last_role = None
            for h_msg in past_history:
                role = h_msg['role']
                # Google SDK uses 'user' and 'model'
                role = 'user' if role == 'user' else 'model'
                
                # Enforce alternating role validation check
                if role == last_role:
                    continue
                sdk_history.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=h_msg['content'])]
                    )
                )
                last_role = role

            # Create the chat conversation session
            chat_session = ai_client.chats.create(
                model="gemini-2.5-flash",
                history=sdk_history
            )
            
            # Run the conversation turn
            response = chat_session.send_message(message_text)
            reply_text = response.text
            
        except Exception as e:
            print(f"Gemini API execution error: {e}")
            reply_text = f"Companion encountered an error: {str(e)}. (Running in fallback mode)"
    else:
        # Fallback Mock Mode response
        reply_text = f"Hello! I received your prompt: \"{message_text}\". (Note: GEMINI_API_KEY is not configured in your .env file, so I am running in local Echo Companion mode. Please supply your API key to activate full Gemini brains!)"

    # 4. Save generated response to backend database
    save_chat_message(session_id, user_email, 'model', reply_text)

    # Return response payload
    return jsonify({"reply": reply_text})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
