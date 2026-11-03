"""Picks an outfit from the user's own wardrobe for the current weather.

1. Gemini (if GEMINI_API_KEY is set) is shown the list of items and the weather,
   and chooses the item ids. It only ever sees text (category, colour, pattern,
   season), never the photos.
2. Whatever it answers is checked. If the answer is unusable, or there is no
   key, a simple rule-based picker chooses instead, so the page always works.

The Generate Outfit page also passes preferences (occasion, colour, season,
pattern). They are wishes, not rules: the closest outfit is chosen, and the page
is told which wishes the wardrobe could not meet.

An outfit is either one dress, or one top plus one bottom, plus shoes if the
wardrobe has any, outerwear when it is cold or wet, and sometimes an accessory.
"""
import json
import random

import ai_identify

TOPS = {"short_sleeve_top", "long_sleeve_top"}
BOTTOMS = {"pants", "shorts", "skirt"}
DRESSES = {"dress"}
OUTERWEAR = {"outerwear"}
SHOES = {"shoes"}
ACCESSORIES = {"accessory"}

# Top to bottom, the order the items are returned (and drawn) in.
SLOT_ORDER = [OUTERWEAR, TOPS, DRESSES, BOTTOMS, SHOES, ACCESSORIES]

WET_WORDS = ("rain", "drizzle", "thunder", "storm", "snow")
MAX_ITEMS_SHOWN_TO_AI = 120


def _group(item) -> int:
    for position, categories in enumerate(SLOT_ORDER):
        if item.category in categories:
            return position
    return len(SLOT_ORDER)


def _is_wet(condition: str) -> bool:
    return any(word in (condition or "").lower() for word in WET_WORDS)


OCCASIONS = ("casual", "smart", "sporty")


def _occasion_score(item, occasion) -> float:
    """The wardrobe doesn't record how dressy an item is, so this goes by the type of garment."""
    c, p = item.category, item.pattern
    if occasion == "smart":
        s = {"pants": 1.5, "skirt": 1, "dress": 1, "long_sleeve_top": 1, "shorts": -3}.get(c, 0)
        if p == "graphic":
            s -= 2
        if p == "solid":
            s += 1
        return s
    if occasion == "sporty":
        s = {"shorts": 1.5, "short_sleeve_top": 1, "pants": 0.5, "skirt": -1, "dress": -2}.get(c, 0)
        if p == "graphic":
            s += 0.5
        return s
    return 0


def _temp_score(category, temp) -> float:
    if category == "short_sleeve_top":
        return 2 if temp >= 22 else (-2 if temp < 16 else 0)
    if category == "long_sleeve_top":
        return 2 if temp <= 17 else (-2 if temp >= 26 else 0)
    if category == "shorts":
        return 2 if temp >= 26 else (-3 if temp < 20 else 0)
    if category == "skirt":
        return 1 if temp >= 22 else (-2 if temp < 16 else 0)
    if category == "pants":
        return 1 if temp <= 22 else (-1 if temp >= 30 else 0)
    return 0


def _score(item, temp, avoid: set[int], prefs=None) -> float:
    """Higher = a better fit. Random noise gives variety.

    temp is None on the Generate Outfit page (no weather); prefs holds the user's wishes.
    """
    prefs = prefs or {}
    score = random.random()
    if prefs.get("season"):
        if item.season == prefs["season"]:
            score += 3
    elif temp is not None and (item.season == "spring_summer") == (temp >= 18):
        score += 1.5
    if temp is not None:
        score += _temp_score(item.category, temp)
    if prefs.get("colour") and item.colour == prefs["colour"]:
        score += 3
    if prefs.get("pattern") and item.pattern == prefs["pattern"]:
        score += 3
    score += _occasion_score(item, prefs.get("occasion"))
    if item.id in avoid:
        score -= 3  # "Regenerate" should give something different if it can
    return score


def _best(items, temp, avoid, prefs=None):
    return max(items, key=lambda i: _score(i, temp, avoid, prefs)) if items else None


def _unmatched(chosen, prefs) -> list[str]:
    """Which of the colour / pattern / season wishes no chosen item satisfies."""
    return [k for k in ("colour", "pattern", "season")
            if prefs.get(k) and not any(getattr(i, k) == prefs[k] for i in chosen)]


