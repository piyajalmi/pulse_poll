from flask import Blueprint, request, jsonify, session
from datetime import datetime, timezone
from models import get_db_connection
from utils.security import encrypt_identifier, hash_ip
from utils.firebase import push_poll_results

vote_bp = Blueprint('vote', __name__)


@vote_bp.route("/poll/<string:token>/vote", methods=["POST"])
def submit_vote(token):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM polls WHERE share_token = %s",
        (token,)
    )
    poll = cursor.fetchone()

    if not poll:
        cursor.close()
        conn.close()
        return jsonify({"error": "Poll not found."}), 404

    poll_id = poll["id"]

    now = datetime.now(timezone.utc)
    if poll["start_time"] and now < poll["start_time"]:
        cursor.close()
        conn.close()
        return jsonify({
            "error": "This poll hasn't started yet.",
            "not_started": True,
        }), 400

    if poll["end_time"] and now > poll["end_time"]:
        cursor.close()
        conn.close()
        return jsonify({
            "error": "This poll has expired.",
            "is_expired": True,
            "results_link": f"/poll/{token}/results",
        }), 400

    cursor.execute(
        """
        SELECT id FROM votes
        WHERE poll_id = %s AND created_id = %s
        """,
        (poll_id, session.get("user_id")),
    )
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "You have already voted."}), 400

    data = request.get_json() or {}
    option_ids = data.get("option_ids", [])
    submission_id = data.get("submission_id", "")

    if not option_ids:
        cursor.close()
        conn.close()
        return jsonify({"error": "No option selected."}), 400

    if poll["poll_type"] == "single" and len(option_ids) > 1:
        cursor.close()
        conn.close()
        return jsonify({"error": "Only one option allowed."}), 400

    for option_id in option_ids:
        cursor.execute(
            """
            SELECT id FROM options
            WHERE id = %s AND poll_id = %s AND status = 1
            """,
            (option_id, poll_id),
        )
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": f"Invalid option: {option_id}"}), 400

    ip_address = request.remote_addr or "unknown"
    hashed_ip = hash_ip(ip_address)
    identifier = f"{hashed_ip}_{poll_id}"

    first_vote_id = None
    for option_id in option_ids:
        cursor.execute(
            """
            INSERT INTO votes
                (poll_id, selected_option_id, submission_id, created_at, created_id)
            VALUES (%s, %s, %s, NOW(), %s)
            RETURNING id
            """,
            (poll_id, option_id, submission_id, session.get("user_id")),
        )
        row = cursor.fetchone()
        if first_vote_id is None:
            first_vote_id = row["id"]

    encrypted = encrypt_identifier(identifier)
    cursor.execute(
        """
        INSERT INTO vote_identity
            (vote_id, encrypted_identifier, created_at)
        VALUES (%s, %s, NOW())
        """,
        (first_vote_id, encrypted),
    )

    conn.commit()

    cursor.execute(
        """
        SELECT id, option FROM options
        WHERE poll_id = %s AND status = 1
        """,
        (poll_id,),
    )
    options = cursor.fetchall()

    cursor.execute(
        """
        SELECT selected_option_id, COUNT(DISTINCT submission_id) as count
        FROM votes
        WHERE poll_id = %s
        GROUP BY selected_option_id
        """,
        (poll_id,),
    )
    all_votes = cursor.fetchall()

    cursor.execute(
        """
        SELECT COUNT(DISTINCT submission_id) as total
        FROM votes
        WHERE poll_id = %s
        """,
        (poll_id,),
    )
    total_row = cursor.fetchone()
    total_votes = total_row["total"] if total_row else 0

    vote_counts = {o["id"]: 0 for o in options}
    for vote in all_votes:
        vote_counts[vote["selected_option_id"]] = vote["count"]

    results = []
    for option in options:
        count = vote_counts.get(option["id"], 0)
        percentage = round((count / total_votes * 100), 1) if total_votes > 0 else 0
        results.append({
            "option": option["option"],
            "votes": count,
            "percentage": percentage,
        })

    cursor.close()
    conn.close()

    try:
        push_poll_results(poll_id, results, total_votes)
    except Exception as error:
        print(f"Firebase push error (non-fatal): {error}")

    return jsonify({
        "message": "Vote submitted successfully!",
        "results_link": f"/poll/{token}/results",
    }), 201


@vote_bp.route("/api/poll/<string:token>/results", methods=["GET"])
def get_results(token):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM polls WHERE share_token = %s",
        (token,)
    )
    poll = cursor.fetchone()

    if not poll:
        cursor.close()
        conn.close()
        return jsonify({"error": "Poll not found."}), 404

    poll_id = poll["id"]

    cursor.execute(
        """
        SELECT id, option FROM options
        WHERE poll_id = %s AND status = 1
        """,
        (poll_id,),
    )
    options = cursor.fetchall()

    cursor.execute(
        """
        SELECT selected_option_id, COUNT(DISTINCT submission_id) as count
        FROM votes
        WHERE poll_id = %s
        GROUP BY selected_option_id
        """,
        (poll_id,),
    )
    all_votes = cursor.fetchall()

    cursor.execute(
        """
        SELECT COUNT(DISTINCT submission_id) as total
        FROM votes
        WHERE poll_id = %s
        """,
        (poll_id,),
    )
    total_row = cursor.fetchone()
    total_votes = total_row["total"] if total_row else 0

    vote_counts = {o["id"]: 0 for o in options}
    for vote in all_votes:
        vote_counts[vote["selected_option_id"]] = vote["count"]

    results = []
    for option in options:
        count = vote_counts.get(option["id"], 0)
        percentage = round((count / total_votes * 100), 1) if total_votes > 0 else 0
        results.append({
            "option": option["option"],
            "votes": count,
            "percentage": percentage,
        })

    is_expired = datetime.now(timezone.utc) >= poll["end_time"]

    cursor.close()
    conn.close()

    try:
        push_poll_results(poll_id, results, total_votes)
    except Exception as error:
        print(f"Firebase sync error (non-fatal): {error}")

    return jsonify({
        "poll_id": poll_id,
        "question": poll["question"],
        "results": results,
        "total_votes": total_votes,
        "is_expired": is_expired,
        "end_time": str(poll["end_time"]),
    }), 200
