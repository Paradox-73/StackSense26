"""Deterministic reader for a free-text project description: pulls out the answers that can be found with
patterns (numbers, money, skills, regions, compliance words, app-type keywords).

It never guesses: every value it returns comes with the exact words of the brief that it was read from,
and every value is one the questionnaire accepts (see engine/profile.py and data/questions.json).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .kb import field_specs, load_kb
from .profile import INR_PER_USD

# Monthly users to daily users: a planning heuristic. Typical products see 10-25% of their monthly users on
# a given day (daily-to-monthly "stickiness"); the middle of that range is used.
DAU_PER_MAU = 0.2
WEEKS_PER_MONTH = 52 / 12
# "an app for 5,000 students" names the whole audience, not the people who visit on one day. It is read like a
# monthly user count: DAU_PER_MAU of them are taken as daily users, and the note says so.
AUDIENCE_NOUNS = r"(?:users?|customers?|students?|people|members?|shoppers?|patients?|clients?|employees?|players?|riders?|drivers?)"


@dataclass
class Hit:
    """One value found in the text and the exact words it was read from."""
    value: object
    quotes: list[str] = field(default_factory=list)
    note: str | None = None  # an assumption made while reading, shown beside the quote


def _flags(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.I)


# ------------------------------------------------------------------ numbers

NUM = r"(?<![\w.,])(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>k|m|thousand|million|lakhs?|crores?)?(?![a-z])"
UNIT = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "lakh": 1e5, "lakhs": 1e5, "crore": 1e7, "crores": 1e7}
WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
            "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "dozen": 12, "fifteen": 15, "twenty": 20}
NUMW = r"(?P<n>\d{1,4}|(?:a\s+)?(?:" + "|".join(WORD_NUM) + r"))"
USERS = (r"(?:users?|visitors?|customers?|students?|people|members?|players?|riders?|shoppers?|patients?|"
         r"drivers?|employees?|clients?|devices?|sessions?)")
DAY = r"(?:per\s+day|a\s+day|each\s+day|every\s+day|daily|/\s*day)"
MONTH = r"(?:per\s+month|a\s+month|each\s+month|monthly|/\s*month)"


def _number(m: re.Match) -> float:
    """The numeric value of a NUM match, with k / lakh / million suffixes applied."""
    value = float(m.group("num").replace(",", "").rstrip("."))
    return value * UNIT.get((m.group("unit") or "").lower(), 1)


def _scaled_note(total: float, dau: int, what: str) -> str:
    return (f"{what} of {total:,.0f} read as {DAU_PER_MAU:.0%} active on a given day: {dau:,} daily users "
            f"(assumption; edit the daily users answer if you know the real number)")


def read_daily_users(text: str) -> dict[str, Hit]:
    """Daily users from '20,000 students visit per day', '5k DAU', monthly users scaled by DAU_PER_MAU, or an
    audience size ('an app for 5,000 students') scaled the same way."""
    daily = [
        _flags(NUM + r"\s*(?:[a-z-]+\s+){0,3}?" + USERS + r"(?:\s+[a-z]+){0,3}?\s*" + DAY),
        _flags(NUM + r"\s*(?:dau\b|daily\s+(?:active\s+)?" + USERS + ")"),
        _flags(r"(?:dau|daily\s+(?:active\s+)?users?)(?:\s+(?:of|is|are|around|about|roughly|:|=|~))*\s*" + NUM),
    ]
    for rx in daily:
        if m := _first(rx, text):
            return {"dau": Hit(round(_number(m)), [m.group(0)])}
    monthly = [
        _flags(NUM + r"\s*(?:[a-z-]+\s+){0,2}?" + USERS + r"\s*" + MONTH),
        _flags(NUM + r"\s*(?:mau\b|monthly\s+(?:active\s+)?" + USERS + ")"),
        _flags(r"(?:mau|monthly\s+(?:active\s+)?users?)(?:\s+(?:of|is|are|around|about|roughly|:|=|~))*\s*" + NUM),
    ]
    for rx in monthly:
        if m := _first(rx, text):
            dau = max(1, round(_number(m) * DAU_PER_MAU))
            return {"dau": Hit(dau, [m.group(0)], _scaled_note(_number(m), dau, "monthly users"))}
    if m := _staff(text):
        # Staff of an internal tool use it on working days, so the head count is taken as the daily users.
        return {"dau": Hit(round(_number(m)), [m.group(0)],
                           "staff counted as daily users (an internal tool is used on working days; edit the answer if "
                           "only some staff use it each day)")}
    audience = _flags(r"\bfor\s+(?:about\s+|around\s+|roughly\s+|approximately\s+|approx\.?\s+|up\s+to\s+|nearly\s+|~)?"
                      + NUM + r"\s*(?:[a-z-]+\s+){0,2}?" + AUDIENCE_NOUNS + r"\b")
    if m := _first(audience, text):
        dau = max(1, round(_number(m) * DAU_PER_MAU))
        return {"dau": Hit(dau, [m.group(0)], _scaled_note(_number(m), dau, "an audience"))}
    if m := _devices(text):
        # A device fleet counts devices, each active every day (the daily-users question says "or active devices").
        return {"dau": Hit(round(_number(m)), [m.group(0)], "each device counted as active every day")}
    orders = _flags(NUM + r"\s*(?:[a-z-]+\s+){0,1}?(?:orders?|bookings?|transactions?|rides?|deliveries|tickets?)\s*" + DAY)
    if m := orders.search(text):
        return {"dau": Hit(round(_number(m)), [m.group(0)],
                           "each order read as one active user that day (assumption; edit the daily users answer if "
                           "people place several a day)")}
    # An audience without "for": "2 lakh students", "10000 users", "40,000 employees".
    bare = _flags(NUM + r"\s*(?:[a-z-]+\s+){0,2}?" + AUDIENCE_NOUNS + r"\b(?!\s+(?:per|a|each|every)\s+(?:day|week|month))")
    m = next((m for m in bare.finditer(text) if _number(m) >= BARE_AUDIENCE_MIN and not _concurrency_words(text, m)
              and not _flags(r"(?:we\s+are|we(?:'|’)re|we\s+r|team\s+of|just|only)\s*$").search(text[:m.start()])), None)
    if m:
        dau = max(1, round(_number(m) * DAU_PER_MAU))
        return {"dau": Hit(dau, [m.group(0)], _scaled_note(_number(m), dau, "an audience"))}
    return {}


INTERNAL_WORDS = _flags(r"\b(?:internal|back-?office|intranet|admin\s+panel)\b")


def _staff(text: str) -> re.Match | None:
    """'800 staff users' (any brief) or '50 employees' (in a brief that calls the app internal): the people are the daily users."""
    rx = _flags(NUM + r"\s*(?:[a-z-]+\s+){0,1}?(?P<noun>staff|employees|workers|agents|operators|clerks)\b(?:\s+(?:users|members|accounts))?")
    return next((m for m in rx.finditer(text) if (m.group("noun").lower() == "staff" or INTERNAL_WORDS.search(text))
                 and not _concurrency_words(text, m)), None)


# A bare count below this ("3 students", "4 people") is more likely the team than the audience.
BARE_AUDIENCE_MIN = 50
# "meters" alone is also a distance and "machines" the servers, so a meter needs a kind ("smart meters"). Device
# words count a fleet only in a brief about connected devices, and only from DEVICE_MIN up ("2 gateways" is setup).
DEVICES = _flags(NUM + r"\s*(?:[a-z-]+\s+){0,2}?(?:devices|sensors|trackers|vehicles|trucks|buses|gateways|"
                 r"(?:smart|energy|electricity|power|water|gas|utility)\s+meters)\b")
IOT_CONTEXT = _flags(r"\biot\b|telemetry|\bsensors?\b|\breadings?\b|\breport(?:s|ing)?\s+(?:\w+\s+){0,2}?every\b|\bsmart\s+meters?\b|"
                     r"\bfleets?\b|\bconnected\s+(?:devices|vehicles|cars)\b|\btrackers?\b|\bgps\s+(?:every|pings?|reports?|data)\b")
DEVICE_MIN = 10


def _devices(text: str) -> re.Match | None:
    """The first device-fleet count in a brief about connected devices."""
    if not IOT_CONTEXT.search(text):
        return None
    return next((m for m in DEVICES.finditer(text) if _number(m) >= DEVICE_MIN and not _concurrency_words(text, m)), None)


def read_device_rate(text: str) -> dict[str, Hit]:
    """Peak requests per second from a device fleet and its reporting interval: '5000 meters reporting every 15
    seconds' is 5000 / 15 = 333 requests a second."""
    m = _devices(text)
    if not m:
        return {}
    rest = re.split(r"[.;!?\n]", text[m.end():])[0]
    every = _flags(r"\bevery\s+(?P<n>\d+(?:\.\d+)?)?\s*(?P<u>seconds?|secs?|s|minutes?|mins?)\b").search(rest)
    if not every:
        return {}
    n = float(every.group("n") or 1)
    secs = n * (60 if every.group("u").lower().startswith("m") else 1)
    rps = round(_number(m) / secs, 1)
    return {"peak_rps": Hit(int(rps) if rps.is_integer() else rps, [m.group(0), every.group(0)],
                            f"{_number(m):,.0f} devices each sending one reading every {secs:g} s")}


