# from select import poll
import os
import uuid
import base64
import sqlite3
from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from flask_socketio import SocketIO
from config import Config
from functools import wraps
from models import get_db_connection, init_db
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash


# ── Create Flask app ──────────────────────────────────────
app = Flask(__name__)
app.config.from_object(Config)
app.permanent_session_lifetime = timedelta(minutes=30)  

# ── Uploads folder ────────────────────────────────────────
UPLOADS_FOLDER = os.path.join(
    os.path.dirname(__file__),
    'static', 'uploads'
)
# ── Initialize SocketIO ───────────────────────────────────
socketio = SocketIO(app,
                    cors_allowed_origins="*",
                    async_mode="eventlet",
                    logger=True,           # ← shows debug info
                    engineio_logger=True) #shows cinnnection info

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
    return render_template('login.html', hide_navbar=True, hide_footer=True)  # ← pass flag to hide navbar and footer

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
        AND p.user_id = ?
        GROUP BY p.id
        ORDER BY p.created_at DESC
        LIMIT 5
    """, (user_id,)).fetchall()
                                
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
            vi.encrypted_identifier
        FROM votes v
        LEFT JOIN vote_identity vi ON vi.vote_id = v.id
        WHERE v.poll_id = ?
        ORDER BY v.created_at DESC
    """, (poll_id,)).fetchall()           

    #step 8 is poll active or expired
    
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

