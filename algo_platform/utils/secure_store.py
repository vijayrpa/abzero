from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


@dataclass(frozen=True)
class SecureStore:
    path: str
    iterations: int

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.iterations,
        )
        return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def init_new(self, passphrase: str) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        salt = os.urandom(16)
        key = self._derive_key(passphrase, salt)
        f = Fernet(key)
        payload = {"version": 1, "data": {}}
        token = f.encrypt(json.dumps(payload).encode("utf-8"))
        blob = {
            "salt_b64": base64.b64encode(salt).decode("ascii"),
            "token_b64": base64.b64encode(token).decode("ascii"),
        }
        with open(self.path, "w", encoding="utf-8") as fp:
            json.dump(blob, fp)

    def _load_blob(self) -> Dict[str, str]:
        with open(self.path, "r", encoding="utf-8") as fp:
            return json.load(fp)

    def _save_blob(self, blob: Dict[str, str]) -> None:
        with open(self.path, "w", encoding="utf-8") as fp:
            json.dump(blob, fp)

    def load_data(self, passphrase: str) -> Dict[str, Any]:
        if not self.exists():
            self.init_new(passphrase)
        blob = self._load_blob()
        salt = base64.b64decode(blob["salt_b64"])
        token = base64.b64decode(blob["token_b64"])
        key = self._derive_key(passphrase, salt)
        f = Fernet(key)
        try:
            raw = f.decrypt(token)
        except InvalidToken as e:
            raise ValueError("Invalid passphrase for encrypted credentials store.") from e
        payload = json.loads(raw.decode("utf-8"))
        if payload.get("version") != 1 or "data" not in payload:
            raise ValueError("Unsupported credentials store format.")
        return payload["data"]

    def save_data(self, passphrase: str, data: Dict[str, Any]) -> None:
        if not self.exists():
            self.init_new(passphrase)
        blob = self._load_blob()
        salt = base64.b64decode(blob["salt_b64"])
        key = self._derive_key(passphrase, salt)
        f = Fernet(key)
        payload = {"version": 1, "data": data}
        token = f.encrypt(json.dumps(payload).encode("utf-8"))
        blob["token_b64"] = base64.b64encode(token).decode("ascii")
        self._save_blob(blob)

    def get_broker_creds(self, passphrase: str, broker_name: str) -> Dict[str, Any]:
        data = self.load_data(passphrase)
        return dict(data.get(broker_name, {}))

    def set_broker_creds(self, passphrase: str, broker_name: str, creds: Dict[str, Any]) -> None:
        data = self.load_data(passphrase)
        data[broker_name] = creds
        self.save_data(passphrase, data)

    def delete_broker_creds(self, passphrase: str, broker_name: str) -> None:
        data = self.load_data(passphrase)
        if broker_name in data:
            del data[broker_name]
            self.save_data(passphrase, data)


def redact_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if any(s in k.lower() for s in ("password", "token", "secret", "api_key", "apikey", "otp", "totp")):
            out[k] = "***"
        else:
            out[k] = v
    return out