# Users online at the same moment are not an audience and not daily users: "10,000 concurrent players" is read as
# peak concurrency (a separate question), never scaled into a daily-user count.
CONCURRENT = r"(?:concurrent(?:ly)?|simultaneous(?:ly)?|online\s+at\s+(?:once|the\s+same\s+time)|at\s+(?:once|the\s+same\s+time)|connected\s+at\s+once)"
CONNECTIONS = r"(?:(?:open|live|persistent|websocket|socket)\s+)+connections|open\s+websockets?|websocket\s+connections"
# A spike counted in another unit ("spikes to 5000 requests per second", "budget spikes to 2000 rupees") is not users.
SPIKE_NOT_USERS = (r"(?!\d|[.,]\d)(?!\s*(?:requests?|reqs?|rps|queries|calls|events|messages|orders|rupees?|rs\b|inr|usd|dollars?|bucks|"
                   r"%|percent|gb|tb|mb|ms\b|seconds?|minutes?|per\b|/))")


def _concurrency_words(text: str, m: re.Match) -> bool:
    """True when a user count found by `m` is a count of users online at once."""
    return bool(_flags(CONCURRENT).search(m.group(0)) or _flags(r"^\s*(?:\w+\s+){0,2}?" + CONCURRENT).match(text[m.end():]))


def _first(rx: re.Pattern, text: str) -> re.Match | None:
    """The first match of a user-count pattern that does not count users online at the same moment."""
    return next((m for m in rx.finditer(text) if not _concurrency_words(text, m)), None)


def read_concurrency(text: str) -> dict[str, Hit]:
    """Users connected at the same moment from '10,000 concurrent players', '5k users online at once' or '10k open
    WebSockets'. A stated spike ('spikes to 50k') in the same sentence is the peak."""
    patterns = [
        _flags(NUM + r"\s*(?:[a-z-]+\s+){0,1}?" + CONCURRENT + r"\s+(?:[a-z-]+\s+){0,1}?" + USERS),
        _flags(NUM + r"\s*(?:[a-z-]+\s+){0,2}?" + USERS + r"\s+(?:\w+\s+){0,2}?" + CONCURRENT),
        _flags(r"\b(?:concurrent|simultaneous)\s+(?:users|connections|players)(?:\s+(?:of|is|are|around|about|:|~))*\s*" + NUM),
        _flags(NUM + r"\s*(?:" + CONNECTIONS + r")"),
    ]
    for rx in patterns:
        if m := rx.search(text):
            value, quotes, note = _number(m), [m.group(0)], None
            rest = re.split(r"[.;!?\n]", text[m.end():])[0]
            if s := _flags(r"\b(?:spikes?|spiking|peaks?|peaking|bursts?|surges?)\s+(?:up\s+)?to\s+" + NUM + SPIKE_NOT_USERS).search(rest):
                if _number(s) > value:
                    note = f"planned for the spike of {_number(s):,.0f}, not the usual {value:,.0f}"
                    value = _number(s)
                    quotes.append(s.group(0))
            return {"peak_concurrent": Hit(round(value), quotes, note)}
    return {}


