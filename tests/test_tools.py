"""
test_tools.py

Unit tests for Tool 1: search_listings().

Run with:
    pytest test_tools.py -v

These tests exercise the real mock dataset in data/listings.json. They cover
both successful searches (matches found, correct filtering, correct ranking)
and unsuccessful searches (no keyword match, filters that exclude everything,
empty/blank queries).

Note:
    tools.py imports `groq` and `python-dotenv` at module load time for the
    LLM-backed tools (suggest_outfit / create_fit_card). search_listings does
    NOT use them. We stub those modules before importing so the Tool 1 tests
    run even in an environment where the LLM dependencies aren't installed.
"""

import re
import sys
import types
import os

# --- Stub LLM-only dependencies so importing tools.py never fails here -------
if "dotenv" not in sys.modules:
    _dotenv = types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **k: None
    sys.modules["dotenv"] = _dotenv

if "groq" not in sys.modules:
    _groq = types.ModuleType("groq")
    _groq.Groq = object
    sys.modules["groq"] = _groq

sys.path.append(os.path.abspath("../ai201-project2-fitfindr-starter"))

import pytest

import tools
from tools import create_fit_card, search_listings, suggest_outfit
from utils.data_loader import (
    get_empty_wardrobe,
    get_example_wardrobe,
    load_listings,
)


# ── Fixtures / helpers ──────────────────────────────────────────────────────

# Every field the spec promises a listing dict should carry.
EXPECTED_FIELDS = {
    "id", "title", "description", "category", "style_tags",
    "size", "condition", "price", "colors", "brand", "platform",
}


@pytest.fixture(scope="module")
def all_listings():
    return load_listings()


def ids(results):
    """Convenience: pull the id list out of a results list."""
    return [r["id"] for r in results]


def keyword_overlap(listing, query):
    """
    Recompute the relevance score the way search_listings does: count how many
    distinct query keywords appear in the listing's searchable text fields.
    Used to verify ordering without depending on a single 'winner'.
    """
    keywords = re.findall(r"[a-z0-9]+", query.lower())
    haystack = " ".join([
        str(listing.get("title", "")),
        str(listing.get("description", "")),
        str(listing.get("category", "")),
        " ".join(listing.get("style_tags", []) or []),
        " ".join(listing.get("colors", []) or []),
        str(listing.get("brand") or ""),
    ])
    tokens = set(re.findall(r"[a-z0-9]+", haystack.lower()))
    return sum(1 for kw in keywords if kw in tokens)


# ── Successful searches ─────────────────────────────────────────────────────

def test_basic_match_returns_results():
    """A plain keyword query returns a non-empty list of dicts."""
    results = search_listings("graphic tee")
    assert isinstance(results, list)
    assert len(results) > 0
    assert all(isinstance(r, dict) for r in results)


def test_results_have_all_expected_fields():
    """Returned listings preserve the full schema, not a trimmed copy."""
    results = search_listings("vintage denim jacket")
    assert results, "expected at least one match for this query"
    for r in results:
        assert EXPECTED_FIELDS.issubset(r.keys())


def test_known_listing_is_found():
    """The 2003 bootleg graphic tee (lst_006) must surface for this query."""
    results = search_listings("graphic tee vintage streetwear")
    assert "lst_006" in ids(results)


def test_results_are_real_listings(all_listings):
    """Every returned item is an actual entry from the dataset."""
    valid_ids = {l["id"] for l in all_listings}
    results = search_listings("vintage")
    assert ids(results), "expected matches for 'vintage'"
    assert all(r["id"] in valid_ids for r in results)


def test_max_price_filter_is_respected():
    """No result may exceed the price ceiling."""
    results = search_listings("jacket", max_price=45.0)
    assert results, "expected jackets at/under $45"
    assert all(r["price"] <= 45.0 for r in results)


def test_max_price_excludes_expensive_items():
    """The $75 leather bomber (lst_022) is dropped by a $50 ceiling."""
    cheap = search_listings("leather bomber", max_price=50.0)
    assert "lst_022" not in ids(cheap)


def test_max_price_boundary_is_inclusive():
    """A listing priced exactly at max_price is kept (inclusive bound)."""
    # lst_013 "90s Silk Slip Dress" is priced at exactly $30.00.
    results = search_listings("90s silk slip dress", max_price=30.0)
    assert "lst_013" in ids(results)


def test_size_filter_substring_match():
    """size='XL' matches 'XL', 'XL (oversized)', 'XL (fits oversized)'."""
    results = search_listings("vintage", size="XL")
    assert results, "expected XL vintage items"
    for r in results:
        assert "xl" in r["size"].lower()
    # lst_003 (XL oversized) and lst_027 (XL) should be among them.
    assert {"lst_003", "lst_027"}.issubset(set(ids(results)))


