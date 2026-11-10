"""Picks an outfit from the user's own wardrobe for the current weather.

1. Gemini (if GEMINI_API_KEY is set) is shown the list of items and the weather,
   and chooses the item ids. It only ever sees text (category, colour, pattern,
   season, occasion and the saved description), never the photos.
2. Whatever it answers is checked. If the answer is unusable, or there is no
   key, a simple rule-based picker chooses instead, so the page always works.

The Generate Outfit page also passes preferences (occasion, colour, season,
pattern). They are wishes, not rules: the closest outfit is chosen, and the page
is told which wishes the wardrobe could not meet.

An outfit is either one dress, or one top plus one bottom, plus shoes if the
wardrobe has any, outerwear when it is cold or wet, and sometimes a few accessories.
"""
import json
import random
import re

import ai_identify
import models

TOPS = {"short_sleeve_top", "long_sleeve_top", "t_shirt", "button_up_shirt", "singlet", "jumper"}
BOTTOMS = {"pants", "jeans", "shorts", "skirt"}
DRESSES = {"dress"}
OUTERWEAR = {"outerwear", "jacket", "coat", "vest"}
SHOES = {"shoes"}
ACCESSORIES = {
    "accessory", "hat", "sunglasses", "glasses", "necklace", "watch", "bracelet", "ring",
    "earrings", "scarf", "gloves", "belt", "bag", "tie",
}
MAX_ACCESSORIES = 3

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


OCCASIONS = tuple(models.OCCASIONS)
# Occasions that sit next to each other in how dressy they are
_NEAR_OCCASIONS = {frozenset(("casual", "smart")), frozenset(("smart", "formal"))}


def _occasion_score(item, occasion) -> float:
    """Each item is saved with an occasion, so this compares it with the one wanted."""
    if not occasion:
        return 0
    have = getattr(item, "occasion", None) or "casual"
    if have == occasion:
        return 3
    return 1 if frozenset((have, occasion)) in _NEAR_OCCASIONS else -2


STOP_WORDS = {"the", "and", "for", "with", "something", "wear", "want", "need", "outfit", "that", "this",
              "something", "like", "some", "have", "going", "day", "night", "today", "tomorrow", "look"}


def _request_words(request) -> set[str]:
    """The meaningful words in what the user typed, used to match saved descriptions."""
    return {w for w in re.findall(r"[a-z]+", (request or "").lower()) if len(w) >= 3 and w not in STOP_WORDS}


def _text_score(item, words) -> float:
    """A small boost for each word of the user's request found in the item's description."""
    if not words:
        return 0
    text = f"{(getattr(item, 'description', None) or '')} {item.category.replace('_', ' ')}".lower()
    have = set(re.findall(r"[a-z]+", text))
    return min(3, sum(1 for w in words if w in have or w.rstrip("s") in have))


def _temp_score(category, temp) -> float:
    if temp is None:
        return 0
    if category in ("short_sleeve_top", "t_shirt"):
        return 2 if temp >= 22 else (-2 if temp < 16 else 0)
    if category == "singlet":
        return 2 if temp >= 26 else (-3 if temp < 20 else 0)
    if category == "jumper":
        return 2 if temp <= 17 else (-3 if temp >= 24 else 0)
    if category == "coat":
        return 2 if temp <= 12 else (-3 if temp >= 20 else 0)
    if category == "jacket":
        return 1 if temp <= 20 else (-2 if temp >= 28 else 0)
    if category == "vest":
        return 1 if 8 <= temp <= 20 else (-2 if temp >= 26 else 0)
    if category == "scarf":
        return 2 if temp <= 14 else (-4 if temp >= 22 else 0)
    if category == "gloves":
        return 2 if temp <= 10 else (-4 if temp >= 18 else 0)
    if category == "sunglasses":
        return 1 if temp >= 20 else 0
    if category == "hat":
        return 0
    if category == "long_sleeve_top":
        return 2 if temp <= 17 else (-2 if temp >= 26 else 0)
    if category == "shorts":
        return 2 if temp >= 26 else (-3 if temp < 20 else 0)
    if category == "skirt":
        return 1 if temp >= 22 else (-2 if temp < 16 else 0)
    if category in ("pants", "jeans"):
        return 1 if temp <= 22 else (-1 if temp >= 30 else 0)
    return 0


def _score(item, temp, avoid: set[int], prefs=None, words=None) -> float:
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
    score += _text_score(item, words)
    if item.id in avoid:
        score -= 3  # "Regenerate" should give something different if it can
    return score


