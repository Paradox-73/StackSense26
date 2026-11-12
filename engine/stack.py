"""Stack-level search: combines per-layer candidates and applies compatibility rules."""
from __future__ import annotations

from itertools import product

from .kb import LAYERS
from .scoring import INPUT_LABELS, input_importance, input_points, no_frontend_skill, shape_models

TOP_K = 5

# Stacks whose scores differ by less than this many stack points are treated as tied: the inputs
# that set the weights are planning estimates, so a sub-point gap is noise, and letting it decide
# makes the pick flip back and forth as an unrelated input (e.g. user count) changes.
TIE_MARGIN = 1.0
# Growth path: the engine also works out the recommendation at every scale tier (hobby to hyperscale)
# for the same answers, smallest first, so that the answer does not move back and forth as only the
# user count grows. Two rules use it, both priced at one avoided migration:
#  - going back to a technology a smaller tier already moved away from is avoided when a stack that
#    does not go back scores within RETURN_MARGIN of the top stack;
#  - a technology the path leaves and later comes back to is held through the tiers in between when
#    it stays within RETURN_MARGIN of the top there (a team would otherwise migrate away and back).
# Outside these two cases the recommendation is the top stack (or a tie-break among near-ties); an
# earlier pick is not kept just because it came first.
RETURN_MARGIN = 4.0
# When the earlier pick cannot be held through the tiers in between (it falls more than RETURN_MARGIN
# behind there), the return is avoided as long as a stack that does not go back is within this margin.
FORWARD_MARGIN = 2 * RETURN_MARGIN

# Tie-break preferences, in order. Each is a property of the technologies themselves (not of the
# scale/budget inputs), so the same near-tied stacks resolve the same way at every scale:
#   0. the cloud the user said they prefer (a stated preference beats a sub-point score gap);
#   0b. the architecture the user said they want (serverless, monolith, microservices), for the same reason;
#   1. what the team already knows (no ramp-up): the number of layers whose technology the team lists
#      as a skill. Adjacent skills (TypeScript for a BaaS, SQL for MySQL) are already in the score and
#      move by half a level, the size of the knowledge base's own judgement error, so they do not
#      decide a tie. Then how easy it is to hire for (the same question for a team that listed no skills);
#   2. the user's most important inputs: the answers that put the most weight on what users see and touch
#      (SEO, the app type's interactivity, offline use), heaviest first. The stack whose frontend gives more
#      points through the heaviest answer on which the tied stacks differ wins (a gap under INPUT_STEP stack
#      points does not count). What the user asked for decides before lock-in, which is only a hedge against
#      being wrong;
#   3. lower vendor lock-in: a tie means the evidence does not separate the options, so prefer the
#      one that is cheaper to walk away from if the estimate turns out wrong (skipped when the user
#      said lock-in tolerance is high).
# Past these, the higher score wins. General quality (maturity, speed, ops) is already weighted in
# every layer's score, so it is not counted a second time to let a lower-scoring stack win a tie.
# Inputs that state a requirement the stack must meet (not a preference). A layer whose score carries
# a penalty from one of them that the user stated (not left at its default) misses that requirement
# (e.g. a single-node database under a stated 99.9% availability target, a client-rendered page where
# SEO is critical, a store that fits the stated data shape poorly). A penalty marked "binding" counts
# even when its input was left at the default: the stack is priced without meeting that default.
TARGET_INPUTS = frozenset({"availability", "latency_target_ms", "seo", "offline", "realtime", "compliance",
                           "data_shapes", "data_volume_gb", "consistency"})
# Skill fit of a technology the team lists directly (4.5 for one matching skill, 5 for two or more).
KNOWN_SKILL_FIT = 4.5
TIE_BREAKERS = (
    # layers that get the stated cloud-preference bonus
    ("your preferred cloud", "cloud_pref", 1),
    # layers that run on a cloud the team lists as a skill (AWS, GCP, Azure): before the hiring pool, since
    # the people you already have know that cloud
    ("your team's cloud", "cloud_skill", 1),
    # layers that get the stated architecture's bonus (serverless, monolith ...)
    ("your stated architecture", "arch_pref", 1),
    # layers whose technology the team already uses, more wins
    ("team skill match", "skill_fit", 1),
    # sum of per-layer hiring-pool scores (1-5): decides when no skills are listed
    ("hiring pool", "hiring", 1),
    # answer by answer, heaviest first: stacks INPUT_STEP or more behind drop out (pick_tied)
    ("your most important inputs", "inputs", 1),
    # sum of per-layer lock-in (1-5), lower wins
    ("lower vendor lock-in", "lock_in", -1),
    # sum of per-layer skill-fit scores (1-5), higher wins
    ("adjacent team skills", "skill_sum", 1),
)


