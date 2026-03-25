from flask import Blueprint, request, jsonify, session
from flask_socketio import join_room, leave_room
from datetime import datetime
from models import get_db_connection
from utils.security import encrypt_identifier, hash_ip
import json

vote_bp = Blueprint('vote', __name__)


# ── Helper ────────────────────────────────────────────────
def get_socketio():
    from app import socketio
    return socketio


# ── POST /poll/<poll_id>/vote ─────────────────────────────
@vote_bp.route("/poll/<string:token>/vote", methods=["POST"])
def submit_vote(token):

    conn = get_db_connection()

    # ── Step 1: Get poll ──────────────────────────────────
    poll = conn.execute(
        "SELECT * FROM polls WHERE share_token = ?", (token,)
    ).fetchone()

    if not poll:
        conn.close()
        return jsonify({"error": "Poll not found."}), 404

    poll_id = poll["id"]
    # ── Step 2a: Check not started ────────────────────────
    start_time_raw = poll["start_time"]
    if start_time_raw:
        start_time_raw = start_time_raw.replace("T"," ")[:19]
        start_dt = datetime.fromisoformat(start_time_raw)
        if datetime.utcnow() < start_dt:
            conn.close()
            return jsonify({
                "error":       "This poll hasn't started yet.",
                "not_started": True
            }), 400

    # ── Step 2b: Check expiry ─────────────────────────────
    end_time_raw = poll["end_time"].replace("T"," ")[:19]
    end_dt       = datetime.fromisoformat(end_time_raw)
    if datetime.utcnow() > end_dt:
        conn.close()
        return jsonify({
            "error":        "This poll has expired.",
            "is_expired":   True,
            "results_link": f"/poll/{poll['share_token']}/results"
        }), 400

    # ── Step 3: Check duplicate via session ───────────────
    # voted_key = f"voted_{poll_id}"
    # if session.get(voted_key):
    #     conn.close()
    #     return jsonify({
    #         "error": "You have already voted in this poll."
    #     }), 400
    existing_vote = conn.execute("""
        SELECT id FROM votes
        WHERE poll_id = ? AND created_id = ?
    """, (poll_id, session.get('user_id'))).fetchone()

    if existing_vote:
        conn.close()
        return jsonify({
            "error": "You have already voted in this poll."
        }), 400
    # ── Step 4: Get option_ids + submission_id ────────────
    data          = request.get_json()
    option_ids    = data.get("option_ids", [])
    submission_id = data.get("submission_id", "")

    if not option_ids:
        conn.close()
        return jsonify({"error": "No option selected."}), 400

    # ── Step 5: Validate poll_type vs selection ───────────
    poll_type = poll["poll_type"]

    if poll_type == "single" and len(option_ids) > 1:
        conn.close()
        return jsonify({
            "error": "Only one option allowed for this poll."
        }), 400

    # ── Step 6: Validate all option_ids belong to poll ────
    for option_id in option_ids:
        option = conn.execute("""
            SELECT id FROM options
            WHERE id = ? AND poll_id = ? AND status = 1
        """, (option_id, poll_id)).fetchone()

        if not option:
            conn.close()
            return jsonify({
                "error": f"Invalid option: {option_id}"
            }), 400

    # ── Step 7: Build voter identifier ────────────────────
    ip_address = request.remote_addr or "unknown"
    hashed_ip  = hash_ip(ip_address)
    identifier = f"{hashed_ip}_{poll_id}"

    # ── Step 8: Insert one vote row per option_id ─────────
    first_vote_id = None

    for option_id in option_ids:
        cursor = conn.execute("""
            INSERT INTO votes (poll_id, selected_option_id,
                               submission_id,
                               created_at, created_id)
            VALUES (?, ?, ?, ?, ?)
        """, (
            poll_id,
            option_id,
            submission_id,
            datetime.now().isoformat(),
            session.get('user_id')
        ))

        # Save first vote_id for vote_identity
        if first_vote_id is None:
            first_vote_id = cursor.lastrowid

    # ── Step 9: Save encrypted identity ───────────────────
    # Only ONE identity record per submission
    encrypted = encrypt_identifier(identifier)
    conn.execute("""
        INSERT INTO vote_identity (vote_id,
                                   encrypted_identifier,
                                   created_at)
        VALUES (?, ?, ?)
    """, (
        first_vote_id,
        encrypted,
        datetime.now().isoformat()
    ))

    conn.commit()

    # ── Step 10: Calculate results for broadcast ──────────
    options = conn.execute("""
        SELECT id, option FROM options
        WHERE poll_id = ? AND status = 1
    """, (poll_id,)).fetchall()

    # Count using DISTINCT submission_id
    # so multiple choice doesn't inflate totals
    all_votes = conn.execute("""
        SELECT selected_option_id,
               COUNT(DISTINCT submission_id) as count
        FROM votes
        WHERE poll_id = ?
        GROUP BY selected_option_id
    """, (poll_id,)).fetchall()

    # Total unique submissions
    total_row = conn.execute("""
        SELECT COUNT(DISTINCT submission_id) as total
        FROM votes WHERE poll_id = ?
    """, (poll_id,)).fetchone()
    total_votes = total_row['total'] if total_row else 0

    # Build vote_counts dict
    vote_counts = {o["id"]: 0 for o in options}
    for v in all_votes:
        vote_counts[v["selected_option_id"]] = v["count"]

    option_map = {o["id"]: o["option"] for o in options}
    results    = []
    for o in options:
        count      = vote_counts.get(o["id"], 0)
        percentage = round((count / total_votes * 100), 1) \
                     if total_votes > 0 else 0
        results.append({
            "option":     o["option"],
            "votes":      count,
            "percentage": percentage
        })

    conn.close()

    # ── Step 11: Emit WebSocket update ────────────────────
    get_socketio().emit(
        "vote_update",
        {
            "poll_id":     poll_id,
            "results":     results,
            "total_votes": total_votes
        },
        room=str(poll_id)
    )

    # ── Step 12: Mark session as voted ────────────────────
    # session[voted_key] = True
    # session.permanent  = True

    return jsonify({
        "message":      "Vote submitted successfully!",
        "results_link": f"/poll/{poll_id}/results"
    }), 201


