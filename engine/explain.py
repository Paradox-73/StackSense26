"""Turns scores into human-readable reasons, trade-offs, risks and input attributions."""
from __future__ import annotations

from collections import defaultdict

from .kb import CRITERION_LABELS, relevant_lines
from .scoring import INPUT_LABELS, Weights, shape_models, write_scale
from .stack import TIE_MARGIN, TIE_ORDER_TEXT, tie_reason

# How the paragraphs' closing sentence defines "stack points" (data/explain_templates.json); said once per result.
STACK_POINTS_DEF = " (points of the overall stack score, the average of the four layer scores)"

RULE_LAYER_KEYS = {"frontend": "frontend", "backend": "backend", "backend_kind": "backend",
                   "database": "database", "hosting": "hosting", "hosting_kind": "hosting",
                   "hosting_provider": "hosting"}


def rule_layers(rule: dict) -> set[str]:
    return {RULE_LAYER_KEYS[k] for k in list(rule.get("when", {})) + list(rule.get("not", {})) if k in RULE_LAYER_KEYS}


def _driver_text(w: Weights, crit: str) -> str:
    parts = [(i, a, r) for i, a, r in w.parts.get(crit, []) if i != "baseline" and a > 0]
    parts.sort(key=lambda x: -x[1])
    return "; ".join(r for _, _, r in parts[:2])


def explain_pick(layer: str, pick: dict, layer_scored: list[dict], w: Weights, rules_hit: list[dict],
                 alts: list[dict], best_stack_score: float, skills_given: bool, best: dict | None = None,
                 p: dict | None = None, skills: set | None = None) -> dict:
    stack_ids = {c["id"] for c in best["picks"].values()} if best else {pick["id"]}
    W = sum(b["weight"] for b in pick["breakdown"]) or 1.0
    avg = defaultdict(float)
    for cand in layer_scored:
        for c, v in cand["raw"].items():
            avg[c] += v / len(layer_scored)

    advantages = []
    for b in pick["breakdown"]:
        c, s, wc = b["criterion"], b["score"], b["weight"]
        if wc <= 0:
            continue
        adv = wc * (s - avg[c]) / W * 25
        advantages.append((adv, c, s, wc))
    advantages.sort(reverse=True)
    why = []
    # Skill fit is about the people, not the technology: it is never the headline reason. It is
    # stated last, saying whether the team's skills match directly or only carry over.
    skill_adv = next((a for a, c, _, _ in advantages if c == "skill_fit"), 0.0)
    for adv, c, s, wc in [a for a in advantages if a[1] != "skill_fit"][:3]:
        if adv <= 0.05:
            continue
        drv = _driver_text(w, c)
        why.append(f"{CRITERION_LABELS[c]}: {s:.1f}/5 vs {avg[c]:.1f} average for this layer"
                   + (f" - weighted up because: {drv}." if drv else "."))
    for x in pick["adjustments"]:
        if x["delta"] > 0:
            why.append(f"Bonus +{x['delta']}: {x['reason']}.")
    mine = [r for r in rules_hit if layer in rule_layers(r)]
    for r in mine:
        if r["kind"] == "synergy":
            why.append(f"Stack synergy (+{r['delta']}): {r['note']}")
    skill_line = _skill_text(pick, skills or set()) if skill_adv > 0.05 else None
    if not why:
        # Nothing technical stands out above the layer average: say why it was still chosen instead of listing nothing.
        n = len(layer_scored)
        why.append("The only option that meets all your hard requirements (see Ruled out)." if n <= 1 else
                   f"Chosen as part of the highest-scoring full stack among the {n} options that meet your hard "
                   "requirements; on the technical criteria it is level with the layer average"
                   + (", so the team's existing skills decide (below)." if skill_line else "."))
    if skill_line:
        why.append(skill_line)

    tradeoffs = []
    for b in pick["breakdown"]:
        if b["score"] <= 2.5 and b["weight"] >= 0.8:
            tradeoffs.append(f"{b['label']} is only {b['score']:.1f}/5 (weight {b['weight']:.1f}).")
    tradeoffs += relevant_lines(pick["item"].get("weaknesses", []), stack_ids, p)[:2]

    risks = [f"{x['reason'].rstrip('.')}." for x in pick["adjustments"] if x["delta"] < 0]
    risks += [f"{r['note']}" for r in mine if r["kind"] in ("caveat", "conflict")]
    if skills_given and pick["raw"].get("skill_fit", 3) <= 1.5:
        risks.append(f"Nobody on the team listed {pick['name']} or a closely related skill; plan 2-4 weeks to learn it.")
    if pick["item"].get("lock_in", 1) >= 4:
        risks.append("High vendor lock-in: migrating away later means rewriting data access code.")

    contribs = sorted(({"input": k, "label": INPUT_LABELS.get(k, k), "points": round(v, 2)}
                       for k, v in pick["contributions"].items() if abs(v) >= 0.05),
                      key=lambda x: -abs(x["points"]))

    vs = None
    confidence = "high"
    if alts:
        alt = alts[0]
        ac = alt["candidate"]
        diff = defaultdict(float)
        for k, v in pick["contributions"].items():
            diff[k] += v
        for k, v in ac["contributions"].items():
            diff[k] -= v
        my_rules = sum(r["delta"] for r in rules_hit)
        alt_rules = sum(r["delta"] for r in alt["rules"])
        if abs(my_rules - alt_rules) > 1e-9:
            diff["stack"] += (my_rules - alt_rules)  # rule deltas are expressed in layer points
        # Express every difference in stack points (the stack score averages four layers), so the
        # listed contributions add up exactly to the margin between the two stacks.
        diff = {k: v / 4 for k, v in diff.items()}
        ordered = sorted(diff.items(), key=lambda kv: -kv[1])
        favour_pick = [{"input": k, "label": INPUT_LABELS.get(k, k), "points": round(v, 2)} for k, v in ordered if v > 0.1][:4]
        favour_alt = [{"input": k, "label": INPUT_LABELS.get(k, k), "points": round(-v, 2)} for k, v in reversed(ordered) if v < -0.1][:3]
        margin = round(best_stack_score - alt["stack_score"], 2)
        # Remainder: answers below the listing threshold, rule and clamping effects, and rounding, so the
        # listed items add up exactly to the margin.
        rest = round(margin - (sum(x["points"] for x in favour_pick) - sum(x["points"] for x in favour_alt)), 2)
        if rest >= 0.01:
            favour_pick.append({"input": "remainder", "label": "Other answers and rounding", "points": rest})
        elif rest <= -0.01:
            favour_alt.append({"input": "remainder", "label": "Other answers and rounding", "points": -rest})
        confidence = "high" if margin >= 4 else "medium" if margin >= 1.5 else "low"
        tie = abs(margin) < TIE_MARGIN
        text = _vs_text(pick["name"], ac["name"], favour_pick, favour_alt, margin, best)
        if tie:
            text = _tie_text(layer, pick["name"], ac, favour_pick, favour_alt, margin, best, pick)
        vs = {"runner_up": ac["name"], "runner_up_id": ac["id"], "margin": margin, "tie": tie,
              "favour_pick": favour_pick, "favour_runner_up": favour_alt, "text": text,
              "kept": kept_text(layer, pick["name"], ac, margin, best)}
    return {"why": why, "strengths": relevant_lines(pick["item"].get("strengths", []), stack_ids, p)[:3], "tradeoffs": tradeoffs,
            "risks": risks, "input_contributions": contribs, "vs_runner_up": vs, "confidence": confidence}