CLOUD_SKILLS = frozenset(("aws", "gcp", "azure"))
TIE_ORDER_TEXT = "the tie-break order (" + ", then ".join(label for label, _, _ in TIE_BREAKERS) + ")"


# Smallest gap, in stack points, on one answer that counts as a difference for the "most important
# inputs" tie-break: the tie margin itself, so a gap inside it on one answer is noise there too.
INPUT_STEP = 1.0


def _input_sums(combo: dict) -> tuple[list[str], dict[str, float]]:
    """(answers heaviest first, stack points each gives this stack): layer points summed over the four layers
    and divided by four, like the stack score."""
    hit = combo.get("_inputs")
    if hit is None:
        picks = list(combo["picks"].values())
        if not all("_ctx" in c for c in picks):
            hit = ([], {})
        else:
            sums: dict[str, float] = {}
            for c in picks:
                for inp, v in input_points(c).items():
                    sums[inp] = sums.get(inp, 0.0) + v / len(picks)
            hit = (input_importance(picks[0]["_ctx"][0]), sums)
        combo["_inputs"] = hit
    return hit


def _tb_value(combo: dict, attr: str) -> float:
    tot = 0.0
    for c in combo["picks"].values():
        if attr == "lock_in":
            if combo.get("lock_in_ok"):
                return 0.0  # the user accepts lock-in: it is not a reason to prefer one tied stack
            tot += c["item"].get("lock_in", 1)
        elif attr == "hiring" and not combo.get("no_skills"):
            if combo.get("no_fe_skills"):
                # The team listed skills but none for any web frontend: it hires for the frontend, so that
                # layer's hiring pool decides, as every layer's does when no skills are listed.
                return float(combo["picks"]["frontend"]["item"].get("scores", {}).get("hiring", 3))
            return 0.0  # the team listed skills: skill match already speaks for the people you have
        elif attr == "skill_fit":
            tot += c["raw"].get("skill_fit", 3.0) >= KNOWN_SKILL_FIT
        elif attr == "skill_sum":
            tot += c["raw"].get("skill_fit", 3.0)
        elif attr == "cloud_skill":
            tot += (c["item"].get("cloud") or c["item"].get("provider")) in combo.get("cloud_skills", ())
        elif attr == "cloud_pref":
            # A layer the stack does without (no server code, no database) puts nothing off the preferred cloud,
            # so a static site is not out-voted by a stack that adds a database on that cloud.
            picks = combo["picks"]
            static = picks["backend"]["item"].get("kind") == "none" and picks["database"]["item"].get("static_only")
            absent = static and (c["item"].get("kind") == "none" or (c["item"].get("static_only") and not c["item"].get("provider")))
            tot += absent or any(a["input"] == "cloud_preference" and a["delta"] > 0 for a in c.get("adjustments", []))
        elif attr == "arch_pref":
            tot += any(a["input"] == "architecture" and a["delta"] > 0 for a in c.get("adjustments", []))
        else:
            tot += c["raw"].get(attr, c["item"].get("scores", {}).get(attr, 3))
    return round(tot, 2)


def target_misses(combo: dict) -> int:
    """Layers whose score carries a penalty from a requirement the user stated (TARGET_INPUTS). A penalty marked
    "preference" weighs an answer without being a requirement the layer fails (server rendering nobody asked for)."""
    n = combo.get("_misses")
    if n is None:  # fixed for a stack once it is built; the growth path asks again at every repair
        skip = combo.get("defaulted", ())
        n = combo["_misses"] = sum(any(a["input"] in TARGET_INPUTS and (a["input"] not in skip or a.get("binding"))
                                           and a["delta"] < 0 and not a.get("preference")
                                       for a in c.get("adjustments", []))
                                   for c in combo["picks"].values())
    return n


