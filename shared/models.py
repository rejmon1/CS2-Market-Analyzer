"""
Modele danych wspólne dla wszystkich serwisów.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class PriceRecord:
    """Pojedynczy odczyt ceny dla jednego przedmiotu z jednego rynku."""

    market_hash_name: str
    market: str               # 'steam' | 'skinport' | 'csfloat'
    lowest_price: float       # najniższa cena w USD
    quantity: int             # metryka zależna od rynku (np. oferty, sprzedaż 7d)
    raw_data: dict[str, Any]  # surowa odpowiedź API
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Item:
    """Przedmiot CS2 śledzony przez system."""

    id: int
    market_hash_name: str
    is_active: bool
    added_by: str | None      # Discord user ID lub None (seed z pliku)
    created_at: datetime


@dataclass
class MarketFee:
    """Prowizje jednego rynku — pobierane z tabeli market_fees."""

    market: str
    seller_fee: float   # ułamek ceny potrącany od sprzedającego (0.15 = 15%)
    buyer_fee: float    # ułamek doliczany kupującemu ponad cenę listingu (zwykle 0)


@dataclass
class Alert:
    """Alert arbitrażowy lub anomalia wolumenu gotowa do wysłania przez bota."""

    id: int
    item_id: int
    alert_type: str           # 'arbitrage' | 'pump_dump' | 'price_drop'
    details: dict[str, Any]
    sent: bool
    created_at: datetime
