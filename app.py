# from select import poll
import sqlite3
from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from flask_socketio import SocketIO
from config import Config
from models import get_db_connection, init_db
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash


# ── Create Flask app ──────────────────────────────────────
app = Flask(__name__)
app.config.from_object(Config)
app.permanent_session_lifetime = timedelta(minutes=30)  # 1 min is too short, changed to 30

# ── Initialize SocketIO ───────────────────────────────────
socketio = SocketIO(app,
                    cors_allowed_origins="*",
                    async_mode="eventlet")

# ── Initialize database ───────────────────────────────────
with app.app_context():
    init_db()

# ── Register Blueprints ───────────────────────────────────
from routes.poll_routes import poll_bp
from routes.vote_routes import vote_bp
from routes.admin_routes import admin_bp

app.register_blueprint(poll_bp)
app.register_blueprint(vote_bp)
app.register_blueprint(admin_bp)

# ── Register SocketIO events ──────────────────────────────
from routes.vote_routes import register_socket_events
register_socket_events()        # ← moved here, before app runs

# ── Session permanent on every request ───────────────────
@app.before_request
def make_session_permanent():
    session.permanent = True

# ── Auth Routes ───────────────────────────────────────────
@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/faqs')
def faqs():
    return render_template('faqs.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id =session['user_id']
    conn =  get_db_connection()

    #total polls by user
    total_polls = conn.execute("""
        SELECT COUNT(*) as count FROM polls WHERE user_id =? 
    """, (user_id,)).fetchone()['count']


    #active polls
    active_polls = conn.execute("""
        SELECT COUNT(*) as count FROM polls 
        WHERE user_id = ? AND end_time > datetime('now', 'localtime')
    """, (user_id,)).fetchone()['count']

    #total votes across all user_id
    total_votes = conn.execute("""
        SELECT COUNT(*) as count FROM votes 
        WHERE poll_id IN (
            SELECT id FROM polls WHERE user_id = ?
        )
    """, (user_id,)).fetchone()['count']

    #recent polls 
    recent_polls = conn.execute("""
        SELECT 
            p.id,
            p.question,
            p.end_time,
            p.user_id,
            COUNT(v.id) as vote_count,
            u.first_name,         
            u.last_name,  
            CASE 
                WHEN datetime(p.end_time) <= datetime('now', 'localtime')
                    THEN 'Expired'
                 WHEN datetime(p.start_time) > datetime('now', 'localtime')
                    THEN 'Not Started'
                ELSE 'Active'
            END as status
        FROM polls p
        LEFT JOIN votes v ON v.poll_id = p.id
        LEFT JOIN users u ON u.id = p.user_id 
        WHERE p.status = 1 
        GROUP BY p.id
        ORDER BY p.created_at DESC
        LIMIT 5
    """).fetchall()
                                
    conn.close()
    # ── Calculate percentages for progress circles ────────
    active_pct = round((active_polls / total_polls * 100)) \
                 if total_polls > 0 else 0
    ended_polls = total_polls - active_polls
    ended_pct   = round((ended_polls / total_polls * 100)) \
                  if total_polls > 0 else 0
    max_votes   = 100
    votes_pct   = min(round((total_votes / max_votes * 100)), 100)

    return render_template('dashboard.html', active_page  = 'dashboard',
                       total_polls  = total_polls,
                       active_polls = active_polls,
                       total_votes  = total_votes,
                       active_pct   = active_pct,
                       ended_pct    = ended_pct,
                       votes_pct    = votes_pct,
                       recent_polls = recent_polls)


@app.route('/dashboard/polls')
def my_polls():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    page = request.args.get('page', 1, type=int)
    per_page = 8
    offset = (page - 1) * per_page

    conn    = get_db_connection()
    # 1. Get  TOTAL count of polls for this user 
    total_count = conn.execute(
        "SELECT COUNT(*) FROM polls WHERE user_id = ? AND status = 1", 
        (user_id,)
    ).fetchone()[0]
    # 2 fetch polls using limit and offset for pagination
    polls = conn.execute("""
        SELECT
            p.id,
            p.question,
            p.end_time,
            p.created_at,
            COUNT(v.id) as vote_count,
            CASE
                WHEN datetime(p.end_time) <= datetime('now', 'localtime')
                    THEN 'Expired'
                 WHEN datetime(p.start_time) > datetime('now', 'localtime')
                    THEN 'Not Started'
                ELSE 'Active'
            END as status
        FROM polls p
        LEFT JOIN votes v ON v.poll_id = p.id
        WHERE p.user_id = ?
        AND p.status = 1
        GROUP BY p.id
        ORDER BY p.created_at DESC
        LIMIT ? OFFSET ?
    """, (user_id, per_page, offset)).fetchall()

    conn.close()

    total_pages = (total_count + per_page - 1) // per_page

    return render_template('my_polls.html',
                           active_page = 'polls',
                           polls       = polls,
                           current_page = page,
                           total_pages = total_pages)

@app.route('/dashboard/poll/<int:poll_id>')
def poll_detail(poll_id):
    #step 1 must be logged in 
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()

    #step 2 get poll - verifying it belongs to that user 
    poll = conn.execute("""
        SELECT * FROM polls
        WHERE id = ? AND user_id = ? 
    """, (poll_id, session['user_id'])).fetchone()

    #step 3 poll not found and doesnt belong to user
    if not poll:
        conn.close()
        return render_template('404.html'), 404
    
    #step 4 get options wih votes counts
    options = conn.execute("""
        SELECT
            o.id,
            o.option,
            COUNT(v.id) as vote_count
        FROM options o
        LEFT JOIN votes v ON v.selected_option_id = o.id
        WHERE o.poll_id = ? AND o.status = 1
        GROUP BY o.id
    """, (poll_id,)).fetchall()

    #step 5 total votes across all options 
    total_votes = sum(o['vote_count'] for o in options)

    #step 6 calculate percentage for each option
    options_data = []
    for o in options:
        percentage = round((o['vote_count'] / total_votes * 100), 1) \
                        if total_votes > 0 else 0
        options_data.append({
             'id':         o['id'],
            'text':       o['option'],
            'votes':      o['vote_count'],
            'percentage': percentage
        })
        
    #step 7 get vote logs for logs tab
    logs = conn.execute("""
        SELECT
            v.id,
            v.created_at,
            vi.encrypted_identifier,
            vi.browser
        FROM votes v
        LEFT JOIN vote_identity vi ON vi.vote_id = v.id
        WHERE v.poll_id = ?
        ORDER BY v.created_at DESC
    """, (poll_id,)).fetchall()           

    #step 8 is poll active or expired
    from datetime import datetime
    end_time_raw = poll['end_time'].replace("T", " ")[:19]  # ← normalize
    end_dt       = datetime.fromisoformat(end_time_raw)
    is_expired   = datetime.now() > end_dt

    
    conn.close()

    return render_template('poll_detail.html', 
                           active_page = 'polls', 
                           poll = poll,
                           options_data=options_data,
                           total_votes=total_votes,
                           logs=logs,
                           is_expired=is_expired)
 
@app.route('/dashboard/poll/<int:poll_id>/delete', methods=['POST'])
def delete_poll(poll_id):
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db_connection()

    poll = conn.execute("""
        SELECT * FROM polls
        WHERE id = ? AND user_id = ?
    """, (poll_id, session['user_id'])).fetchone()

    if not poll:
        conn.close()
        return jsonify({"error": "Poll not found"}), 404

    # Soft delete
    conn.execute("UPDATE polls SET status = 0 WHERE id = ?", (poll_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Poll deleted"}), 200

@app.route('/polls')
def polls_list():
    page = request.args.get('page', 1, type=int)
    per_page = 8
    offset = (page - 1) * per_page

    conn = get_db_connection()
    total_count = conn.execute("SELECT COUNT(*) FROM polls WHERE status = 1").fetchone()[0]
    polls = conn.execute("""
        SELECT 
            p.id,
            p.question,
            p.start_time,
            p.end_time,
            u.first_name,         
            u.last_name,
            COUNT(v.id) as vote_count,
            CASE 
                WHEN datetime(p.end_time) <= datetime('now', 'localtime')
                    THEN 'Expired'
                 WHEN datetime(p.start_time) > datetime('now', 'localtime')
                    THEN 'Not Started'
                ELSE 'Active'
            END as status
        FROM polls p
        LEFT JOIN votes v ON v.poll_id = p.id
        LEFT JOIN users u ON u.id = p.user_id 
        WHERE p.status = 1 
        GROUP BY p.id
        ORDER BY p.created_at DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset)).fetchall()
    conn.close()
    total_pages = (total_count + per_page - 1) // per_page
    return render_template('polls.html', polls=  polls,
                           current_page = page,
                           total_pages = total_pages,
                           total_count = total_count)


@app.route('/login_validation', methods=['POST'])
def login_validation():
    email    = request.form.get('email')
    password = request.form.get('password')

    conn   = get_db_connection()        # ← use get_db_connection() for row_factory
    user   = conn.execute(
        "SELECT * FROM users WHERE email = ? AND password = ?",
        (email, password)
    ).fetchone()
    conn.close()

    if user:
        session['user_id']   = user['id']           # ← use column names not indices
        session['user_name'] = user['first_name']   # ← safer with row_factory
        session.permanent    = True
        return redirect(url_for('dashboard'))           # ← go to home, no need to pass params in URL
    else:
        flash('Invalid email or password.', 'danger')
        return redirect(url_for('login'))


@app.route('/signup')
def signup():
    return render_template('signUp.html')


@app.route('/add_user', methods=['POST'])
def add_user():
    fname    = request.form.get('fname')
    lname    = request.form.get('lname')
    email    = request.form.get('email')
    password = request.form.get('password')

    conn = get_db_connection()

    # Check if user already exists
    existing = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()

    if existing:
        conn.close()
        flash('An account with this email already exists.', 'warning')
        return redirect(url_for('login'))
    else:
        conn.execute("""
            INSERT INTO users (first_name, last_name, email, password,
                               created_at, status)
            VALUES (?, ?, ?, ?, datetime('now', 'localtime'), 1)
        """, (fname, lname, email, password))
        conn.commit()

        #gets new users auto generated id
        new_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()['id']

        # Update created_id to new user's id
        conn.execute("UPDATE users SET created_id = ? WHERE id = ?", (new_id, new_id))
        conn.commit()
        conn.close()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))


# @app.route('/polls')
# def polls_list():
#     conn = get_db_connection()
#     all_polls = conn.execute("""
#         SELECT polls.*, users.first_name, users.last_name
#         FROM polls
#         JOIN users ON polls.user_id = users.id
#     """).fetchall()                     # ← was fetchone(), fixed to fetchall()
#     conn.close()
#     return render_template('polls.html', polls=all_polls)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('poll.index'))  # ← redirect to poll blueprint's index


# ── Global Error Handlers ─────────────────────────────────
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template("500.html"), 500


# ── Run ───────────────────────────────────────────────────
if __name__ == "__main__":
    socketio.run(app, debug=True)