_INPUTS_AT = next(k for k, (_, attr, _) in enumerate(TIE_BREAKERS) if attr == "inputs")


def tie_key(combo: dict) -> tuple:
    """TIE_BREAKERS values, larger is better. The "inputs" entry is a constant 0 here: a gap under
    INPUT_STEP does not count, which is not an order on single stacks, so pick_tied() applies it to the set."""
    key = combo.get("_tie_key")
    if key is None:
        key = combo["_tie_key"] = tuple(0.0 if attr == "inputs" else sign * _tb_value(combo, attr)
                                        for _, attr, sign in TIE_BREAKERS)
    return key


def pick_tied(tied: list[dict], lead=lambda c: ()) -> dict:
    """The winner among tied stacks: the best `lead(c)` (rankings that come before TIE_BREAKERS), then
    TIE_BREAKERS in order, then the higher score. For "your most important inputs" every stack more than
    INPUT_STEP stack points behind the best one on an answer is dropped, answer by answer, heaviest first."""
    head = lambda c: lead(c) + tie_key(c)[:_INPUTS_AT]
    best = max(head(c) for c in tied)
    pool = [c for c in tied if head(c) == best]
    for inp in _input_sums(pool[0])[0]:
        top = max(_input_sums(c)[1].get(inp, 0.0) for c in pool)
        pool = [c for c in pool if top - _input_sums(c)[1].get(inp, 0.0) < INPUT_STEP - 1e-9]
    return max(pool, key=lambda c: (tie_key(c)[_INPUTS_AT + 1:], c["score"]))


def tie_reason(winner: dict, other: dict) -> str | None:
    """First tie-break preference that separates two stacks, as text; None if all are equal."""
    for label, attr, sign in TIE_BREAKERS:
        if attr == "inputs":
            order, sa = _input_sums(winner)
            sb = _input_sums(other)[1]
            inp = next((i for i in order if abs(sa.get(i, 0.0) - sb.get(i, 0.0)) >= INPUT_STEP - 1e-9), None)
            if inp is None:
                continue
            if sa.get(inp, 0.0) < sb.get(inp, 0.0):
                return None
            return (f"{label} ({INPUT_LABELS.get(inp, inp)}: {sa.get(inp, 0.0):.1f} vs {sb.get(inp, 0.0):.1f} "
                    "points, the heaviest answer on which they differ)")
        a, b = _tb_value(winner, attr), _tb_value(other, attr)
        if abs(a - b) > 1e-9:
            if (a - b) * sign > 0:
                unit = {"lock_in": "summed lock-in", "cloud_pref": "layers on it", "cloud_skill": "layers on a cloud the team knows",
                        "arch_pref": "layers that match it",
                        "skill_fit": "layers the team already uses",
                        "skill_sum": "summed skill fit"}.get(attr, "summed across layers")
                if attr == "hiring" and not winner.get("no_skills") and winner.get("no_fe_skills"):
                    unit = "the frontend's, as no frontend skill is listed"
                return f"{label} ({a:g} vs {b:g}, {unit})"
            return None
    return None


def _attrs(combo: dict) -> dict[str, str]:
    """combo: layer -> item dict. Returns matchable attributes."""
    return {
        "frontend": combo["frontend"]["id"],
        "backend": combo["backend"]["id"],
        "database": combo["database"]["id"],
        "hosting": combo["hosting"]["id"],
        "backend_kind": combo["backend"].get("kind", ""),
        "hosting_kind": combo["hosting"].get("kind", ""),
        "hosting_provider": combo["hosting"].get("provider", ""),
    }


