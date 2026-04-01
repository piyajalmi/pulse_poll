from flask import Blueprint, redirect, request, \
                  jsonify, render_template, \
                  session, url_for
from datetime import datetime, timezone
from models import get_db_connection
import base64
import uuid
import os
import secrets
import string

poll_bp = Blueprint('poll', __name__)

UPLOAD_FOLDER = os.path.join('static', 'uploads')


def generate_share_token():
    chars = string.ascii_letters + string.digits
    return ''.join(
        secrets.choice(chars) for _ in range(12)
    )


# ── GET / ─────────────────────────────────────────────────
@poll_bp.route("/")
def index():
    return render_template("index.html")


# ── GET /create ───────────────────────────────────────────
@poll_bp.route("/create")
def create_poll_page():
    if 'user_name' not in session:
        return redirect(url_for('login'))
    return render_template("create_poll.html",
                           active_page='create_poll')


# ── POST /poll/create ─────────────────────────────────────
@poll_bp.route("/poll/create", methods=["POST"])
def create_poll():
    data       = request.get_json()
    question   = data.get("question", "").strip()
    options    = data.get("options", [])
    start_time_raw = data.get("start_time")
    end_time_raw   = data.get("end_time")
    poll_type  = data.get("poll_type", "single")

    if poll_type not in ('single', 'multiple'):
        poll_type = 'single'

    if not question:
        return jsonify({
            "error": "Poll question is required."
        }), 400

    valid_options = [
        o for o in options
        if o.get("text", "").strip() or
           o.get("file_base64")
    ]

    if len(valid_options) < 2:
        return jsonify({
            "error": "At least 2 options required."
        }), 400
    
    option_texts = [
    o.get("text", "").strip().lower()
    for o in valid_options
    if o.get("text", "").strip()
    ]

    if len(option_texts) != len(set(option_texts)):
        return jsonify({
        "error": "All options must be unique."
        }), 400

    try:
        start_dt = datetime.fromisoformat(start_time_raw)
        end_dt   = datetime.fromisoformat(end_time_raw)

        # Make them timezone-aware (assume input is local IST)
        import pytz
        ist = pytz.timezone('Asia/Kolkata')

        start_dt = ist.localize(start_dt).astimezone(timezone.utc)
        end_dt   = ist.localize(end_dt).astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        if start_dt <= now:
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

    conn   = get_db_connection()
    cursor = conn.cursor()

    try:
        # Generate unique token
        while True:
            token = generate_share_token()
            cursor.execute(
                "SELECT id FROM polls WHERE share_token=%s",
                (token,)
            )
            if not cursor.fetchone():
                break

        # Insert poll → RETURNING id
        cursor.execute("""
            INSERT INTO polls
                (question, start_time, end_time,
                 user_id, poll_type, share_token,
                 created_at, created_id)
            VALUES (%s,%s,%s,%s,%s,%s,NOW(),%s)
            RETURNING id
        """, (
            question, start_dt, end_dt ,
            session.get('user_id'), poll_type,
            token, session.get('user_id')
        ))
        poll_id = cursor.fetchone()['id']

        # Process each option
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        for opt in valid_options:
            text       = opt.get("text", "").strip()
            media_id   = None
            file_base64 = opt.get("file_base64")

            if file_base64:
                try:
                    file_name = opt.get("file_name","file")
                    file_type = opt.get("file_type", "")
                    file_size = opt.get("file_size", 0)
                    _, ext    = os.path.splitext(file_name)
                    if not ext:
                        ext = ".bin"

                    unique_name = f"{uuid.uuid4()}{ext}"
                    file_path   = os.path.join(
                        UPLOAD_FOLDER, unique_name
                    )
                    file_bytes  = base64.b64decode(
                        file_base64
                    )
                    with open(file_path, 'wb') as f:
                        f.write(file_bytes)

                    cursor.execute("""
                        INSERT INTO media
                            (file_name, file_path,
                             file_type, file_size,
                             original_name,
                             created_at, created_id,
                             status)
                        VALUES (%s,%s,%s,%s,%s,NOW(),%s,1)
                        RETURNING id
                    """, (
                        unique_name, file_path,
                        file_type, file_size,
                        file_name,
                        session.get('user_id')
                    ))
                    media_id = cursor.fetchone()['id']

                except Exception as e:
                    print(f"File error: {e}")
                    media_id = None

            cursor.execute("""
                INSERT INTO options
                    (poll_id, option, media_id,
                     status, created_at, created_id)
                VALUES (%s,%s,%s,1,NOW(),%s)
            """, (
                poll_id, text, media_id,
                session.get('user_id')
            ))

        conn.commit()

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        print(f"Create poll error: {e}")
        return jsonify({
            "error": "Failed to create poll."
        }), 500

    cursor.close()
    conn.close()

    return jsonify({
        "message":      "Poll created successfully!",
        "poll_id":      poll_id,
        "vote_link":    f"/poll/{token}",
        "results_link": f"/poll/{token}/results"
    }), 201