HYPERSCALERS = ("aws", "gcp", "azure")


def _skill_text(pick: dict, skills: set) -> str | None:
    """'Team skill match' reason naming the skills behind it: direct (the team lists this tool or its
    cloud) or related (adjacent skills that carry over)."""
    from .kb import field_specs
    labels = {o["value"]: o["label"] for o in field_specs()["team_skills"].get("options", [])}
    item, s = pick["item"], pick["raw"].get("skill_fit", 3)
    if item.get("static_only"):
        return None  # nothing to build or run, so no skill to match
    name = lambda xs: ", ".join(labels.get(x, x) for x in sorted(xs))
    direct = skills & (set(item.get("skills", [])) | ({item.get("provider")} & set(HYPERSCALERS)))
    related = skills & set(item.get("related_skills", []))
    if direct:
        return f"Team skill match ({s:.1f}/5, direct): your team lists {name(direct)}, a direct match for {pick['name']}."
    if related:
        return (f"Team skill match ({s:.1f}/5, related): nobody listed {pick['name']}, but {name(related)} "
                f"{'carry' if len(related) > 1 else 'carries'} over.")
    return None


def points(x: float, unit: str = "stack points") -> str:
    """A score gap in words: '1.3 stack points', or 'less than 0.05 stack points' where one decimal would print 0.0."""
    return f"{abs(x):.1f} {unit}" if round(abs(x), 1) > 0 else f"less than 0.05 {unit}"


def stack_rule(best: dict | None) -> str:
    """The rule that chose the stack over a higher-scoring one, in words."""
    tb = (best or {}).get("tie_break") or {}
    if tb.get("budget_guard"):
        return "the budget rule (a stack whose minimum bill fits your budget is preferred when it scores only a few points lower)"
    if tb.get("avoided_return"):
        return ("the growth-path rule (the stack does not switch back to a technology the recommendation at a smaller "
                "scale had already moved away from)")
    if tb.get("kept_on_growth_path"):
        return "the growth-path rule (a pick the recommendation at a larger scale comes back to is held)"
    if tb.get("decided_by"):
        return f"the tie-break on {tb['decided_by']}"
    return TIE_ORDER_TEXT