def _input_ok(rule: dict, p: dict, d: dict) -> bool:
    for key, vals in rule.get("input", {}).items():
        if key == "team_size_max":
            if p["team_size"] > vals:
                return False
        elif key == "concurrent_min":
            if d.get("peak_concurrent", 0) < vals:
                return False
        elif key == "architecture":
            if d["architecture"] not in vals:
                return False
        elif key == "skills_any":
            # A tooling synergy only pays off for a team that uses that tooling: skip it when the
            # team listed its skills and none of them is on the rule's list.
            if d["skills"] and not (d["skills"] & set(vals)):
                return False
        elif key == "skills_match":
            # A vendor's first-party tooling bundle pays off only for a team that already uses that
            # vendor's tools; with no skills listed nothing ties the team to one cloud.
            if not (d["skills"] & set(vals)):
                return False
        elif key == "skills_none":
            # A tooling synergy for one language does not apply to a team that lists a skill in another
            # server-side language: that team's backend is not written in this one.
            if d["skills"] & set(vals):
                return False
        elif p.get(key) not in vals:
            return False
    return True


def matching_rules(combo: dict, rules: list[dict], p: dict, d: dict) -> list[dict]:
    """Return the compatibility rules (bonuses and penalties for pairings) that apply to this stack."""
    at = _attrs(combo)
    hits = []
    for r in rules:
        if not all(at[k] in v for k, v in r.get("when", {}).items()):
            continue
        if r.get("not") and any(at[k] in v for k, v in r["not"].items()):
            continue
        if not _input_ok(r, p, d):
            continue
        hits.append(r)
    return hits


def combo_score(scores: dict[str, float], rules_hit: list[dict]) -> float:
    """Average layer score, with rule deltas counted as layer points (so +4 = one layer gaining 4 points)."""
    return (sum(scores.values()) + sum(r["delta"] for r in rules_hit)) / len(scores)


ATTR_LAYER = {"frontend": "frontend", "backend": "backend", "database": "database", "hosting": "hosting",
              "backend_kind": "backend", "hosting_kind": "hosting", "hosting_provider": "hosting"}


def _attr(item: dict, key: str) -> str:
    if key in LAYERS:
        return item["id"]
    return item.get("kind" if key.endswith("_kind") else "provider", "")


_PLACEMENTS: dict[tuple, tuple] = {}
_PLACEMENTS_MAX = 4096
_CONDITIONS: dict[int, tuple] = {}
_MATCH: dict[int, tuple] = {}


def _rule_conditions(rules: list[dict]) -> list[tuple]:
    """Each rule's `when` and `not` conditions split by layer: ([(attribute, values)] per layer, same for not)."""
    hit = _CONDITIONS.get(id(rules))
    if hit is not None and hit[0] is rules:
        return hit[1]
    out = []
    for r in rules:
        out.append(tuple(tuple([(k, v) for k, v in (r.get(part) or {}).items() if ATTR_LAYER[k] == l]
                               for l in LAYERS) for part in ("when", "not")))
    _CONDITIONS[id(rules)] = (rules, out)
    return out


def _rule_placements(pools: list[list[dict]], rules: list[dict]) -> list[tuple[int, list[tuple]]]:
    """For each rule, the candidate combinations (index per layer) its `when`/`not` conditions match.
    This depends only on which technologies are in the pools, not on the answers, so it is kept
    between calls; the answer-dependent `input` conditions are checked by the caller."""
    key = (id(rules), tuple(tuple(c["id"] for c in pl) for pl in pools))
    hit = _PLACEMENTS.get(key)
    if hit is not None and hit[0] is rules:
        return hit[1]
    pre = _rule_conditions(rules)
    ok = _MATCH.setdefault(id(rules), (rules, {}))[1]  # (rule, layer, technology) -> (when holds, a `not` holds)
    out = []
    for ri, (when, nots) in enumerate(pre):
        allowed, bad = [], []
        for li, pl in enumerate(pools):
            a_l, b_l = [], set()
            for i, c in enumerate(pl):
                m = ok.get((ri, li, c["id"]))
                if m is None:
                    item = c["item"]
                    m = ok[(ri, li, c["id"])] = (all(_attr(item, k) in v for k, v in when[li]),
                                                 any(_attr(item, k) in v for k, v in nots[li]))
                if m[0]:
                    a_l.append(i)
                if m[1]:
                    b_l.add(i)
            allowed.append(a_l)
            bad.append(b_l)
        if not all(allowed):
            continue
        if any(bad):
            idxs = [idx for idx in product(*allowed) if not any(idx[li] in b_l for li, b_l in enumerate(bad) if b_l)]
        else:
            idxs = list(product(*allowed))
        if idxs:
            out.append((ri, idxs))
    if len(_PLACEMENTS) >= _PLACEMENTS_MAX:
        _PLACEMENTS.clear()
    _PLACEMENTS[key] = (rules, out)
    return out


