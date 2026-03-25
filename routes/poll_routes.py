from flask import Blueprint, redirect, request, jsonify, \
                  render_template, session, url_for
from datetime import datetime
from models import get_db_connection
import base64
import uuid
import os
import secrets
import string

def generate_share_token():
    '''Generate unique 12 char alphanumeric token'''
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(12))

poll_bp = Blueprint('poll', __name__)

# ── Uploads folder path ───────────────────────────────────
UPLOAD_FOLDER = os.path.join('static', 'uploads')


# ── GET / (Landing Page) ──────────────────────────────────
@poll_bp.route("/")
def index():
    return render_template("index.html")


# ── GET /create (Create Poll Page) ───────────────────────
@poll_bp.route("/create")
def create_poll_page():
    if 'user_name' not in session:
        return redirect(url_for('login'))
    return render_template("create_poll.html",
                           active_page='create_poll')


# ── POST /poll/create ─────────────────────────────────────
@poll_bp.route("/poll/create", methods=["POST"])
def create_poll():
    data = request.get_json()

    # ── Step 1: Extract data ──────────────────────────────
    question   = data.get("question", "").strip()
    options    = data.get("options", [])
    start_time = data.get("start_time", "").replace("T", " ")
    end_time   = data.get("end_time", "").replace("T", " ")
    poll_type  = data.get("poll_type", "single")

    # ── Step 2: Validate poll_type ────────────────────────
    if poll_type not in ('single', 'multiple'):
        poll_type = 'single'

    # ── Step 3: Validate inputs ───────────────────────────
    if not question:
        return jsonify({
            "error": "Poll question is required."
        }), 400

    valid_options = [
        o for o in options 
        if o.get("text","").strip() or o.get("file_base64")
    ]
    
    if len(valid_options) < 2:
        return jsonify({
            "error": "At least 2 options with text required."
        }), 400

    try:
        start_dt = datetime.fromisoformat(start_time)
        end_dt   = datetime.fromisoformat(end_time)

        if start_dt <= datetime.utcnow():
            return jsonify({
                "error": "Start time must be in the future."
            }), 400

        if end_dt <= start_dt:
            return jsonify({
                "error": "End time must be after start time."
            }), 400

    except ValueError:
        return jsonify({
            "error": "Invalid date/time format."
        }), 400

    # ── Step 4: Save poll to DB ───────────────────────────
    conn   = get_db_connection()
    while True:
        token = generate_share_token()  
        existing = conn.execute(
            "SELECT id FROM polls WHERE share_token = ?",
            (token,)
        ).fetchone()
        if not existing:
            break
    cursor = conn.execute("""
        INSERT INTO polls (question, start_time, end_time,
                           user_id, poll_type,share_token,
                           created_at, created_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        question,
        start_time,
        end_time,
        session.get('user_id'),
        poll_type,
        token,
        datetime.now().isoformat(),
        session.get('user_id')
    ))
    poll_id = cursor.lastrowid

    # ── Step 5: Process each option ───────────────────────
    for opt in valid_options:
        text      = opt.get("text", "").strip()
        media_id  = None

        # ── Step 5a: Handle file if present ───────────────
        file_base64 = opt.get("file_base64")
        if file_base64:
            try:
                file_name     = opt.get("file_name", "file")
                file_type     = opt.get("file_type", "")
                file_size     = opt.get("file_size", 0)

                # Get file extension from original name
                _, ext = os.path.splitext(file_name)
                if not ext:
                    ext = ".bin"  # fallback extension

                # Generate unique filename using UUID
                unique_name = f"{uuid.uuid4()}{ext}"
                file_path   = os.path.join(
                    UPLOAD_FOLDER, unique_name
                )

                # Decode base64 and save to disk
                file_bytes = base64.b64decode(file_base64)
                with open(file_path, 'wb') as f:
                    f.write(file_bytes)

                # Insert into media table
                media_cursor = conn.execute("""
                    INSERT INTO media (file_name, file_path,
                                      file_type, file_size,
                                      original_name,
                                      created_at, created_id,
                                      status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, (
                    unique_name,
                    file_path,
                    file_type,
                    file_size,
                    file_name,
                    datetime.now().isoformat(),
                    session.get('user_id')
                ))
                media_id = media_cursor.lastrowid

            except Exception as e:
                print(f"File save error: {e}")
                # Continue without file if error
                media_id = None

        # ── Step 5b: Insert option ─────────────────────────
        conn.execute("""
            INSERT INTO options (poll_id, option, media_id,
                                 status, created_at, created_id)
            VALUES (?, ?, ?, 1, ?, ?)
        """, (
            poll_id,
            text,
            media_id,
            datetime.now().isoformat(),
            session.get('user_id')
        ))

    conn.commit()
    conn.close()

    # ── Step 6: Return response ───────────────────────────
    return jsonify({
        "message":      "Poll created successfully!",
        "poll_id":      poll_id,
        "vote_link":    f"/poll/{poll_id}",
        "results_link": f"/poll/{poll_id}/results"
    }), 201


# ── GET /poll/<poll_id> (Vote Page) ───────────────────────
@poll_bp.route("/poll/<string:token>", methods=["GET"])
def vote_page(token):
    # Must be logged in to vote
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()

    poll = conn.execute(
        "SELECT * FROM polls WHERE share_token = ? AND status = 1",
        (token,)
    ).fetchone()

    if not poll:
        conn.close()
        return render_template("404.html"), 404

    poll_id = poll["id"]
    # Fetch options WITH media info
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

    conn.close()

    poll_data = {
        "id":        poll["id"],
        "question":  poll["question"],
        "poll_type": poll["poll_type"],
        "share_token": poll["share_token"],
        "options": [{
            "id":            o["id"],
            "text":          o["option"],
            "file_path":     o["file_path"],
            "file_type":     o["file_type"],
            "original_name": o["original_name"]
        } for o in options],
        "start_time": poll["start_time"],
        "end_time":   poll["end_time"],
    }

    now         = datetime.utcnow()
    end_time_raw = poll["end_time"].replace("T", " ")[:19]
    end_dt      = datetime.fromisoformat(end_time_raw)
    is_expired  = now >= end_dt

    start_time_raw = poll["start_time"]
    if start_time_raw:
        start_time_raw = start_time_raw.replace("T", " ")[:19]
        start_dt       = datetime.fromisoformat(start_time_raw)
        not_started    = now < start_dt
    else:
        not_started = False

    has_voted = session.get(f"voted_{poll_id}", False)

    return render_template("vote.html",
                           poll        = poll_data,
                           has_voted   = has_voted,
                           is_expired  = is_expired,
                           not_started = not_started)


# ── GET /poll/<poll_id>/results ───────────────────────────
@poll_bp.route("/poll/<string:token>/results")
def results_page(token):
    conn = get_db_connection()

    poll = conn.execute(
        "SELECT * FROM polls WHERE share_token = ?", (token,)
    ).fetchone()

    if not poll:
        conn.close()
        return render_template("404.html"), 404

    poll_id = poll["id"]
    # ── Check expiry ──────────────────────────────────────
    end_dt     = datetime.fromisoformat(
                     poll["end_time"].replace("T"," ")[:19])
    is_expired = datetime.utcnow() > end_dt

    # ── Who is visiting? ──────────────────────────────────
    user_id    = session.get('user_id')
    is_creator = user_id and \
                 int(user_id) == int(poll["user_id"])

    # ── Check if visitor has voted (DB check) ─────────────
    has_voted    = False
    voted_option = None

    if user_id:
        vote = conn.execute("""
            SELECT v.id, o.option as voted_option
            FROM votes v
            JOIN options o
              ON o.id = v.selected_option_id
            WHERE v.poll_id    = ?
            AND   v.created_id = ?
            LIMIT 1
        """, (poll_id, user_id)).fetchone()

        has_voted    = vote is not None
        voted_option = vote['voted_option'] \
                       if vote else None

    conn.close()

    poll_data = {
        "id":       poll["id"],
        "question": poll["question"],
        "end_time": poll["end_time"],
        "user_id":  poll["user_id"],
        "share_token": poll["share_token"]
    }

    #showing results to creator and after expiry only
    show_results = is_expired or is_creator

    return render_template("results.html",
                           poll         = poll_data,
                           is_expired   = is_expired,
                           is_creator   = is_creator,
                           has_voted    = has_voted,
                           voted_option = voted_option,
                           show_results = show_results)