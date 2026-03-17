from flask import Blueprint, request, jsonify, session
from flask_socketio import join_room, leave_room
from datetime import datetime
from models import get_db_connection
from utils.security import encrypt_identifier, hash_ip
import json

vote_bp = Blueprint('vote', __name__)


# ── Helper to get socketio instance ──────────────────────
def get_socketio():
    from app import socketio
    return socketio


# ── POST /poll/<poll_id>/vote ─────────────────────────────
@vote_bp.route("/poll/<int:poll_id>/vote", methods=["POST"])
def submit_vote(poll_id):

    # ── Step 1: Get the poll ──────────────────────────────
    conn = get_db_connection()
    poll = conn.execute(
        "SELECT * FROM polls WHERE id = ?", (poll_id,)
    ).fetchone()

    if not poll:
        conn.close()
        return jsonify({"error": "Poll not found."}), 404

    # ── Step 2: Check expiry ──────────────────────────────
    end_dt = datetime.fromisoformat(poll["end_time"])
    if datetime.now() > end_dt:
        conn.close()
        return jsonify({
            "error":        "This poll has expired.",
            "is_expired":   True,
            "results_link": f"/poll/{poll_id}/results"
        }), 400

    # ── Step 3: Check duplicate via session ───────────────
    voted_key = f"voted_{poll_id}"
    if session.get(voted_key):
        conn.close()
        return jsonify({
            "error": "You have already voted in this poll."
        }), 400

    # ── Step 4: Get selected option_id from request ───────
    data      = request.get_json()
    option_id = data.get("option_id")

    if not option_id:
        conn.close()
        return jsonify({"error": "No option selected."}), 400

    # ── Step 5: Validate option belongs to this poll ──────
    option = conn.execute("""
        SELECT * FROM options
        WHERE id = ? AND poll_id = ? AND status = 1
    """, (option_id, poll_id)).fetchone()

    if not option:
        conn.close()
        return jsonify({"error": "Invalid option selected."}), 400

    # ── Step 6: Build voter identifier ────────────────────
    ip_address = request.remote_addr or "unknown"
    hashed_ip  = hash_ip(ip_address)
    identifier = f"{hashed_ip}_{poll_id}"

    # ── Step 7: Save vote ─────────────────────────────────
    cursor = conn.execute("""
        INSERT INTO votes (poll_id, selected_option_id,
                           created_at, created_id)
        VALUES (?, ?, ?, ?)
    """, (
        poll_id,
        option_id,
        datetime.now().isoformat(),
        session.get('user_id')
    ))
    vote_id = cursor.lastrowid

    # ── Step 8: Save encrypted identity ───────────────────
    encrypted = encrypt_identifier(identifier)
    conn.execute("""
        INSERT INTO vote_identity (vote_id, encrypted_identifier,
                                   created_at)
        VALUES (?, ?, ?)
    """, (vote_id, encrypted, datetime.now().isoformat()))

    conn.commit()

    # ── Step 9: Calculate updated results for broadcast ───
    options = conn.execute("""
        SELECT id, option FROM options
        WHERE poll_id = ? AND status = 1
    """, (poll_id,)).fetchall()

    all_votes = conn.execute("""
        SELECT selected_option_id FROM votes
        WHERE poll_id = ?
    """, (poll_id,)).fetchall()

    option_map  = {o["id"]: o["option"] for o in options}
    vote_counts = {o["option"]: 0 for o in options}

    for v in all_votes:
        option_text = option_map.get(v["selected_option_id"])
        if option_text:
            vote_counts[option_text] += 1

    total_votes = sum(vote_counts.values())
    results     = []
    for opt, count in vote_counts.items():
        percentage = round((count / total_votes * 100), 1) \
                     if total_votes > 0 else 0
        results.append({
            "option":     opt,
            "votes":      count,
            "percentage": percentage
        })

    conn.close()

    # ── Step 10: Emit WebSocket update to poll room ───────
    get_socketio().emit(
        "vote_update",
        {
            "poll_id":     poll_id,
            "results":     results,
            "total_votes": total_votes
        },
        room=str(poll_id)
    )

    # ── Step 11: Mark session as voted ────────────────────
    session[voted_key] = True
    session.permanent  = True

    return jsonify({
        "message":      "Vote submitted successfully!",
        "results_link": f"/poll/{poll_id}/results"
    }), 201


# ── GET /api/poll/<poll_id>/results ───────────────────────
@vote_bp.route("/api/poll/<int:poll_id>/results", methods=["GET"])
def get_results(poll_id):

    conn = get_db_connection()
    poll = conn.execute(
        "SELECT * FROM polls WHERE id = ?", (poll_id,)
    ).fetchone()

    if not poll:
        conn.close()
        return jsonify({"error": "Poll not found."}), 404

    options = conn.execute("""
        SELECT id, option FROM options
        WHERE poll_id = ? AND status = 1
    """, (poll_id,)).fetchall()

    all_votes = conn.execute("""
        SELECT selected_option_id FROM votes
        WHERE poll_id = ?
    """, (poll_id,)).fetchall()

    conn.close()

    option_map  = {o["id"]: o["option"] for o in options}
    vote_counts = {o["option"]: 0 for o in options}

    for vote in all_votes:
        option_text = option_map.get(vote["selected_option_id"])
        if option_text:
            vote_counts[option_text] += 1

    total_votes = sum(vote_counts.values())
    results     = []
    for option_text, count in vote_counts.items():
        percentage = round((count / total_votes * 100), 1) \
                     if total_votes > 0 else 0
        results.append({
            "option":     option_text,
            "votes":      count,
            "percentage": percentage
        })

    end_dt     = datetime.fromisoformat(poll["end_time"])
    is_expired = datetime.now() > end_dt

    return jsonify({
        "poll_id":     poll_id,
        "question":    poll["question"],
        "results":     results,
        "total_votes": total_votes,
        "is_expired":  is_expired,
        "end_time":    poll["end_time"]
    }), 200


# ── SocketIO Room Event Handlers ──────────────────────────
def register_socket_events():
    from app import socketio

    @socketio.on("join_poll")
    def handle_join(data):
        poll_id = data.get("poll_id")
        if poll_id:
            join_room(str(poll_id))
            print(f"✅ Client joined room: {poll_id}")

    @socketio.on("leave_poll")
    def handle_leave(data):
        poll_id = data.get("poll_id")
        if poll_id:
            leave_room(str(poll_id))
            print(f"❌ Client left room: {poll_id}")