_HITS: dict[tuple, tuple] = {}
_IDX: dict[tuple, list] = {}


def _all_idx(sizes: tuple) -> list[tuple]:
    hit = _IDX.get(sizes)
    if hit is None:
        hit = _IDX[sizes] = list(product(*(range(k) for k in sizes)))
    return hit


def _hits_for(pools: list[list[dict]], rules: list[dict], placements: list, active: tuple) -> tuple[dict, list | None]:
    """Rule indices, and summed deltas in product order, per candidate combination, for the rules in `active`. Kept
    between calls: many different answers switch on the same rules for the same candidates."""
    key = (id(rules), tuple(tuple(c["id"] for c in pl) for pl in pools), active)
    hit = _HITS.get(key)
    if hit is not None and hit[0] is rules:
        return hit[1], hit[2]
    all_idx = _all_idx(tuple(len(pl) for pl in pools))
    on = set(active)
    hits_by_idx: dict[tuple, list[int]] = {}
    for ri, idxs in placements:
        if ri in on:
            for idx in idxs:
                hits_by_idx.setdefault(idx, []).append(ri)
    if len(_HITS) >= _PLACEMENTS_MAX:
        _HITS.clear()
    flat = [sum(rules[ri]["delta"] for ri in hits_by_idx[idx]) if idx in hits_by_idx else 0
            for idx in all_idx] if hits_by_idx else None  # None: no rule applies
    _HITS[key] = (rules, hits_by_idx, flat)
    return hits_by_idx, flat


_RANKED: dict[tuple, list] = {}
_RANKED_MAX = 2048


def _ranked(pools: list[list[dict]], rules: list[dict], placements: list, active: tuple,
            window: float | None) -> list[tuple]:
    """(score, index per layer) for the candidate combinations, in itertools.product order. With a
    window only the combinations within it of the top score are kept, and the result is remembered:
    the same candidate scores with the same rules switched on give the same list."""
    key = None
    if window is not None:
        key = (id(rules), window, active, tuple(tuple((c["id"], c["score"]) for c in pl) for pl in pools))
        hit = _RANKED.get(key)
        if hit is not None and hit[0] is rules:
            return hit[1]
    flat = _hits_for(pools, rules, placements, active)[1]
    n = len(LAYERS)
    ps = [[c["score"] for c in pl] for pl in pools]
    # Same arithmetic as combo_score (builtin sum of the layer scores, plus builtin sum of the rule
    # deltas), over all combinations in itertools.product order.
    all_idx = _all_idx(tuple(len(pl) for pl in pools))
    s0123 = [sum((ps[0][i], ps[1][j], ps[2][k], ps[3][m])) for i, j, k, m in all_idx]
    totals = [t + dl for t, dl in zip(s0123, flat)] if flat else s0123
    if window is None:
        scored = [(round(t / n, 2), all_idx[i]) for i, t in enumerate(totals)]
    elif totals:
        # Rounding to 2 places moves a score by at most 0.005, so test the unrounded total first.
        floor = (max(totals) / n - window - 0.01) * n
        scored = [(round(t / n, 2), all_idx[i]) for i, t in enumerate(totals) if t >= floor]
        top = max(sc for sc, _ in scored)
        scored = [x for x in scored if x[0] >= top - window]
    else:
        scored = []
    if key is not None:
        if len(_RANKED) >= _RANKED_MAX:
            _RANKED.clear()
        _RANKED[key] = (rules, scored)
    return scored