# ── GET /api/poll/<poll_id>/results ───────────────────────
@vote_bp.route("/api/poll/<string:token>/results",
               methods=["GET"])
def get_results(token):

    conn = get_db_connection()
    poll = conn.execute(
        "SELECT * FROM polls WHERE share_token = ?", (token,)
    ).fetchone()

    if not poll:
        conn.close()
        return jsonify({"error": "Poll not found."}), 404

    poll_id = poll["id"]

    options = conn.execute("""
        SELECT id, option FROM options
        WHERE poll_id = ? AND status = 1
    """, (poll_id,)).fetchall()

    # Count per option using DISTINCT submission_id
    all_votes = conn.execute("""
        SELECT selected_option_id,
               COUNT(DISTINCT submission_id) as count
        FROM votes
        WHERE poll_id = ?
        GROUP BY selected_option_id
    """, (poll_id,)).fetchall()

    # Total unique voters
    total_row = conn.execute("""
        SELECT COUNT(DISTINCT submission_id) as total
        FROM votes WHERE poll_id = ?
    """, (poll_id,)).fetchone()
    total_votes = total_row['total'] if total_row else 0

    conn.close()

    vote_counts = {o["id"]: 0 for o in options}
    for v in all_votes:
        vote_counts[v["selected_option_id"]] = v["count"]

    results = []
    for o in options:
        count      = vote_counts.get(o["id"], 0)
        percentage = round((count / total_votes * 100), 1) \
                     if total_votes > 0 else 0
        results.append({
            "option":     o["option"],
            "votes":      count,
            "percentage": percentage
        })

    end_dt     = datetime.fromisoformat(
        poll["end_time"].replace("T"," ")[:19]
    )
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