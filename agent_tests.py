"""
agent_tests.py

Unit tests for the FitFindr planning loop (agent.py):
    _parse_query()  — natural-language → {description, size, max_price}
    run_agent()     — orchestrates the three tools and manages session state

Run with:
    pytest agent_tests.py -v

run_agent() tests monkeypatch the three tools (as bound in the agent module)
so the loop's control flow and state-passing are tested in isolation, with no
LLM calls and no dependency on the live dataset.
"""

import sys
import types

# tools.py (imported transitively by agent.py) pulls in groq/python-dotenv for
# the LLM tools. Stub them so the loop tests run without those dependencies.
if "dotenv" not in sys.modules:
    _dotenv = types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **k: None
    sys.modules["dotenv"] = _dotenv

if "groq" not in sys.modules:
    _groq = types.ModuleType("groq")
    _groq.Groq = object
    sys.modules["groq"] = _groq

import pytest

import agent
from agent import _parse_query, run_agent


# ═════════════════════════════════════════════════════════════════════════════
# _parse_query()
# ═════════════════════════════════════════════════════════════════════════════

def test_parse_full_query():
    parsed = _parse_query("vintage graphic tee under $30, size M")
    assert parsed["description"] == "vintage graphic tee"
    assert parsed["size"] == "M"
    assert parsed["max_price"] == 30.0


def test_parse_price_without_dollar_sign():
    parsed = _parse_query("baggy jeans below 40 dollars")
    assert parsed["max_price"] == 40.0
    assert parsed["size"] is None
    assert "baggy jeans" in parsed["description"]


def test_parse_decimal_price():
    parsed = _parse_query("silk slip dress under $29.99")
    assert parsed["max_price"] == 29.99


def test_parse_no_price_no_size():
    parsed = _parse_query("flannel shirt")
    assert parsed["max_price"] is None
    assert parsed["size"] is None
    assert parsed["description"] == "flannel shirt"


def test_parse_explicit_compound_size():
    parsed = _parse_query("cottagecore linen trousers size M/L max $40")
    assert parsed["size"] == "M/L"
    assert parsed["max_price"] == 40.0
    assert parsed["description"] == "cottagecore linen trousers"


def test_parse_does_not_treat_contraction_as_size():
    """The 'm' in 'I'm' must not be picked up as size M."""
    parsed = _parse_query("I'm looking for a vintage graphic tee under $30")
    assert parsed["size"] is None
    assert parsed["max_price"] == 30.0


def test_parse_preserves_decade_in_description():
    """'90s' must survive — the bare number is not a price."""
    parsed = _parse_query("show me 90s leather bomber")
    assert parsed["max_price"] is None
    assert "90s" in parsed["description"]


def test_parse_does_not_grab_item_number_as_price():
    """A model number like '501' is part of the item, not a budget."""
    parsed = _parse_query("vintage levi 501 jeans")
    assert parsed["max_price"] is None
    assert "501" in parsed["description"]


def test_parse_strips_filler_phrases():
    parsed = _parse_query("show me a denim jacket")
    assert "show me" not in parsed["description"]
    assert "denim jacket" in parsed["description"]


def test_parse_standalone_size_token():
    parsed = _parse_query("oversized hoodie in XL")
    assert parsed["size"] == "XL"


# ═════════════════════════════════════════════════════════════════════════════
# run_agent()
# ═════════════════════════════════════════════════════════════════════════════

# A minimal listing dict, enough for the loop to pass around.
FAKE_ITEM = {
    "id": "lst_test",
    "title": "Test Graphic Tee",
    "price": 24.0,
    "platform": "depop",
    "category": "tops",
}
FAKE_WARDROBE = {"items": [{"id": "w1", "name": "white sneakers"}]}