def search(layer_results: dict[str, list[dict]], rules: list[dict], p: dict, d: dict,
           window: float | None = None, widen: dict[str, list[dict]] | None = None) -> list[dict]:
    """Evaluate all combinations of the top-K candidates per layer; return combos sorted by score.

    Rules are matched per layer first (a rule's conditions each name one layer), so each rule only
    visits the combinations it can apply to. Same result as calling matching_rules on every combo.
    With `window`, only the stacks scoring within that many points of the top one are built (the
    rest, in the same order, are simply not returned). `widen` adds candidates (layer -> scored options)
    after the top-K of a layer; the budget guard uses it to look at cheap options the top K left out."""
    pools = [layer_results[l][:TOP_K] + list((widen or {}).get(l, ())) for l in LAYERS]
    placements = _rule_placements(pools, rules)
    active = tuple(ri for ri, _ in placements if _input_ok(rules[ri], p, d))
    hits_by_idx = _hits_for(pools, rules, placements, active)[0]
    no_skills, lock_in_ok, defaulted = not d["skills"], p.get("lock_in_tolerance") == "high", d.get("defaulted", set())
    no_fe = bool(d["skills"]) and no_frontend_skill(frozenset(d["skills"]))
    cloud_skills = frozenset(d["skills"]) & CLOUD_SKILLS
    scored = _ranked(pools, rules, placements, active, window)
    combos = []
    l0, l1, l2, l3 = LAYERS
    p0, p1, p2, p3 = pools
    get_hits = hits_by_idx.get
    for score, idx in scored:
        ri_hits = get_hits(idx)
        combos.append({"picks": {l0: p0[idx[0]], l1: p1[idx[1]], l2: p2[idx[2]], l3: p3[idx[3]]},
                       "rules": [rules[ri] for ri in ri_hits] if ri_hits else [], "score": score,
                       "no_skills": no_skills, "no_fe_skills": no_fe, "lock_in_ok": lock_in_ok, "defaulted": defaulted,
                       "cloud_skills": cloud_skills})
    combos.sort(key=lambda c: -c["score"])
    return combos


def combo_ids(combo: dict) -> tuple:
    """The ids of the picked technologies, one per layer, as a tuple that can be compared and hashed."""
    return tuple(combo["picks"][l]["id"] for l in LAYERS)


FITS_BUDGET = "a minimum bill that fits your budget"
# The tie-break's bill is the bands' floors; when the estimate shown is over the budget, it must not say "fits".
FLOOR_BILL = "a lower minimum bill at the price bands' floors (the estimate for your scale is still over your budget)"


def decided_text(tb: dict) -> str:
    """The tie-break preference that decided, in words true of the estimate shown (tie_break 'shown_over')."""
    return FLOOR_BILL if tb.get("decided_by") == FITS_BUDGET and tb.get("shown_over") else tb["decided_by"]


def _decided_by(winner: dict, top: dict, left: dict | None = None, fit=None) -> str | None:
    if _returns(winner, left) < _returns(top, left):
        return "not switching back to a technology the stack had already moved away from at a smaller scale"
    if fit is not None:
        mw, mt = target_misses(winner), target_misses(top)
        uw, ut = int(not fit(winner)), int(not fit(top))
        if mw + uw < mt + ut:
            if mw < mt:
                return f"meeting more of your stated requirements ({mw} vs {mt} layers short of one)"
            return FITS_BUDGET
    return tie_reason(winner, top)


def _returns(combo: dict, left: dict | None) -> int:
    """Layers on which this stack goes back to a pick the smaller-scale path already moved away from."""
    if not left:
        return 0
    return sum(combo["picks"][l]["id"] in left.get(l, ()) for l in LAYERS)


def _holds(combo: dict, hold: dict | None) -> bool:
    return bool(hold) and all(combo["picks"][l]["id"] == i for l, i in hold.items())


