"""Shared stock/values fetch for LumoNews Rubika bot."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import codecs
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

log = logging.getLogger("bloxfars.core")

API_BASE = "https://bloxfruitsvalues.com/api/ws"
VALUES_PAGE = "https://bloxfruitsvalues.com/values"
FRUITYBLOX_STOCK_PAGE = "https://fruityblox.com/stock"
GAMERSBERG_STOCK_PAGE = "https://www.gamersberg.com/blox-fruits/stock"
WIKI_STOCK_PAGE = "https://bloxfruitswiki.org/wiki/stock/"
LEGACY_STOCK_PAGE = "https://bloxfruitsvalues.com/stock"
SEED_PATH = Path(__file__).with_name("values_seed.json")

S = requests.Session()
S.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html,application/xhtml+xml",
    "trpc-accept": "application/json",
    "Origin": "https://bloxfruitsvalues.com",
    "Referer": "https://bloxfruitsvalues.com/stock",
})

FRUITS = [
    "Rocket", "Spin", "Blade", "Chop", "Spring", "Bomb", "Smoke", "Spike",
    "Flame", "Falcon", "Eagle", "Ice", "Sand", "Dark", "Diamond", "Light",
    "Rubber", "Barrier", "Ghost", "Magma", "Quake", "Buddha", "Love",
    "Creation", "Spider", "Sound", "Phoenix", "Portal", "Rumble", "Lightning",
    "Pain", "Blizzard", "Gravity", "Mammoth", "T-Rex", "Dough", "Shadow",
    "Venom", "Control", "Spirit", "Dragon", "West Dragon", "East Dragon",
    "Leopard", "Tiger", "Kitsune", "Yeti", "Gas", "Magnet",
]
LOOKUP = {x.lower(): x for x in FRUITS}
LOOKUP.update({"trex": "T-Rex", "t-rex": "T-Rex", "west dragon": "West Dragon", "east dragon": "East Dragon"})

BASE_VALUES: dict[str, float] = {}
try:
    if SEED_PATH.is_file():
        BASE_VALUES = {k: float(v) for k, v in json.loads(SEED_PATH.read_text(encoding="utf-8")).items()}
except Exception:
    log.warning("values_seed.json missing or invalid")

IMAGES: dict[str, str] = {}

FRUIT_EMOJI = {
    "Rocket": "🚀", "Spin": "🌀", "Blade": "⚔️", "Chop": "🪓", "Spring": "🌀",
    "Bomb": "💣", "Smoke": "💨", "Spike": "🦔", "Flame": "🔥", "Falcon": "🦅",
    "Eagle": "🦅", "Ice": "🧊", "Sand": "🏜️", "Dark": "🌑", "Diamond": "💎",
    "Light": "✨", "Rubber": "🟣", "Barrier": "🛡️", "Ghost": "👻", "Magma": "🌋",
    "Quake": "🌎", "Buddha": "🙏", "Love": "💖", "Creation": "🪄", "Spider": "🕷️",
    "Sound": "🎵", "Phoenix": "🔥", "Portal": "🌀", "Rumble": "⚡", "Lightning": "⚡",
    "Pain": "💥", "Blizzard": "❄️", "Gravity": "🪐", "Mammoth": "🦣", "T-Rex": "🦖",
    "Dough": "🍩", "Shadow": "🌑", "Venom": "🐍", "Control": "🎛️", "Spirit": "👻",
    "Dragon": "🐉", "West Dragon": "🐉", "East Dragon": "🐉", "Leopard": "🐆",
    "Tiger": "🐅", "Kitsune": "🦊", "Yeti": "☃️", "Gas": "☁️", "Magnet": "🧲",
}

# Alternate emoji sets so each user sees a stable but different look for values.
FRUIT_EMOJI_ALTS: dict[str, list[str]] = {
    "Rocket": ["🚀", "🛸", "☄️", "🛰"],
    "Spin": ["🌀", "💫", "🌪️", "✩"],
    "Blade": ["⚔️", "🗡️", "🔪", "✦"],
    "Chop": ["🪓", "🪚", "🪵", "✦"],
    "Spring": ["🌀", "🌱", "🔆", "✧"],
    "Bomb": ["💣", "🧨", "💥", "✦"],
    "Smoke": ["💨", "☁️", "🌫️", "✧"],
    "Spike": ["🦔", "📌", "🔱", "✦"],
    "Flame": ["🔥", "🧡", "♨️", "✦"],
    "Falcon": ["🦅", "🪶", "🪽", "✧"],
    "Eagle": ["🦅", "🪶", "🪽", "✧"],
    "Ice": ["🧊", "❄️", "🌨️", "✦"],
    "Sand": ["🏜️", "⏳", "🟤", "✧"],
    "Dark": ["🌑", "🌚", "🖤", "✦"],
    "Diamond": ["💎", "💠", "🔷", "✧"],
    "Light": ["✨", "🌟", "☀️", "✦"],
    "Rubber": ["🟣", "🫧", "🔮", "✧"],
    "Barrier": ["🛡️", "🧱", "🔲", "✦"],
    "Ghost": ["👻", "🌫️", "🤍", "✧"],
    "Magma": ["🌋", "🔥", "🟠", "✦"],
    "Quake": ["🌎", "🌍", "💥", "✧"],
    "Buddha": ["🙏", "🧘", "🟡", "✦"],
    "Love": ["💖", "💗", "💕", "✧"],
    "Creation": ["🪄", "✨", "🧬", "✦"],
    "Spider": ["🕷️", "🕸️", "🖤", "✧"],
    "Sound": ["🎵", "🎶", "🔊", "✦"],
    "Phoenix": ["🔥", "🪶", "🧡", "✧"],
    "Portal": ["🌀", "🚪", "🌌", "✦"],
    "Rumble": ["⚡", "🌩️", "🔋", "✧"],
    "Lightning": ["⚡", "🌩️", "💛", "✦"],
    "Pain": ["💥", "💢", "❤️‍🔥", "✧"],
    "Blizzard": ["❄️", "🌨️", "🧊", "✦"],
    "Gravity": ["🪐", "🌌", "🟣", "✧"],
    "Mammoth": ["🦣", "🐘", "🟤", "✦"],
    "T-Rex": ["🦖", "🦕", "🟢", "✧"],
    "Dough": ["🍩", "🍪", "🟤", "✦"],
    "Shadow": ["🌑", "👤", "🖤", "✧"],
    "Venom": ["🐍", "☠️", "🟢", "✦"],
    "Control": ["🎛️", "🎮", "🟣", "✧"],
    "Spirit": ["👻", "✨", "🤍", "✦"],
    "Dragon": ["🐉", "🐲", "🔥", "✧"],
    "West Dragon": ["🐉", "🐲", "🔥", "✦"],
    "East Dragon": ["🐉", "🐲", "🔥", "✧"],
    "Leopard": ["🐆", "🟡", "✨", "✦"],
    "Tiger": ["🐅", "🧡", "⚡", "✧"],
    "Kitsune": ["🦊", "🧡", "✨", "✦"],
    "Yeti": ["☃️", "❄️", "🤍", "✧"],
    "Gas": ["☁️", "💨", "🟢", "✦"],
    "Magnet": ["🧲", "🔵", "⚡", "✧"],
}

_GENERIC_VALUE_EMOJIS = ["💠", "✨", "🌟", "💫", "⭐", "🔮", "🧿", "🪬", "💎", "🔷"]


def fruit_emoji_for_user(name: str, user_id: str = "") -> str:
    """Stable per-user emoji for a fruit/item name. Same user always sees the same set."""
    base = FRUIT_EMOJI.get(name, "💠")
    if not user_id:
        return base
    choices = FRUIT_EMOJI_ALTS.get(name)
    if not choices:
        choices = [base] + _GENERIC_VALUE_EMOJIS
    digest = hashlib.md5(f"{user_id}:{name}".encode("utf-8")).hexdigest()
    idx = int(digest[:8], 16) % len(choices)
    return choices[idx]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def fruit_name(text: str) -> str | None:
    t = " ".join(str(text or "").split()).lower()
    for k in sorted(LOOKUP, key=len, reverse=True):
        if re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", t):
            return LOOKUP[k]
    return None


def parse_num(s: Any) -> float | None:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    m = re.search(r"(?<![A-Za-z])(\d[\d,]*(?:\.\d+)?)\s*([KMBT])?\b", str(s), re.I)
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    mult = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}.get((m.group(2) or "").upper(), 1)
    return n * mult


def fmt_num(n: float | int | None) -> str:
    if n is None:
        return "?"
    n = float(n)
    for unit, scale in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= scale:
            v = n / scale
            if v >= 10 or abs(v - int(v)) < 1e-9:
                return f"{int(round(v))}{unit}" if v >= 10 else f"{int(v)}{unit}"
            return f"{v:.2f}".rstrip("0").rstrip(".") + unit
    return f"{int(n)}" if abs(n - int(n)) < 1e-9 else f"{n:g}"


def trpc_get(procedure: str) -> Any:
    url = f"{API_BASE}/{procedure}"
    params = {"batch": "1", "input": json.dumps({"0": {"json": None}}, separators=(",", ":"))}
    r = S.get(url, params=params, timeout=5)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"Empty tRPC for {procedure}")
    item = data[0]
    if "error" in item:
        msg = item["error"].get("json", {}).get("message", str(item["error"]))
        raise RuntimeError(f"tRPC {procedure}: {msg}")
    return item["result"]["data"]["json"]


def _fetch_stock_primary() -> dict[str, Any]:
    payload = trpc_get("stock.get")
    out: dict[str, Any] = {"sections": {}, "meta": {"source": "bloxfruitsvalues.com"}}
    for key, title in (("normal", "معمولی"), ("mirage", "میراژ")):
        fruits = (payload.get(key) or {}).get("fruits") or []
        items = []
        for f in fruits:
            name = fruit_name(f.get("name") or "") or f.get("name") or "?"
            img = f.get("image") or ""
            if img:
                IMAGES[name] = img
            items.append({
                "name": name,
                "image": img,
                "rarity": f.get("rarity") or "",
                "type": f.get("fruitType") or "",
                "beli": f.get("beliPrice"),
                "robux": f.get("robuxPrice"),
                "value": f.get("regularValue"),
                "value_fmt": fmt_num(f.get("regularValue")),
                "demand": f.get("regularDemand"),
            })
        out["sections"][title] = items
        win = (payload.get(key) or {}).get("window") or {}
        reset_value = win.get("resetsAt")
        reset_epoch = _epoch_seconds(reset_value)
        if reset_epoch is None:
            raise RuntimeError(f"Stock API has no valid {key} reset timestamp")
        now_epoch = time.time()
        interval = 4 * 3600 if key == "normal" else 2 * 3600
        if reset_epoch < now_epoch - 90 or reset_epoch > now_epoch + interval + 300:
            raise RuntimeError(f"Stock API {key} snapshot has stale/invalid reset timestamp")
        out["meta"][f"{key}_resets_at"] = reset_value
    _validate_stock_snapshot(out, "BloxFruitsValues API")
    log.info("Stock OK source=bloxfruitsvalues.com n=%s m=%s", len(out["sections"].get("معمولی", [])), len(out["sections"].get("میراژ", [])))
    return out


def _next_reset(hours: int) -> int:
    """Return the next UTC interval boundary as a Unix timestamp."""
    interval = hours * 3600
    now_ts = int(time.time())
    return ((now_ts // interval) + 1) * interval


def _epoch_seconds(value: Any) -> float | None:
    """Parse reset timestamps from API payloads (seconds, milliseconds, or ISO)."""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)) or str(value).strip().replace(".", "", 1).isdigit():
            stamp = float(value)
            return stamp / 1000 if stamp > 10_000_000_000 else stamp
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def _validate_stock_snapshot(data: dict[str, Any], source: str) -> None:
    """Reject partial, mixed-history, or price-incomplete dealer snapshots."""
    sections = data.get("sections") or {}
    for title in ("معمولی", "میراژ"):
        items = sections.get(title) or []
        if len(items) < 3:
            raise RuntimeError(f"{source}: {title} list is incomplete ({len(items)} fruits)")
        names = [str(item.get("name") or "").strip().lower() for item in items]
        if len(names) != len(set(names)):
            raise RuntimeError(f"{source}: duplicate fruit names in {title}")
        # Rocket and Spin are always available in both dealers; their absence
        # is a strong sign that the parser captured a history/partial section.
        if not {"rocket", "spin"}.issubset(set(names)):
            raise RuntimeError(f"{source}: current {title} list is missing Rocket or Spin")
        for item in items:
            price = parse_num(item.get("beli"))
            if price is None or price <= 0:
                raise RuntimeError(f"{source}: missing/invalid Beli price for {item.get('name') or '?'}")
            item["beli"] = int(price)


def _fetch_stock_fruityblox() -> dict[str, Any]:
    """Fallback stock source. Parses the publicly rendered FruityBlox stock page."""
    from bs4 import BeautifulSoup

    response = S.get(FRUITYBLOX_STOCK_PAGE, timeout=5, headers={"Referer": FRUITYBLOX_STOCK_PAGE})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    sections: dict[str, list[dict[str, Any]]] = {"معمولی": [], "میراژ": []}
    heading_map = {"normal": "معمولی", "mirage": "میراژ"}

    for heading in soup.find_all(["h2", "h3"]):
        label = " ".join(heading.get_text(" ", strip=True).split()).lower()
        if label not in heading_map:
            continue
        key = heading_map[label]
        container = heading.find_parent("section")
        if container is None:
            # Generic fallback for markup without semantic section tags: read headings
            # until the next dealer heading instead of treating the whole page as one list.
            names = []
            for node in heading.find_all_next(["h2", "h3"]):
                node_label = " ".join(node.get_text(" ", strip=True).split()).lower()
                if node.name == "h2" and node_label in heading_map:
                    break
                if node.name == "h3":
                    names.append(node)
        else:
            names = container.find_all("h3")

        seen = {str(x.get("name", "")).lower() for x in sections[key]}
        for name_node in names:
            name = " ".join(name_node.get_text(" ", strip=True).split())
            if not name or name.lower() in heading_map or name.lower() in seen:
                continue
            # Look for the smallest card-like ancestor containing price numbers.
            candidate = name_node
            chosen_text = name
            chosen_node = name_node
            chosen_nums: list[str] = []
            for _ in range(7):
                if candidate.parent is None:
                    break
                candidate = candidate.parent
                text = " ".join(candidate.get_text(" ", strip=True).split())
                if len(text) > 260:
                    continue
                nums = re.findall(r"(?<![A-Za-z])(\d[\d,]*(?:\.\d+)?)", text)
                if nums:
                    chosen_text, chosen_node, chosen_nums = text, candidate, nums
                    if len(nums) >= 2:
                        break
            beli = robux = None
            if chosen_nums:
                try: beli = int(chosen_nums[0].replace(",", ""))
                except (ValueError, TypeError): pass
            if len(chosen_nums) > 1:
                try: robux = int(chosen_nums[1].replace(",", ""))
                except (ValueError, TypeError): pass
            image = ""
            try:
                img = chosen_node.find("img")
                if img:
                    image = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
            except Exception:
                pass
            canonical = fruit_name(name) or name
            if image:
                IMAGES[canonical] = image
            sections[key].append({
                "name": canonical, "image": image, "rarity": "", "type": "",
                "beli": beli, "robux": robux, "value": None, "value_fmt": "?", "demand": None,
            })
            seen.add(name.lower())

    if not sections["معمولی"] or not sections["میراژ"]:
        raise RuntimeError(
            "FruityBlox fallback page structure changed or stock list was incomplete "
            f"(normal={len(sections['معمولی'])}, mirage={len(sections['میراژ'])})"
        )
    out = {
        "sections": sections,
        "meta": {
            "source": "fruityblox.com (fallback)",
            "normal_resets_at": _next_reset(4),
            "mirage_resets_at": _next_reset(2),
        },
    }
    log.warning("Stock fallback OK source=fruityblox.com n=%s m=%s", len(sections["معمولی"]), len(sections["میراژ"]))
    return out


def _fetch_stock_legacy_page() -> dict[str, Any]:
    """Last-resort parser for the legacy stock page, separate from its tRPC API."""
    from bs4 import BeautifulSoup

    response = S.get(LEGACY_STOCK_PAGE, timeout=6, headers={"Referer": LEGACY_STOCK_PAGE})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    sections: dict[str, list[dict[str, Any]]] = {"معمولی": [], "میراژ": []}
    heading_map = {"normal": "معمولی", "regular": "معمولی", "ordinary": "معمولی", "mirage": "میراژ"}
    headings = soup.find_all(["h1", "h2", "h3", "h4"])
    for heading in headings:
        label = " ".join(heading.get_text(" ", strip=True).split()).lower()
        key = heading_map.get(label)
        if not key:
            continue
        # Parse cards in the section/parent around this heading, stopping at next stock heading.
        container = heading.find_parent("section") or heading.parent
        if container is None:
            continue
        for node in container.find_all(["h3", "h4", "strong", "p", "div"]):
            name = " ".join(node.get_text(" ", strip=True).split())
            canonical = fruit_name(name)
            if not canonical or any(x.get("name") == canonical for x in sections[key]):
                continue
            parent = node
            text = name
            nums = []
            for _ in range(5):
                if parent.parent is None:
                    break
                parent = parent.parent
                text = " ".join(parent.get_text(" ", strip=True).split())
                if len(text) > 220:
                    continue
                nums = re.findall(r"(?<![A-Za-z])(\d[\d,]*(?:\.\d+)?)", text)
                if nums:
                    break
            price = None
            if nums:
                try: price = int(nums[0].replace(",", ""))
                except ValueError: pass
            image = ""
            img = parent.find("img") if hasattr(parent, "find") else None
            if img:
                image = img.get("src") or img.get("data-src") or ""
            if image:
                IMAGES[canonical] = image
            sections[key].append({"name": canonical, "image": image, "rarity": "", "type": "", "beli": price, "robux": None, "value": None, "value_fmt": "?", "demand": None})
    if not sections["معمولی"] or not sections["میراژ"]:
        raise RuntimeError(f"Legacy stock page incomplete (normal={len(sections['معمولی'])}, mirage={len(sections['میراژ'])})")
    out = {"sections": sections, "meta": {"source": "bloxfruitsvalues.com/stock (legacy fallback)", "normal_resets_at": _next_reset(4), "mirage_resets_at": _next_reset(2)}}
    log.warning("Stock fallback OK source=legacy stock page n=%s m=%s", len(sections["معمولی"]), len(sections["میراژ"]))
    return out


def _parse_public_stock_page(url: str, source_name: str, timeout: int = 12) -> dict[str, Any]:
    """Parse a server-rendered stock page, accepting only complete normal+Mirage lists."""
    from bs4 import BeautifulSoup

    response = S.get(url, timeout=timeout, headers={"Referer": url})
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    page_text = " ".join(soup.get_text(" ", strip=True).split())

    # Gamersberg currently exposes an explicit update-age label. Do not accept
    # its page as a live fallback if it itself reports an old snapshot.
    if "gamersberg" in url.lower():
        age = re.search(r"Updated\s+(\d+)\s*h", page_text, re.I)
        if age and int(age.group(1)) >= 6:
            raise RuntimeError(f"Gamersberg stock page reports stale data ({age.group(1)}h old)")

    def section_for_heading(label: str) -> str | None:
        x = " ".join(label.lower().split())
        if "mirage" in x and "stock" in x and not any(k in x for k in ("last", "previous", "history")):
            return "میراژ"
        if x in {"normal stock", "current stock", "normal", "regular stock", "ordinary stock"}:
            return "معمولی"
        if any(k in x for k in ("normal stock", "regular stock", "ordinary stock")) and not any(k in x for k in ("last", "previous", "history")):
            return "معمولی"
        return None

    sections: dict[str, list[dict[str, Any]]] = {"معمولی": [], "میراژ": []}
    headings = soup.find_all(["h1", "h2", "h3", "h4"])
    active = None
    candidates: list[tuple[str, Any]] = []
    for heading in headings:
        label = " ".join(heading.get_text(" ", strip=True).split())
        mapped = section_for_heading(label)
        if mapped:
            active = mapped
            continue
        low_label = label.lower()
        # Crucial: do not keep parsing fruit headings after "Last Stock",
        # "Previous Stock", history, or any other top-level section. That was
        # mixing old rotations into the current stock and causing false alerts.
        if heading.name in ("h1", "h2"):
            active = None
            continue
        if any(word in low_label for word in ("last stock", "previous stock", "stock history", "history", "stock display", "in-stock alarm")):
            active = None
            continue
        if active and heading.name in ("h3", "h4"):
            name = fruit_name(label)
            if name:
                candidates.append((active, heading))

    for section, name_node in candidates:
        canonical = fruit_name(name_node.get_text(" ", strip=True))
        if not canonical or any(x.get("name") == canonical for x in sections[section]):
            continue
        node = name_node
        chosen = None
        for _ in range(7):
            if node.parent is None:
                break
            node = node.parent
            text = " ".join(node.get_text(" ", strip=True).split())
            if len(text) > 320:
                continue
            # Support values like 5,000, 5.0K, 1.3M; first price in a fruit card
            # is the Beli price on both supported page layouts.
            nums = re.findall(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?\s*[KMBT]?", text, re.I)
            nums = [n.strip() for n in nums if parse_num(n) is not None]
            if nums:
                chosen = (node, nums)
                # The smallest ancestor containing the fruit and its first price
                # is the least likely to mix values from adjacent fruit cards.
                break
        if not chosen:
            continue
        card, nums = chosen
        beli = parse_num(nums[0])
        # External page cards mix demand and value numbers in their text, so
        # don't guess a Robux price from an arbitrary second numeric token.
        robux = None
        img = card.find("img") if hasattr(card, "find") else None
        image = ""
        if img:
            image = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
        if image:
            IMAGES[canonical] = image
        sections[section].append({
            "name": canonical, "image": image, "rarity": "", "type": "",
            "beli": int(beli) if beli is not None else None,
            "robux": int(robux) if robux is not None else None,
            "value": None, "value_fmt": "?", "demand": None,
        })

    out = {"sections": sections, "meta": {
        "source": source_name,
        "normal_resets_at": _next_reset(4),
        "mirage_resets_at": _next_reset(2),
    }}
    _validate_stock_snapshot(out, source_name)
    log.info("Stock OK source=%s n=%s m=%s", source_name, len(sections["معمولی"]), len(sections["میراژ"]))
    return out


def _fetch_stock_gamersberg() -> dict[str, Any]:
    return _parse_public_stock_page(GAMERSBERG_STOCK_PAGE, "gamersberg.com", timeout=6)


def _fetch_stock_wiki() -> dict[str, Any]:
    return _parse_public_stock_page(WIKI_STOCK_PAGE, "bloxfruitswiki.org", timeout=6)


def fetch_stock() -> dict[str, Any]:
    """Fetch stock from sources in priority order, avoiding parallel request/thread buildup.

    The primary API wins whenever it returns a complete, valid current snapshot.
    Fallback pages are queried only if the preceding source fails validation.
    This prevents different sources racing and alternating snapshots on a small host.
    """
    attempts = (
        ("BloxFruitsValues API", _fetch_stock_primary),
        ("FruityBlox page", _fetch_stock_fruityblox),
        ("legacy stock page", _fetch_stock_legacy_page),
        ("Blox Fruits Wiki live page", _fetch_stock_wiki),
        ("Gamersberg page", _fetch_stock_gamersberg),
    )
    errors = []
    for label, fetcher in attempts:
        try:
            data = fetcher()
            _validate_stock_snapshot(data, label)
            data.setdefault("meta", {})["source_chain"] = label
            data["meta"].pop("stale", None)
            log.info("Stock selected source=%s", label)
            return data
        except Exception as exc:
            errors.append(f"{label}: {str(exc)[:150]}")
            log.warning("Stock source unavailable (%s): %s", label, str(exc)[:180])
    raise RuntimeError("All stock sources failed; " + " | ".join(errors))


def _canonical_item_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return name
    low = name.lower()
    exact = {"trex": "T-Rex", "t-rex": "T-Rex", "t rex": "T-Rex", "west dragon": "West Dragon", "east dragon": "East Dragon"}
    if low in exact:
        return exact[low]
    if low in LOOKUP:
        return LOOKUP[low]
    return name


def _extract_initial_items(html: str) -> list[Any]:
    """Extract the initialItems JSON array from a bloxfruitsvalues HTML page."""
    idx = html.find("initialItems")
    if idx < 0:
        raise RuntimeError("initialItems not found")
    start = html.find("[", idx)
    if start < 0:
        raise RuntimeError("initialItems array start not found")
    depth = 0
    end = start
    for i in range(start, min(start + 2_000_000, len(html))):
        c = html[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    else:
        raise RuntimeError("initialItems not closed")
    raw = html[start:end]
    try:
        data = json.loads(raw)
    except Exception:
        # Some server-rendered payloads escape the JSON string once.
        data = json.loads(codecs.decode(raw, "unicode_escape"))
    if not isinstance(data, list):
        raise RuntimeError("Unexpected values payload type")
    return data


def _normalize_category(cat: str) -> str:
    """Map various category spellings to canonical keys."""
    c = (cat or "").strip().lower()
    if c in ("fruits", "fruit"):
        return "Fruits"
    if c in ("limiteds", "limited", "limit"):
        return "Limiteds"
    if c in ("gamepasses", "gamepass", "game passes", "game pass"):
        return "Gamepasses"
    return (cat or "").strip()


def _item_reg_value(it: dict[str, Any]) -> float | None:
    """Extract a positive regular value from an item dict."""
    meta = it.get("metadata") or {}
    rv = meta.get("regValue")
    if rv is None:
        top = it.get("value")
        if isinstance(top, (int, float)) and top > 0:
            rv = top
        else:
            parsed = parse_num(top)
            if parsed and parsed > 0:
                rv = parsed
    try:
        if rv is not None and float(rv) > 0:
            return float(rv)
    except (TypeError, ValueError):
        pass
    return None


def _item_perm_value(it: dict[str, Any]) -> float | None:
    meta = it.get("metadata") or {}
    pv = meta.get("permValue")
    try:
        if pv is not None and float(pv) > 0:
            return float(pv)
    except (TypeError, ValueError):
        pass
    return None


def _fetch_values_page(url: str, timeout: int = 10) -> list[Any]:
    r = S.get(url, timeout=timeout)
    r.raise_for_status()
    return _extract_initial_items(r.text)


def fetch_values_structured() -> dict[str, Any]:
    """Fetch trading values from bloxfruitsvalues category pages.

    The main /values page currently embeds only Fruits in initialItems.
    Limiteds and Gamepasses live on their own category routes and must be
    fetched separately so the Limited / Gamepass menus are not empty.
    """
    fruits: dict[str, float] = {}
    permanent: dict[str, float] = {}
    limiteds: dict[str, float] = {}
    gamepasses: dict[str, float] = {}
    all_reg: dict[str, float] = {}

    pages = (
        (VALUES_PAGE, "main"),
        (VALUES_PAGE.rstrip("/") + "/fruits", "fruits"),
        (VALUES_PAGE.rstrip("/") + "/limiteds", "limiteds"),
        (VALUES_PAGE.rstrip("/") + "/gamepasses", "gamepasses"),
    )
    errors: list[str] = []
    seen_pages = 0

    for url, label in pages:
        try:
            data = _fetch_values_page(url)
            if not data:
                continue
            seen_pages += 1
            for it in data:
                if not isinstance(it, dict):
                    continue
                name = _canonical_item_name((it.get("name") or "").strip())
                if not name:
                    continue
                cat = _normalize_category(it.get("category") or "")
                rv = _item_reg_value(it)
                pv = _item_perm_value(it)
                if it.get("image"):
                    IMAGES[name] = it["image"]
                if cat == "Fruits":
                    if rv is not None:
                        fruits[name] = rv
                        all_reg[name] = rv
                    if pv is not None:
                        permanent[name] = pv
                elif cat == "Limiteds":
                    if rv is not None:
                        limiteds[name] = rv
                        all_reg[name] = rv
                elif cat == "Gamepasses":
                    if rv is not None:
                        gamepasses[name] = rv
                        all_reg[name] = rv
                elif rv is not None:
                    # Unknown category: still keep in the combined list.
                    all_reg[name] = rv
        except Exception as exc:
            errors.append(f"{label}: {str(exc)[:120]}")
            log.warning("Values page unavailable (%s): %s", label, str(exc)[:180])

    def _fmt_sorted(d: dict[str, float]) -> dict[str, str]:
        formatted = {k: fmt_num(v) for k, v in d.items()}
        return dict(sorted(formatted.items(), key=lambda x: parse_num(x[1]) or 0, reverse=True))

    if len(all_reg) < 5:
        detail = " | ".join(errors) if errors else "no items"
        raise RuntimeError(f"Too few values: {len(all_reg)}; {detail}")
    log.info(
        "Values fruits=%s perm=%s lim=%s gp=%s pages=%s",
        len(fruits), len(permanent), len(limiteds), len(gamepasses), seen_pages,
    )
    return {
        "fruits": _fmt_sorted(fruits),
        "permanent": _fmt_sorted(permanent),
        "limiteds": _fmt_sorted(limiteds),
        "gamepasses": _fmt_sorted(gamepasses),
        "all": _fmt_sorted(all_reg),
    }


def fetch_values() -> dict[str, str]:
    """Fetch current trading values. Seed is an explicitly stale fallback only.

    Never overlay dealer stock values onto the trading-value list: those are
    different concepts and stock may contain only a small subset of fruits.
    """
    try:
        return fetch_values_structured()["all"]
    except Exception as e:
        log.warning("Live values unavailable; seed fallback is stale: %s", e)
        if len(BASE_VALUES) < 5:
            raise RuntimeError("Live values unavailable and no valid seed fallback") from e
        formatted = {k: fmt_num(v) for k, v in BASE_VALUES.items()}
        return dict(sorted(formatted.items(), key=lambda x: parse_num(x[1]) or 0, reverse=True))


def stock_content_signature(data: dict[str, Any]) -> str:
    sections = data.get("sections") or {}
    payload = {}
    for title in ("معمولی", "میراژ"):
        rows = []
        for it in sections.get(title) or []:
            rows.append({"name": str(it.get("name") or ""), "beli": it.get("beli"), "robux": it.get("robux")})
        rows.sort(key=lambda x: x["name"])
        payload[title] = rows
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)


def values_content_signature(data: dict[str, str]) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False)


def values_change_significant(
    old: dict[str, str] | None,
    new: dict[str, str] | None,
    *,
    min_rel_change: float = 0.08,
    min_changed_items: int = 3,
    big_rel_change: float = 0.20,
) -> tuple[bool, str]:
    """Decide whether a values update is worth broadcasting.

    Avoids spamming channels when the source only drifts by a tiny amount
    (formatting noise, 1-2% wiggles on a couple of items, etc.).

    Returns (should_broadcast, reason).
    """
    if not new or len(new) < 5:
        return False, "new_empty"
    if not old or len(old) < 5:
        return True, "no_previous_snapshot"

    changed = 0
    big = 0
    added = 0
    removed = 0
    max_rel = 0.0

    for name, new_s in new.items():
        new_v = parse_num(new_s)
        if new_v is None or new_v <= 0:
            continue
        if name not in old:
            added += 1
            continue
        old_v = parse_num(old.get(name))
        if old_v is None or old_v <= 0:
            added += 1
            continue
        rel = abs(new_v - old_v) / old_v
        if rel > max_rel:
            max_rel = rel
        if rel >= min_rel_change:
            changed += 1
        if rel >= big_rel_change:
            big += 1

    for name in old:
        if name not in new:
            removed += 1

    if big >= 1:
        return True, f"big_change items={big} max_rel={max_rel:.1%}"
    if changed >= min_changed_items:
        return True, f"many_small_changes items={changed} max_rel={max_rel:.1%}"
    if added + removed >= 3:
        return True, f"catalog_shift added={added} removed={removed}"
    return False, (
        f"insignificant changed={changed} big={big} "
        f"added={added} removed={removed} max_rel={max_rel:.1%}"
    )


def _countdown(reset_at: Any) -> str:
    if reset_at is None:
        return ""
    try:
        if isinstance(reset_at, str) and not reset_at.strip().replace(".", "", 1).isdigit():
            parsed = datetime.fromisoformat(reset_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            stamp = parsed.timestamp()
        else:
            stamp = float(reset_at)
            if stamp > 10_000_000_000:
                stamp /= 1000
        seconds = max(0, int(stamp - datetime.now(timezone.utc).timestamp()))
        h, rem = divmod(seconds, 3600)
        m, sec = divmod(rem, 60)
        return f"{h} ساعت و {m} دقیقه و {sec} ثانیه"
    except (TypeError, ValueError, OverflowError):
        return ""


def format_stock_message(data: dict[str, Any]) -> list[str]:
    """Compact text-only stock layout; avoid long Unicode box-drawing lines in Rubika."""
    meta = data.get("meta") or {}
    sections = data.get("sections") or {}
    lines = [
        "📈 استاک بلاکس فروت",
        "━━━━━━━━━━━━━━",
        "🤖 @LumoNews_Bot",
        "",
    ]
    if meta.get("stale"):
        lines.extend(["⚠️ منبع فعلاً در دسترس نیست؛ آخرین استاک ذخیره‌شده نمایش داده می‌شود.", ""])
    for title, key, heading, fallback_icon in (
        ("معمولی", "normal", "┌─ 🛒 استاک عادی", "🍏"),
        ("میراژ", "mirage", "┌─ 🌌 استاک میراژ", "🌌"),
    ):
        items = sections.get(title) or []
        lines.append(heading)
        if not items:
            lines.append("│ ▫️ فعلاً داده‌ای نیست")
        for item in items:
            name = str(item.get("name") or "?")
            emoji = FRUIT_EMOJI.get(name, fallback_icon)
            price = item.get("beli")
            try:
                price_text = f"{int(float(price)):,}" if price is not None else "?"
            except (TypeError, ValueError):
                price_text = str(price)
            lines.append(f"│ {emoji} {name}  ┊  {price_text} Beli")
        reset = _countdown(meta.get(f"{key}_resets_at"))
        if reset:
            lines.append(f"│ ⏳ ریست بعدی: {reset}")
        lines.extend(["└──────────────", ""])
    lines.append("📢 @LumoNews")
    text = "\n".join(lines).strip()
    if len(text) <= 3500:
        return [text]
    chunks, cur = [], ""
    for line in lines:
        if len(cur) + len(line) + 1 > 3500:
            chunks.append(cur.rstrip())
            cur = ""
        cur += line + "\n"
    if cur.strip():
        chunks.append(cur.rstrip())
    return chunks


def format_values_message(
    data: dict[str, str],
    limit: int = 120,
    *,
    user_id: str = "",
    footer: str = "📢 @LumoNews",
    bot_line: str = "🤖 @LumoNews_Bot",
) -> list[str]:
    title = f"💎 ولیو بلاکس فروت\n━━━━━━━━━━━━━━\n{bot_line}"
    return format_values_category(
        data, title=title, limit=limit, user_id=user_id, footer=footer
    )


def format_values_category(
    data: dict[str, str],
    title: str,
    limit: int = 200,
    *,
    user_id: str = "",
    footer: str = "📢 @LumoNews",
) -> list[str]:
    entries = list(data.items())[:limit]
    lines = [title, "━━━━━━━━━━━━━━", ""]
    if not entries:
        lines.append("▫️ موردی نیست")
    for name, value in entries:
        emoji = fruit_emoji_for_user(name, user_id)
        lines.append(f"{emoji} 「{name}」  ┊  {value}")
    if footer:
        lines += ["", footer]
    chunks, cur = [], ""
    for line in lines:
        if len(cur) + len(line) + 1 > 3500:
            chunks.append(cur.rstrip())
            cur = ""
        cur += line + "\n"
    if cur.strip():
        chunks.append(cur.rstrip())
    return chunks