def read_team_size(text: str) -> dict[str, Hit]:
    """Team size from 'team of 4', 'three of us', '2 developers' or 'solo'."""
    patterns = [
        _flags(r"\bteam\s+of\s+" + NUMW + r"\b"),
        _flags(r"\b" + NUMW + r"[- ]?(?:person|people|member|developer|dev)\s+team\b"),
        _flags(r"\b" + NUMW + r"\s+of\s+us\b"),
        _flags(r"\b" + NUMW + r"\s+(?:[a-z+#.]+\s+){0,2}?(?:developers?|devs?|engineers?|programmers?|team-?mates?|co-?founders?|founders?|coders?)\b"),
    ]
    patterns += [
        _flags(r"\bwe(?:\s+are|(?:'|’)re|\s+r)\s+(?:just\s+|only\s+)?" + NUMW + r"\s+(?:\w+\s+)?(?:students?|friends|frnds|people|members|undergrads?|"
               r"classmates|developers?|devs?|engineers?|founders?|co-?founders?|of\s+us)\b"),
        _flags(r"\b" + NUMW + r"\s+(?:\w+\s+)?(?:students?|friends|classmates|undergrads?)\s+(?:who\s+are\s+)?"
               r"(?:building|making|creating|developing|working|launching|starting)\b"),
    ]
    for rx in patterns:
        for m in rx.finditer(text):
            n = re.sub(r"^a\s+", "", m.group("n").lower())
            value = WORD_NUM.get(n) or int(n)
            if value >= 1:
                return {"team_size": Hit(value, [m.group(0)])}
    if m := _flags(r"\b(?:solo|just\s+me|only\s+me|by\s+myself|on\s+my\s+own|single\s+developer|"
                   r"sole\s+developer|one-person|one\s+man)\b").search(text):
        return {"team_size": Hit(1, [m.group(0)])}
    return {}


# ------------------------------------------------------------------ money

CURRENCY_WORDS = {"₹": "INR", "rs": "INR", "inr": "INR", "rupee": "INR", "rupees": "INR",
                  "$": "USD", "us$": "USD", "usd": "USD", "dollar": "USD", "dollars": "USD", "bucks": "USD"}
PERIOD = {"year": 1 / 12, "yr": 1 / 12, "annum": 1 / 12, "yearly": 1 / 12, "annual": 1 / 12, "annually": 1 / 12,
          "week": WEEKS_PER_MONTH, "weekly": WEEKS_PER_MONTH, "day": 30.0, "daily": 30.0, "month": 1.0, "monthly": 1.0, "mo": 1.0}
BUDGET_CONTEXT = _flags(r"budget|spend|afford|cost|pay|hosting|infra|cap\b|limit|up\s+to|at\s+most|max|gives?\s+us|allocat|fund|grant|credits?")
NOT_A_BUDGET = _flags(r"\s*(?:per|a|each|/)\s*(?:user|seat|transaction|request|gb|order|device|ticket)\b")
ZERO_BUDGET = _flags(
    r"\b(?:zero|no|nil)\s+(?:\w+\s+){0,2}?(?:budget|money|funds?)\b|\bbudget\s+(?:of|is|:)?\s*(?:basically\s+|practically\s+|almost\s+|pretty\s+much\s+|next\s+to\s+)?(?:zero|nil|nothing)\b|"
    r"\bfree[- ]tiers?\s+(?:only|please)\b|\b(?:on|using|within)\s+(?:a|the)\s+free[- ]tiers?\b|\bonly\s+(?:the\s+)?free\s+tiers?\b|\b(?:completely|totally|entirely)\s+free\b|"
    r"\bmust\s+be\s+free\b|\b(?:can(?:'|’)?t|cannot)\s+(?:afford|pay)\b")
MONEY = [
    _flags(r"(?<![\w])(?P<cur>₹|rs\.?|inr|us\$|usd|\$)\s*" + NUM),
    _flags(NUM + r"\s*(?P<cur>rupees?|rs\b\.?|inr|usd|dollars?|bucks)"),
]


PERIOD_WORDS = r"(?:year|yr|annum|week|day|month|mo|yearly|annually|annual|monthly|weekly|daily)"
PERIOD_TAIL = _flags(r"^[\s,()]*(?:(?:per|a|an|each|every|/)\s*)?(" + PERIOD_WORDS + r")\b")


def read_budget(text: str) -> dict[str, Hit]:
    """Monthly budget and its currency from '₹5,000 a month', '$25/month', '1 lakh rupees monthly' or 'zero budget'.

    An amount counts only when a period follows it ('a month', 'per year': converted to a monthly figure) or the
    words around it talk about a budget. 'Per user' and similar prices are skipped."""
    for rx in MONEY:
        for m in rx.finditer(text):
            after, before = text[m.end():], text[max(0, m.start() - 40):m.start()]
            if NOT_A_BUDGET.match(after):
                continue
            tail = PERIOD_TAIL.match(after)
            if not tail and not BUDGET_CONTEXT.search(before + after[:30]):
                continue
            factor = PERIOD[tail.group(1).lower()] if tail else 1.0
            amount = round(_number(m) * factor, 2)
            quote = text[m.start():m.end() + (tail.end() if tail else 0)].strip()
            cur = CURRENCY_WORDS[m.group("cur").lower().rstrip(".")]
            return {"budget_monthly": Hit(int(amount) if amount.is_integer() else amount, [quote]),
                    "currency": Hit(cur, [quote])}
    if m := ZERO_BUDGET.search(text):
        return {"budget_monthly": Hit(0, [m.group(0)])}
    return {}


def usd_note(amount: float, currency: str) -> str | None:
    """A note giving the dollar equivalent of a rupee budget, at the engine's fixed planning rate."""
    if currency != "INR" or not amount:
        return None
    return f"about ${amount / INR_PER_USD:,.0f} a month at the engine's fixed planning rate of {INR_PER_USD:.0f} INR = 1 USD"


# ------------------------------------------------------------------ skills

NOT_SKILLS = {"data_engineering", "devops", "functional", "git", "markdown", "nosql", "serverless", "render", "cypher", "go",
              "r", "c", "other_language"}