# ── GET /poll/<token> ─────────────────────────────────────
@poll_bp.route("/poll/<string:token>", methods=["GET"])


def vote_page(token):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn   = get_db_connection()
    cursor = conn.cursor()

    # ── Get poll ─────────────────────────
    cursor.execute("""
        SELECT * FROM polls
        WHERE share_token = %s AND status = 1
    """, (token,))
    poll = cursor.fetchone()

    if not poll:
        cursor.close()
        conn.close()
        return render_template("404.html"), 404

    poll_id = poll["id"]

    # ── Get options ─────────────────────
    cursor.execute("""
        SELECT o.id, o.option, o.media_id,
               m.file_path, m.file_type,
               m.original_name
        FROM options o
        LEFT JOIN media m ON m.id = o.media_id
        WHERE o.poll_id = %s AND o.status = 1
    """, (poll_id,))
    options = cursor.fetchall()

    # ── Check vote BEFORE closing cursor ✅
    has_voted = False

    cursor.execute("""
        SELECT 1 FROM votes
        WHERE poll_id = %s AND created_id = %s
        LIMIT 1
    """, (poll_id, session["user_id"]))

    existing_vote = cursor.fetchone()

    if existing_vote:
        has_voted = True

    # ── Time logic ──────────────────────
    now = datetime.now(timezone.utc)

    start_time = poll["start_time"]
    end_time   = poll["end_time"]

    if start_time and start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)

    if end_time and end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    is_expired  = now >= end_time
    not_started = now < start_time if start_time else False

    is_admin = session.get("role") == "admin"
    voted_poll_ids = []
    if "user_id" in session:
        cursor = conn.cursor()

        cursor.execute("""
        SELECT DISTINCT poll_id
        FROM votes
        WHERE created_id = %s
    """, (session["user_id"],))

        voted = cursor.fetchall()
    voted_poll_ids = [int(v["poll_id"]) for v in voted]

    
    # ── Close AFTER everything ✅
    cursor.close()
    conn.close()

    # ── Prepare data ───────────────────
    poll_data = {
        "id":          poll["id"],
        "question":    poll["question"],
        "poll_type":   poll["poll_type"],
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

    return render_template(
        "vote.html",
        poll        = poll_data,
        has_voted   = has_voted,
        is_admin    = is_admin,
        is_expired  = is_expired,
        not_started = not_started,
        voted_poll_ids=voted_poll_ids
    )


# ── GET /poll/<token>/results ─────────────────────────────
@poll_bp.route("/poll/<string:token>/results")
def results_page(token):
    conn   = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM polls WHERE share_token = %s",
        (token,)
    )
    poll = cursor.fetchone()

    if not poll:
        cursor.close()
        conn.close()
        return render_template("404.html"), 404

    poll_id    = poll["id"]
    now=datetime.now(timezone.utc)
    is_expired=now>=poll["end_time"]
    user_id    = session.get('user_id')
    is_creator = user_id and \
                 int(user_id) == int(poll["user_id"])

    has_voted    = False
    voted_option = None

    if user_id:
        cursor.execute("""
            SELECT v.id, o.option as voted_option
            FROM votes v
            JOIN options o
              ON o.id = v.selected_option_id
            WHERE v.poll_id    = %s
            AND   v.created_id = %s
            LIMIT 1
        """, (poll_id, user_id))
        vote = cursor.fetchone()

        has_voted    = vote is not None
        voted_option = vote['voted_option'] \
                       if vote else None

    cursor.close()
    conn.close()

    poll_data = {
        "id":          poll["id"],
        "question":    poll["question"],
        "end_time":    poll["end_time"],
        "user_id":     poll["user_id"],
        "share_token": poll["share_token"]
    }

    is_admin = session.get('role') == 'admin'
    show_results = is_expired or is_creator or is_admin

    return render_template("results.html",
                           poll         = poll_data,
                           is_expired   = is_expired,
                           is_creator   = is_creator,
                           has_voted    = has_voted,
                           voted_option = voted_option,
                           show_results = show_results)




