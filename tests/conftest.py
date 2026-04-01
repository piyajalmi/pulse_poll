import sys
from pathlib import Path
import types
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_stubbed_modules():
    # dotenv fallback for app/config import.
    if "dotenv" not in sys.modules:
        dotenv = types.ModuleType("dotenv")
        dotenv.load_dotenv = lambda *_args, **_kwargs: None
        sys.modules["dotenv"] = dotenv

    # pytz fallback for app/poll route datetime handling.
    if "pytz" not in sys.modules:
        from datetime import timezone

        pytz = types.ModuleType("pytz")

        class _Tz:
            def localize(self, dt):
                return dt.replace(tzinfo=timezone.utc)

        pytz.timezone = lambda _name: _Tz()
        sys.modules["pytz"] = pytz

    # firebase_admin fallback for firebase utility tests.
    if "firebase_admin" not in sys.modules:
        fadmin = types.ModuleType("firebase_admin")
        fadmin._apps = []
        fadmin.initialize_app = lambda *_args, **_kwargs: None

        cred_mod = types.ModuleType("credentials")
        cred_mod.Certificate = lambda payload: payload

        class _DummyRef:
            def set(self, _payload):
                return None

        db_mod = types.ModuleType("db")
        db_mod.reference = lambda _path: _DummyRef()

        fadmin.credentials = cred_mod
        fadmin.db = db_mod
        sys.modules["firebase_admin"] = fadmin

    # psycopg2 fallback so models.py can import.
    if "psycopg2" not in sys.modules:
        psy = types.ModuleType("psycopg2")

        class _StubCursor:
            def execute(self, *_args, **_kwargs):
                return None

            def fetchone(self):
                return None

            def fetchall(self):
                return []

            def close(self):
                return None

        class _StubConn:
            def cursor(self):
                return _StubCursor()

            def commit(self):
                return None

            def rollback(self):
                return None

            def close(self):
                return None

        psy.connect = lambda *_args, **_kwargs: _StubConn()
        extras = types.ModuleType("extras")
        extras.RealDictCursor = object
        psy.extras = extras
        sys.modules["psycopg2"] = psy
        sys.modules["psycopg2.extras"] = extras

    # bcrypt fallback for auth routes.
    if "bcrypt" not in sys.modules:
        bcrypt = types.ModuleType("bcrypt")
        bcrypt.gensalt = lambda: b"salt"
        bcrypt.hashpw = lambda password, _salt: b"hashed-" + password
        bcrypt.checkpw = lambda password, hashed: hashed == b"hashed-" + password
        sys.modules["bcrypt"] = bcrypt

    # openpyxl fallback for report export routes.
    if "openpyxl" not in sys.modules:
        openpyxl = types.ModuleType("openpyxl")
        openpyxl.__path__ = []

        styles_mod = types.ModuleType("styles")
        utils_mod = types.ModuleType("utils")

        class _Style:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        class _FakeSheet:
            def append(self, _row):
                return None

        class _FakeWorkbook:
            def __init__(self):
                self.active = _FakeSheet()

            def save(self, _file):
                return None

        openpyxl.Workbook = _FakeWorkbook
        styles_mod.Font = _Style
        styles_mod.Alignment = _Style
        styles_mod.PatternFill = _Style
        styles_mod.Border = _Style
        styles_mod.Side = _Style
        utils_mod.get_column_letter = lambda index: str(index)
        openpyxl.styles = styles_mod
        openpyxl.utils = utils_mod
        sys.modules["openpyxl"] = openpyxl
        sys.modules["openpyxl.styles"] = styles_mod
        sys.modules["openpyxl.utils"] = utils_mod

    # Crypto fallback for security utils.
    if "Crypto" not in sys.modules:
        crypto = types.ModuleType("Crypto")
        cipher_mod = types.ModuleType("Cipher")
        util_mod = types.ModuleType("Util")
        padding_mod = types.ModuleType("Padding")

        def pad(data, block_size):
            pad_len = block_size - (len(data) % block_size)
            return data + bytes([pad_len] * pad_len)

        def unpad(data, _block_size):
            pad_len = data[-1]
            return data[:-pad_len]

        class _FakeAES:
            MODE_CBC = 1
            block_size = 16

            def __init__(self, key, mode, iv=None):
                self.key = key
                self.mode = mode
                self.iv = iv or (b"0" * 16)

            def encrypt(self, data):
                return data

            def decrypt(self, data):
                return data

            @classmethod
            def new(cls, key, mode, iv=None):
                return cls(key, mode, iv=iv)

        aes_mod = types.ModuleType("AES")
        aes_mod.MODE_CBC = _FakeAES.MODE_CBC
        aes_mod.block_size = _FakeAES.block_size
        aes_mod.new = _FakeAES.new

        padding_mod.pad = pad
        padding_mod.unpad = unpad
        cipher_mod.AES = aes_mod
        util_mod.Padding = padding_mod

        crypto.Cipher = cipher_mod
        crypto.Util = util_mod

        sys.modules["Crypto"] = crypto
        sys.modules["Crypto.Cipher"] = cipher_mod
        sys.modules["Crypto.Cipher.AES"] = aes_mod
        sys.modules["Crypto.Util"] = util_mod
        sys.modules["Crypto.Util.Padding"] = padding_mod


_ensure_stubbed_modules()


class ScriptedCursor:
    def __init__(self, fetchone_values=None, fetchall_values=None):
        self.fetchone_values = list(fetchone_values or [])
        self.fetchall_values = list(fetchall_values or [])
        self.executed = []
        self.closed = False

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        return self.fetchone_values.pop(0) if self.fetchone_values else None

    def fetchall(self):
        return self.fetchall_values.pop(0) if self.fetchall_values else []

    def close(self):
        self.closed = True


class ScriptedConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


@pytest.fixture
def make_scripted_db():
    def _factory(fetchone_values=None, fetchall_values=None):
        cursor = ScriptedCursor(
            fetchone_values=fetchone_values,
            fetchall_values=fetchall_values,
        )
        conn = ScriptedConnection(cursor)
        return conn, cursor

    return _factory