def _vs_text(a, b, fa, fb, margin, best=None):
    fa, fb = [x for x in fa if x["input"] != "remainder"], [x for x in fb if x["input"] != "remainder"]
    if margin < 0:
        # The runner-up's stack scores higher; the pick stays because the stack-level choice kept it.
        s = (f"{b} would give a stack {abs(margin):.1f} stack points higher (stack points: points on the 0-100 stack score), but {a} was kept as part of "
             f"the stack chosen by {stack_rule(best)}")
    else:
        s = f"{a} beats {b} by {margin:.1f} stack points (points on the 0-100 stack score, the average of the four layer scores)"
    if fa:
        s += ", mainly on " + ", ".join(f"{x['label'].lower()} (+{x['points']:.1f})" for x in fa[:3])
    if fb:
        s += f". {b} is stronger on " + ", ".join(f"{x['label'].lower()} (+{x['points']:.1f})" for x in fb[:2])
    if margin < 1.5:
        s += ". Close call: either is defensible"
    return s + "."


# What a user would value to prefer the other option, per criterion ("choose B instead if ... matters more").
CHOOSE_IF = {"cost": "a lower bill", "scalability": "headroom to scale", "ease": "a gentler learning curve",
             "ops": "less to operate", "maturity": "a mature ecosystem", "realtime": "live updates",
             "performance": "raw speed", "seo": "search traffic", "velocity": "development speed",
             "hiring": "an easy hire", "offline": "offline use", "structure": "structure for a growing team",
             "interactivity": "rich client interaction", "skill_fit": "what your team already knows",
             "portability": "low lock-in", "data_fit": "data-model fit", "consistency_fit": "strict consistency",
             "region_fit": "region coverage", "compliance_maturity": "audit and compliance depth"}


def _crit_diffs(pick: dict, other: dict) -> list[tuple[float, str, float, float]]:
    """(weighted difference, criterion, pick score, other score) for weighted criteria, largest first. A criterion
    whose scores print the same at one decimal is left out: "stronger on cost (4.2 vs 4.2)" says nothing."""
    ob = {b["criterion"]: b["score"] for b in other["breakdown"]}
    out = [(b["weight"] * (b["score"] - ob.get(b["criterion"], b["score"])), b["criterion"], b["score"],
            ob.get(b["criterion"], b["score"])) for b in pick["breakdown"] if b["weight"] > 0]
    return sorted((x for x in out if f"{x[2]:.1f}" != f"{x[3]:.1f}"), reverse=True)


def kept_text(layer: str, a: str, alt_cand: dict, margin: float, best: dict | None) -> str:
    """Why the pick stays over a runner-up within the tie margin, as a sentence."""
    if best and best.get("tie_break", {}).get("kept_on_growth_path"):
        return (f"{a}'s stack is kept because it is also the pick at larger scale: otherwise a growing team "
                "would have to migrate away and back")
    reason = None
    if best is not None:
        other = {"picks": dict(best["picks"], **{layer: alt_cand}), "no_skills": best.get("no_skills"),
                 "no_fe_skills": best.get("no_fe_skills"), "lock_in_ok": best.get("lock_in_ok"),
                 "cloud_skills": best.get("cloud_skills", ())}
        reason = tie_reason(best, other)
    if reason:
        return f"The tie went to {a} on {reason}"
    if margin >= 0:
        return f"{a} has the higher stack score"
    return f"{a} stays as part of the stack chosen by {stack_rule(best)}"