# GET /dashboard/poll/<id>/edit ------------
@app.route('/dashboard/poll/<int:poll_id>/edit')
def edit_poll(poll_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()

    #verifying poll belongs to user
    poll = conn.execute("""
        SELECT * FROM polls
        WHERE id = ? AND user_id = ? AND status = 1
    """, (poll_id, session['user_id'])).fetchone()
    
    if not poll:
        conn.close()
        return render_template('404.html'), 404
    
    #checking poll expiration
        
    end_time_raw = poll['end_time'].replace("T", " ")[:19]
    end_dt       = datetime.fromisoformat(end_time_raw) 
    if datetime.now() > end_dt:
        conn.close()
        flash('Cannot edit expired poll.', 'warning')
        return redirect(url_for('poll_detail', poll_id=poll_id))
    
    #get options withmedia info
    options = conn.execute("""
        SELECT
            o.id,
            o.option,
            o.media_id,
            m.file_path,
            m.file_type,
            m.original_name
        FROM options o
        LEFT JOIN media m ON m.id = o.media_id
        WHERE o.poll_id = ? AND o.status = 1
    """, (poll_id,)).fetchall()

    #counting votes to check if poll_type is locked
    vote_count = conn.execute("""
        SELECT COUNT(*) as count FROM votes WHERE poll_id = ?
    """, (poll_id,)).fetchone()['count']
    conn.close()

    #convert options to list 
    options_data = [{
        'id':            o['id'],
        'text':          o['option'],
        'media_id':      o['media_id'],
        'file_path':     o['file_path'],
        'file_type':     o['file_type'],
        'original_name': o['original_name']
    } for o in options]
    
    return render_template('edit_poll.html',
                           active_page = 'polls',
                           poll        = poll,
                           options_data     = options_data,
                           vote_count  = vote_count)


# ── POST /dashboard/poll/<id>/edit ───────────────────────
@app.route('/dashboard/poll/<int:poll_id>/edit',
           methods=['POST'])
def edit_poll_submit(poll_id):
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()

    question   = data.get("question", "").strip()
    end_time   = data.get("end_time", "")
    poll_type  = data.get("poll_type", "single")
    options    = data.get("options", [])

    # ── Validate ──────────────────────────────────────────
    if not question:
        return jsonify({
            "error": "Question is required."
        }), 400

    valid_options = [o for o in options
                     if o.get("text", "").strip()]
    if len(valid_options) < 2:
        return jsonify({
            "error": "At least 2 options required."
        }), 400

    try:
        end_dt = datetime.fromisoformat(end_time)
        if end_dt <= datetime.now():
            return jsonify({
                "error": "End time must be in the future."
            }), 400
    except ValueError:
        return jsonify({"error": "Invalid end time."}), 400

    conn = get_db_connection()

    # Verify ownership
    poll = conn.execute("""
        SELECT * FROM polls
        WHERE id = ? AND user_id = ? AND status = 1
    """, (poll_id, session['user_id'])).fetchone()

    if not poll:
        conn.close()
        return jsonify({"error": "Poll not found."}), 404

    # Check vote count for poll_type lock
    vote_count = conn.execute("""
        SELECT COUNT(*) as count FROM votes
        WHERE poll_id = ?
    """, (poll_id,)).fetchone()['count']

    try:
        # ── Update poll ───────────────────────────────────
        if vote_count == 0:
            # Can update poll_type if no votes
            conn.execute("""
                UPDATE polls
                SET question=?, end_time=?, poll_type=?
                WHERE id=?
            """, (question, end_time, poll_type, poll_id))
        else:
            # Lock poll_type if votes exist
            conn.execute("""
                UPDATE polls
                SET question=?, end_time=?
                WHERE id=?
            """, (question, end_time, poll_id))

        # ── Process options ───────────────────────────────
        os.makedirs(UPLOADS_FOLDER, exist_ok=True)

        for opt in valid_options:
            option_id  = opt.get("id")       # existing or None
            text       = opt.get("text", "").strip()
            file_data  = opt.get("file_data")
            file_name  = opt.get("file_name")
            file_type  = opt.get("file_type")
            file_size  = opt.get("file_size", 0)
            remove_file = opt.get("remove_file", False)
            media_id   = opt.get("media_id")

            # ── Handle file ───────────────────────────────
            new_media_id = media_id  # keep existing by default

            if remove_file:
                # User removed file → set media_id to NULL
                new_media_id = None

            elif file_data and file_name:
                # New file uploaded → save it
                ext         = os.path.splitext(file_name)[1].lower()
                unique_name = f"{uuid.uuid4()}{ext}"
                file_path   = os.path.join(
                    UPLOADS_FOLDER, unique_name
                )
                file_bytes  = base64.b64decode(file_data)

                with open(file_path, 'wb') as f:
                    f.write(file_bytes)

                media_cursor = conn.execute("""
                    INSERT INTO media (file_name, file_path,
                                      file_type, file_size,
                                      original_name,
                                      created_at, created_id,
                                      status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, (
                    unique_name,
                    f"uploads/{unique_name}",
                    file_type,
                    file_size,
                    file_name,
                    datetime.now().isoformat(),
                    session.get('user_id')
                ))
                new_media_id = media_cursor.lastrowid

            # ── Existing option → UPDATE ──────────────────
            if option_id:
                conn.execute("""
                    UPDATE options
                    SET option=?, media_id=?
                    WHERE id=? AND poll_id=?
                """, (text, new_media_id, option_id, poll_id))

            # ── New option → INSERT ───────────────────────
            else:
                conn.execute("""
                    INSERT INTO options
                    (poll_id, option, media_id,
                     status, created_at, created_id)
                    VALUES (?, ?, ?, 1, ?, ?)
                """, (
                    poll_id,
                    text,
                    new_media_id,
                    datetime.now().isoformat(),
                    session.get('user_id')
                ))

        # ── Soft delete removed options ───────────────────
        kept_ids = [o.get("id") for o in valid_options
                    if o.get("id")]

        if kept_ids:
            placeholders = ",".join("?" * len(kept_ids))
            conn.execute(f"""
                UPDATE options SET status = 0
                WHERE poll_id = ?
                AND id NOT IN ({placeholders})
            """, [poll_id] + kept_ids)
        else:
            # All options are new — soft delete old ones
            conn.execute("""
                UPDATE options SET status = 0
                WHERE poll_id = ?
            """, (poll_id,))

        conn.commit()

    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"Edit poll error: {e}")
        return jsonify({
            "error": "Failed to update poll."
        }), 500

    finally:
        conn.close()

    return jsonify({
        "message": "Poll updated successfully!"
    }), 200   




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
        session['user_id']   = user['id']           
        session['user_name'] = user['first_name'] 
        session['role'] = user['role']  
        session.permanent    = True

        #direction based on role
        if user['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('poll.index'))           
    else:
        flash('Invalid email or password.', 'danger')
        return redirect(url_for('login'))


@app.route('/signup')
def signup():
    return render_template('signUp.html', hide_navbar=True, hide_footer=True)  # ← pass flag to hide navbar and footer


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



# ADMIN ROUTES-------------------
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            return render_template('404.html'), 404
        return f(*args, **kwargs)
    return decorated
#GET /admin/dashboard
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():

    conn = get_db_connection()

    # Get filter parameter
    filter_user = request.args.get('user_id', None)

    # ── Platform stats ────────────────────────────────────
    total_users = conn.execute("""
        SELECT COUNT(*) as count FROM users
        WHERE role = 'user' AND status = 1
    """).fetchone()['count']

    # If filter applied → stats for that user only
    if filter_user:
        total_polls = conn.execute("""
            SELECT COUNT(*) as count FROM polls
            WHERE user_id = ? AND status = 1
        """, (filter_user,)).fetchone()['count']

        total_votes = conn.execute("""
            SELECT COUNT(*) as count FROM votes
            WHERE poll_id IN (
                SELECT id FROM polls WHERE user_id = ?
            )
        """, (filter_user,)).fetchone()['count']

        active_polls = conn.execute("""
            SELECT COUNT(*) as count FROM polls
            WHERE user_id = ?
            AND status = 1
            AND end_time > datetime('now', 'localtime')
        """, (filter_user,)).fetchone()['count']

    else:
        # All users stats
        total_polls = conn.execute("""
            SELECT COUNT(*) as count FROM polls
            WHERE status = 1
        """).fetchone()['count']

        total_votes = conn.execute("""
            SELECT COUNT(*) as count FROM votes
        """).fetchone()['count']

        active_polls = conn.execute("""
            SELECT COUNT(*) as count FROM polls
            WHERE status = 1
            AND end_time > datetime('now', 'localtime')
        """).fetchone()['count']

    # ── Recent polls ──────────────────────────────────────
    if filter_user:
        recent_polls = conn.execute("""
            SELECT
                p.id, p.question, p.end_time,
                p.start_time,
                u.first_name, u.last_name,
                COUNT(v.id) as vote_count,
                CASE
                    WHEN datetime(p.end_time) <=
                         datetime('now','localtime')
                        THEN 'Expired'
                    WHEN datetime(p.start_time) >
                         datetime('now','localtime')
                        THEN 'Not Started'
                    ELSE 'Active'
                END as status
            FROM polls p
            LEFT JOIN votes v ON v.poll_id = p.id
            LEFT JOIN users u ON u.id = p.user_id
            WHERE p.status = 1 AND p.user_id = ?
            GROUP BY p.id
            ORDER BY p.created_at DESC
            LIMIT 5
        """, (filter_user,)).fetchall()
    else:
        recent_polls = conn.execute("""
            SELECT
                p.id, p.question, p.end_time,
                p.start_time,
                u.first_name, u.last_name,
                COUNT(v.id) as vote_count,
                CASE
                    WHEN datetime(p.end_time) <=
                         datetime('now','localtime')
                        THEN 'Expired'
                    WHEN datetime(p.start_time) >
                         datetime('now','localtime')
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

    # ── Users list for filter dropdown ────────────────────
    users = conn.execute("""
        SELECT id, first_name, last_name, email
        FROM users
        WHERE role = 'user' AND status = 1
        ORDER BY first_name
    """).fetchall()

    conn.close()

    return render_template('admin_dashboard.html',
                           active_page  = 'admin_dashboard',
                           total_users  = total_users,
                           total_polls  = total_polls,
                           total_votes  = total_votes,
                           active_polls = active_polls,
                           recent_polls = recent_polls,
                           users        = users,
                           filter_user  = filter_user)

#GET /admin/polls
@app.route('/admin/polls')
@admin_required
def admin_polls():

    conn = get_db_connection()
    page     = request.args.get('page', 1, type=int)
    per_page = 10
    offset   = (page - 1) * per_page

    # ── Filters from URL params ───────────────────────────
    filter_user   = request.args.get('user_id', '')
    filter_status = request.args.get('status', '')
    filter_date   = request.args.get('date', '')

    # ── Build dynamic WHERE clause ────────────────────────
    where_clauses = ["p.status = 1"]
    params        = []

    if filter_user:
        where_clauses.append("p.user_id = ?")
        params.append(filter_user)

    if filter_status == 'active':
        where_clauses.append("""
            datetime(p.end_time) > datetime('now','localtime')
            AND datetime(p.start_time) <=
                datetime('now','localtime')
        """)
    elif filter_status == 'expired':
        where_clauses.append("""
            datetime(p.end_time) <=
            datetime('now','localtime')
        """)
    elif filter_status == 'not_started':
        where_clauses.append("""
            datetime(p.start_time) >
            datetime('now','localtime')
        """)

    if filter_date:
        where_clauses.append("DATE(p.created_at) = ?")
        params.append(filter_date)

    where_sql = " AND ".join(where_clauses)

    # ── Total count for pagination ────────────────────────
    total_count = conn.execute(f"""
        SELECT COUNT(*) FROM polls p
        WHERE {where_sql}
    """, params).fetchone()[0]

    # ── Fetch polls ───────────────────────────────────────
    polls = conn.execute(f"""
        SELECT
            p.id, p.question,
            p.start_time, p.end_time,
            p.poll_type,
            u.first_name, u.last_name,
            COUNT(v.id) as vote_count,
            CASE
                WHEN datetime(p.end_time) <=
                     datetime('now','localtime')
                    THEN 'Expired'
                WHEN datetime(p.start_time) >
                     datetime('now','localtime')
                    THEN 'Not Started'
                ELSE 'Active'
            END as status
        FROM polls p
        LEFT JOIN votes v ON v.poll_id = p.id
        LEFT JOIN users u ON u.id = p.user_id
        WHERE {where_sql}
        GROUP BY p.id
        ORDER BY p.created_at DESC
        LIMIT ? OFFSET ?
    """, params + [per_page, offset]).fetchall()

    # ── Users for filter dropdown ─────────────────────────
    users = conn.execute("""
        SELECT id, first_name, last_name
        FROM users WHERE role = 'user' AND status = 1
        ORDER BY first_name
    """).fetchall()

    conn.close()

    total_pages = (total_count + per_page - 1) // per_page

    return render_template('admin_polls.html',
                           active_page    = 'admin_polls',
                           polls          = polls,
                           users          = users,
                           current_page   = page,
                           total_pages    = total_pages,
                           total_count    = total_count,
                           filter_user    = filter_user,
                           filter_status  = filter_status,
                           filter_date    = filter_date)

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
    session.pop('role', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('poll.index'))  



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