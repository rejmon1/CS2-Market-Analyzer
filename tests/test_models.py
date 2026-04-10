from datetime import datetime, timezone

from shared.models import Item, PriceRecord


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