@pytest.fixture
def stub_tools(monkeypatch):
    """
    Replace the three tools (as referenced inside agent.py) with recorders.
    Returns a dict of call logs so tests can assert what the loop invoked.
    Search results / tool outputs are configurable via the returned dict.
    """
    log = {
        "search_args": None,
        "suggest_args": None,
        "card_args": None,
        "search_return": [FAKE_ITEM],
        "suggest_return": "OUTFIT SUGGESTION",
        "card_return": "FIT CARD CAPTION",
    }

    def fake_search(description, size=None, max_price=None):
        log["search_args"] = (description, size, max_price)
        return log["search_return"]

    def fake_suggest(new_item, wardrobe):
        log["suggest_args"] = (new_item, wardrobe)
        return log["suggest_return"]

    def fake_card(outfit, new_item):
        log["card_args"] = (outfit, new_item)
        return log["card_return"]

    monkeypatch.setattr(agent, "search_listings", fake_search)
    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest)
    monkeypatch.setattr(agent, "create_fit_card", fake_card)
    return log


# ── happy path ──────────────────────────────────────────────────────────────

def test_run_agent_happy_path_populates_session(stub_tools):
    session = run_agent("vintage graphic tee under $30", FAKE_WARDROBE)
    assert session["error"] is None
    assert session["selected_item"] == FAKE_ITEM
    assert session["outfit_suggestion"] == "OUTFIT SUGGESTION"
    assert session["fit_card"] == "FIT CARD CAPTION"


def test_run_agent_passes_parsed_params_to_search(stub_tools):
    run_agent("vintage graphic tee under $30, size L", FAKE_WARDROBE)
    description, size, max_price = stub_tools["search_args"]
    assert description == "vintage graphic tee"
    assert size == "L"
    assert max_price == 30.0


def test_run_agent_stores_parsed_in_session(stub_tools):
    session = run_agent("flannel size M", FAKE_WARDROBE)
    assert session["parsed"]["size"] == "M"
    assert session["parsed"]["description"] == "flannel"


def test_run_agent_selects_first_search_result(stub_tools):
    second = {**FAKE_ITEM, "id": "lst_other", "title": "Other Tee"}
    stub_tools["search_return"] = [FAKE_ITEM, second]
    session = run_agent("graphic tee", FAKE_WARDROBE)
    assert session["selected_item"]["id"] == "lst_test"  # the top result


def test_run_agent_threads_state_between_tools(stub_tools):
    """The selected item and the outfit string flow into the next tools."""
    run_agent("graphic tee", FAKE_WARDROBE)
    # suggest_outfit receives the selected item + the wardrobe.
    assert stub_tools["suggest_args"] == (FAKE_ITEM, FAKE_WARDROBE)
    # create_fit_card receives suggest_outfit's output + the selected item.
    assert stub_tools["card_args"] == ("OUTFIT SUGGESTION", FAKE_ITEM)


# ── no-results path ─────────────────────────────────────────────────────────

def test_run_agent_no_results_sets_error(stub_tools):
    stub_tools["search_return"] = []
    session = run_agent("designer ballgown under $5", FAKE_WARDROBE)
    assert session["error"]
    assert "no matches were found" in session["error"].lower()


def test_run_agent_no_results_skips_downstream_tools(stub_tools):
    """On no match, suggest_outfit and create_fit_card must NOT be called."""
    stub_tools["search_return"] = []
    session = run_agent("designer ballgown under $5", FAKE_WARDROBE)
    assert stub_tools["suggest_args"] is None
    assert stub_tools["card_args"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None
    assert session["selected_item"] is None


def test_run_agent_error_message_mentions_constraints(stub_tools):
    """The early-exit message suggests relaxing the budget / size."""
    stub_tools["search_return"] = []
    session = run_agent("ballgown size XXS under $5", FAKE_WARDROBE)
    msg = session["error"].lower()
    assert "$5" in session["error"]
    assert "xxs" in msg


# ── empty wardrobe still completes ──────────────────────────────────────────

def test_run_agent_empty_wardrobe_completes(stub_tools):
    """An empty wardrobe is passed through; the loop still finishes.
    (suggest_outfit handles the empty-wardrobe fallback internally.)"""
    empty = {"items": []}
    session = run_agent("graphic tee", empty)
    assert session["error"] is None
    assert stub_tools["suggest_args"][1] == empty  # wardrobe forwarded as-is
    assert session["fit_card"] == "FIT CARD CAPTION"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