def _best(items, temp, avoid, prefs=None, words=None):
    return max(items, key=lambda i: _score(i, temp, avoid, prefs, words)) if items else None


def _unmatched(chosen, prefs) -> list[str]:
    """Which of the colour / pattern / season wishes no chosen item satisfies."""
    return [k for k in ("colour", "pattern", "season")
            if prefs.get(k) and not any(getattr(i, k) == prefs[k] for i in chosen)]


def _pick_accessories(accessories, temp, avoid, prefs, words, wet=False):
    """Up to MAX_ACCESSORIES, at most one of each type, and none that suit the weather badly."""
    by_type = {}
    for i in accessories:
        by_type.setdefault(i.category, []).append(i)
    types = list(by_type)
    random.shuffle(types)
    picked = []
    for category in types:
        if len(picked) >= MAX_ACCESSORIES:
            break
        fit = _temp_score(category, temp)
        if fit < 0 or (wet and category == "sunglasses"):
            continue
        if random.random() < (0.6 if fit > 0 else 0.3):
            picked.append(_best(by_type[category], temp, avoid, prefs, words))
    return picked


def _rule_based(items, temp, wet, avoid, prefs=None, words=None):
    prefs = prefs or {}
    tops = [i for i in items if i.category in TOPS]
    bottoms = [i for i in items if i.category in BOTTOMS]
    dresses = [i for i in items if i.category in DRESSES]
    outer = [i for i in items if i.category in OUTERWEAR]
    shoes = [i for i in items if i.category in SHOES]
    accessories = [i for i in items if i.category in ACCESSORIES]

    if prefs or words:
        bases = [[d] for d in dresses] + [[t, b] for t in tops for b in bottoms]
        if len(bases) > 600:
            bases = random.sample(bases, 600)
        if not bases:
            return None

        def base_score(base):
            total = sum(_score(i, temp, avoid, prefs, words) for i in base)
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
        chosen.append(_best(shoes, temp, avoid, prefs, words))
    cold = (temp is not None and temp < 18) or (temp is None and prefs.get("season") == "autumn_winter")
    if outer and (cold or wet):
        chosen.append(_best(outer, temp, avoid, prefs, words))
    chosen.extend(_pick_accessories(accessories, temp, avoid, prefs, words, wet))
    return chosen


def _is_valid(chosen) -> bool:
    """At most one item per slot (accessories: one of each type, up to MAX_ACCESSORIES),
    and a complete base: a dress, or a top and a bottom."""
    counts = [sum(1 for i in chosen if i.category in slot) for slot in SLOT_ORDER]
    if any(c > 1 for c in counts[:-1]):
        return False
    acc = [i.category for i in chosen if i.category in ACCESSORIES]
    if len(acc) > MAX_ACCESSORIES or len(set(acc)) != len(acc):
        return False
    outer, tops, dress, bottoms, _shoes, _acc = counts
    return (dress == 1 and tops == 0 and bottoms == 0) or (dress == 0 and tops == 1 and bottoms == 1)


