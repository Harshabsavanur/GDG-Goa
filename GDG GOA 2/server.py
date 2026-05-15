"""
AthleticConnect — Flask Backend Server
Serves the frontend, REST APIs, authentication, and AI coaching proxy.
"""

import os
import json
import functools
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from database import get_db, init_db

# ── Loading Environment ─────────────────────────────────────────
load_dotenv()

app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app)

JWT_SECRET = os.getenv('JWT_SECRET', 'athleticconnect-default-secret')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')


# ══════════════════════════════════════════════════════════════
#  AUTH MIDDLEWARE harsha
# ══════════════════════════════════════════════════════════════

def auth_required(f):
    """Decorator that verifies JWT token and injects user info."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Access token required. Please log in.'}), 401

        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            request.user = payload  # { id, email, name }
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired. Please log in again.'}), 403
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token. Please log in again.'}), 403

        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════════════════════
#  STATIC FILE SERVING
# ══════════════════════════════════════════════════════════════

@app.route('/')
def serve_index():
    return send_from_directory('public', 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    # Try to serve as static file, fallback to index.html (SPA)
    file_path = os.path.join(app.static_folder, path)
    if os.path.isfile(file_path):
        return send_from_directory('public', path)
    return send_from_directory('public', 'index.html')


# ══════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    location = (data.get('location') or '').strip()
    sports = data.get('sports', [])

    if not name or not email or not password:
        return jsonify({'error': 'Name, email, and password are required.'}), 400
    if len(password) < 4:
        return jsonify({'error': 'Password must be at least 4 characters.'}), 400

    conn = get_db()
    try:
        existing = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            return jsonify({'error': 'An account with this email already exists.'}), 409

        pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        initials = ''.join(w[0] for w in name.split() if w)[:2].upper()

        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, location, sports, avatar_initials) VALUES (?,?,?,?,?,?)",
            (name, email, pw_hash, location, json.dumps(sports), initials)
        )
        user_id = cur.lastrowid

        # Create initial weekly stats
        conn.execute(
            "INSERT INTO weekly_stats (user_id, calories, active_minutes, points, week_start) VALUES (?,0,0,0,date('now'))",
            (user_id,)
        )
        conn.commit()

        token = jwt.encode(
            {'id': user_id, 'email': email, 'name': name,
             'exp': datetime.now(timezone.utc) + timedelta(days=7)},
            JWT_SECRET, algorithm='HS256'
        )

        return jsonify({
            'token': token,
            'user': {'id': user_id, 'name': name, 'email': email, 'avatar_initials': initials}
        }), 201
    finally:
        conn.close()


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({'error': 'Email and password are required.'}), 400

    conn = get_db()
    try:
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if not user:
            return jsonify({'error': 'Invalid email or password.'}), 401

        if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            return jsonify({'error': 'Invalid email or password.'}), 401

        token = jwt.encode(
            {'id': user['id'], 'email': user['email'], 'name': user['name'],
             'exp': datetime.now(timezone.utc) + timedelta(days=7)},
            JWT_SECRET, algorithm='HS256'
        )

        return jsonify({
            'token': token,
            'user': {
                'id': user['id'], 'name': user['name'],
                'email': user['email'], 'avatar_initials': user['avatar_initials']
            }
        })
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════

@app.route('/api/dashboard')
@auth_required
def dashboard():
    user_id = request.user['id']
    conn = get_db()
    try:
        stats = conn.execute(
            "SELECT calories, active_minutes, points FROM weekly_stats WHERE user_id = ? ORDER BY week_start DESC LIMIT 1",
            (user_id,)
        ).fetchone()

        friend_count = conn.execute(
            "SELECT COUNT(*) as count FROM friendships WHERE user_id = ?", (user_id,)
        ).fetchone()['count']

        activities = conn.execute(
            "SELECT type, distance_km, duration_minutes, calories, description, date FROM activities WHERE user_id = ? ORDER BY date DESC LIMIT 5",
            (user_id,)
        ).fetchall()

        return jsonify({
            'stats': {
                'calories': stats['calories'] if stats else 0,
                'minutes': stats['active_minutes'] if stats else 0,
                'points': stats['points'] if stats else 0,
                'friends': friend_count
            },
            'recentActivities': [dict(a) for a in activities]
        })
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
#  PROFILE
# ══════════════════════════════════════════════════════════════

@app.route('/api/profile')
@auth_required
def get_profile():
    user_id = request.user['id']
    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, name, email, location, sports, avatar_initials, created_at FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        if not user:
            return jsonify({'error': 'User not found.'}), 404

        user_dict = dict(user)
        user_dict['sports'] = json.loads(user_dict.get('sports') or '[]')

        pbs = conn.execute(
            "SELECT event_name, time_display FROM personal_bests WHERE user_id = ? ORDER BY event_name",
            (user_id,)
        ).fetchall()

        total_activities = conn.execute(
            "SELECT COUNT(*) as count FROM activities WHERE user_id = ?", (user_id,)
        ).fetchone()['count']

        total_distance = conn.execute(
            "SELECT COALESCE(SUM(distance_km), 0) as total FROM activities WHERE user_id = ?", (user_id,)
        ).fetchone()['total']

        achievements = []
        if total_activities >= 1: achievements.append({'icon': '🥇', 'label': 'First Workout'})
        if total_activities >= 5: achievements.append({'icon': '🔥', 'label': '5 Workouts'})
        if total_distance >= 10: achievements.append({'icon': '🚀', 'label': '10km Total'})
        if total_distance >= 50: achievements.append({'icon': '💎', 'label': '50km Club'})
        if total_activities >= 20: achievements.append({'icon': '⭐', 'label': '20 Workouts'})
        if total_distance >= 100: achievements.append({'icon': '👑', 'label': '100km Legend'})

        return jsonify({
            'user': user_dict,
            'personalBests': [dict(p) for p in pbs],
            'achievements': achievements
        })
    finally:
        conn.close()


@app.route('/api/profile', methods=['PUT'])
@auth_required
def update_profile():
    user_id = request.user['id']
    data = request.get_json()
    conn = get_db()
    try:
        updates, values = [], []
        if data.get('name'):
            updates.append('name = ?')
            values.append(data['name'])
            initials = ''.join(w[0] for w in data['name'].split() if w)[:2].upper()
            updates.append('avatar_initials = ?')
            values.append(initials)
        if 'location' in data:
            updates.append('location = ?')
            values.append(data['location'])
        if data.get('sports'):
            updates.append('sports = ?')
            values.append(json.dumps(data['sports']))

        if not updates:
            return jsonify({'error': 'No fields to update.'}), 400

        values.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
        return jsonify({'message': 'Profile updated successfully.'})
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
#  CHALLENGES
# ══════════════════════════════════════════════════════════════

@app.route('/api/challenges')
@auth_required
def get_challenges():
    user_id = request.user['id']
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT c.id, c.title, c.description, c.duration_days, c.target, c.icon,
                   uc.joined_at, uc.progress
            FROM challenges c
            LEFT JOIN user_challenges uc ON c.id = uc.challenge_id AND uc.user_id = ?
            ORDER BY c.id
        """, (user_id,)).fetchall()

        challenges = [{
            'id': r['id'], 'title': r['title'], 'description': r['description'],
            'duration_days': r['duration_days'], 'target': r['target'], 'icon': r['icon'],
            'joined': r['joined_at'] is not None,
            'progress': r['progress'] or None,
            'joined_at': r['joined_at']
        } for r in rows]

        return jsonify({'challenges': challenges})
    finally:
        conn.close()