def _tie_text(layer, a, alt_cand, fa, fb, margin, best, pick=None):
    """Runner-up within the tie margin: the technical differences, when to choose the other one, and
    the preference that decided."""
    b = alt_cand["name"]
    fa, fb = [x for x in fa if x["input"] != "remainder"], [x for x in fb if x["input"] != "remainder"]
    s = (f"{a} and {b} are within {points(margin)} of each other" if round(abs(margin), 1) > 0 else
         f"{a} and {b} score the same (less than 0.05 stack points apart)")
    s += f", inside the {TIE_MARGIN:g}-point tie margin, so they count as tied"
    diffs = _crit_diffs(pick, alt_cand) if pick else []
    lab = lambda c: CRITERION_LABELS[c] if CRITERION_LABELS[c][:3].isupper() else CRITERION_LABELS[c].lower()  # noqa: E731
    mine = [x for x in diffs if x[0] > 0.05 and x[1] != "skill_fit"][:2]
    theirs = [x for x in reversed(diffs) if x[0] < -0.05 and x[1] != "skill_fit"][:2]
    if mine:
        s += f". {a} is stronger on " + ", ".join(f"{lab(c)} ({x:.1f} vs {y:.1f})" for _, c, x, y in mine)
    if theirs:
        s += f"; {b} is stronger on " + ", ".join(f"{lab(c)} ({y:.1f} vs {x:.1f})" for _, c, x, y in theirs)
        s += f". Choose {b} instead if {CHOOSE_IF[theirs[0][1]]} matters more to you" + (
            f" than {CHOOSE_IF[mine[0][1]]}" if mine else "")
    elif not mine:
        if fa:
            s += ". It is stronger on " + ", ".join(f"{x['label'].lower()} (+{x['points']:.1f})" for x in fa[:2])
        if fb:
            s += f"; {b} is stronger on " + ", ".join(f"{x['label'].lower()} (+{x['points']:.1f})" for x in fb[:2])
    return s + f". {kept_text(layer, a, alt_cand, margin, best)}. Either is defensible."


# ---------------------------------------------------------------- why a pick switched
def layer_views(core: dict) -> dict:
    """Compact per-layer view of one engine run, enough to explain a later switch: each feasible
    candidate's per-criterion points, scores and weights, the exclusions, and the chosen stack's rules."""
    combos = core.get("combos") or []
    rules = combos[0]["rules"] if combos else []
    out = {}
    for layer in core["scored"]:
        out[layer] = {
            "cands": {c["id"]: {"name": c["name"], "score": c["score"],
                                "pts": {b["criterion"]: b["points"] for b in c["breakdown"]},
                                "s": {b["criterion"]: b["score"] for b in c["breakdown"]},
                                "w": {b["criterion"]: b["weight"] for b in c["breakdown"]},
                                "adj": {x["reason"]: x["delta"] for x in c["adjustments"]}}
                      for c in core["scored"][layer]},
            "excluded": {e["id"]: e["reasons"] for e in core["excluded"].get(layer, [])},
            "rules": {r["id"]: (r["note"], r["delta"]) for r in rules if layer in rule_layers(r)},
        }
    return out


def switch_reason(old_id: str, new_id: str, before: dict, after: dict) -> str:
    """Cause of a layer switching from old_id to new_id between two runs, named from what actually
    differs: an exclusion, the criteria whose points moved the gap, a penalty or bonus, or a stack rule."""
    from .kb import load_kb
    name = lambda i: load_kb()["index"][i]["name"]  # noqa: E731
    old, new = name(old_id), name(new_id)
    if old_id == new_id:
        return f"{old} is still the scored pick; only how it is shown changed."
    if old_id in after["excluded"]:
        return f"{old} is now ruled out: {after['excluded'][old_id][0].rstrip('.')}."
    ca, cb = after["cands"].get(new_id), after["cands"].get(old_id)
    bn, bo = before["cands"].get(new_id), before["cands"].get(old_id)
    if not (ca and cb):
        return f"{new} is the pick in the new run; {old} is no longer scored in this layer."
    lead = []
    if new_id in before["excluded"]:
        lead.append(f"{new} passes the hard constraints now (before: {before['excluded'][new_id][0].rstrip('.')})")
    if bn and bo:
        shift = sorted((((ca["pts"][c] - cb["pts"][c]) - (bn["pts"].get(c, 0) - bo["pts"].get(c, 0)), c)
                        for c in ca["pts"]), reverse=True)
        total = lambda x: sum(x["adj"].values())  # noqa: E731
        d_adj = (total(ca) - total(cb)) - (total(bn) - total(bo))
        moved = [(dv, c) for dv, c in shift if dv > 0.1]
        # Prefer a criterion the new pick actually leads on; one it trails on only counts for less now.
        top = ([x for x in moved if ca["s"][x[1]] >= cb["s"][x[1]]] or moved)[:1]
        if d_adj > 0.1 and (not top or d_adj >= top[0][0]):
            reasons = set(ca["adj"]) | set(cb["adj"]) | set(bn["adj"]) | set(bo["adj"])
            g = lambda x, r: x["adj"].get(r, 0)  # noqa: E731
            r = max(reasons, key=lambda r: (g(ca, r) - g(cb, r)) - (g(bn, r) - g(bo, r)))
            dn, do = g(ca, r) - g(bn, r), g(cb, r) - g(bo, r)
            rr = r.rstrip(".")
            if -do >= dn:
                what = (f"{old} now takes a penalty ({rr})" if g(cb, r) < 0 else f"{old} lost a bonus ({rr})")
            else:
                what = (f"{new} now gets a bonus ({rr})" if g(ca, r) > 0 else
                        f"{new} no longer takes a penalty ({rr})" if g(ca, r) == 0 else f"{new}'s penalty shrank ({rr})")
            lead.append(f"{what}, moving the gap {d_adj:.1f} points toward {new}")
        for dv, c in top:
            label = CRITERION_LABELS.get(c, c)
            label = label if label[:3].isupper() else label.lower()
            wb, wa = bn["w"].get(c, 0), ca["w"][c]
            sb_new, sb_old = bn["s"].get(c, ca["s"][c]), bo["s"].get(c, cb["s"][c])
            if ca["s"][c] >= cb["s"][c]:
                bits = [f"{new} {ca['s'][c]:.1f}/5 vs {old} {cb['s'][c]:.1f}/5"]
                if abs(wa - wb) >= 0.05:
                    bits.append(f"weight {wb:.1f} -> {wa:.1f}")
                if abs(ca["s"][c] - sb_new) >= 0.05 or abs(cb["s"][c] - sb_old) >= 0.05:
                    bits.append(f"was {sb_new:.1f} vs {sb_old:.1f}")
                lead.append(f"{label} moved the gap {dv:.1f} points toward {new} ({', '.join(bits)})")
            else:
                lead.append(f"{label}, where {old} leads ({cb['s'][c]:.1f}/5 vs {ca['s'][c]:.1f}/5), counts for less now "
                            f"(share of the total weight fell; gap {dv:.1f} points toward {new})")
    if ca["score"] <= cb["score"]:
        added = [n for i, (n, dl) in after["rules"].items() if i not in before["rules"] and dl > 0]
        gone = [n for i, (n, dl) in before["rules"].items() if i not in after["rules"] and dl > 0]
        via = (f"a stack rule now applies: {added[0]}" if added else
               f"a stack rule no longer applies: {gone[0]}" if gone else
               "the other layers changed, and the stack-level compatibility rules or tie-break favour it")
        lead.append(f"on its own {old} still scores {cb['score'] - ca['score']:.1f} higher, so {new} wins as part "
                    f"of the whole stack ({via.rstrip('.')})")
    if not lead:
        return f"{new} and {old} were within the tie margin (counted as tied), and the tie-break now favours {new}."
    s = "; ".join(lead)
    return s[0].upper() + s[1:] + "."