def _ask_gemini(items, temp, condition, avoid, prefs=None, request=None):
    client = ai_identify._get_client()
    if client is None:
        return None
    from google.genai import types

    shown = items if len(items) <= MAX_ITEMS_SHOWN_TO_AI else random.sample(items, MAX_ITEMS_SHOWN_TO_AI)
    lines = "\n".join(
        f"{i.id}: {i.category}, {i.colour}, {i.pattern}, best in {i.season}, "
        f"{getattr(i, 'occasion', None) or 'casual'}"
        + (f", {i.description}" if getattr(i, "description", None) else "")
        for i in shown
    )
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
    if request:
        # The user's own words. They only describe the outfit wanted; the reply is checked afterwards,
        # and it can only ever be a list of ids from this wardrobe.
        wishes += f'The user asked for: "{request}"\nFollow that request as closely as the wardrobe allows.\n'
    prompt = (
        f"You are a stylist. {setting}\n{wishes}"
        "Choose ONE outfit from this wardrobe. Each line is: id: category, colour, pattern, best season, occasion, description.\n"
        f"{lines}\n\n"
        "Rules:\n"
        "- Either one dress, OR one top plus one bottom (pants, shorts or skirt).\n"
        "- Add one pair of shoes if there are any.\n"
        "- Add outerwear if it is cold or wet.\n"
        "- You may add up to three accessories (each a different type), only ones that suit the weather.\n"
        "- If an occasion is wanted, prefer items whose occasion matches it.\n"
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


def generate(items, temp, condition: str, avoid_ids: set[int], prefs=None, request=None):
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
        ids = _ask_gemini(items, temp, condition, avoid_ids, None if request else prefs, request)
        if ids:
            candidate = list({i: by_id[i] for i in ids if i in by_id}.values())
            if _is_valid(candidate) and {i.id for i in candidate} != avoid_ids:
                chosen = candidate
    except Exception:
        chosen = None  # any AI problem: just use the simple picker below

    if chosen is None:
        chosen = _rule_based(items, temp, wet, avoid_ids, prefs, _request_words(request))
    if not chosen:
        return None

    chosen.sort(key=_group)
    missing = []
    if not any(i.category in SHOES for i in items):
        missing.append("shoes")
    return chosen, missing, _unmatched(chosen, prefs)



# ---------- Style Me: an outfit from a sentence the user typed ----------
COLOUR_WORDS = {
    "black": "black", "white": "white", "grey": "grey", "gray": "grey", "beige": "beige", "cream": "beige",
    "brown": "brown", "red": "red", "orange": "orange", "yellow": "yellow", "green": "green", "blue": "blue",
    "navy": "navy", "purple": "purple", "pink": "pink", "colourful": "multicolour", "colorful": "multicolour",
}
PATTERN_WORDS = {
    "striped": "striped", "stripes": "striped", "stripe": "striped", "checked": "checked", "check": "checked",
    "plaid": "checked", "checkered": "checked", "floral": "floral", "flowers": "floral", "flowery": "floral",
    "spotted": "spotted", "polka": "spotted", "dots": "spotted", "graphic": "graphic", "plain": "solid", "solid": "solid",
}
SMART_WORDS = {"smart", "work", "office", "meeting", "interview", "business", "dinner", "date",
               "dressy", "professional"}
FORMAL_WORDS = {"formal", "wedding", "gala", "ball", "ceremony", "funeral", "elegant", "black-tie", "cocktail"}
SPORTY_WORDS = {"gym", "workout", "sport", "sporty", "run", "running", "training", "active", "athletic", "hike", "hiking"}
CASUAL_WORDS = {"casual", "relaxed", "everyday", "chill", "weekend", "lounge", "comfy"}
# word -> a typical temperature in °C, checked from hottest to coldest
TEMP_WORDS = [
    ({"hot", "scorching", "heatwave", "boiling"}, 32),
    ({"warm", "summer", "sunny", "beach"}, 26),
    ({"mild"}, 20),
    ({"cool", "chilly", "fresh", "autumn", "fall"}, 13),
    ({"cold", "freezing", "winter", "snow", "snowy", "frosty"}, 6),
]
WARM_SEASON_WORDS = {"hot", "warm", "summer", "spring", "sunny", "beach"}
COOL_SEASON_WORDS = {"cold", "cool", "chilly", "freezing", "winter", "autumn", "fall", "snow", "snowy", "frosty"}
WET_TEXT_WORDS = {"rain", "rainy", "raining", "wet", "drizzle", "storm", "stormy", "snow", "snowy"}


def read_request(text: str):
    """Pulls simple wishes out of a sentence. Used when Gemini isn't available, and to
    guess the weather the person has in mind. Returns (temp, condition, prefs)."""
    import re
    words = re.findall(r"[a-z]+", (text or "").lower())
    wordset = set(words)

    temp = next((t for group, t in TEMP_WORDS if wordset & group), None)
    condition = "Rain" if wordset & WET_TEXT_WORDS else ""
    prefs = {
        "colour": next((COLOUR_WORDS[w] for w in words if w in COLOUR_WORDS), None),
        "pattern": next((PATTERN_WORDS[w] for w in words if w in PATTERN_WORDS), None),
        "season": ("spring_summer" if wordset & WARM_SEASON_WORDS
                   else "autumn_winter" if wordset & COOL_SEASON_WORDS else None),
        "occasion": ("formal" if wordset & FORMAL_WORDS else "smart" if wordset & SMART_WORDS
                     else "sporty" if wordset & SPORTY_WORDS
                     else "casual" if wordset & CASUAL_WORDS else None),
    }
    return temp, condition, {k: v for k, v in prefs.items() if v}


def generate_from_text(items, text: str, avoid_ids: set[int]):
    """Same return value as generate(). Gemini reads the sentence; without it, read_request() does."""
    temp, condition, prefs = read_request(text)
    return generate(items, temp, condition, avoid_ids, prefs, request=text)