@app.route('/api/challenges/<int:challenge_id>/join', methods=['POST'])
@auth_required
def join_challenge(challenge_id):
    user_id = request.user['id']
    conn = get_db()
    try:
        challenge = conn.execute("SELECT id, title FROM challenges WHERE id = ?", (challenge_id,)).fetchone()
        if not challenge:
            return jsonify({'error': 'Challenge not found.'}), 404

        existing = conn.execute(
            "SELECT id FROM user_challenges WHERE user_id = ? AND challenge_id = ?",
            (user_id, challenge_id)
        ).fetchone()
        if existing:
            return jsonify({'error': 'You have already joined this challenge.'}), 409

        conn.execute(
            "INSERT INTO user_challenges (user_id, challenge_id, progress) VALUES (?,?,?)",
            (user_id, challenge_id, "Just started!")
        )
        conn.commit()
        return jsonify({'message': f'Joined "{challenge["title"]}" successfully!'}), 201
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
#  COMMUNITY
# ══════════════════════════════════════════════════════════════

def time_ago(dt_str):
    """Return a human-readable 'time ago' string."""
    try:
        then = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        diff = now - then
        seconds = diff.total_seconds()

        if seconds < 60: return 'just now'
        if seconds < 3600: return f'{int(seconds // 60)}m ago'
        if seconds < 86400: return f'{int(seconds // 3600)}h ago'
        if seconds < 604800: return f'{int(seconds // 86400)}d ago'
        return then.strftime('%b %d')
    except Exception:
        return ''


