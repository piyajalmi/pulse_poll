import json
import os

import firebase_admin
from firebase_admin import credentials, db

DEFAULT_FIREBASE_DATABASE_URL = (
    "https://pulsepoll-e4314-default-rtdb.firebaseio.com"
)


def init_firebase():
    """Initialize Firebase Admin SDK once."""
    if firebase_admin._apps:
        return

    # On hosting platforms: JSON in env var.
    # Local development: read service account file.
    cred_json = os.environ.get("FIREBASE_CREDENTIALS")

    if cred_json:
        cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)
    else:
        cred = credentials.Certificate("firebase_credentials.json")

    firebase_admin.initialize_app(
        cred,
        {
            "databaseURL": os.environ.get(
                "FIREBASE_DATABASE_URL",
                DEFAULT_FIREBASE_DATABASE_URL,
            )
        },
    )


def push_poll_results(poll_id, results, total_votes):
    """Push vote results to Firebase Realtime Database."""
    try:
        init_firebase()
        ref = db.reference(f"polls/{poll_id}/results")
        ref.set(
            {
                "poll_id": int(poll_id),
                "results": results or [],
                "total_votes": int(total_votes or 0),
                "updated_at": {".sv": "timestamp"},
            }
        )
        print(f"Firebase updated for poll {poll_id}")
    except Exception as error:
        print(f"Firebase error: {error}")
        # Non-fatal: vote/result data is already in PostgreSQL.
