
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet, InvalidToken

from config.paths import vault_path


@dataclass
class VaultRecord:
    version: int
    salt_b64: str
    iterations: int
    token_b64: str


class CredentialVault:
    '''
    Encrypted local vault.
    - Derives key from master password (PBKDF2-HMAC-SHA256).
    - Encrypts JSON payload with Fernet.
    '''

    VERSION = 1
    DEFAULT_ITERATIONS = 310_000

    def __init__(self, path: Optional[Path] = None):
        self.path = path or vault_path()

    def exists(self) -> bool:
        return self.path.exists()

    def _derive_key(self, password: str, salt: bytes, iterations: int) -> bytes:
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
        return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))

    def init_empty(self, password: str) -> None:
        salt = os.urandom(16)
        it = self.DEFAULT_ITERATIONS
        key = self._derive_key(password=password, salt=salt, iterations=it)
        f = Fernet(key)
        payload = {"brokers": {}, "telegram": {}}
        token = f.encrypt(json.dumps(payload).encode("utf-8"))
        rec = VaultRecord(
            version=self.VERSION,
            salt_b64=base64.b64encode(salt).decode("ascii"),
            iterations=it,
            token_b64=base64.b64encode(token).decode("ascii"),
        )
        self._write_record(rec)

    def _read_record(self) -> VaultRecord:
        raw = self.path.read_text(encoding="utf-8")
        d = json.loads(raw)
        return VaultRecord(
            version=int(d["version"]),
            salt_b64=str(d["salt_b64"]),
            iterations=int(d["iterations"]),
            token_b64=str(d["token_b64"]),
        )

    def _write_record(self, rec: VaultRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "version": rec.version,
                    "salt_b64": rec.salt_b64,
                    "iterations": rec.iterations,
                    "token_b64": rec.token_b64,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        # Best-effort private perms (0600)
        try:
            os.chmod(self.path, 0o600)
        except Exception:
            pass

    def unlock(self, password: str) -> Dict[str, Any]:
        rec = self._read_record()
        salt = base64.b64decode(rec.salt_b64.encode("ascii"))
        token = base64.b64decode(rec.token_b64.encode("ascii"))
        key = self._derive_key(password=password, salt=salt, iterations=rec.iterations)
        f = Fernet(key)
        try:
            raw = f.decrypt(token)
        except InvalidToken as e:
            raise ValueError("Invalid master password or corrupted vault") from e
        return json.loads(raw.decode("utf-8"))

    def save(self, password: str, payload: Dict[str, Any]) -> None:
        rec = self._read_record()
        salt = base64.b64decode(rec.salt_b64.encode("ascii"))
        key = self._derive_key(password=password, salt=salt, iterations=rec.iterations)
        f = Fernet(key)
        token = f.encrypt(json.dumps(payload).encode("utf-8"))
        new_rec = VaultRecord(
            version=rec.version,
            salt_b64=rec.salt_b64,
            iterations=rec.iterations,
            token_b64=base64.b64encode(token).decode("ascii"),
        )
        self._write_record(new_rec)


def get_broker_creds(payload: Dict[str, Any], broker_name: str) -> Dict[str, Any]:
    return dict((payload.get("brokers") or {}).get(broker_name.upper()) or {})


def set_broker_creds(payload: Dict[str, Any], broker_name: str, creds: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(payload or {})
    brokers = dict(payload.get("brokers") or {})
    brokers[broker_name.upper()] = dict(creds or {})
    payload["brokers"] = brokers
    return payload


def get_telegram_creds(payload: Dict[str, Any]) -> Dict[str, Any]:
    return dict(payload.get("telegram") or {})


def set_telegram_creds(payload: Dict[str, Any], creds: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(payload or {})
    payload["telegram"] = dict(creds or {})
    return payload