def test_size_filter_is_case_insensitive():
    """A lowercase size query still matches 'US 8'-style sizes."""
    results = search_listings("platform sneakers", size="us 8")
    assert results, "expected a US 8 sneaker match"
    assert all("us 8" in r["size"].lower() for r in results)
    assert "lst_019" in ids(results)  # Platform Sneakers, US 8


def test_combined_filters_all_apply():
    """Description + size + max_price constraints are enforced together."""
    results = search_listings("vintage tee", size="L", max_price=25.0)
    for r in results:
        assert r["price"] <= 25.0
        assert "l" in r["size"].lower()
    # lst_033 (Vintage Band Tee, size L, $19) satisfies all three.
    assert "lst_033" in ids(results)


def test_keyword_matches_color_field():
    """Queries can match on the colors field, not just the title."""
    results = search_listings("olive")
    assert results, "expected items described/colored olive"
    # lst_021 (olive trousers) and lst_032 (olive shacket) are olive-colored.
    assert {"lst_021", "lst_032"} & set(ids(results))


# ── Relevance ranking ───────────────────────────────────────────────────────

def test_results_sorted_by_relevance():
    """Relevance is non-increasing: each result matches >= as many keywords
    as the next one. (Ties between equally-relevant items are allowed.)"""
    query = "vintage band graphic tee streetwear"
    results = search_listings(query)
    assert len(results) >= 2, "need multiple matches to check ordering"
    scores = [keyword_overlap(r, query) for r in results]
    assert scores == sorted(scores, reverse=True)
    # The top result must match every keyword in this query.
    assert scores[0] == 5


def test_more_specific_query_ranks_best_match_first():
    """A denim-jacket query ranks the actual denim jacket above loose matches."""
    results = search_listings("denim jacket vintage")
    assert results, "expected denim-related matches"
    # lst_007 is the Denim Jacket (denim + vintage + 'jacket' in title).
    assert results[0]["id"] == "lst_007"


# ── Unsuccessful searches (the failure mode for the agent loop) ─────────────

def test_no_keyword_match_returns_empty():
    """A query with no overlap returns an empty list, not an error."""
    results = search_listings("scuba diving wetsuit snorkel")
    assert results == []


def test_empty_description_returns_empty():
    """An empty description yields no matches."""
    assert search_listings("") == []


def test_whitespace_description_returns_empty():
    """A blank/whitespace-only description yields no matches."""
    assert search_listings("   ") == []


def test_punctuation_only_description_returns_empty():
    """A query of only punctuation tokenizes to nothing → no matches."""
    assert search_listings("!!! ??? ...") == []


def test_price_too_low_returns_empty():
    """A valid keyword but an impossibly low ceiling returns nothing."""
    # Cheapest items are well above $1.
    assert search_listings("vintage jacket", max_price=1.0) == []


def test_nonexistent_size_returns_empty():
    """A size that no listing carries returns an empty list."""
    assert search_listings("vintage", size="XXXL") == []


def test_never_raises_on_no_match():
    """search_listings must degrade to [] rather than raise for any query."""
    for query in ["", "   ", "qwertyuiop", "$$$"]:
        try:
            result = search_listings(query)
        except Exception as exc:  # pragma: no cover - failure path
            pytest.fail(f"search_listings raised on {query!r}: {exc}")
        assert result == []


# ── Complex, realistic user queries ─────────────────────────────────────────

def test_complex_query_vintage_graphic_tee_under_budget():
    """'vintage graphic tee under $30' → only tees within budget."""
    results = search_listings("vintage graphic tee", max_price=30.0)
    assert results, "expected affordable graphic tees"
    assert all(r["price"] <= 30.0 for r in results)
    # The bootleg graphic tee ($24) should be present and well-ranked.
    assert "lst_006" in ids(results)


def test_complex_query_cottagecore_linen_with_size():
    """Aesthetic + material + size: cottagecore linen in M/L."""
    results = search_listings("cottagecore linen", size="M/L")
    assert results, "expected cottagecore linen in M/L"
    for r in results:
        assert "m/l" in r["size"].lower()
    # lst_025 (Wide-Leg Linen Trousers, M/L, cottagecore+linen) qualifies.
    assert "lst_025" in ids(results)


def test_complex_query_no_result_due_to_price_ceiling():
    """A real item exists but the tight budget filters it out entirely."""
    # Only the $52 velvet blazer and $75 bomber are 'statement/leather' heavy;
    # an emerald velvet statement blazer under $20 does not exist.
    results = search_listings("emerald velvet statement blazer", max_price=20.0)
    assert results == []


