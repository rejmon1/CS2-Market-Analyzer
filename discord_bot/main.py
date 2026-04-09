"""
Punkt wejścia modułu discord_bot.

Funkcje:
  - Komendy tekstowe (prefix `!`) do zarządzania listą śledzonych itemów i przeglądania danych.
  - Pętla w tle: co ALERT_POLL_INTERVAL_SECONDS sprawdza niesłane alerty i wysyła je
    na kanał DISCORD_CHANNEL_ID.

Komendy:
  !add_item <market_hash_name>   — dodaje item do śledzenia
  !remove_item <market_hash_name>— deaktywuje śledzenie (soft-delete)
  !list_items                    — wyświetla aktywnie śledzone itemy
  !price <market_hash_name>      — ostatnie ceny z każdego rynku
  !alerts                        — niesłane alerty arbitrażowe
  !clear_alerts                  — oznacza wszystkie alerty jako przeczytane
"""
from __future__ import annotations

import sys

import discord
from discord.ext import commands, tasks

import config
from shared import db
from shared.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Konfiguracja intents
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True   # wymagane dla komend z prefiksem

bot = commands.Bot(command_prefix="!", intents=intents)


# ---------------------------------------------------------------------------
# Pomocnicze
# ---------------------------------------------------------------------------

def _fmt_price_row(row: dict) -> str:
    price = float(row["lowest_price"])
    qty = row["quantity"] if row.get("quantity") is not None else "?"
    ts = row["fetched_at"].strftime("%H:%M:%S") if row.get("fetched_at") else "?"
    return f"  **{row['market']}**: ${price:.2f}  (wolumen: {qty}, o {ts} UTC)"


def _fmt_alert(alert: dict) -> str:
    d = alert["details"]
    spread = d.get("spread_pct", "?")
    buy_market = d.get("market_buy", "?")
    sell_market = d.get("market_sell", "?")
    price_buy = d.get("price_buy_raw", "?")
    price_sell = d.get("price_sell_raw", "?")
    return (
        f"💹 **{alert['market_hash_name']}**\n"
        f"   Kup na **{buy_market}** za ${price_buy}  →  "
        f"Sprzedaj na **{sell_market}** za ${price_sell}\n"
        f"   Spread netto: **{spread}%**"
    )


# ---------------------------------------------------------------------------
# Komendy
# ---------------------------------------------------------------------------

@bot.command(name="add_item")
async def add_item(ctx: commands.Context, *, market_hash_name: str):
    """Dodaje item do listy śledzonych (lub reaktywuje jeśli był deaktywowany)."""
    try:
        conn = db.get_connection()
        try:
            db.upsert_item(conn, market_hash_name, added_by=str(ctx.author.id))
        finally:
            conn.close()
    except Exception as exc:
        logger.exception("Błąd przy add_item: %s", exc)
        await ctx.send(f"❌ Błąd: {exc}")
        return
    await ctx.send(f"✅ Item **{market_hash_name}** dodany do śledzenia.")
    logger.info("add_item: %r przez %s", market_hash_name, ctx.author)


@bot.command(name="remove_item")
async def remove_item(ctx: commands.Context, *, market_hash_name: str):
    """Deaktywuje śledzenie itemu (soft-delete, historia cen zachowana)."""
    try:
        conn = db.get_connection()
        try:
            found = db.deactivate_item(conn, market_hash_name)
        finally:
            conn.close()
    except Exception as exc:
        logger.exception("Błąd przy remove_item: %s", exc)
        await ctx.send(f"❌ Błąd: {exc}")
        return
    if found:
        await ctx.send(f"🗑️ Item **{market_hash_name}** deaktywowany.")
    else:
        await ctx.send(f"⚠️ Nie znaleziono itemu **{market_hash_name}** w bazie.")
    logger.info("remove_item: %r przez %s (found=%s)", market_hash_name, ctx.author, found)


@bot.command(name="list_items")
async def list_items(ctx: commands.Context):
    """Wyświetla wszystkie aktywnie śledzone itemy."""
    try:
        conn = db.get_connection()
        try:
            items = db.get_active_items(conn)
        finally:
            conn.close()
    except Exception as exc:
        logger.exception("Błąd przy list_items: %s", exc)
        await ctx.send(f"❌ Błąd: {exc}")
        return

    if not items:
        await ctx.send("📋 Brak aktywnie śledzonych itemów.")
        return

    lines = [f"📋 **Śledzone itemy ({len(items)}):**"]
    for name in items:
        lines.append(f"  • {name}")

    # Discord ma limit 2000 znaków — podziel na chunki
    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 1 > 1990:
            await ctx.send(chunk)
            chunk = line
        else:
            chunk = f"{chunk}\n{line}" if chunk else line
    if chunk:
        await ctx.send(chunk)