def _rule_based(items, temp, wet, avoid, prefs=None):
    prefs = prefs or {}
    tops = [i for i in items if i.category in TOPS]
    bottoms = [i for i in items if i.category in BOTTOMS]
    dresses = [i for i in items if i.category in DRESSES]
    outer = [i for i in items if i.category in OUTERWEAR]
    shoes = [i for i in items if i.category in SHOES]
    accessories = [i for i in items if i.category in ACCESSORIES]

    if prefs:
        bases = [[d] for d in dresses] + [[t, b] for t in tops for b in bottoms]
        if len(bases) > 600:
            bases = random.sample(bases, 600)
        if not bases:
            return None

        def base_score(base):
            total = sum(_score(i, temp, avoid, prefs) for i in base)
            if len(base) == 1:
                total *= 2  # a dress fills both the top and bottom slots
            return total + 4 * (len([k for k in ("colour", "pattern", "season") if prefs.get(k)]) - len(_unmatched(base, prefs)))

        chosen = list(max(bases, key=base_score))
    else:
        use_dress = bool(dresses) and (not (tops and bottoms) or (temp is not None and temp >= 16 and random.random() < 0.25))
        if use_dress:
            chosen = [_best(dresses, temp, avoid)]
        elif tops and bottoms:
            chosen = [_best(tops, temp, avoid), _best(bottoms, temp, avoid)]
        else:
            return None

    if shoes:
        chosen.append(_best(shoes, temp, avoid, prefs))
    cold = (temp is not None and temp < 18) or (temp is None and prefs.get("season") == "autumn_winter")
    if outer and (cold or wet):
        chosen.append(_best(outer, temp, avoid, prefs))
    if accessories and random.random() < 0.4:
        chosen.append(_best(accessories, temp, avoid, prefs))
    return chosen


def _is_valid(chosen) -> bool:
    """At most one item per slot, and a complete base: a dress, or a top and a bottom."""
    counts = [sum(1 for i in chosen if i.category in slot) for slot in SLOT_ORDER]
    if any(c > 1 for c in counts):
        return False
    outer, tops, dress, bottoms, _shoes, _acc = counts
    return (dress == 1 and tops == 0 and bottoms == 0) or (dress == 0 and tops == 1 and bottoms == 1)


def _ask_gemini(items, temp, condition, avoid, prefs=None):
    client = ai_identify._get_client()
    if client is None:
        return None
    from google.genai import types

    shown = items if len(items) <= MAX_ITEMS_SHOWN_TO_AI else random.sample(items, MAX_ITEMS_SHOWN_TO_AI)
    lines = "\n".join(f"{i.id}: {i.category}, {i.colour}, {i.pattern}, best in {i.season}" for i in shown)
    avoid_text = (
        f"\nDo NOT choose exactly this combination of ids again: {sorted(avoid)}. Choose a different outfit."
        if avoid else ""
    )
    if temp is None:
        setting = "No weather is given."
    else:
        setting = f"The weather is {temp:.0f}°C, {condition or 'unknown conditions'}."
    wishes = ""
    if prefs:
        parts = [f"{k}: {v.replace('_', ' ')}" for k, v in prefs.items() if v]
        if parts:
            wishes = "The user wants an outfit for these wishes (match as many as the wardrobe allows): " + ", ".join(parts) + ".\n"
    prompt = (
        f"You are a stylist. {setting}\n{wishes}"
        "Choose ONE outfit from this wardrobe. Each line is: id: category, colour, pattern, best season.\n"
        f"{lines}\n\n"
        "Rules:\n"
        "- Either one dress, OR one top plus one bottom (pants, shorts or skirt).\n"
        "- Add one pair of shoes if there are any.\n"
        "- Add outerwear if it is cold or wet.\n"
        "- You may add one accessory.\n"
        "- At most one item per category type, and use only the ids listed.\n"
        "- Suit the temperature, and pick colours that look good together."
        f"{avoid_text}\n"
        'Reply with ONLY a JSON object like {"item_ids": [12, 7, 3]}.'
    )
    response = client.models.generate_content(
        model=ai_identify.MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=1.0),
    )
    data = json.loads(response.text.strip().strip("`"))
    return [int(i) for i in data.get("item_ids", [])]


def generate(items, temp, condition: str, avoid_ids: set[int], prefs=None):
    """Returns (chosen_items, missing, unmatched) or None if the wardrobe can't make an outfit.

    `missing` lists what would complete the outfit, e.g. ["shoes"].
    `unmatched` lists wishes (colour, pattern, season) that no chosen item meets.
    temp may be None (no weather); prefs is a dict of wishes or None.
    """
    prefs = {k: v for k, v in (prefs or {}).items() if v}
    wet = _is_wet(condition)
    by_id = {i.id: i for i in items}
    chosen = None

    try:
        ids = _ask_gemini(items, temp, condition, avoid_ids, prefs)
        if ids:
            candidate = list({i: by_id[i] for i in ids if i in by_id}.values())
            if _is_valid(candidate) and {i.id for i in candidate} != avoid_ids:
                chosen = candidate
    except Exception:
        chosen = None  # any AI problem: just use the simple picker below

    if chosen is None:
        chosen = _rule_based(items, temp, wet, avoid_ids, prefs)
    if not chosen:
        return None

    chosen.sort(key=_group)
    missing = []
    if not any(i.category in SHOES for i in items):
        missing.append("shoes")
    return chosen, missing, _unmatched(chosen, prefs)
