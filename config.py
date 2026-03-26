import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    #secret key used to sign session cookies
    SECRET_KEY = os.getenv("SECRET_KEY", "pulsepoll_secret")

    DATABASE_URL  = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://", "postgresql://", 1
        )
    #used to encrypt voter identities
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

    #SQLite file inside our database folder
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # DATABASE_PATH = os.path.join(BASE_DIR, "database", "polls.db")
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    #session configuration
    SESSION_TYPE = "filesystem"