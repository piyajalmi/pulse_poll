from flask import Blueprint, redirect, request, jsonify, render_template, session, url_for
from datetime import datetime
from models import get_db_connection
import json

poll_bp = Blueprint('poll', __name__)


# ── GET / (Landing Page) ──────────────────────────────────
@poll_bp.route("/")
def index():
    return render_template("index.html")


# ── GET /create (Create Poll Page) ───────────────────────
@poll_bp.route("/create")
def create_poll_page():
    if 'user_name' not in session:
        return redirect(url_for('login'))          # ← fixed
    return render_template("create_poll.html",
                           active_page='create_poll')


# ── POST /poll/create ─────────────────────────────────────
@poll_bp.route("/poll/create", methods=["POST"])
def create_poll():
    data = request.get_json()

    # ── Step 1: Extract data ───────────────────────────────
    question   = data.get("question", "").strip()
    options    = data.get("options", [])
    start_time = data.get("start_time", "").replace("T", " ")
    end_time   = data.get("end_time", "").replace("T", " ")

    # ── Step 2: Validate ──────────────────────────────────
    if not question:
        return jsonify({"error": "Poll question is required."}), 400

    if len(options) < 2:
        return jsonify({"error": "At least 2 options required."}), 400

    options = [opt.strip() for opt in options if opt.strip()]

    try:
        start_dt = datetime.fromisoformat(start_time)
        end_dt   = datetime.fromisoformat(end_time)

        if start_dt <= datetime.now():           # ← new check
            return jsonify({
                "error": "Start time must be in the future."
            }), 400

        if end_dt <= start_dt:
            return jsonify({
                "error": "End time must be after start time."
            }), 400

    except ValueError:
        return jsonify({"error": "Invalid date/time format."}), 400

    # ── Step 3: Save poll to DB ───────────────────────────
    conn   = get_db_connection()
    cursor = conn.execute("""
        INSERT INTO polls (question, start_time, end_time,
                           user_id, created_at, created_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        question,
        start_time,                              # ← form value, not now()!
        end_time,
        session.get('user_id'),
        datetime.now().isoformat(),
        session.get('user_id')
    ))

    poll_id = cursor.lastrowid

    # ── Step 4: Insert options ────────────────────────────
    for option_text in options:
        conn.execute("""
            INSERT INTO options (poll_id, option, status,
                                 created_at, created_id)
            VALUES (?, ?, 1, ?, ?)
        """, (
            poll_id,
            option_text,
            datetime.now().isoformat(),
            session.get('user_id')
        ))

    conn.commit()
    conn.close()

    # ── Step 5: Return poll link ──────────────────────────
    return jsonify({
        "message":      "Poll created successfully!",
        "poll_id":      poll_id,
        "vote_link":    f"/poll/{poll_id}",
        "results_link": f"/poll/{poll_id}/results"
    }), 201


# ── GET /poll/<poll_id> (Vote Page) ───────────────────────
@poll_bp.route("/poll/<int:poll_id>", methods=["GET"])
def vote_page(poll_id):
    conn = get_db_connection()

    poll = conn.execute(
        "SELECT * FROM polls WHERE id = ? AND status = 1",
        (poll_id,)
    ).fetchone()

    if not poll:
        conn.close()
        return render_template("404.html"), 404

    options = conn.execute("""
        SELECT id, option FROM options
        WHERE poll_id = ? AND status = 1
    """, (poll_id,)).fetchall()

    conn.close()

    poll_data = {
        "id":         poll["id"],
        "question":   poll["question"],
        "options":    [{"id": o["id"],
                        "text": o["option"]} for o in options],
        "start_time": poll["start_time"],
        "end_time":   poll["end_time"],
    }

    now = datetime.now()

    # ── Normalize end_time ────────────────────────────────
    end_time_raw = poll["end_time"].replace("T", " ")[:19]
    end_dt       = datetime.fromisoformat(end_time_raw)
    is_expired   = now >= end_dt

    # ── Safe start_time check ─────────────────────────────
    start_time_raw = poll["start_time"]

    if start_time_raw:
        # Normalize T → space, trim microseconds
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


# ── GET /poll/<poll_id>/results (Results Page) ────────────
@poll_bp.route("/poll/<int:poll_id>/results")
def results_page(poll_id):
    conn = get_db_connection()

    poll = conn.execute(
        "SELECT * FROM polls WHERE id = ?", (poll_id,)
    ).fetchone()

    conn.close()

    if not poll:
        return render_template("404.html"), 404

    poll_data = {
        "id":       poll["id"],
        "question": poll["question"],
        "end_time": poll["end_time"],
    }

    end_dt     = datetime.fromisoformat(poll["end_time"])
    is_expired = datetime.now() > end_dt

    return render_template("results.html",
                           poll       = poll_data,
                           is_expired = is_expired)