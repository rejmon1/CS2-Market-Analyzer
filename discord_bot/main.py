"""
Punkt wejścia modułu discord_bot.

Funkcje:
  - Komendy hybrydowe (Slash i Prefix `!`) do zarządzania ekwipunkiem i śledzenia cen.
  - Pętla w tle: wysyła alerty arbitrażowe na kanał i alerty ekwipunku w DM.
"""

from __future__ import annotations

import json
import sys
from datetime import timedelta

import config
import discord
from discord.ext import commands, tasks

from shared import db
from shared.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Konfiguracja intents
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True  # wymagane dla komend z prefiksem

bot = commands.Bot(command_prefix="!", intents=intents)


# ---------------------------------------------------------------------------
# Pomocnicze
# ---------------------------------------------------------------------------


def _fmt_price_row(row: dict) -> str:
    def _as_dict(value: object) -> dict:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return {}
        return {}

    # Konwersja czasu (wymuszone UTC+2 / CEST)
    ts_utc = row.get("fetched_at")
    if ts_utc:
        ts_local = ts_utc + timedelta(hours=2)
        ts_str = ts_local.strftime("%H:%M:%S")
    else:
        ts_str = "?"

    raw = _as_dict(row.get("raw_data"))
    market = row.get("market", "unknown")
    qty = row.get("quantity", "?")

    lines = [f"  **{market}**:"]

    if market == "steam":
        p = _as_dict(raw.get("prices"))
        s = _as_dict(p.get("sold"))

        if "min" in p:
            lines.append(f"    • Najniższa cena: **${float(p['min']):.2f}**")
        if "median" in p:
            lines.append(f"    • Mediana: **${float(p['median']):.2f}**")

        sold_7d = s.get("last_7d")
        lines.append(f"    • Sprzedano (7 dni): {sold_7d if sold_7d is not None else '?'}")

    elif market == "skinport":
        if "min_price" in raw:
            msg = f"    • Najniższa cena: **${float(raw['min_price']):.2f}**"
            lines.append(msg)
        if "median_price" in raw:
            msg = f"    • Mediana: **${float(raw['median_price']):.2f}**"
            lines.append(msg)
        lines.append(f"    • Aktywne oferty: {qty}")

    elif market == "csfloat":
        if "min_price" in raw:
            lines.append(f"    • Najniższa cena: **${float(raw['min_price']) / 100:.2f}**")
        lines.append(f"    • Aktywne oferty: {qty}")

    lines.append(f"    • Odświeżono: {ts_str} (CEST)")
    return "\n".join(lines)


def _fmt_alert(alert: dict) -> str:
    at = alert["alert_type"]
    d = alert["details"]
    name = alert.get("market_hash_name") or "Ekwipunek"

    if at == "arbitrage":
        spread = d.get("spread_pct", "?")
        buy_m = d.get("market_buy", "?")
        sell_m = d.get("market_sell", "?")
        p_buy = d.get("price_buy_raw", "?")
        p_sell = d.get("price_sell_raw", "?")
        q_sell = d.get("quantity_sell", "?")

        return (
            f"💹 **{name}**\n"
            f"   Kup na **{buy_m}** (Lowest) za **${p_buy}**\n"
            f"   Sprzedaj na **{sell_m}** za **${p_sell}**\n"
            f"   Spread netto: **{spread}%** | Wolumen sprzedaży: {q_sell}"
        )
    elif at == "inventory_value":
        values = d.get("values", {})
        diff_p = d.get("diff_pct", 0)
        new_total = d.get("new_total", 0)
        emoji = "📈" if diff_p > 0 else "📉"

        lines = [
            f"{emoji} **Zmiana wartości Twojego ekwipunku!**",
            f"   Łącznie: **${new_total:.2f}** ({diff_p:+.2f}%)",
            "   Wycena per rynek:",
        ]
        for market, val in values.items():
            lines.append(f"    • {market}: **${val:.2f}**")

        return "\n".join(lines)
    return f"🔔 **{at}**: {name} - {d}"


# ---------------------------------------------------------------------------
# Komendy
# ---------------------------------------------------------------------------


@bot.hybrid_group(name="set", invoke_without_command=True)
async def set_group(ctx: commands.Context):
    """Grupa komend /set. Użycie: /set inventory <link_lub_id>"""
    await ctx.send("❓ Użycie: `/set inventory <link do profilu lub SteamID64>`")


