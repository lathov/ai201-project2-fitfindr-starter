"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

# Groq-hosted model used for the LLM-backed tools. Change here to swap models.
GROQ_MODEL = "llama-3.3-70b-versatile"


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _chat(system: str, user: str, temperature: float = 0.8, top_p: float = 0.9) -> str:
    """
    Send a single system+user prompt to the Groq chat API and return the text.

    temperature / top_p are tuned slightly high so styling suggestions feel
    creative and vary across runs (mix-and-match, not a canned response).
    """
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        top_p=top_p,
    )
    return (response.choices[0].message.content or "").strip()


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # 1. Tokenize the user's description into lowercase keywords.
    keywords = [w for w in _tokenize(description) if w]
    if not keywords:
        return []

    scored: list[tuple[int, dict]] = []
    for listing in listings:
        # 2. Filter by price ceiling (inclusive) if provided.
        if max_price is not None and listing.get("price", 0) > max_price:
            continue

        # 2. Filter by size (case-insensitive substring match) if provided.
        if size is not None:
            listing_size = (listing.get("size") or "").lower()
            if size.strip().lower() not in listing_size:
                continue

        # 3. Score by keyword overlap across the searchable text fields.
        score = _score_listing(listing, keywords)

        # 4. Drop listings with no relevant matches.
        if score > 0:
            scored.append((score, listing))

    # 5. Sort by score, highest first, and return the listing dicts.
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [listing for _, listing in scored]


def _tokenize(text: str) -> list[str]:
    """Lowercase a string and split it into alphanumeric word tokens."""
    if not text:
        return []
    return re.findall(r"[a-z0-9]+", text.lower())


def _score_listing(listing: dict, keywords: list[str]) -> int:
    """
    Count how many query keywords appear in a listing's searchable text.

    Searches the title, description, category, style_tags, and colors so a
    query like "vintage graphic tee" matches on title words and style tags alike.
    """
    haystack = " ".join(
        [
            str(listing.get("title", "")),
            str(listing.get("description", "")),
            str(listing.get("category", "")),
            " ".join(listing.get("style_tags", []) or []),
            " ".join(listing.get("colors", []) or []),
            str(listing.get("brand") or ""),
        ]
    )
    tokens = set(_tokenize(haystack))
    return sum(1 for kw in keywords if kw in tokens)


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    item_line = _format_item(new_item)
    items = (wardrobe or {}).get("items", [])

    system = (
        "You are FitFindr's resident fashionista — a warm, hype, knowledgeable "
        "thrift stylist. You give specific, wearable outfit ideas in a fun, "
        "encouraging tone. Reference real pieces by name. Keep it to 2-4 sentences, "
        "no bullet lists, no markdown."
    )

    if items:
        # Wardrobe has pieces — pair the new item with the user's actual closet.
        wardrobe_text = "\n".join(_format_wardrobe_item(it) for it in items)
        user = (
            f"My latest thrift find:\n{item_line}\n\n"
            f"Here's what's already in my closet:\n{wardrobe_text}\n\n"
            "Suggest 1-2 complete outfits that pair this new find with specific "
            "pieces from my wardrobe. Name the wardrobe pieces you'd combine it "
            "with and explain why the look works."
        )
    else:
        # Empty wardrobe — fall back to pairing with other thrift listings.
        complements = _complementary_listings(new_item)
        listings_text = "\n".join(_format_item(it) for it in complements)
        user = (
            f"My latest thrift find:\n{item_line}\n\n"
            "I don't have a wardrobe saved yet, but here are other secondhand "
            f"pieces available right now:\n{listings_text}\n\n"
            "Suggest 1-2 complete outfits that pair my new find with specific "
            "pieces from this list. Name the pieces you'd grab and explain the vibe."
        )

    suggestion = _chat(system, user, temperature=0.85, top_p=0.9).strip()

    if not suggestion:
        # LLM returned nothing — degrade gracefully instead of an empty string.
        title = new_item.get("title", "this piece")
        return (
            f"We found {title} for you! Style it with neutral basics and let it "
            "be the statement of the outfit."
        )
    return suggestion


def _format_item(item: dict) -> str:
    """One-line summary of a listing dict for an LLM prompt."""
    parts = [item.get("title", "Untitled")]
    if item.get("colors"):
        parts.append(", ".join(item["colors"]))
    if item.get("category"):
        parts.append(item["category"])
    if item.get("style_tags"):
        parts.append("/".join(item["style_tags"]))
    return " — ".join(parts)


def _format_wardrobe_item(item: dict) -> str:
    """One-line summary of a wardrobe item dict for an LLM prompt."""
    parts = [item.get("name", "Unnamed item")]
    if item.get("colors"):
        parts.append(", ".join(item["colors"]))
    if item.get("category"):
        parts.append(item["category"])
    if item.get("notes"):
        parts.append(item["notes"])
    return " — ".join(parts)


def _complementary_listings(new_item: dict, limit: int = 6) -> list[dict]:
    """
    Pick other listings that complement new_item — items from *different*
    categories (so a top gets paired with bottoms/shoes/etc.), excluding the
    item itself. Falls back to any other listing if the categories are sparse.
    """
    listings = load_listings()
    new_id = new_item.get("id")
    new_category = new_item.get("category")

    different = [
        l for l in listings
        if l.get("id") != new_id and l.get("category") != new_category
    ]
    if len(different) < limit:
        same = [
            l for l in listings
            if l.get("id") != new_id and l.get("category") == new_category
        ]
        different.extend(same)
    return different[:limit]


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """

    title = new_item.get("title")
    price = new_item.get("price")
    platform = new_item.get("platform", "a secondhand shop")
    price_text = f"${price:g}" if isinstance(price, (int, float)) else "a steal"

    # 1. Guard against an empty/whitespace outfit or a missing item.
    if not outfit or not outfit.strip():
        return (
            # "Couldn't create a fit card — no outfit suggestion was provided. "
            # "Run suggest_outfit first and pass its result here."
            f"Just thrifted {title} for {price_text} on {platform} — and the fit "
            "is everything. ♻️ #thrifted #secondhandstyle"
        )
    if not new_item or not new_item.get("title"):
        return (
            "Couldn't create a fit card — the item details are missing or "
            "incomplete."
        )

    # title = new_item.get("title")
    # price = new_item.get("price")
    # platform = new_item.get("platform", "a secondhand shop")
    # price_text = f"${price:g}" if isinstance(price, (int, float)) else "a steal"

    system = (
        "You write short, punchy outfit captions for Instagram/TikTok — the kind "
        "a real person posts about a thrift find, not a product listing. Casual, "
        "authentic, a little hype. 2-4 sentences. A couple of fitting emojis and "
        "hashtags are welcome but don't overdo it. No markdown, no quotes around "
        "the caption."
    )
    user = (
        f"I just thrifted: {title} for {price_text} on {platform}.\n"
        f"Here's how I'm styling it: {outfit.strip()}\n\n"
        "Write a caption for my outfit post. Work the item name, the price, and "
        f"the platform ({platform}) in naturally — once each — and capture the "
        "vibe of the outfit in specific terms. Lean into the thrifted / "
        "second-hand / sustainable-fashion angle."
    )

    # 2-3. Higher temperature so captions differ across runs for the same input.
    caption = _chat(system, user, temperature=1.0, top_p=0.95).strip()

    if not caption:
        # Degrade gracefully rather than returning an empty string.
        return (
            f"Just thrifted {title} for {price_text} on {platform} — and the fit "
            "is everything. ♻️ #thrifted #secondhandstyle"
        )
    return caption
