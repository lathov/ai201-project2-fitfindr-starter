"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── query parsing ───────────────────────────────────────────────────────────────

# Common clothing size tokens we recognize as standalone words.
_SIZE_WORDS = ["xxl", "xl", "xs", "s", "m", "l"]

# Filler phrases stripped from the description so they don't pollute keyword
# matching. search_listings scores on keyword overlap, so leftover filler is
# mostly harmless — this just keeps the description focused.
_FILLER = [
    "i'm looking for", "im looking for", "i am looking for", "looking for",
    "i want", "i need", "show me", "find me", "find", "looking",
    "what's out there", "whats out there", "how would i style it",
    "can you", "please",
]


def _parse_query(query: str) -> dict:
    """
    Extract a search description, optional size, and optional max_price from a
    natural-language query using regex/string rules (no LLM call).

    Examples:
        "vintage graphic tee under $30, size M"
            -> {"description": "vintage graphic tee", "size": "M", "max_price": 30.0}
        "baggy jeans below 40 dollars"
            -> {"description": "baggy jeans", "size": None, "max_price": 40.0}

    Returns:
        A dict with keys: description (str), size (str|None), max_price (float|None).
    """
    text = query.strip()
    lowered = text.lower()

    # --- max_price -------------------------------------------------------------
    # Only trust a number that carries a price cue ($ or under/below/max/...) so
    # bare numbers that are part of the item ("501 jeans", "90s") aren't grabbed.
    # The price phrase pattern is reused below to strip it from the description.
    price_pattern = (
        r"(?:under|below|less than|max(?:imum)?|up to|<=?)\s*\$?\s*\d+(?:\.\d{1,2})?(?:\s*(?:dollars|usd|bucks))?"
        r"|\$\s*\d+(?:\.\d{1,2})?"
    )
    max_price = None
    cue_match = re.search(price_pattern, lowered)
    if cue_match:
        digits = re.search(r"\d+(?:\.\d{1,2})?", cue_match.group(0))
        max_price = float(digits.group(0))

    # --- size ------------------------------------------------------------------
    size = None
    # Explicit "size M" / "size: XL" / "size large".
    explicit = re.search(r"size[:\s]+([a-z0-9/]+)", lowered)
    if explicit:
        size = explicit.group(1).upper()
    else:
        # Standalone size word as a whole token (e.g. "... in XL"). The
        # surrounding guards keep single letters from matching inside words or
        # contractions (e.g. the "m" in "I'm").
        for sw in _SIZE_WORDS:
            if re.search(rf"(?<![\w']){sw}(?![\w'])", lowered):
                size = sw.upper()
                break

    # --- description -----------------------------------------------------------
    description = lowered
    # Drop the price phrase and the size phrase from the description.
    description = re.sub(price_pattern, " ", description)
    description = re.sub(r"size[:\s]+[a-z0-9/]+", " ", description)
    for phrase in _FILLER:
        description = description.replace(phrase, " ")
    # Collapse leftover punctuation/whitespace.
    description = re.sub(r"[^a-z0-9\s/-]", " ", description)
    description = re.sub(r"\s+", " ", description).strip()

    return {
        "description": description or query.strip(),
        "size": size,
        "max_price": max_price,
    }


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # Step 1: fresh session.
    session = _new_session(query, wardrobe)

    # Step 2: parse the query into search parameters.
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # Step 3: search the listings.
    results = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    if not results:
        # No match → end the loop early with a helpful message. Do NOT call
        # the downstream tools with empty input.
        hints = []
        if parsed["max_price"] is not None:
            hints.append(f"raising your budget above ${parsed['max_price']:g}")
        if parsed["size"]:
            hints.append(f"trying a different size than {parsed['size']}")
        hints.append("describing the item differently or by color")
        session["error"] = (
            f"No matches were found for \"{parsed['description']}\". "
            "Are you interested in other items? Try "
            + ", or ".join(hints)
            + "."
        )
        return session

    # Step 4: select the top result.
    session["selected_item"] = results[0]

    # Step 5: suggest an outfit (handles empty wardrobe internally).
    session["outfit_suggestion"] = suggest_outfit(
        session["selected_item"], wardrobe
    )

    # Step 6: build the shareable fit card.
    session["fit_card"] = create_fit_card(
        session["outfit_suggestion"], session["selected_item"]
    )

    # Step 7: done.
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
    print(f"\nFit card: {session2['fit_card']}")
