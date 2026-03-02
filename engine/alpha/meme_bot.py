"""Meme Bot — sends a mix of images, text, and GIFs after losing trades.

Randomly picks between:
  1. Reddit meme image (from trading subreddits via meme-api.com)
  2. Short text one-liner
  3. GIF/animation from Reddit

Tracks recently sent items so nothing repeats until the pool cycles.
"""

from __future__ import annotations

import random
from typing import Any

from telegram import Bot
from telegram.constants import ParseMode

from alpha.config import config
from alpha.utils import setup_logger

logger = setup_logger("meme_bot")

# ---------------------------------------------------------------------------
# Text one-liners (used ~40% of the time)
# ---------------------------------------------------------------------------
LOSS_LINES = [
    "Buy high, sell low. As is tradition.",
    "That wasn't a loss, that was tuition.",
    "The market can stay irrational longer than you can stay solvent.",
    "At least it wasn't leverage... oh wait.",
    "Pain is temporary. Bags are forever.",
    "You miss 100% of the trades you don't take. You also lose 100% of the ones you do.",
    "It's called a stop loss, not a stop profit.",
    "Think of it as a donation to the market makers.",
    "Every loss brings you closer to a win. Statistically. Maybe.",
    "The real gains were the lessons we learned along the way.",
    "Portfolio diversification: losing money on multiple assets.",
    "Another day, another dollar... gone.",
    "Zoom out. No, further. Keep going.",
    "Sir, this is a casino.",
    "Cost of doing business.",
    "The chart looked different 5 minutes ago.",
    "Diamond hands would've made this worse.",
    "Small loss. Next trade. Move on.",
    "Even Buffett has red days.",
    "Red today, green tomorrow. Hopefully.",
    "The stop loss did its job. Respect the stop.",
    "Losses are just negative gains.",
    "Think of it as paying rent to the market.",
    "It's not a loss until you sell... oh wait, you sold.",
    "Market makers thank you for your service.",
    "The trend was not your friend today.",
    "When in doubt, zoom out. Still red? Zoom out more.",
    "At least crypto is open 24/7... for losing money.",
    "This trade was a character-building exercise.",
    "Volatility giveth, volatility taketh away.",
]

# Subreddits to pull meme images/GIFs from (rotated randomly)
MEME_SUBREDDITS = [
    "wallstreetbets",
    "cryptocurrencymemes",
    "bitcoinmemes",
    "SatoshiStreetBets",
]

# Track recently used items to avoid repetition
_used_text: set[str] = set()
_used_images: set[str] = set()


def _pick_text() -> str:
    """Pick a text line, cycling through all before repeating."""
    available = [l for l in LOSS_LINES if l not in _used_text]
    if not available:
        _used_text.clear()
        available = LOSS_LINES
    line = random.choice(available)
    _used_text.add(line)
    return line


async def _fetch_reddit_meme() -> dict[str, Any] | None:
    """Fetch a random meme from a trading subreddit via meme-api.com."""
    try:
        import aiohttp
    except ImportError:
        return None

    sub = random.choice(MEME_SUBREDDITS)
    url = f"https://meme-api.com/gimme/{sub}/5"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
    except Exception as e:
        logger.debug("meme-api fetch failed: %s", e)
        return None

    memes = data.get("memes", [])
    if not memes:
        return None

    # Filter: no NSFW, no spoilers, prefer decent upvotes, skip already-sent
    candidates = [
        m for m in memes
        if not m.get("nsfw")
        and not m.get("spoiler")
        and m.get("url")
        and m["url"] not in _used_images
    ]

    if not candidates:
        # All were used or filtered — clear history and retry
        _used_images.clear()
        candidates = [
            m for m in memes
            if not m.get("nsfw") and not m.get("spoiler") and m.get("url")
        ]

    if not candidates:
        return None

    # Prefer higher upvotes
    candidates.sort(key=lambda m: m.get("ups", 0), reverse=True)
    pick = candidates[0]
    _used_images.add(pick["url"])
    return pick


def _is_gif(url: str) -> bool:
    """Check if URL is a GIF/animation."""
    lower = url.lower()
    return lower.endswith(".gif") or "gif" in lower


async def send_meme(bot: Bot | None = None, chat_id: str | None = None) -> bool:
    """Send a random meme after a losing trade. Mixes text, images, GIFs."""
    if bot is None:
        token = config.telegram.bot_token
        chat_id = chat_id or config.telegram.chat_id
        if not token or not chat_id:
            return False
        bot = Bot(token=token)

    chat_id = chat_id or config.telegram.chat_id

    # Randomly pick content type: 40% text, 60% image/GIF from Reddit
    roll = random.random()

    if roll < 0.40:
        # ── Text one-liner ──
        line = _pick_text()
        emoji = random.choice(["😏", "🫡", "💀", "📉", "🎰", "🤷", "😤", "🫠"])
        try:
            await bot.send_message(chat_id=chat_id, text=f"{emoji} {line}")
            return True
        except Exception as e:
            logger.debug("Text meme send failed: %s", e)
            return False

    # ── Image or GIF from Reddit ──
    meme = await _fetch_reddit_meme()

    if meme is None:
        # Fallback to text if API fails
        line = _pick_text()
        try:
            await bot.send_message(chat_id=chat_id, text=f"😏 {line}")
            return True
        except Exception:
            return False

    meme_url = meme["url"]
    caption = meme.get("title", "")
    # Keep caption short
    if len(caption) > 200:
        caption = caption[:197] + "..."

    try:
        if _is_gif(meme_url):
            # Send as animation (GIF)
            await bot.send_animation(
                chat_id=chat_id,
                animation=meme_url,
                caption=caption or None,
            )
        else:
            # Send as photo
            await bot.send_photo(
                chat_id=chat_id,
                photo=meme_url,
                caption=caption or None,
            )
        return True
    except Exception as e:
        logger.debug("Meme image/gif send failed (%s), falling back to text: %s", meme_url, e)
        # Fallback to text
        line = _pick_text()
        try:
            await bot.send_message(chat_id=chat_id, text=f"😏 {line}")
            return True
        except Exception:
            return False