SKILL_ALIASES = {
    "javascript": ["javascript", "js"], "node": ["node.js", "nodejs", "node"], "nextjs": ["next.js", "nextjs", "next js"],
    "react": ["react", "react.js", "reactjs"], "react_native": ["react native"], "vue": ["vue", "vue.js", "vuejs"],
    "nuxt": ["nuxt", "nuxt.js"], "svelte": ["svelte"], "sveltekit": ["sveltekit"], "csharp": ["c#", "c sharp", ".net", "asp.net"],
    "dotnet": ["dotnet"], "postgres": ["postgresql", "postgres"], "mongodb": ["mongodb", "mongo"], "gcp": ["gcp", "google cloud"],
    "aws": ["aws", "amazon web services"], "azure": ["azure"], "flyio": ["fly.io", "flyio"], "rails": ["ruby on rails", "rails"],
    "spring": ["spring boot", "spring"], "nestjs": ["nestjs", "nest.js"], "cpp": ["c++"], "c++": ["c++"],
    "digitalocean": ["digitalocean", "digital ocean"], "sqlite": ["sqlite"], "firebase": ["firebase"],
    "kubernetes": ["kubernetes", "k8s"], "html": ["html", "html5"], "scylladb": ["scylladb", "scylla"],
}
# Names that are also ordinary words are matched only in their capitalised form.
CASE_SENSITIVE_SKILLS = {"go": [r"\bGo\b(?=\s*(?:,|and\b|/|\)|\.|$|developers?|backend|lang))", r"\bGolang\b"],
                         # one-letter language names: capitalised and followed by a list mark or a language word
                         "r": [r"\bR\b(?=\s*(?:,|and\b|/|\)|\.|$|developers?|programmers?|language|scripts?))"],
                         "c": [r"\bC\b(?=\s*(?:,|and\b|/|\)|\.|$|developers?|programmers?|language))"]}
NEGATION = _flags(r"\b(?:no|not|nobody|none|without|avoid|never|unfamiliar|hate|dislike)\b|n(?:'|’)t\b")


def skill_ids() -> list[str]:
    """Every skill name the engine can match: the questionnaire's options and the skills the KB lists."""
    kb = load_kb()
    ids = {o["value"] for o in field_specs()["team_skills"]["options"]}
    for layer in ("frontend", "backend", "database", "hosting"):
        for item in kb[layer]:
            ids |= set(item.get("skills", [])) | set(item.get("related_skills", []))
    return sorted(ids - NOT_SKILLS)


def _skill_patterns() -> list[tuple[str, re.Pattern]]:
    """(skill id, pattern) pairs, longest alias first so 'React Native' wins over 'React'."""
    pairs: list[tuple[str, str, re.Pattern]] = []
    for sid in skill_ids():
        for alias in dict.fromkeys(SKILL_ALIASES.get(sid, []) + [sid.replace("_", " ")]):
            pairs.append((sid, alias, re.compile(r"(?<![\w.#+])" + re.escape(alias) + r"(?![\w#+]|\.\w)", re.I)))
    for sid, pats in CASE_SENSITIVE_SKILLS.items():
        for p in pats:
            pairs.append((sid, p, re.compile(p)))
    pairs.sort(key=lambda t: -len(t[1]))
    return [(sid, rx) for sid, _, rx in pairs]


# A negation word denies a skill only inside the same clause (a comma, 'and', 'but' or 'while' ends it) and only
# within a few words before it: "no money, flutter devs" keeps Flutter; "nobody here knows Kubernetes" drops it.
CLAUSE_BREAK = re.compile(r"[.;:!?\n,]|\b(?:and|but|while|whereas|though|although|so)\b", re.I)
NEGATION_WORDS = 5
# Identity providers and cloud credits name a product the project will use, not a skill of the team:
# "SSO with Azure AD", "Microsoft Entra", "AWS credits".
NOT_A_SKILL_AFTER = _flags(r"^\s*(?:ad\b|active\s+directory|entra\b|ad\s+b2c|credits?\b|sso\b|single\s+sign)")


def negated(before: str) -> bool:
    """True when the words just before a term, in its own clause, deny it ("no", "not", "don't know", "without")."""
    words = CLAUSE_BREAK.split(before)[-1].split()[-NEGATION_WORDS:]
    return bool(NEGATION.search(" ".join(words)))


# A denial right after the term, in its own clause: "SSO is not needed", "payments aren't required for now".
DENIED_AFTER = _flags(r"^[^.;:!?\n,]{0,25}?(?:\bnot|n(?:'|’)t)\s+(?:\w+\s+)?(?:needed|required|necessary|wanted|planned|in\s+scope)\b|"
                      r"^[^.;:!?\n,]{0,25}?\b(?:unnecessary|out\s+of\s+scope)\b")


def _stated(rx: re.Pattern, text: str) -> re.Match | None:
    """The first match of `rx` that the brief does not deny, before it ("no payments happen in the app") or after it
    ("SSO is not needed")."""
    return next((m for m in rx.finditer(text) if not negated(re.split(r"[.;!?\n]", text[:m.start()])[-1])
                 and not DENIED_AFTER.match(text[m.end():])), None)


def read_skills(text: str) -> dict[str, Hit]:
    """Team skills: the technologies the brief says the team knows, matched on names and aliases from the KB."""
    masked, found, quotes = text, [], []
    for sid, rx in _skill_patterns():
        for m in list(rx.finditer(masked)):
            before = re.split(r"[.;!?\n]", masked[:m.start()])[-1]
            masked = masked[:m.start()] + " " * (m.end() - m.start()) + masked[m.end():]
            if negated(before) or NOT_A_SKILL_AFTER.match(text[m.end():]):
                continue
            if sid not in found:
                found.append(sid)
                quotes.append(text[m.start():m.end()])
    return {"team_skills": Hit(found, quotes)} if found else {}


# ------------------------------------------------------------------ regions, compliance, cloud, deployment