@app.route('/api/community/feed')
@auth_required
def community_feed():
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT cp.id, cp.content, cp.post_type, cp.metadata, cp.created_at,
                   u.name as author_name, u.avatar_initials
            FROM community_posts cp
            JOIN users u ON cp.user_id = u.id
            ORDER BY cp.created_at DESC LIMIT 20
        """).fetchall()

        posts = [{
            'id': r['id'], 'content': r['content'], 'post_type': r['post_type'],
            'metadata': json.loads(r['metadata'] or '{}'),
            'created_at': r['created_at'],
            'author': {'name': r['author_name'], 'initials': r['avatar_initials']},
            'timeAgo': time_ago(r['created_at'])
        } for r in rows]

        return jsonify({'posts': posts})
    finally:
        conn.close()


@app.route('/api/community/post', methods=['POST'])
@auth_required
def create_post():
    user_id = request.user['id']
    data = request.get_json()
    content = (data.get('content') or '').strip()

    if not content:
        return jsonify({'error': 'Post content is required.'}), 400

    post_type = data.get('post_type', 'update')
    metadata = data.get('metadata', {})

    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO community_posts (user_id, content, post_type, metadata) VALUES (?,?,?,?)",
            (user_id, content, post_type, json.dumps(metadata))
        )
        conn.commit()

        user = conn.execute("SELECT name, avatar_initials FROM users WHERE id = ?", (user_id,)).fetchone()

        return jsonify({
            'post': {
                'id': cur.lastrowid, 'content': content, 'post_type': post_type,
                'metadata': metadata, 'created_at': datetime.now(timezone.utc).isoformat(),
                'author': {'name': user['name'], 'initials': user['avatar_initials']},
                'timeAgo': 'just now'
            }
        }), 201
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
#  AI COACH (Gemini Proxy)
# ══════════════════════════════════════════════════════════════

@app.route('/api/ai/chat', methods=['POST'])
@auth_required
def ai_chat():
    data = request.get_json()
    message = (data.get('message') or '').strip()
    history = data.get('history', [])

    if not message:
        return jsonify({'error': 'Message is required.'}), 400

    api_key = GEMINI_API_KEY
    if not api_key or api_key == 'your-gemini-api-key-here':
        return jsonify({
            'error': 'AI Coach is not configured. The server admin needs to set GEMINI_API_KEY in the .env file.'
        }), 503

    # Fetch user's real data from DB
    user_id = request.user['id']
    conn = get_db()
    try:
        user = conn.execute("SELECT name, location, sports FROM users WHERE id = ?", (user_id,)).fetchone()
        pbs = conn.execute("SELECT event_name, time_display FROM personal_bests WHERE user_id = ?", (user_id,)).fetchall()
        stats = conn.execute(
            "SELECT calories, active_minutes, points FROM weekly_stats WHERE user_id = ? ORDER BY week_start DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        challenges = conn.execute("""
            SELECT c.title, uc.progress FROM user_challenges uc
            JOIN challenges c ON uc.challenge_id = c.id WHERE uc.user_id = ?
        """, (user_id,)).fetchall()
        recent = conn.execute(
            "SELECT type, distance_km, duration_minutes, description, date FROM activities WHERE user_id = ? ORDER BY date DESC LIMIT 1",
            (user_id,)
        ).fetchone()
    finally:
        conn.close()

    sports = json.loads(user['sports'] or '[]')
    pb_str = ', '.join(f"{p['event_name']} = {p['time_display']}" for p in pbs) or 'None recorded'
    ch_str = '; '.join(f"{c['title']} ({c['progress']})" for c in challenges) or 'None active'
    recent_str = (f"{recent['type']} — {recent['distance_km']}km in {recent['duration_minutes']} min ({recent['date']})"
                  if recent else 'No recent activity')

    system_prompt = f"""You are "Coach", the AI fitness coach inside the AthleticConnect app.

