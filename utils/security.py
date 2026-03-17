import hashlib
import secrets
import base64
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from config import Config

#getting encryption key
def get_encryption_key():
    '''get 32-byte AES encryption key from config'''
    key = Config.ENCRYPTION_KEY
    if not key:
        raise ValueError("Encryption key not set in .env")
    #ensuring key is 32-byte
    return key.encode("utf-8")[:32].ljust(32, b"0")

#AES encryption
def encrypt_identifier(plain_text):
    '''encrypt voter identifier using AES encryption'''
    key = get_encryption_key()
    cipher = AES.new(key, AES.MODE_CBC)
    encrypted = cipher.encrypt(pad(plain_text.encode("utf-8"), AES.block_size))
    #commbining IV + encrypted data and encode to base64 for storage
    result = base64.b64encode(cipher.iv + encrypted).decode("utf-8")
    return result

#AES DECRYPTION
def decrypt_identifier(encrypted_text):
    '''decrypt encrypted voter identifier'''
    key = get_encryption_key()
    raw = base64.b64decode(encrypted_text)
    iv = raw[:16]
    encrypted_data = raw[16:]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = unpad(cipher.decrypt(encrypted_data), AES.block_size)
    return decrypted.decode("utf-8")

#SHA-256 IP HASGING
def hash_ip(ip_address):
    '''hash IP address using SHA-256'''
    return hashlib.sha256(ip_address.encode("utf-8")).hexdigest()

# #unique poll id generator
# def generate_poll_id():
#     '''generate a unique 8 character  poll ID'''
#     return secrets.token_urlsafe(6)