@set_group.command(name="inventory")
async def set_inventory(ctx: commands.Context, *, steam_url_or_id: str):
    """Ustawia SteamID i zleca pobranie ekwipunku."""
    from shared.steam import resolve_steam_id

    steam_id64 = resolve_steam_id(steam_url_or_id)
    if not steam_id64:
        await ctx.send(
            "❌ Nie udało się wyciągnąć SteamID64. "
            "Podaj link `/profiles/ID64` lub samo 17-cyfrowe ID."
        )
        return

    try:
        conn = db.get_connection()
        try:
            db.upsert_user_profile(conn, str(ctx.author.id), steam_id64, pending_update=True)
            await ctx.send(
                f"✅ Ustawiono SteamID: `{steam_id64}`. Ekwipunek zostanie pobrany wkrótce."
            )
        finally:
            conn.close()
    except Exception as e:
        logger.exception("Błąd przy zapisie profilu: %s", e)
        await ctx.send("❌ Wystąpił błąd bazy danych.")


@bot.hybrid_group(name="inv", invoke_without_command=True)
async def inv_group(ctx: commands.Context):
    """Grupa komend /inv. Użycie: /inv info lub /inv update"""
    await ctx.send("❓ Użycie: `/inv info` lub `/inv update`")


@inv_group.command(name="info")
async def inv_info(ctx: commands.Context):
    """Wyświetla listę przedmiotów w ekwipunku i ich aktualną wartość."""
    try:
        conn = db.get_connection()
        try:
            profile = db.get_user_profile(conn, str(ctx.author.id))
            if not profile:
                await ctx.send("❌ Nie masz ustawionego ekwipunku. Użyj `/set inventory <link>`.")
                return

            items = db.get_user_inventory(conn, str(ctx.author.id))
            if not items:
                await ctx.send("📋 Twój ekwipunek w bazie jest pusty. Użyj `/inv update`.")
                return

            market_totals: dict[str, float] = {}
            lines = [f"💰 **Twój ekwipunek CS2 ({len(items)} przedmiotów):**"]

            for item in items:
                name = item["market_hash_name"]
                amount = item["amount"]
                prices = db.get_latest_prices(conn, name)

                # Dodaj do sumy każdego rynku
                for p in prices:
                    m = p["market"]
                    val = float(p["lowest_price"]) * amount
                    market_totals[m] = market_totals.get(m, 0.0) + val

                # Wypisz cenę Steam jako referencyjną
                steam_p = next((p["lowest_price"] for p in prices if p["market"] == "steam"), None)
                if steam_p:
                    total_val = float(steam_p) * amount
                    lines.append(f"  • {name} x{amount} — **${total_val:.2f}** (Steam)")
                else:
                    lines.append(f"  • {name} x{amount} — *brak ceny Steam*")

            lines.append("\n💵 **Wartość portfela per rynek:**")
            for market, total in market_totals.items():
                lines.append(f"  • {market}: **${total:.2f}**")

            last_ts = profile["last_updated"].strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"\n🕒 Ostatnia aktualizacja: {last_ts} UTC")

            chunk = ""
            for line in lines:
                if len(chunk) + len(line) + 2 > 1990:
                    await ctx.send(chunk)
                    chunk = line
                else:
                    chunk = f"{chunk}\n{line}" if chunk else line
            if chunk:
                await ctx.send(chunk)

        finally:
            conn.close()
    except Exception as e:
        logger.exception("Błąd przy inv_info: %s", e)
        await ctx.send("❌ Wystąpił błąd.")


@inv_group.command(name="update")
async def inv_update(ctx: commands.Context):
    """Ręczne wymuszenie odświeżenia ekwipunku."""
    try:
        conn = db.get_connection()
        profile = db.get_user_profile(conn, str(ctx.author.id))
        conn.close()

        if not profile:
            await ctx.send("❌ Najpierw ustaw ekwipunek: `/set inventory <link>`.")
            return

        await set_inventory(ctx, steam_url_or_id=profile["steam_id64"])
    except Exception as e:
        await ctx.send(f"❌ Błąd: {e}")


@bot.hybrid_command(name="add_item")
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
        await ctx.send("❌ Błąd.")
        return
    await ctx.send(f"✅ Item **{market_hash_name}** dodany do śledzenia.")