Your athlete's profile:
- Name: {user['name']}
- Location: {user['location']}
- Sports: {', '.join(sports)}
- Recent activity: {recent_str}
- Personal bests: {pb_str}
- This week: {stats['calories'] if stats else 0} calories burned, {stats['active_minutes'] if stats else 0} minutes active
- Active challenges: {ch_str}

Rules:
- Be encouraging, knowledgeable, and concise (keep replies under 150 words unless a detailed plan is requested).
- Reference the athlete's actual data when relevant.
- Cover: training plans, pacing, nutrition, recovery, injury prevention, motivation.
- Use occasional emojis for energy.
- If the user asks something unrelated to fitness/health, gently redirect."""

    # Build conversation
    contents = [{'role': h['role'], 'parts': [{'text': h['text']}]} for h in history]
    contents.append({'role': 'user', 'parts': [{'text': message}]})

    request_body = {
        'system_instruction': {'parts': [{'text': system_prompt}]},
        'contents': contents
    }

    # Try models with fallback
    selected = GEMINI_MODEL or 'gemini-2.5-flash'
    fallbacks = [m for m in ['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.5-pro'] if m != selected]
    models = [selected] + fallbacks

    last_error = None
    for model in models:
        try:
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
                json=request_body,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            if resp.status_code == 200:
                resp_data = resp.json()
                ai_text = (resp_data.get('candidates', [{}])[0]
                           .get('content', {}).get('parts', [{}])[0]
                           .get('text', "Sorry, I couldn't generate a response. Please try again."))
                return jsonify({'reply': ai_text})

            err_data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
            err_msg = err_data.get('error', {}).get('message', '')

            if 'quota' in err_msg.lower() or resp.status_code == 429:
                print(f"[WARN] Quota exceeded for {model}, trying next...")
                last_error = err_msg
                continue
            else:
                return jsonify({'error': err_msg or f'Gemini API error ({resp.status_code})'}), resp.status_code

        except requests.exceptions.Timeout:
            last_error = 'Request timed out'
            continue
        except Exception as e:
            return jsonify({'error': f'AI Coach error: {str(e)}'}), 500

    return jsonify({'error': last_error or 'All models exceeded quota. Please wait and try again.'}), 429


# ══════════════════════════════════════════════════════════════
#  START SERVER
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    init_db()

    port = int(os.getenv('PORT', 3000))
    print(f"""\n======================================================""")
    print(f"  AthleticConnect Server Running!")
    print(f"  Local:  http://localhost:{port}")
    print(f"  Demo Login:")
    print(f"  Email:    mohan@example.com")
    print(f"  Password: demo123")
    print(f"======================================================\n")
    app.run(host='0.0.0.0', port=port, debug=True)