REGIONS = {
    # Cities, states, Indian exams and payment rails, Indian languages and the lakh/crore number words.
    "india": r"\b(?:india|indian|bharat|bengaluru|bangalore|mumbai|delhi|hyderabad|chennai|pune|kolkata|ahmedabad|jaipur|"
             r"karnataka|kerala|tamil\s+nadu|maharashtra|gujarat|rajasthan|uttar\s+pradesh|bihar|west\s+bengal|telangana|"
             r"andhra\s+pradesh|punjab|haryana|odisha|assam|madhya\s+pradesh|goa|tier[- ]?[23]\s+cities|"
             r"jee|neet|upsc|cbse|gst|aadhaar|upi|razorpay|paytm|hindi|kannada|marathi|telugu|malayalam|lakhs?|crores?|rupees?)\b",
    "europe": r"\b(?:europe|european|germany|france|spain|italy|netherlands|sweden|united\s+kingdom|britain)\b|(?-i:\bEU\b|\bUK\b)",
    "north_america": r"\b(?:north\s+america|united\s+states|usa|canada)\b|(?-i:\bUS\b|\bU\.S\.)",
    "southeast_asia": r"\b(?:south-?east\s+asia|singapore|indonesia|vietnam|thailand|malaysia|philippines|asean)\b",
    "global": r"\b(?:global|worldwide|around\s+the\s+world|across\s+the\s+world|all\s+over\s+the\s+world)\b",
}
COMPLIANCE = {
    "gdpr": r"\bgdpr\b", "hipaa": r"\bhipaa\b", "pci_dss": r"\bpci(?:[- ]?dss)?\b", "soc2": r"\bsoc\s?2\b",
    "dpdp": r"\bdpdp\b|digital\s+personal\s+data\s+protection",
    "data_residency_india": r"data\s+(?:must\s+)?(?:stay|remain|reside|be\s+(?:stored|kept))\s+(?:in|within)\s+india|"
                            r"indian\s+data\s+residency|data\s+residency\s+(?:in|within)\s+india|"
                            r"data\s+(?:can(?:'|’)?t|cannot|must\s+not|should\s+not|shouldn(?:'|’)t|may\s+not|never)\s+leave\s+india|"
                            r"(?:hosted|stored|kept)\s+(?:only\s+)?(?:in|within)\s+india|(?:servers?|data)\s+(?:only\s+)?in\s+india\s+only",
    "data_residency_eu": r"data\s+(?:must\s+)?(?:stay|remain|reside|be\s+(?:stored|kept))\s+(?:in|within)\s+(?:the\s+)?(?:eu|europe)\b|"
                         r"eu\s+data\s+residency|data\s+(?:can(?:'|’)?t|cannot|must\s+not|should\s+not|may\s+not|never)\s+leave\s+(?:the\s+)?(?:eu|europe)\b",
}
CLOUDS = {"aws": "aws", "amazon web services": "aws", "gcp": "gcp", "google cloud": "gcp", "azure": "azure"}


def _collect(table: dict[str, str], text: str) -> tuple[list[str], list[str]]:
    """Keys of `table` whose pattern occurs in `text`, with the matched words."""
    keys, quotes = [], []
    for key, pat in table.items():
        if m := _flags(pat).search(text):
            keys.append(key)
            quotes.append(m.group(0))
    return keys, quotes


def read_regions(text: str) -> dict[str, Hit]:
    keys, quotes = _collect(REGIONS, text)
    return {"regions": Hit(keys, quotes)} if keys else {}


def read_compliance(text: str) -> dict[str, Hit]:
    keys, quotes = _collect(COMPLIANCE, text)
    # RBI's 2018 payment-data circular binds payment system providers, so "RBI" means India-only storage only when the
    # app takes payments; a lending or wealth app answers to other RBI rules.
    rbi, pays = _flags(r"\brbi\b").search(text), _stated(_flags(PAYMENTS), text)
    if rbi and pays and "data_residency_india" not in keys:
        keys.append("data_residency_india")
        quotes.append(rbi.group(0))
    return {"compliance": Hit(keys, quotes)} if keys else {}


def read_hosting_words(text: str) -> dict[str, Hit]:
    """Deployment model and preferred cloud provider."""
    out: dict[str, Hit] = {}
    if m := _flags(r"\bon[- ]prem(?:ises?)?\b|\bown\s+(?:servers|hardware|data\s?cent(?:er|re)s?)\b|\bin-house\s+servers\b|\bair-?gapped\b").search(text):
        out["deployment"] = Hit("on_prem", [m.group(0)])
    elif m := _flags(r"\bhybrid\b").search(text):
        out["deployment"] = Hit("hybrid", [m.group(0)])
    lead = r"(?:\bon|\buse|\buses|\busing|\bprefer|\bcredits?\s+(?:on|for|from)|\bdeploy(?:ed)?\s+(?:on|to))\s+"
    clouds = "(" + "|".join(map(re.escape, CLOUDS)) + ")"
    # "log in using Azure AD" names an identity provider, not where the app runs.
    if m := next((m for m in _flags(lead + clouds + r"\b").finditer(text) if not NOT_A_SKILL_AFTER.match(text[m.end():])), None):
        out["cloud_preference"] = Hit(CLOUDS[m.group(1).lower()], [m.group(0)])
    elif m := _flags(r"\b" + clouds + r"\s+(?:shop|house|only)\b|\ball[- ]in\s+(?:on\s+)?" + clouds + r"\b").search(text):
        out["cloud_preference"] = Hit(CLOUDS[next(g for g in m.groups() if g).lower()], [m.group(0)])
    elif m := _flags(r"\b" + clouds + r"\s+(?:startup\s+|promotional\s+|free\s+)?credits?\b").search(text):
        out["cloud_preference"] = Hit(CLOUDS[m.group(1).lower()], [m.group(0)])
    return out


# ------------------------------------------------------------------ requirements stated in words

