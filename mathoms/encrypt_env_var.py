import os, base64, json, getpass
from Crypto.Protocol.KDF import scrypt as _scrypt
from Crypto.Cipher import AES

VERSION = 1
b64e = lambda b: base64.urlsafe_b64encode(b).decode("ascii")


def derive_key(password: bytes, salt: bytes) -> bytes:
    return _scrypt(password, salt, 32, N=2**15, r=8, p=1)


api_key_name = input("API key name to encrypt: ").upper()


print(f"Getting {api_key_name} from environment...")
api_key = os.getenv(api_key_name, None)
if api_key is None:
    print(f"Error: environment variable {api_key_name} not set.")
    exit(1)

api_key = api_key.encode()
password = getpass.getpass("Password (to derive encryption key): ").encode()

salt = os.urandom(16)
key = derive_key(password, salt)

nonce = os.urandom(12)
cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
ct, tag = cipher.encrypt_and_digest(api_key)

payload = {"v": VERSION, "s": b64e(salt), "n": b64e(nonce), "c": b64e(ct + tag)}
token = "ENC:" + base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()

print("\nPut this in your env:\n")
print(f'export ENCRYPTED_{api_key_name}="{token}"\n')
