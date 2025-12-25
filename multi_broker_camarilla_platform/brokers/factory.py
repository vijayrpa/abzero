
from __future__ import annotations

from config.defaults import BrokerName
from brokers.paper import PaperBroker
from brokers.zerodha import ZerodhaBroker
from brokers.angelone import AngelOneBroker
from brokers.aliceblue import AliceBlueBroker
from brokers.shoonya import ShoonyaBroker


def create_broker(name: BrokerName):
    n = (name.value if hasattr(name, "value") else str(name)).upper()
    if n == "PAPER":
        return PaperBroker()
    if n == "ZERODHA":
        return ZerodhaBroker()
    if n == "ANGELONE":
        return AngelOneBroker()
    if n == "ALICEBLUE":
        return AliceBlueBroker()
    if n == "SHOONYA":
        return ShoonyaBroker()
    raise ValueError(f"Unknown broker: {name}")