def read_requirements(text: str) -> dict[str, Hit]:
    """SEO, realtime, offline, consistency, availability, peak load, timeline and lock-in, from plain wording."""
    out: dict[str, Hit] = {}
    seo = r"\bseo\b|search\s+engines?|(?:show(?:s|ing)?\s+up|found|rank(?:ed|s)?|indexed)\s+(?:on|by|in)\s+google|organic\s+(?:search|traffic)|google\s+search"
    if m := _flags(seo).search(text):
        critical = _flags(r"(?:seo|google)\b[^.]{0,40}\b(?:critical|crucial|essential|most\s+important|top\s+priority)").search(text)
        ignored = _flags(r"^[^.]{0,20}\b(?:do(?:es)?\s+not|don(?:'|’)t|doesn(?:'|’)t|never)\s+(?:matter|apply|count)|"
                         r"^[^.]{0,20}\b(?:irrelevant|not\s+needed|not\s+important)").search(text[m.end():])
        # "no SEO", "we don't have SEO needs", "without search engines": a denial a few words before, same clause.
        if ignored or negated(re.split(r"[.;!?\n]", text[:m.start()])[-1]):
            out["seo"] = Hit("none", [text[m.start():m.end() + (ignored.end() if ignored else 0)]])
        else:
            out["seo"] = Hit("critical" if critical else "important", [critical.group(0) if critical else m.group(0)])
    # Not "messaging" alone: "updates through WhatsApp messaging" sends messages, it does not hold connections open.
    if m := _stated(_flags(r"\b(?:real-?time\s+(?:collaboration|editing)|multiplayer|co-?editing|live\s+chat|chat\s+app|chat|in-app\s+messaging)\b"), text):
        out["realtime"] = Hit("core", [m.group(0)])
    elif m := _stated(_flags(r"\breal-?time\b|\blive\s+(?:\w+\s+)?(?:updates?|scores?|tracking|location|dashboard)\b|\bwebsockets?\b|\bupdate[sd]?\s+live\b|\bpush\s+notifications?\b"), text):
        out["realtime"] = Hit("some", [m.group(0)])
    if m := _flags(r"\bworks?\s+offline\b|\boffline[- ](?:first|mode|support|capable)\b|\bwithout\s+(?:an\s+)?internet\b").search(text):
        out["offline"] = Hit(True, [m.group(0)])
    if m := _flags(r"\b(?:never|must\s+not|cannot|can(?:'|’)t)\s+(?:oversell|double[- ]?spend|lose\s+(?:a\s+)?(?:payment|transaction|write))\w*|\bacid\b|\bstrong\s+consistency\b|\bdouble[- ]entry\b").search(text):
        out["consistency"] = Hit("strong", [m.group(0)])
    elif m := _flags(r"\beventual(?:ly)?\s+consisten\w*\s+(?:is\s+)?(?:fine|ok|okay|acceptable)\b").search(text):
        out["consistency"] = Hit("eventual_ok", [m.group(0)])
    if m := _flags(r"(?<![\d.])(99|99\.9|99\.95|99\.99)\s*%").search(text):
        if _flags(r"uptime|availab|sla|nines").search(text):
            out["availability"] = Hit("99.0" if m.group(1) == "99" else m.group(1), [m.group(0).strip()])
    if m := _flags(NUM + r"\s*(?:requests?|reqs?|rps|queries)\s*(?:/|per\s+)\s*(?:s|sec|second)\b").search(text):
        out["peak_rps"] = Hit(_number(m), [m.group(0)])
    if m := _flags(r"\b(?:avoid|no|without|minimi[sz]e|hate)\s+(?:vendor\s+)?lock-?in\b").search(text):
        out["lock_in_tolerance"] = Hit("low", [m.group(0)])
    out.update(read_timeline(text))
    return out


def read_timeline(text: str) -> dict[str, Hit]:
    """Weeks to a first release from '4 weeks', 'in 3 months' or '48 hours'."""
    rx = _flags(r"\b(?:in|within|have|has|need|ready|launch|ship|deliver|deadline|timeline|build|takes?|next|about|around|just|only|over|for|by)\s+(?:about\s+|around\s+)?(?P<n>\d+(?:\.\d+)?)[- ]?(?P<u>weeks?|months?|hours?|days?)\b")
    if m := rx.search(text):
        n, unit = float(m.group("n")), m.group("u").lower()
        weeks = n if unit.startswith("week") else n * WEEKS_PER_MONTH if unit.startswith("month") else n / 7 if unit.startswith("day") else n / 168
        return {"timeline_weeks": Hit(max(1, round(weeks)), [m.group(0)])}
    return {}


# ------------------------------------------------------------------ data, workloads and systems already in place

EXISTING_DBS = {"postgres": r"postgres(?:ql)?", "mysql": r"mysql|mariadb", "mongodb": r"mongo(?:db)?", "redis": r"redis",
                "sqlserver": r"sql\s+server|mssql",
                # "our price oracle" is a blockchain data feed: lowercase "oracle" counts only as "oracle db / database".
                "oracle": r"(?-i:Oracle)|oracle(?=\s+(?:db|database|rdbms)\b)"}
EXISTING_LEAD = (r"(?:\b(?:already|currently)\s+(?:\w+\s+){0,2}?(?:run|runs|running|use|uses|using|have|has|on)\s+(?:a\s+|an\s+|our\s+|the\s+)?"
                 r"|\bexisting\s+|\blegacy\s+|\bkeep\s+(?:using\s+)?(?:our\s+|the\s+)?|\bour\s+(?:own\s+)?|\bstuck\s+(?:on|with)\s+)")


def read_existing_systems(text: str) -> dict[str, Hit]:
    """Databases the company already runs: 'we already run MySQL', 'our existing Oracle database', 'keep our Postgres'."""
    keys, quotes = [], []
    for key, pat in EXISTING_DBS.items():
        m = _flags(EXISTING_LEAD + r"(?:\w+\s+){0,1}?(?:" + pat + r")\b").search(text)
        if m and not negated(re.split(r"[.;!?\n]", text[:m.start()])[-1]):
            keys.append(key)
            quotes.append(m.group(0))
    return {"existing_systems": Hit(keys, quotes)} if keys else {}