# ═════════════════════════════════════════════════════════════════════════════
# Tool 2: suggest_outfit()
#
# These tests never hit the network. We monkeypatch tools._chat (the single
# Groq entry point) so we can (a) assert which branch ran and what prompt was
# built, and (b) force an empty LLM response to exercise the fallback.
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def fake_chat(monkeypatch):
    """
    Replace tools._chat with a recorder. Returns a `calls` list; each entry is
    the dict of arguments the tool passed. The canned reply can be overridden
    via `calls.reply`.
    """
    class Recorder(list):
        reply = "FAKE STYLING SUGGESTION"

    calls = Recorder()

    def _fake(system, user, temperature=0.8, top_p=0.9):
        calls.append({
            "system": system,
            "user": user,
            "temperature": temperature,
            "top_p": top_p,
        })
        return calls.reply

    monkeypatch.setattr(tools, "_chat", _fake)
    return calls


@pytest.fixture
def selected_item():
    """The top match for the canonical query — a real listing dict."""
    results = search_listings("vintage graphic tee", max_price=30.0)
    assert results, "fixture precondition: expected a graphic tee match"
    return results[0]


# ── non-empty wardrobe branch ───────────────────────────────────────────────

def test_suggest_outfit_returns_llm_text(fake_chat, selected_item):
    """With a wardrobe, the tool returns the LLM's suggestion verbatim."""
    out = suggest_outfit(selected_item, get_example_wardrobe())
    assert out == "FAKE STYLING SUGGESTION"
    assert len(fake_chat) == 1  # exactly one LLM call


def test_suggest_outfit_prompt_includes_wardrobe_pieces(fake_chat, selected_item):
    """The prompt names actual pieces from the user's closet."""
    suggest_outfit(selected_item, get_example_wardrobe())
    prompt = fake_chat[0]["user"]
    assert "Wide-leg khaki trousers" in prompt
    assert "Chunky white sneakers" in prompt
    assert "closet" in prompt.lower()


def test_suggest_outfit_prompt_includes_new_item(fake_chat, selected_item):
    """The new item being styled appears in the prompt."""
    suggest_outfit(selected_item, get_example_wardrobe())
    assert selected_item["title"] in fake_chat[0]["user"]


def test_suggest_outfit_uses_creative_temperature(fake_chat, selected_item):
    """Suggestions should be generated with elevated temperature for variety."""
    suggest_outfit(selected_item, get_example_wardrobe())
    assert fake_chat[0]["temperature"] > 0.5


# ── empty wardrobe branch (falls back to other listings) ────────────────────

def test_empty_wardrobe_falls_back_to_listings(fake_chat, selected_item):
    """An empty wardrobe pairs the item with other secondhand listings."""
    suggest_outfit(selected_item, get_empty_wardrobe())
    prompt = fake_chat[0]["user"]
    assert "secondhand" in prompt.lower()
    assert "wardrobe saved" in prompt.lower()  # the 'no wardrobe yet' framing


def test_empty_wardrobe_does_not_suggest_the_item_itself(fake_chat, selected_item):
    """The complement list must exclude the item the user already picked."""
    suggest_outfit(selected_item, get_empty_wardrobe())
    prompt = fake_chat[0]["user"]
    # Split off the section listing the available pieces and check the item
    # isn't recommended back to the user.
    available_section = prompt.split("available right now:")[1]
    assert selected_item["title"] not in available_section


def test_empty_wardrobe_complements_are_other_categories(selected_item):
    """_complementary_listings prefers items from different categories."""
    complements = tools._complementary_listings(selected_item)
    assert complements, "expected complementary listings"
    assert all(c["id"] != selected_item["id"] for c in complements)
    # The graphic tee is a 'top'; complements should lean to other categories.
    assert any(c["category"] != selected_item["category"] for c in complements)


# ── degraded LLM response ───────────────────────────────────────────────────

def test_empty_llm_response_returns_nonempty_fallback(fake_chat, selected_item):
    """If the LLM returns nothing, the tool still returns a useful string."""
    fake_chat.reply = ""
    out = suggest_outfit(selected_item, get_example_wardrobe())
    assert out, "fallback must be a non-empty string"
    assert selected_item["title"] in out


def test_suggest_outfit_never_returns_empty_string(fake_chat, selected_item):
    """Contract: suggest_outfit always returns a non-empty string."""
    for reply in ["a real suggestion", "", "   "]:
        fake_chat.reply = reply
        out = suggest_outfit(selected_item, get_example_wardrobe())
        assert isinstance(out, str) and out.strip()


# ── prompt-formatting helpers ───────────────────────────────────────────────

