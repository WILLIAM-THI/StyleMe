"""Tests for outfits.py: the rules for what counts as an outfit, scoring, reading a
typed request, and generate() using the rule-based picker (no Gemini key in tests)."""
from types import SimpleNamespace

import outfits


def item(item_id, category, colour="black", pattern="solid", season="spring_summer",
         occasion="casual", description=None):
    """A fake clothing item with only the fields the outfit code reads."""
    return SimpleNamespace(id=item_id, category=category, colour=colour, pattern=pattern,
                           season=season, occasion=occasion, description=description)


# ---------- _is_valid: what counts as a complete outfit ----------
def test_top_plus_bottom_is_valid():
    assert outfits._is_valid([item(1, "t_shirt"), item(2, "jeans")])


def test_dress_alone_is_valid():
    assert outfits._is_valid([item(1, "dress")])


def test_top_without_bottom_is_invalid():
    assert not outfits._is_valid([item(1, "t_shirt"), item(2, "shoes")])


def test_dress_with_a_top_is_invalid():
    assert not outfits._is_valid([item(1, "dress"), item(2, "t_shirt")])


def test_two_of_the_same_accessory_type_is_invalid():
    base = [item(1, "t_shirt"), item(2, "jeans")]
    assert not outfits._is_valid(base + [item(3, "hat"), item(4, "hat")])


# ---------- small helpers and scoring ----------
def test_wet_weather_is_detected():
    assert outfits._is_wet("Light Rain") and outfits._is_wet("Thunderstorm")
    assert not outfits._is_wet("Clear") and not outfits._is_wet("")


def test_temperature_scoring_prefers_the_right_clothes():
    assert outfits._temp_score("shorts", 30) > 0 > outfits._temp_score("shorts", 10)
    assert outfits._temp_score("jumper", 10) > 0 > outfits._temp_score("jumper", 30)
    assert outfits._temp_score("t_shirt", None) == 0


def test_occasion_scoring():
    assert outfits._occasion_score(item(1, "t_shirt", occasion="smart"), "smart") == 3      # exact match
    assert outfits._occasion_score(item(1, "t_shirt", occasion="casual"), "smart") == 1     # next to each other
    assert outfits._occasion_score(item(1, "t_shirt", occasion="sporty"), "formal") == -2   # far apart
    assert outfits._occasion_score(item(1, "t_shirt"), None) == 0                           # no wish


# ---------- reading the sentence the user typed ----------
def test_read_request_finds_colour_pattern_temperature_and_occasion():
    temp, condition, prefs = outfits.read_request("a hot day at the beach, something red and striped for a date")
    assert temp == 32
    assert condition == ""
    assert prefs["colour"] == "red"
    assert prefs["pattern"] == "striped"
    assert prefs["season"] == "spring_summer"
    assert prefs["occasion"] == "smart"


def test_read_request_with_nothing_useful_returns_nothing():
    assert outfits.read_request("") == (None, "", {})
    assert outfits.read_request(None) == (None, "", {})


# ---------- generate(): the whole picker, without Gemini ----------
def test_generate_returns_none_without_a_complete_base():
    assert outfits.generate([item(1, "t_shirt"), item(2, "shoes")], 20, "", set()) is None   # no bottom
    assert outfits.generate([item(1, "jeans")], 20, "", set()) is None                       # no top
    assert outfits.generate([], 20, "", set()) is None


def test_generate_builds_a_valid_ordered_outfit_and_reports_missing_shoes():
    wardrobe = [item(1, "jeans"), item(2, "t_shirt"), item(3, "pants"), item(4, "long_sleeve_top")]
    for _ in range(20):   # the picker uses randomness, so check it many times
        chosen, missing, unmatched = outfits.generate(wardrobe, 20, "Clear", set())
        assert outfits._is_valid(chosen)
        assert [i.category in outfits.TOPS for i in chosen] == [True, False]   # top is listed before bottom
        assert missing == ["shoes"]
        assert unmatched == []


def test_generate_adds_shoes_and_outerwear_when_cold():
    wardrobe = [item(1, "t_shirt"), item(2, "jeans"), item(3, "shoes"), item(4, "coat"), item(5, "shorts")]
    chosen, missing, _unmatched = outfits.generate(wardrobe, 5, "Clear", set())
    categories = [i.category for i in chosen]
    assert "coat" in categories and "shoes" in categories
    assert missing == []