# ---------------------------------------------------------------- justification paragraph
LANG_LABELS = {"node": "Node.js", "python": "Python", "go": "Go", "jvm": "Java/Kotlin", "dotnet": "C#/.NET",
               "ruby": "Ruby", "php": "PHP", "elixir": "Elixir"}


NATIVE_NAMES = {("ios",): "Native iOS (Swift)", ("android",): "Native Android (Kotlin)"}
PHONE_NAMES = {"ios": "iOS", "android": "Android"}


def _and(xs: list[str]) -> str:
    return ", ".join(xs[:-1]) + f" and {xs[-1]}" if len(xs) > 1 else "".join(xs)


def mobile_name(item_id: str, name: str, platforms) -> str:
    """The native toolkit named for the phone platforms the project targets: one platform is one app, not two."""
    if item_id != "native_mobile":
        return name
    return NATIVE_NAMES.get(tuple(x for x in ("ios", "android") if x in platforms), name)


def _skill_sentence(item: dict, fit: float | None, skills: set) -> str | None:
    """A server backend's deciding human reason: which listed language it uses, with its team skill match score."""
    from .kb import field_specs
    if item.get("kind") not in ("server", "faas") or fit is None or not skills:
        return None
    labels = {o["value"]: o["label"] for o in field_specs()["team_skills"].get("options", [])}
    names = lambda xs: " and ".join(labels.get(x, x) for x in sorted(xs))  # noqa: E731
    lang = LANG_LABELS.get(item.get("language", ""), item["name"])
    direct = skills & set(item.get("skills", []))
    related = skills & set(item.get("related_skills", []))
    if direct:
        return f"The team lists {names(direct)}, so it needs no new server language (team skill match {fit:.1f}/5)."
    if related:
        return (f"Nobody listed {lang}, but {names(related)} {'carry' if len(related) > 1 else 'carries'} over "
                f"(team skill match {fit:.1f}/5).")
    return f"Nobody on the team lists {lang} or a related skill (team skill match {fit:.1f}/5), so plan time to learn it."


def _templates() -> dict:
    from .kb import _read
    return _read("explain_templates.json")


def _fmt_int(x: float) -> str:
    return f"{x:,.0f}"


def _money_txt(lo: float, hi: float, p: dict) -> str:
    from .profile import INR_PER_USD
    sym, k = ("₹", INR_PER_USD) if p.get("currency") == "INR" else ("$", 1)
    a, b = lo * k, hi * k
    return f"{sym}{a:,.0f}" if round(a) == round(b) else f"{sym}{a:,.0f}-{sym}{b:,.0f}"