@bot.hybrid_command(name="remove_item")
async def remove_item(ctx: commands.Context, *, market_hash_name: str):
    """Deaktywuje śledzenie itemu (soft-delete)."""
    try:
        conn = db.get_connection()
        try:
            found = db.deactivate_item(conn, market_hash_name)
        finally:
            conn.close()
    except Exception as exc:
        logger.exception("Błąd przy remove_item: %s", exc)
        await ctx.send("❌ Błąd.")
        return
    if found:
        await ctx.send(f"🗑️ Item **{market_hash_name}** deaktywowany.")
    else:
        await ctx.send("⚠️ Nie znaleziono itemu w bazie.")


@bot.hybrid_command(name="list_items")
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
        await ctx.send("❌ Błąd.")
        return

    if not items:
        await ctx.send("📋 Brak aktywnie śledzonych itemów.")
        return

    lines = [f"📋 **Śledzone itemy ({len(items)}):**"]
    for name in items:
        lines.append(f"  • {name}")

    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 1 > 1990:
            await ctx.send(chunk)
            chunk = line
        else:
            chunk = f"{chunk}\n{line}" if chunk else line
    if chunk:
        await ctx.send(chunk)


@bot.hybrid_command(name="price")
async def price(ctx: commands.Context, *, market_hash_name: str):
    """Pokazuje ostatnie ceny z każdego rynku dla podanego itemu."""
    try:
        conn = db.get_connection()
        try:
            rows = db.get_latest_prices(conn, market_hash_name)
        finally:
            conn.close()
    except Exception as exc:
        logger.exception("Błąd przy price: %s", exc)
        await ctx.send("❌ Błąd.")
        return

    if not rows:
        await ctx.send("⚠️ Brak danych cenowych.")
        return

    lines = [f"💰 **{market_hash_name}**"]
    for row in rows:
        lines.append(_fmt_price_row(row))
    await ctx.send("\n".join(lines))


@bot.hybrid_command(name="alerts")
async def alerts_cmd(ctx: commands.Context):
    """Wyświetla nowe (niesłane) alerty arbitrażowe."""
    try:
        conn = db.get_connection()
        try:
            unsent = db.get_unsent_alerts(conn)
        finally:
            conn.close()
    except Exception as exc:
        logger.exception("Błąd przy alerts: %s", exc)
        await ctx.send("❌ Błąd.")
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


@bot.hybrid_command(name="clear_alerts")
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
        await ctx.send("❌ Błąd.")
        return

    if ids:
        await ctx.send(f"🧹 Oznaczono {len(ids)} alertów jako przeczytane.")
    else:
        await ctx.send("✅ Nie było niesłanych alertów.")


# ---------------------------------------------------------------------------
# Pętla w tle — automatyczne wysyłanie nowych alertów
# ---------------------------------------------------------------------------


@tasks.loop(seconds=config.get_alert_poll_interval())
async def alert_sender():
    """Wysyła niesłane alerty (DM dla portfela, kanał dla arbitrażu)."""
    channel_id = config.get_discord_channel_id()
    channel = bot.get_channel(channel_id) if channel_id else None

    try:
        conn = db.get_connection()
        try:
            unsent = db.get_unsent_alerts(conn)
            if not unsent:
                return

            ids = [a["id"] for a in unsent]
            for alert in unsent:
                msg_content = _fmt_alert(alert)

                if alert["alert_type"] == "inventory_value":
                    d_id = alert["details"].get("discord_id")
                    if d_id:
                        try:
                            user = await bot.fetch_user(int(d_id))
                            if user:
                                await user.send(msg_content)
                        except Exception as e:
                            logger.warning("Błąd wysyłki DM do %s: %s", d_id, e)
                else:
                    if channel and isinstance(channel, discord.abc.Messageable):
                        await channel.send(msg_content)

            db.mark_alerts_sent(conn, ids)
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
    logger.info("Bot zalogowany jako %s", bot.user)
    try:
        synced = await bot.tree.sync()
        logger.info("Zsynchronizowano %d komend Slash", len(synced))
    except Exception as e:
        logger.error("Błąd synchronizacji: %s", e)

    if not alert_sender.is_running():
        alert_sender.start()


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandNotFound):
        return
    logger.error("Błąd komendy %s: %s", ctx.command, error)
    await ctx.send("❌ Wystąpił błąd podczas wykonywania komendy.")


# ---------------------------------------------------------------------------
# Punkt wejścia
# ---------------------------------------------------------------------------


def main() -> None:
    try:
        token = config.get_discord_token()
    except RuntimeError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    logger.info("Discord bot service starting…")
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
