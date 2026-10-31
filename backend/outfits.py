"""Picks an outfit from the user's own wardrobe for the current weather.

1. Gemini (if GEMINI_API_KEY is set) is shown the list of items and the weather,
   and chooses the item ids. It only ever sees text (category, colour, pattern,
   season), never the photos.
2. Whatever it answers is checked. If the answer is unusable, or there is no
   key, a simple rule-based picker chooses instead, so the page always works.

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


def _score(item, temp: float, avoid: set[int]) -> float:
    """Higher = a better fit for this temperature. Random noise gives variety."""
    score = random.random()
    warm = temp >= 18
    if (item.season == "spring_summer") == warm:
        score += 1.5
    category = item.category
    if category == "short_sleeve_top":
        score += 2 if temp >= 22 else (-2 if temp < 16 else 0)
    elif category == "long_sleeve_top":
        score += 2 if temp <= 17 else (-2 if temp >= 26 else 0)
    elif category == "shorts":
        score += 2 if temp >= 26 else (-3 if temp < 20 else 0)
    elif category == "skirt":
        score += 1 if temp >= 22 else (-2 if temp < 16 else 0)
    elif category == "pants":
        score += 1 if temp <= 22 else (-1 if temp >= 30 else 0)
    if item.id in avoid:
        score -= 3  # "Regenerate" should give something different if it can
    return score


def _best(items, temp, avoid):
    return max(items, key=lambda i: _score(i, temp, avoid)) if items else None


def _rule_based(items, temp, wet, avoid):
    tops = [i for i in items if i.category in TOPS]
    bottoms = [i for i in items if i.category in BOTTOMS]
    dresses = [i for i in items if i.category in DRESSES]
    outer = [i for i in items if i.category in OUTERWEAR]
    shoes = [i for i in items if i.category in SHOES]
    accessories = [i for i in items if i.category in ACCESSORIES]

    use_dress = bool(dresses) and (not (tops and bottoms) or (temp >= 16 and random.random() < 0.25))
    if use_dress:
        chosen = [_best(dresses, temp, avoid)]
    elif tops and bottoms:
        chosen = [_best(tops, temp, avoid), _best(bottoms, temp, avoid)]
    else:
        return None

    if shoes:
        chosen.append(_best(shoes, temp, avoid))
    if outer and (temp < 18 or wet):
        chosen.append(_best(outer, temp, avoid))
    if accessories and random.random() < 0.4:
        chosen.append(random.choice(accessories))
    return chosen


def _is_valid(chosen) -> bool:
    """At most one item per slot, and a complete base: a dress, or a top and a bottom."""
    counts = [sum(1 for i in chosen if i.category in slot) for slot in SLOT_ORDER]
    if any(c > 1 for c in counts):
        return False
    outer, tops, dress, bottoms, _shoes, _acc = counts
    return (dress == 1 and tops == 0 and bottoms == 0) or (dress == 0 and tops == 1 and bottoms == 1)


def _ask_gemini(items, temp, condition, avoid):
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
    prompt = (
        f"You are a stylist. The weather is {temp:.0f}°C, {condition or 'unknown conditions'}.\n"
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


def generate(items, temp: float, condition: str, avoid_ids: set[int]):
    """Returns (chosen_items, missing) or None if the wardrobe can't make an outfit.

    `missing` lists what would complete the outfit, e.g. ["shoes"].
    """
    wet = _is_wet(condition)
    by_id = {i.id: i for i in items}
    chosen = None

    try:
        ids = _ask_gemini(items, temp, condition, avoid_ids)
        if ids:
            candidate = list({i: by_id[i] for i in ids if i in by_id}.values())
            if _is_valid(candidate) and {i.id for i in candidate} != avoid_ids:
                chosen = candidate
    except Exception:
        chosen = None  # any AI problem: just use the simple picker below

    if chosen is None:
        chosen = _rule_based(items, temp, wet, avoid_ids)
    if not chosen:
        return None

    chosen.sort(key=_group)
    missing = []
    if not any(i.category in SHOES for i in items):
        missing.append("shoes")
    return chosen, missing