WORKLOADS = {
    "media_uploads": r"\b(?:upload(?:s|ing)?|share|sharing|post(?:s|ing)?)\s+(?:\w+\s+){0,3}?(?:photos?|images?|pictures?|pics|files|documents|videos?)\b|"
                     r"\b(?:photo|image|picture|file)\s+uploads?\b",
    "video_on_demand": r"\bvideo[- ]on[- ]demand\b|\bvod\b|\bvideo\s+(?:streaming|courses?|lectures?|lessons|library)\b|"
                       r"\b(?:recorded|pre-?recorded)\s+(?:video|lectures?|classes)\b|\bstream(?:ing)?\s+(?:\w+\s+)?videos?\b",
    "live_video": r"\bvideo\s+(?:calls?|calling|chat|conferenc\w*|consult\w*)\b|\blive\s+(?:video|classes|streams?|streaming|broadcast\w*)\b|\bwebrtc\b",
    # Not "tracking deliveries" alone: an order-status page tracks a delivery without a live map.
    "live_location": r"\blive\s+(?:\w+\s+)?(?:tracking|location)\b|\bgps\s+tracking\b|\breal-?time\s+(?:\w+\s+)?(?:tracking|location)\b|\btrack(?:ing)?\s+(?:riders?|drivers?|vehicles)\b",
    "phone_otp": r"\botp\b|\bphone(?:[- ]number)?\s+(?:login|sign[- ]?in|verification)\b|\bsms\s+(?:login|verification|codes?)\b",
    "user_code": r"\b(?:code\s+execution|online\s+judge|run(?:s|ning)?\s+(?:user|student|submitted|their)\s+code|"
                 r"(?:compile|execute)\s+(?:user|student)\s+(?:code|submissions)|coding\s+(?:platform|contests?|judge))\b",
    "text_search": r"\bfull[- ]text\s+search\b|\bsearch\s+(?:across|over|through)\s+(?:\w+\s+){0,2}?(?:documents|articles|products|listings)\b",
}


def read_workloads(text: str) -> dict[str, Hit]:
    """Special workloads named in the brief: photo uploads, recorded video, live video, live tracking, OTP login,
    running users' code, full-text search."""
    keys, quotes = [], []
    for key, pat in WORKLOADS.items():
        m = _flags(pat).search(text)
        if m and not negated(re.split(r"[.;!?\n]", text[:m.start()])[-1]):
            keys.append(key)
            quotes.append(m.group(0))
    return {"special_workloads": Hit(keys, quotes)} if keys else {}


PAYMENTS = r"\bpayments?\b|\bcheckout\b|\bupi\b|\brazorpay\b|\bstripe\b|\bpaytm\b|\bcashfree\b|\bpay\s+(?:online|by)\b|\bsubscriptions?\s+billing\b"


def read_user_actions(text: str) -> dict[str, Hit]:
    """Payments add 'pay' to what users do. The usual read / sign in / post stay in, as in the questionnaire default."""
    m = _stated(_flags(PAYMENTS), text)
    if not m:
        return {}
    return {"user_actions": Hit(["read", "sign_in", "post", "pay"], [m.group(0)],
                                "payments mentioned, so 'pay' was added to the usual read, sign in and post")}


SIZE = r"(?<![\w.,])(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<u>gb|tb|pb|gigabytes?|terabytes?|petabytes?)\b"
SIZE_GB = {"g": 1, "t": 1000, "p": 1e6}
# "Each user gets 5 GB of storage" is a quota per user, not the data stored.
PER_USER_BEFORE = re.compile(r"\b(?:each|every|per)\s+(?:user|customer|member|account|seat|student)\b[^.;!?\n]{0,25}$", re.I)


def read_data_size(text: str) -> dict[str, Hit]:
    """Data at launch from '2 TB of PDFs', and growth from '50 GB a month'. Memory and per-user figures are skipped."""
    out: dict[str, Hit] = {}
    for m in _flags(SIZE).finditer(text):
        after = text[m.end():]
        if _flags(r"^\s*(?:of\s+)?(?:ram|memory|vram)\b|^\s*(?:per|a|each|/)\s*(?:user|device|seat)\b").match(after) or \
                PER_USER_BEFORE.search(text[:m.start()]):
            continue
        gb = float(m.group("num").replace(",", "")) * SIZE_GB[m.group("u")[0].lower()]
        gb = int(gb) if gb.is_integer() else gb
        tail = PERIOD_TAIL.match(after)
        if tail:  # "10 GB a day" grows the data by 30 x 10 GB a month
            month = round(gb * PERIOD[tail.group(1).lower()], 2)
            out.setdefault("data_growth_gb_month", Hit(int(month) if float(month).is_integer() else month,
                                                       [text[m.start():m.end() + tail.end()].strip()]))
        elif not tail:
            out.setdefault("data_volume_gb", Hit(gb, [m.group(0)]))
    return out


def read_data_traits(text: str) -> dict[str, Hit]:
    """Latency target ('latency < 100ms'), read/write mix ('read-mostly') and data shapes named outright
    ('vector search', 'time-series', 'graph database')."""
    out: dict[str, Hit] = {}
    lat = _flags(r"(?:latency|response\s+times?|p9[59]|respond)[^.;\n]{0,25}?(?:<|≤|<=|under|below|less\s+than|within|of|at\s+most)\s*"
                 r"(?P<n>\d+(?:\.\d+)?)\s*ms\b|(?:<|≤|<=|under|below)\s*(?P<m>\d+(?:\.\d+)?)\s*ms\s+(?:latency|response)")
    if m := lat.search(text):
        out["latency_target_ms"] = Hit(float(m.group("n") or m.group("m")), [m.group(0)])
    if m := _flags(r"\bread[- ](?:mostly|heavy|intensive)\b|\bmostly\s+reads?\b|\bmore\s+reads\s+than\s+writes\b").search(text):
        out["read_write"] = Hit("read_heavy", [m.group(0)])
    elif m := _flags(r"\bwrite[- ](?:heavy|intensive|mostly)\b|\bmostly\s+writes?\b").search(text):
        out["read_write"] = Hit("write_heavy", [m.group(0)])
    shapes = [("time_series", r"\btime[- ]series\b", ["time_series", "relational"], "readings over time are the main data"),
              ("vector", r"\bvector\s+(?:search|database|store)\b|\bembeddings?\b|\bsemantic\s+search\b|\bsimilarity\s+search\b",
               ["relational", "vector"], "records stay the main data; embeddings are added for the search"),
              ("graph", r"\bgraph\s+(?:database|db|queries)\b|\bsocial\s+graph\b|\bknowledge\s+graph\b",
               ["relational", "graph"], "records stay the main data; the graph is added beside them")]
    for _key, pat, value, note in shapes:
        if m := _flags(pat).search(text):
            out["data_shapes"] = Hit(value, [m.group(0)], note)
            break
    return out