def _ctx(layer: str, s: dict, items: dict, p: dict, d: dict, cost: dict, provided: bool, api_host: dict | None = None) -> dict:
    from .advice import short_name
    from .export import _num
    from .kb import field_specs
    from .recommender import _article
    specs = field_specs()
    opt = lambda key, v: next((o["label"] for o in specs[key].get("options", []) if o["value"] == v), str(v))  # noqa: E731
    it = items[layer]
    pick = s["pick"]
    raw = {b["criterion"]: b["score"] for b in pick["breakdown"]}
    app = opt("app_type", p["app_type"])
    title = s["title"]
    line = next((x for x in cost["lines"] if x["component"].startswith(f"{title}:")), None)
    vs = s["explanation"].get("vs_runner_up")
    comp = it.get("compliance", {})
    runs = it.get("runs", {})
    kind = "static" if it.get("static_only") and layer == "database" else it.get("kind")
    lead = max((b for b in pick["breakdown"] if b["criterion"] != "skill_fit" and b["weight"] > 0),
               key=lambda b: b["points"], default=None)
    be_line = next((x for x in cost["lines"] if x["component"].startswith("Backend:")), None)
    phones = [x for x in ("ios", "android") if x in p.get("platforms", [])]
    from .advice import architecture
    c = {
        "lead_crit": lead["label"].lower() if lead and not lead["label"][:3].isupper() else lead and lead["label"],
        "lead_s": f"{lead['score']:.1f}" if lead else None, "lead_w": f"{lead['weight']:.1f}" if lead else None,
        "optional_host": s.get("optional_host"),
        "backend_cost": _money_txt(be_line["low"], be_line["high"], p) if be_line else None,
        "name": mobile_name(pick["id"], pick["name"], p.get("platforms", [])),
        "app_phrase": f"{_article(app)} {app} project", "users": _fmt_int(p["dau"]),
        "peak": _num(d["peak_rps"]) if d["peak_rps"] else "<0.1",
        "team_phrase": "a solo developer" if p["team_size"] == 1 else f"a team of {p['team_size']}",
        "weeks": p["timeline_weeks"],
        "tier": d["tier_label"].replace("daily users", "devices") if p["app_type"] == "iot_telemetry" else d["tier_label"], "seo_label": opt("seo", p["seo"]).lower(),
        "seo_s": raw.get("seo"), "inter_s": raw.get("interactivity"), "rt_s": raw.get("realtime"),
        "lang": LANG_LABELS.get(it.get("language", ""), None),
        "hipaa_note": (comp.get("hipaa_note") or "").rstrip(".") or None,
        "data_gb": _num(d["data_12mo_gb"]), "shape": d["primary_shape"].replace("_", "-"),
        "fit": shape_models(it, d).get(d["primary_shape"]) if it.get("models") else None,
        "strong": 1 if it.get("consistency") == "strong" else 0,
        "write_s": write_scale(it, d) if it.get("models") else it.get("write_scale"),
        "regions_txt": ("users worldwide" if "global" in p["regions"] else
                        "users in " + " and ".join(opt("regions", r) for r in p["regions"])) if p["regions"]
                       else "users in regions you did not state",
        "availability": f"{d['availability']:g}", "backend": short_name(items["backend"]),
        "long_running": 1 if runs.get("long_running") else 0,
        "ws_phrase": " with WebSockets" if runs.get("websockets") and p["realtime"] != "none" else "",
        "hipaa": 1 if comp.get("hipaa") else 0, "pci": 1 if comp.get("pci") else 0,
        "hipaa_min": f" (from about ${comp['hipaa_min_usd']:,.0f} a month)" if comp.get("hipaa_min_usd") else "",
        "baas": short_name(items["backend"]),
        "cost": _money_txt(line["low"], line["high"], p) if line else None,
        "budget": _money_txt(d["budget_usd"], d["budget_usd"], p),
        "runner": vs["runner_up"] if vs else None, "margin": points(vs["margin"]) if vs else None,
        "tie": bool(vs and vs["tie"]), "kind": kind, "provided": provided,
        "kept": _lower_first(vs["kept"]) if vs and vs.get("kept") else None,
        "assumed": 1 if "consistency" in d.get("defaulted", ()) else 0, "static": 1 if kind == "static" else 0,
        "phones": " and ".join(PHONE_NAMES[x] for x in phones) or None, "both_phones": 1 if len(phones) == 2 else 0,
        "one": 1 if d.get("one_codebase") else 0, "api": 1 if d.get("api_only") else 0,
        "targets": _and([PHONE_NAMES.get(x, x) for x in d.get("one_codebase") or []]) or None,
        "other_phone": PHONE_NAMES[({"ios", "android"} - set(phones)).pop()] if len(phones) == 1 else None,
        "native_lang": {"ios": "Swift", "android": "Kotlin"}[phones[0]] if len(phones) == 1 else None,
        "skill_sentence": _skill_sentence(it, raw.get("skill_fit"), set(p.get("team_skills", []))) if layer == "backend" else None,
        "ws_list": "background jobs, WebSockets and database connection pools" if p["realtime"] != "none"
                   else "background jobs and database connection pools",
        "seo": p["seo"], "consistency": p["consistency"], "read_write": p["read_write"],
        # The server code runs as request-scoped functions: a functions backend, or a server framework on a
        # frontend or functions platform with no API host of its own.
        "functions": 1 if items["backend"].get("kind") == "faas" or (
            items["backend"].get("kind") == "server" and not api_host
            and items["hosting"].get("kind") in ("frontend_paas", "faas")) else 0,
        "host": (api_host or items["hosting"])["name"],
        # The architecture answer splits the backend into services: the backend sentence follows it.
        "services": 1 if architecture(p, d, items)["style"].startswith("Service-oriented") else 0,
        # IoT counts devices, not people (the scale question asks for "daily active users (or active devices)").
        "user_noun": "active devices" if p["app_type"] == "iot_telemetry" else "daily users",
    }
    return c