def test_format_item_includes_title_and_colors():
    item = {
        "title": "Test Tee", "colors": ["black", "white"],
        "category": "tops", "style_tags": ["vintage"],
    }
    line = tools._format_item(item)
    assert "Test Tee" in line
    assert "black" in line and "white" in line


def test_format_wardrobe_item_uses_name_field():
    """Wardrobe items use 'name' (not 'title') and may carry 'notes'."""
    wardrobe_item = {
        "name": "Chunky white sneakers", "colors": ["white"],
        "category": "shoes", "notes": "go-to everyday shoe",
    }
    line = tools._format_wardrobe_item(wardrobe_item)
    assert "Chunky white sneakers" in line
    assert "go-to everyday shoe" in line


# ═════════════════════════════════════════════════════════════════════════════
# Tool 3: create_fit_card()
#
# Like the suggest_outfit tests, these monkeypatch tools._chat so no network
# call is made. We assert the guard behavior (empty/missing inputs return an
# error string, never raise) and that the prompt carries the item details and
# the outfit through to the LLM.
# ═════════════════════════════════════════════════════════════════════════════

# A representative outfit suggestion, as suggest_outfit would produce.
SAMPLE_OUTFIT = (
    "Pair this with your baggy straight-leg jeans and chunky white sneakers "
    "for an easy retro look."
)


# ── happy path ──────────────────────────────────────────────────────────────

def test_create_fit_card_returns_llm_caption(fake_chat, selected_item):
    """With a valid outfit + item, returns the LLM caption verbatim."""
    out = create_fit_card(SAMPLE_OUTFIT, selected_item)
    assert out == "FAKE STYLING SUGGESTION"
    assert len(fake_chat) == 1


def test_create_fit_card_prompt_includes_item_details(fake_chat, selected_item):
    """The prompt carries the item title, price, and platform."""
    create_fit_card(SAMPLE_OUTFIT, selected_item)
    prompt = fake_chat[0]["user"]
    assert selected_item["title"] in prompt
    assert selected_item["platform"] in prompt
    assert f"{selected_item['price']:g}" in prompt  # e.g. "18" from 18.0


def test_create_fit_card_prompt_includes_outfit(fake_chat, selected_item):
    """The outfit suggestion is passed into the caption prompt."""
    create_fit_card(SAMPLE_OUTFIT, selected_item)
    assert "chunky white sneakers" in fake_chat[0]["user"]


def test_create_fit_card_uses_high_temperature(fake_chat, selected_item):
    """Captions should vary across runs → high temperature."""
    create_fit_card(SAMPLE_OUTFIT, selected_item)
    assert fake_chat[0]["temperature"] >= 0.9


# ── guard: empty / missing outfit ───────────────────────────────────────────

def test_empty_outfit_returns_error_without_calling_llm(fake_chat, selected_item):
    """An empty outfit short-circuits to an error string, no LLM call."""
    out = create_fit_card("", selected_item)
    assert isinstance(out, str) and out.strip()
    assert "outfit suggestion" in out.lower()
    assert len(fake_chat) == 0  # guard runs before any LLM call


def test_whitespace_outfit_returns_error(fake_chat, selected_item):
    """A whitespace-only outfit is treated as missing."""
    out = create_fit_card("   \n  ", selected_item)
    assert "couldn't create a fit card" in out.lower()
    assert len(fake_chat) == 0


@pytest.mark.parametrize("bad_outfit", ["", "   ", None])
def test_create_fit_card_never_raises_on_bad_outfit(bad_outfit, selected_item):
    """Bad outfit input degrades to an error string rather than raising."""
    out = create_fit_card(bad_outfit, selected_item)
    assert isinstance(out, str) and out.strip()


# ── guard: missing / incomplete item ────────────────────────────────────────

def test_missing_item_returns_error(fake_chat):
    """An empty item dict yields an error string, not an exception."""
    out = create_fit_card(SAMPLE_OUTFIT, {})
    assert "item details" in out.lower()
    assert len(fake_chat) == 0


# ── degraded LLM response ───────────────────────────────────────────────────

def test_empty_llm_caption_returns_nonempty_fallback(fake_chat, selected_item):
    """If the LLM returns nothing, fall back to a non-empty caption."""
    fake_chat.reply = ""
    out = create_fit_card(SAMPLE_OUTFIT, selected_item)
    assert out.strip()
    assert selected_item["title"] in out


def test_create_fit_card_always_returns_nonempty_string(fake_chat, selected_item):
    """Contract: a valid call always returns a non-empty string."""
    for reply in ["a real caption", "", "   "]:
        fake_chat.reply = reply
        out = create_fit_card(SAMPLE_OUTFIT, selected_item)
        assert isinstance(out, str) and out.strip()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
