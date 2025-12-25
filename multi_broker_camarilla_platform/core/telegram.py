
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, Optional

import requests


log = logging.getLogger("telegram")


class TelegramClient:
    def __init__(self, bot_token: str, chat_id: str, poll_interval_sec: float = 2.0):
        self.bot_token = bot_token.strip()
        self.chat_id = str(chat_id).strip()
        self.poll_interval_sec = float(poll_interval_sec)
        self._base = f"https://api.telegram.org/bot{self.bot_token}"
        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._offset: Optional[int] = None

    def send(self, text: str) -> None:
        if not self.bot_token or not self.chat_id:
            return
        try:
            requests.post(
                f"{self._base}/sendMessage",
                json={"chat_id": self.chat_id, "text": text},
                timeout=10,
            ).raise_for_status()
        except Exception as e:
            log.warning("Telegram send failed: %s", e)

    def start_kill_switch_listener(self, on_stop: Callable[[], None]) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._poll_loop, args=(on_stop,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()

    def _poll_loop(self, on_stop: Callable[[], None]) -> None:
        if not self.bot_token:
            return
        while not self._stop_evt.is_set():
            try:
                params = {"timeout": 0}
                if self._offset is not None:
                    params["offset"] = self._offset
                r = requests.get(f"{self._base}/getUpdates", params=params, timeout=15)
                r.raise_for_status()
                data = r.json()
                for upd in data.get("result", []):
                    self._offset = int(upd["update_id"]) + 1
                    msg = (upd.get("message") or {}).get("text") or ""
                    chat = (upd.get("message") or {}).get("chat") or {}
                    chat_id = str(chat.get("id") or "")
                    if chat_id != self.chat_id:
                        continue
                    if msg.strip().upper() == "STOP":
                        log.warning("Telegram STOP received. Triggering kill switch.")
                        try:
                            on_stop()
                        except Exception as e:
                            log.exception("Kill switch handler failed: %s", e)
            except Exception as e:
                log.warning("Telegram poll error: %s", e)
            time.sleep(self.poll_interval_sec)