def choose(combos: list[dict], left: dict | None = None, hold: dict | None = None, fits=None,
           forbid: dict | None = None) -> dict | None:
    """Pick the recommended stack from score-sorted combos.

    1. `hold` (layer -> id, from the growth path): the path leaves this technology and comes back to
       it at a larger scale, so the best stack that keeps it is chosen while it scores within
       RETURN_MARGIN of the top.
    2. Otherwise a stack inside TIE_MARGIN of the top score counts as tied with it, and the tied stack
       that does not go back to a pick the smaller-scale path already left (`left`: layer -> ids) wins,
       then the one with the fewest missed requirements, counting a minimum bill over the budget
       (`fits`) as one more, then the TIE_BREAKERS preferences.
    3. If the winner still goes back, the best stack that does not, within RETURN_MARGIN of the top,
       is chosen instead.
    Annotates the winner with 'tie_break' when it is not the single highest-scoring stack."""
    if not combos:
        return None
    top = combos[0]
    held = next((c for c in combos if _holds(c, hold) and not _returns(c, left)
                 and top["score"] - c["score"] < RETURN_MARGIN - 1e-9), None)
    avoided = None
    fit = (lambda c: bool(fits(c))) if fits else (lambda c: True)
    if held is not None:
        tied = [c for c in combos if _holds(c, hold) and not _returns(c, left)
                and held["score"] - c["score"] < TIE_MARGIN - 1e-9]
        winner = pick_tied(tied)
    else:
        tied = [top] + [c for c in combos[1:] if top["score"] - c["score"] < TIE_MARGIN - 1e-9]
        # A missed requirement and a minimum bill over the budget count alike: neither may be traded
        # for the other inside a tie (a cheaper stack that drops the availability target is not cheaper
        # for the same product).
        winner = pick_tied(tied, lambda c: (-_returns(c, left), -(target_misses(c) + (not fit(c)))))
        if _returns(winner, left):
            margin = RETURN_MARGIN
            forward = next((c for c in combos if not _returns(c, left)
                            and top["score"] - c["score"] < RETURN_MARGIN - 1e-9), None)
            if forward is None and _returns(winner, forbid):
                # The growth path could not hold the earlier pick through the tiers in between, so the
                # return itself is avoided over a wider margin.
                margin = FORWARD_MARGIN
                forward = next((c for c in combos if not _returns(c, left)
                                and top["score"] - c["score"] < FORWARD_MARGIN - 1e-9), None)
            if forward is not None:
                avoided = [[l, winner["picks"][l]["name"]] for l in LAYERS if winner["picks"][l]["id"] in left.get(l, ())]
                winner = forward
    winner.pop("tie_break", None)
    if winner is not top:
        winner["tie_break"] = {
            "top_scorer": {l: c["name"] for l, c in top["picks"].items()},
            "top_score": top["score"], "margin": round(top["score"] - winner["score"], 2),
            "decided_by": None if held is not None else _decided_by(winner, top, left, fit if held is None else None),
            "kept_on_growth_path": held is not None,
        }
        if held is not None:
            winner["tie_break"]["held"] = [[l, winner["picks"][l]["name"]] for l in hold]
        if avoided:
            winner["tie_break"]["avoided_return"] = avoided
            winner["tie_break"]["return_margin"] = margin
    return winner


def _weak_db_alternative(cand: dict, pick: dict, d: dict) -> bool:
    """A database is not worth listing as an alternative when it fits the project's data poorly, or when it
    is a specialised store (its best data shape is one the project does not have) that fits the
    project's primary data worse than the pick does."""
    if cand["raw"].get("data_fit", 3) < 3:
        return True
    models = shape_models(cand["item"], d)
    shapes = {d["primary_shape"], *d["secondary_shapes"]}
    specialty = max(models, key=models.get)
    return specialty not in shapes and models[d["primary_shape"]] < shape_models(pick["item"], d)[d["primary_shape"]]


def layer_alternatives(best: dict, layer: str, layer_results: list[dict], rules, p, d, n=2) -> list[dict]:
    """Swap one layer of the best stack for each other candidate and rescore the whole stack."""
    out = []
    for cand in layer_results[:TOP_K]:  # the candidates the stack search saw, so no alternative beats the top stack
        if cand["id"] == best["picks"][layer]["id"]:
            continue
        if layer == "database" and _weak_db_alternative(cand, best["picks"][layer], d):
            continue
        picks = dict(best["picks"])
        picks[layer] = cand
        items = {l: c["item"] for l, c in picks.items()}
        hits = matching_rules(items, rules, p, d)
        sc = combo_score({l: c["score"] for l, c in picks.items()}, hits)
        out.append({"candidate": cand, "stack_score": round(sc, 2), "rules": hits,
                    "delta_vs_pick": round(sc - best["score"], 2)})
    out.sort(key=lambda x: -x["stack_score"])
    return out[:n]