@bot.command(name="price")
async def price(ctx: commands.Context, *, market_hash_name: str):
    """Pokazuje ostatnie ceny z każdego rynku dla podanego itemu (bez odpytywania API)."""
    try:
        conn = db.get_connection()
        try:
            rows = db.get_latest_prices(conn, market_hash_name)
        finally:
            conn.close()
    except Exception as exc:
        logger.exception("Błąd przy price: %s", exc)
        await ctx.send(f"❌ Błąd: {exc}")
        return

    if not rows:
        await ctx.send(f"⚠️ Brak danych cenowych dla **{market_hash_name}**.")
        return

    lines = [f"💰 **{market_hash_name}**"]
    for row in rows:
        lines.append(_fmt_price_row(row))
    await ctx.send("\n".join(lines))


@bot.command(name="alerts")
async def alerts_cmd(ctx: commands.Context):
    """Wyświetla nowe (niesłane) alerty arbitrażowe z bazy danych."""
    try:
        conn = db.get_connection()
        try:
            unsent = db.get_unsent_alerts(conn)
        finally:
            conn.close()
    except Exception as exc:
        logger.exception("Błąd przy alerts: %s", exc)
        await ctx.send(f"❌ Błąd: {exc}")
        return

    if not unsent:
        await ctx.send("✅ Brak nowych alertów arbitrażowych.")
        return

    lines = [f"🔔 **Nowe alerty ({len(unsent)}):**\n"]
    for alert in unsent:
        lines.append(_fmt_alert(alert))

    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 2 > 1990:
            await ctx.send(chunk)
            chunk = line
        else:
            chunk = f"{chunk}\n{line}" if chunk else line
    if chunk:
        await ctx.send(chunk)


@bot.command(name="clear_alerts")
async def clear_alerts(ctx: commands.Context):
    """Oznacza wszystkie niesłane alerty jako przeczytane."""
    ids: list[int] = []
    try:
        conn = db.get_connection()
        try:
            unsent = db.get_unsent_alerts(conn)
            ids = [a["id"] for a in unsent]
            db.mark_alerts_sent(conn, ids)
        finally:
            conn.close()
    except Exception as exc:
        logger.exception("Błąd przy clear_alerts: %s", exc)
        await ctx.send(f"❌ Błąd: {exc}")
        return

    if ids:
        await ctx.send(f"🧹 Oznaczono {len(ids)} alertów jako przeczytane.")
    else:
        await ctx.send("✅ Nie było niesłanych alertów.")
    logger.info("clear_alerts: oznaczono %d alertów przez %s", len(ids), ctx.author)


# ---------------------------------------------------------------------------
# Pętla w tle — automatyczne wysyłanie nowych alertów na kanał
# ---------------------------------------------------------------------------

@tasks.loop(seconds=config.get_alert_poll_interval())
async def alert_sender():
    """Co ALERT_POLL_INTERVAL_SECONDS sprawdza niesłane alerty i wysyła je na kanał."""
    channel_id = config.get_discord_channel_id()
    if channel_id is None:
        return

    channel = bot.get_channel(channel_id)
    if channel is None:
        logger.warning("Kanał %d nie znaleziony — sprawdź DISCORD_CHANNEL_ID", channel_id)
        return

    try:
        conn = db.get_connection()
        try:
            unsent = db.get_unsent_alerts(conn)
            if not unsent:
                return
            ids = [a["id"] for a in unsent]
            for alert in unsent:
                await channel.send(_fmt_alert(alert))
            db.mark_alerts_sent(conn, ids)
            logger.info("alert_sender: wysłano %d alertów na kanał %d", len(ids), channel_id)
        finally:
            conn.close()
    except Exception as exc:
        logger.exception("Błąd w pętli alert_sender: %s", exc)


@alert_sender.before_loop
async def before_alert_sender():
    await bot.wait_until_ready()


# ---------------------------------------------------------------------------
# Zdarzenia bota
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    logger.info("Bot zalogowany jako %s (id: %s)", bot.user, bot.user.id)
    logger.info("Prefiks komend: !")
    channel_id = config.get_discord_channel_id()
    if channel_id:
        logger.info("Kanał alertów: %d", channel_id)
    else:
        logger.warning("DISCORD_CHANNEL_ID nie ustawiony — automatyczne alerty wyłączone")
    if not alert_sender.is_running():
        alert_sender.start()


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ Brakujący argument. Użycie: `!{ctx.command.name} <market_hash_name>`")
    elif isinstance(error, commands.CommandNotFound):
        pass  # ignoruj nieznane komendy
    else:
        logger.error("Błąd komendy %s: %s", ctx.command, error)
        await ctx.send(f"❌ Nieoczekiwany błąd: {error}")


# ---------------------------------------------------------------------------
# Punkt wejścia
# ---------------------------------------------------------------------------

def main() -> None:
    try:
        token = config.get_discord_token()
    except RuntimeError as exc:
        logger.error("%s — bot nie zostanie uruchomiony", exc)
        logger.info(
            "Ustaw DISCORD_TOKEN w pliku .env i zrestartuj kontener discord_bot. "
            "Instrukcja: https://discord.com/developers/applications"
        )
        sys.exit(1)

    logger.info("Discord bot service starting…")
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()