def _applies(t: dict, c: dict, stack: set, p: dict) -> bool:
    from .kb import LINE_CONDITIONS, _cond_holds
    for k, v in t.get("when", {}).items():
        if k in ("kind", "seo", "consistency", "read_write"):
            if c[k] not in v:
                return False
        elif k in ("provided", "tie", "functions", "services", "assumed", "static", "both_phones", "one", "api"):
            if c[k] != v:
                return False
        elif k in LINE_CONDITIONS:
            if not _cond_holds(k, v, stack, p):
                return False
    for k, v in t.get("min", {}).items():
        if c.get(k) is None or c[k] < v:
            return False
    return True


def _fill(t: dict, c: dict) -> str | None:
    import string
    names = [f for _, f, _, _ in string.Formatter().parse(t["text"]) if f]
    if any(c.get(n) is None for n in names):
        return None
    return t["text"].format_map(c)


def justification(layer: str, s: dict, items: dict, p: dict, d: dict, cost: dict, provided: bool = False,
                  api_host: dict | None = None) -> str:
    """3-5 sentence paragraph for one layer from the fixed templates in data/explain_templates.json,
    quoting the project's numbers and the pick's knowledge-base facts. Deterministic."""
    tpl = _templates()
    c = _ctx(layer, s, items, p, d, cost, provided, api_host)
    stack = {it["id"] for it in items.values()}
    ok = [(t, txt) for t in tpl["layers"][layer] if _applies(t, c, stack, p)
          and (not provided or t.get("when", {}).get("provided")) for txt in [_fill(t, c)] if txt]
    opener = next((txt for t, txt in ok if t.get("open")), None)
    body = [txt for t, txt in ok if not t.get("open") and not t.get("filler")]
    filler = [txt for t, txt in ok if t.get("filler")]
    closing = [] if provided else [txt for t in tpl["layers"]["closing"] if _applies(t, c, stack, p)
                                   for txt in [_fill(t, c)] if txt]
    room = tpl["max_sentences"] - 1 - len(closing)
    body = body[:max(1, room)]
    if 1 + len(body) + len(closing) < 3:
        body += filler[:1]
    out = ([opener] if opener else []) + body + closing
    return " ".join(out[:tpl["max_sentences"]])


# ---------------------------------------------------------------- why not X (per layer)
# Widely used options per layer (Stack Overflow Developer Survey 2025, https://survey.stackoverflow.co/2025/technology):
# a reader is likely to ask about them, so each gets a "Why not" line when it is not the pick.
POPULAR = {"frontend": ["nextjs", "react_spa", "react_native"], "backend": ["express", "django", "spring_boot"],
           "database": ["postgres", "mysql", "mongodb"], "hosting": ["vercel", "aws_ecs", "render"]}


def _lab(c: str) -> str:
    lab = CRITERION_LABELS.get(c, c)
    return lab if lab[:3].isupper() else lab.lower()