def read_tenancy_and_sso(text: str) -> dict[str, Hit]:
    """Customer organisations sharing the app ('multi-tenant', 'a database per customer') and enterprise single
    sign-on ('SSO', 'SAML', 'login with Azure AD / Okta')."""
    out: dict[str, Hit] = {}
    if m := _flags(r"\b(?:separate|own|dedicated|isolated)\s+(?:database|db|schema)s?\s+(?:per|for\s+each)\s+(?:tenant|customer|client)\b|"
                   r"\b(?:database|db|schema)[- ]per[- ](?:tenant|customer|client)\b|"
                   r"\b(?:each|every)\s+(?:tenant|customer|client|company|organi[sz]ation)\s+(?:gets|has|have|with|needs)\s+(?:their|its|a)\s+(?:own|separate|dedicated)\s+(?:database|db|schema)\b").search(text):
        out["tenancy"] = Hit("isolated", [m.group(0)])
    elif m := _flags(r"\bmulti-?tenan(?:t|cy)\b").search(text):  # not "tenants" alone: a rental app has tenants too
        out["tenancy"] = Hit("shared", [m.group(0)], "customers share one database unless you need one each")
    if m := _stated(_flags(r"\bsso\b|\bsaml\b|\bsingle\s+sign[- ]on\b|\bazure\s+ad\b|\bentra\s+id\b|\bokta\b"), text):
        out["enterprise_sso"] = Hit(True, [m.group(0)])
    return out


# ------------------------------------------------------------------ app type and platforms

APP_KEYWORDS = {
    "ecommerce": r"e-?commerce|online\s+(?:store|shop)|storefront|marketplace|checkout|shopping\s+cart|food\s+delivery|delivery\s+app|\bsell(?:s|ing)?\s+(?:products?|tickets?|passes|goods|merch)|product\s+catalog",
    "saas": r"\bsaas\b|multi-?tenant|subscription\s+software|b2b\s+(?:platform|app|software)",
    "realtime_collab": r"collaborat(?:ive|ion)\s+(?:editing|editor|documents?|whiteboard)|real-?time\s+(?:editing|editor)|shared\s+documents?|whiteboard|multiplayer|co-?editing|chat\s+app",
    "content_site": r"\bblog\b|news\s+(?:site|portal)|magazine|documentation\s+site|portfolio|marketing\s+site|\bcms\b|publishing",
    "analytics_dashboard": r"analytics|business\s+intelligence|reporting\s+tool|\bbi\s+tool|data\s+visuali[sz]ation",
    "ml_product": r"machine\s+learning|\bml\b|\bllm\b|\brag\b|chatbot|recommendation\s+engine|computer\s+vision|embeddings|ai-powered",
    "iot_telemetry": r"\biot\b|sensors?|telemetry|smart\s+(?:\w+\s+)?meters?|\bfleets?\b|\bgps\s+(?:every|pings?|reports?|data)\b|"
                     r"\breport(?:s|ing)?\s+(?:\w+\s+){0,2}?every\s+\d+\s*(?:s|secs?|seconds?|minutes?|mins?)\b",
    "fintech": r"fintech|\bbank(?:ing)?\b|lending|\bledger\b|\bwallet\b|neobank|brokerage|\btrading\b|\bloans?\b|payment\s+gateway",
    "healthcare": r"patients?|clinics?|hospitals?|telehealth|telemedicine|\bmedical\b|\behr\b|health\s+records|doctors?",
    "social_network": r"social\s+(?:network|media|app)|followers|news\s?feed|(?:home|activity|social)\s+feed|community\s+platform|user-generated|\bforum\b",
    "internal_tool": r"internal\s+tool|admin\s+panel|back-?office|intranet|inventory\s+management",
    "mobile_first": r"mobile[- ](?:first|app)|\bios\s+and\s+android\b|\bandroid\s+app\b|\bios\s+app\b",
    "prototype": r"prototype|proof\s+of\s+concept|\bpoc\b|hackathon|weekend\s+project|side\s+project|\bdemo\b",
}


def read_app_type(text: str) -> dict[str, Hit]:
    """The app type with the most keyword matches. A tie, or no match, leaves the question open."""
    scored: list[tuple[int, str, list[str]]] = []
    for app, pat in APP_KEYWORDS.items():
        hits = [m.group(0) for m in _flags(pat).finditer(text)]
        if hits:
            scored.append((len(set(h.lower() for h in hits)), app, hits))
    if not scored:
        return {}
    scored.sort(key=lambda t: -t[0])
    # "Mobile-first" names the platform, not the domain: on a tie the domain archetype (e-commerce, fintech...) wins,
    # and the platforms answer still records the mobile apps.
    if len(scored) > 1 and scored[0][0] == scored[1][0] and "mobile_first" in (scored[0][1], scored[1][1]):
        scored = [t for t in scored if t[1] != "mobile_first"]
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return {}
    return {"app_type": Hit(scored[0][1], list(dict.fromkeys(scored[0][2]))[:3])}


def read_platforms(text: str) -> dict[str, Hit]:
    """Client platforms from words such as 'web app', 'iOS', 'Android' or 'mobile app'."""
    keys, quotes = [], []
    web = _flags(r"\bweb(?:\s+(?:app|site|application))?\b|\bwebsite\b|\bbrowser\b|\bsite\b|\bportal\b").search(text)
    ios = _flags(r"\bios\b|\biphone\b").search(text)
    android = _flags(r"\bandroid\b").search(text)
    mobile = _flags(r"\bmobile\s+app|\bmobile[- ]first\b|\bapp\s+store\b").search(text)
    if mobile and not (ios or android):
        ios = android = mobile
    for key, m in (("web", web), ("ios", ios), ("android", android)):
        if m:
            keys.append(key)
            quotes.append(m.group(0))
    return {"platforms": Hit(keys, list(dict.fromkeys(quotes)))} if keys else {}


READERS = [read_daily_users, read_concurrency, read_device_rate, read_team_size, read_budget, read_skills, read_regions,
           read_compliance, read_hosting_words, read_requirements, read_existing_systems, read_workloads, read_user_actions,
           read_data_size, read_data_traits, read_tenancy_and_sso, read_app_type, read_platforms]


def read_all(text: str, only: set[str] | None = None) -> dict[str, Hit]:
    """Run every reader. `only` limits the result to those question keys."""
    out: dict[str, Hit] = {}
    for reader in READERS:
        for key, hit in reader(text).items():
            if only is None or key in only:
                out.setdefault(key, hit)
    return out
