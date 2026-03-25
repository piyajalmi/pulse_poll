import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    #secret key used to sign session cookies
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret_key")

    #used to encrypt voter identities
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

    #SQLite file inside our database folder
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    DATABASE_PATH = os.path.join(BASE_DIR, "database", "polls.db")

    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

    #session configuration
    SESSION_TYPE = "filesystem"