def compare_text(pick: dict, other: dict) -> str:
    """'<pick> is stronger on A (5.0 vs 3.0), B; <other> is stronger on C (4.0 vs 2.0)' from weighted criteria."""
    diffs = _crit_diffs(pick, other)
    mine = [x for x in diffs if x[0] > 0.05][:2]
    theirs = [x for x in reversed(diffs) if x[0] < -0.05][:2]
    parts = []
    if mine:
        parts.append(f"{pick['name']} is stronger on " + ", ".join(f"{_lab(c)} ({x:.1f} vs {y:.1f})" for _, c, x, y in mine))
    if theirs:
        parts.append(f"{other['name']} is stronger on " + ", ".join(f"{_lab(c)} ({y:.1f} vs {x:.1f})" for _, c, x, y in theirs))
    pen = [x["reason"].rstrip(".") for x in other.get("adjustments", []) if x["delta"] <= -2]
    if pen:
        parts.append(f"{other['name']} takes a penalty: {pen[0]}")
    return "; ".join(parts)


def _lower_first(s: str) -> str:
    return "the" + s[3:] if s.startswith("The ") else s


def _rule_gap_text(best: dict, hits: list[dict], gap: float, rule_gap: float) -> str | None:
    """The stack rules behind a swap's gap, when they move it by a point or more: without this a 12-point gap is
    explained by 1-point criterion differences only."""
    if rule_gap < 1:
        return None
    mine = {r["id"]: r for r in best.get("rules", [])}
    theirs = {r["id"]: r for r in hits}
    pool = sorted((r for i, r in theirs.items() if i not in mine and r["delta"] < 0), key=lambda r: r["delta"])
    pool += sorted((r for i, r in mine.items() if i not in theirs and r["delta"] > 0), key=lambda r: -r["delta"])
    if not pool:
        return None
    note = pool[0]["note"].rstrip(".")
    if rule_gap >= gap + 0.05:
        return (f"A stack compatibility rule costs it {rule_gap:.1f} points, more than the whole gap, while on this "
                f"layer's own criteria it is {rule_gap - gap:.1f} points ahead: {note}")
    return f"{min(rule_gap, gap):.1f} of the {gap:.1f} points come from a stack compatibility rule: {note}"


def why_not_list(layer: str, best: dict, scored: list[dict], excluded: list[dict], rules: list[dict],
                 p: dict, d: dict, kb_items: list[dict], runner_id: str | None = None) -> list[dict]:
    """'Why not X' for the runner-up, the layer's top scorer and the popular options of this layer:
    the stack gap if X replaced the pick (or the rule that excludes it) and the criteria behind it."""
    from .stack import combo_score, matching_rules
    pick = best["picks"][layer]
    by_id = {c["id"]: c for c in scored}
    want = []
    if runner_id:
        want.append((runner_id, "runner-up"))
    if scored and scored[0]["id"] != pick["id"]:
        want.append((scored[0]["id"], "highest score in this layer"))
    kinds = {it["id"]: it.get("kind") for it in kb_items}
    want += [(i, "popular choice") for i in POPULAR[layer]
             if i != pick["id"] and (layer != "frontend" or kinds.get(i) == pick["item"].get("kind"))]
    out, seen = [], set()
    for iid, role in want:
        if iid in seen:
            continue
        seen.add(iid)
        ex = next((e for e in excluded if e["id"] == iid), None)
        if ex:
            out.append({"id": iid, "name": ex["name"], "role": role, "excluded": True, "gap": None,
                        "text": f"Ruled out for your answers: {ex['reasons'][0].rstrip('.')}."})
        elif iid in by_id:
            cand = by_id[iid]
            picks = dict(best["picks"], **{layer: cand})
            hits = matching_rules({l: c["item"] for l, c in picks.items()}, rules, p, d)
            gap = round(best["score"] - combo_score({l: c["score"] for l, c in picks.items()}, hits), 2)
            why = compare_text(pick, cand)
            if abs(gap) < TIE_MARGIN:
                head = (f"Within the {TIE_MARGIN:g}-point tie margin (counted as tied): swapped in, its stack scores "
                        + (f"{abs(gap):.1f} points {'lower' if gap >= 0 else 'higher'}" if round(abs(gap), 1) > 0 else
                           "the same (less than 0.05 points apart)")
                        + (f"; {_lower_first(kept_text(layer, pick['name'], cand, gap, best))}" if gap < 0 else "")
                        + "; either is defensible")
            elif gap > 0:
                head = f"Swapping it in lowers the stack score by {gap:.1f} points"
            else:
                head = (f"Swapped into this stack it scores {-gap:.1f} points higher, but "
                        f"{_lower_first(kept_text(layer, pick['name'], cand, gap, best))}")
            rule = _rule_gap_text(best, hits, gap, gap - (pick["score"] - cand["score"]) / 4)
            out.append({"id": iid, "name": cand["name"], "role": role, "excluded": False, "gap": gap,
                        "text": head + (f". {why}." if why else ".") + (f" {rule}." if rule else "")})
        if len(out) >= 4:
            break
    return out
