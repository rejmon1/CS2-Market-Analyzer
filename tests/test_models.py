from datetime import datetime, timezone

from shared.models import Alert, Item, MarketFee, PriceRecord


def test_price_record_creation():
    """Testuje poprawność tworzenia obiektu PriceRecord."""
    now = datetime.now(timezone.utc)
    record = PriceRecord(
        market_hash_name="AK-47 | Redline (Field-Tested)",
        market="steam",
        lowest_price=25.50,
        quantity=150,
        raw_data={"test": "data"},
        fetched_at=now,
    )
    assert record.market_hash_name == "AK-47 | Redline (Field-Tested)"
    assert record.lowest_price == 25.50
    assert record.fetched_at == now


def test_price_record_default_fetched_at():
    """Testuje domyślną wartość fetched_at (powinna być ustawiona automatycznie)."""
    before = datetime.now(timezone.utc)
    record = PriceRecord(
        market_hash_name="AWP | Dragon Lore (Factory New)",
        market="skinport",
        lowest_price=1500.0,
        quantity=2,
        raw_data={},
    )
    after = datetime.now(timezone.utc)
    assert before <= record.fetched_at <= after


def test_price_record_market_field():
    """Testuje pole market dla różnych rynków."""
    for market in ("steam", "skinport", "csfloat"):
        record = PriceRecord(
            market_hash_name="Karambit | Fade (Factory New)",
            market=market,
            lowest_price=500.0,
            quantity=10,
            raw_data={},
        )
        assert record.market == market


def test_item_creation():
    """Testuje poprawność tworzenia obiektu Item."""
    now = datetime.now(timezone.utc)
    item = Item(
        id=1,
        market_hash_name="AWP | Asiimov (Field-Tested)",
        is_active=True,
        added_by=None,
        created_at=now,
    )
    assert item.id == 1
    assert item.is_active is True
    assert item.market_hash_name == "AWP | Asiimov (Field-Tested)"


def test_item_added_by():
    """Testuje pole added_by — może być Discord ID lub None."""
    now = datetime.now(timezone.utc)
    item = Item(
        id=42,
        market_hash_name="M4A4 | Howl (Factory New)",
        is_active=True,
        added_by="123456789012345678",
        created_at=now,
    )
    assert item.added_by == "123456789012345678"


def test_item_inactive():
    """Testuje flagę is_active = False (soft-delete)."""
    now = datetime.now(timezone.utc)
    item = Item(
        id=5,
        market_hash_name="Glock-18 | Fade (Factory New)",
        is_active=False,
        added_by=None,
        created_at=now,
    )
    assert item.is_active is False


def test_market_fee_creation():
    """Testuje poprawność tworzenia obiektu MarketFee."""
    fee = MarketFee(market="steam", seller_fee=0.15, buyer_fee=0.0)
    assert fee.market == "steam"
    assert fee.seller_fee == 0.15
    assert fee.buyer_fee == 0.0


def test_market_fee_skinport():
    """Testuje prowizje dla rynku Skinport."""
    fee = MarketFee(market="skinport", seller_fee=0.12, buyer_fee=0.0)
    assert fee.market == "skinport"
    assert fee.seller_fee == 0.12


def test_market_fee_with_buyer_fee():
    """Testuje rynek z niezerową prowizją kupującego."""
    fee = MarketFee(market="custom_market", seller_fee=0.10, buyer_fee=0.05)
    assert fee.buyer_fee == 0.05


def test_alert_creation():
    """Testuje poprawność tworzenia obiektu Alert."""
    now = datetime.now(timezone.utc)
    alert = Alert(
        id=1,
        item_id=10,
        alert_type="arbitrage",
        details={"market_buy": "steam", "market_sell": "skinport", "spread_pct": 7.5},
        sent=False,
        created_at=now,
    )
    assert alert.id == 1
    assert alert.item_id == 10
    assert alert.alert_type == "arbitrage"
    assert alert.details["spread_pct"] == 7.5
    assert alert.sent is False
    assert alert.created_at == now


def test_alert_sent_flag():
    """Testuje alert z flagą sent=True."""
    now = datetime.now(timezone.utc)
    alert = Alert(
        id=99,
        item_id=5,
        alert_type="pump_dump",
        details={"reason": "volume spike"},
        sent=True,
        created_at=now,
    )
    assert alert.sent is True


def test_alert_no_item_id():
    """Testuje alert globalny (bez powiązanego item_id — None)."""
    now = datetime.now(timezone.utc)
    alert = Alert(
        id=2,
        item_id=None,
        alert_type="inventory_value",
        details={"discord_id": "111", "diff_pct": -6.5},
        sent=False,
        created_at=now,
    )
    assert alert.item_id is None
    assert alert.alert_type == "inventory_value"
