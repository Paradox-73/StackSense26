"""Entry point: recommend(raw_input) -> fully explained stack recommendation (deterministic)."""
from __future__ import annotations

import re
from copy import deepcopy

from . import __version__
from .advice import (
    SPLIT_RULES,
    api_host_reasons,
    apply_ops_budget,
    architecture,
    baas_hosts_everything,
    database_offering,
    estimate_cost,
    how_parts_fit,
    min_feasible_cost,
    pick_api_host,
    runs_here,
    short_name,
    split_note,
    supporting_services,
)
from .conflicts import detect
from .explain import STACK_POINTS_DEF, explain_pick, justification, layer_views, points, rule_layers, switch_reason, why_not_list
from .kb import LAYERS, load_kb
from .profile import (
    DATA_GB_THRESHOLDS,
    INR_PER_USD,
    _tier,
    _warn,
    derive,
    estimated_data,
    growth_steps,
    own_step,
    normalize,
    tier_labels,
)
from .scoring import (
    EXISTING_SYSTEM_BONUS,
    KEPT_DATABASES,
    build_weights,
    hard_constraints,
    net_cost,
    score_layer,
    skill_fit,
    tier_cost,
)
from .stack import (
    FORWARD_MARGIN,
    TIE_ORDER_TEXT,
    RETURN_MARGIN,
    TIE_MARGIN,
    TOP_K,
    _holds,
    _returns,
    choose,
    combo_ids,
    combo_score,
    layer_alternatives,
    matching_rules,
    search,
)

SINGLE_PRIMARY_SQL = ("postgres", "mysql", "timescaledb")
# The languages a backend is written in, where its skills do not name them: the FaaS entry runs Node.js or Python.
BACKEND_LANGUAGES = {"serverless_functions": {"javascript", "typescript", "node", "python"}}


def _languages(item: dict) -> set:
    return BACKEND_LANGUAGES.get(item["id"], set(item.get("skills", [])))


def _unlisted_language_warning(p: dict, d: dict, best: dict, backends: list[dict], rules: list[dict]) -> dict | None:
    """The pick is in a language the team did not list, and a backend in a listed language would have won but for a
    rule that it cannot run on the chosen host (a function platform that runs only some languages)."""
    skills = set(d["skills"])
    be = best["picks"]["backend"]["item"]
    if not skills or be.get("kind") not in ("server", "faas") or _languages(be) & skills:
        return None
    for cand in backends:
        if cand["item"].get("kind") not in ("server", "faas") or not _languages(cand["item"]) & skills:
            continue
        picks = dict(best["picks"], backend=cand)
        hits = matching_rules({l: c["item"] for l, c in picks.items()}, rules, p, d)
        blocking = [r for r in hits if r["kind"] == "conflict" and {"backend", "hosting"} <= rule_layers(r)]
        if blocking and combo_score({l: c["score"] for l, c in picks.items()},
                                    [r for r in hits if r not in blocking]) > best["score"]:
            host = best["picks"]["hosting"]["item"]
            why = re.split(r"(?<=\.)\s+(?=[A-Z])", blocking[0]["note"])[0]  # the rule's first sentence: what the host runs
            return _warn("BACKEND_LANGUAGE_NOT_LISTED", "warning", "Backend in a language the team did not list",
                         f"{cand['name']} matches the team's skills, but {host['name']} cannot host it: {why}",
                         f"The backend is {be['name']}, in a language nobody on the team listed: plan time for the team "
                         f"to learn {short_name(be)}, or host the API on a container or PaaS service to keep "
                         f"{cand['name']}.", ["team_skills"])
    return None
LAYER_TITLES = {"frontend": "Frontend", "backend": "Backend", "database": "Database", "hosting": "Hosting"}


def _score_layers(kb: dict, p: dict, d: dict, w, light: bool = False) -> tuple[dict, dict, dict]:
    """Score every layer, relaxing soft constraints (lock-in, then scale ceiling) if a layer is empty."""
    layer_scored, layer_excluded, relaxed = {}, {}, {}
    for layer in LAYERS:
        scored, excluded = score_layer(layer, kb[layer], p, d, w, light=light)
        level = 0
        while not scored and level < 2:
            level += 1
            scored, excluded = score_layer(layer, kb[layer], p, d, w, relax=level, light=light)
        if level and scored:
            relaxed[layer] = level
        layer_scored[layer], layer_excluded[layer] = scored, excluded
    return layer_scored, layer_excluded, relaxed


def _at_tier(d: dict, k: int, p: dict, users: float | None = None) -> dict:
    """Derived profile as it would be with compute tier k (everything else unchanged); `users` sets the daily
    users of an estimated data size (profile.growth_steps), else the tier's own estimate is used."""
    data_12mo, data_tier = d["data_12mo_gb"], d["data_tier"]
    if d.get("data_estimated"):  # an estimated data size follows the tier (profile.estimated_data)
        vol, growth = estimated_data(p, k, d["data_estimated"], d["data_anchor"] if users is None else (k, users))
        data_12mo = round(vol + 12 * growth, 1)
        data_tier = _tier(data_12mo, DATA_GB_THRESHOLDS)
    db = max(data_tier, k - (1 if p["read_write"] == "read_heavy" else 0))
    label, db_label = tier_labels(k, d["dau_tier"], data_tier, db, d["conn_tier"])
    return dict(d, compute_tier=k, db_tier=db, tier_label=label, db_tier_label=db_label, data_12mo_gb=data_12mo,
                data_tier=data_tier)


# A flip-back found on the growth path is repaired by holding the earlier pick through the tiers in
# between; each repair can expose another one, so the walk is repeated a bounded number of times.
GROWTH_PATH_REPAIRS = 8


def _tier_options(kb: dict, p: dict, d: dict, own: dict | None = None) -> list:
    """Score-sorted stacks at every step of the growth path (profile.growth_steps) for these answers (None where
    a layer has no option). Only the stacks the growth path can still pick are kept (WALK_WINDOW). `own` is the
    layer scoring already done for the answers' own step."""
    out = []
    for k, users in growth_steps(p, d):
        dk = _at_tier(d, k, p, users)
        if own is not None and dk == d:
            scored = own
        else:
            scored, _, _ = _score_layers(kb, p, dk, build_weights(p, dk), light=True)
        if not all(scored[l] for l in LAYERS):
            out.append(None)
            continue
        out.append((dk, search(scored, kb["rules"], p, dk, window=WALK_WINDOW), scored["database"], {},
                    _wider(kb, p, dk, scored)))
    return out


def _tier_pick(p: dict, opt: tuple, left: dict, hold: dict, forbid: dict | None, widen: bool) -> dict | None:
    """The growth path's stack at one tier; `widen` lets the budget guard look past the top K."""
    dk, combos, db_scored, memo, wide = opt
    return _budget_guard(p, dk, combos, choose(combos, left, hold, _fits(p, dk, db_scored, memo), forbid),
                         db_scored, left, memo, wide if widen else None, hold)


def _walk(p: dict, options: list, holds: list, forbids: list | None = None,
          nowide: set | None = None, over: set | None = None) -> tuple[list, list]:
    """Recommendation at each tier, smallest first, and the picks each tier had already moved away from.
    The tiers whose pick is still over the budget are added to `over` when it is given."""
    picks, lefts, prev, left = [], [], None, {l: set() for l in LAYERS}
    for k, opt in enumerate(options):
        lefts.append({l: set(v) for l, v in left.items()})
        if opt is None:
            picks.append(None)
            prev = None  # a hard constraint empties a layer at this scale: no path to keep
            continue
        pick = _tier_pick(p, opt, left, holds[k], forbids[k] if forbids else None, not (nowide and k in nowide))
        new = combo_ids(pick) if pick else None
        if over is not None and pick and not _fits(p, opt[0], opt[2], opt[3])(pick):
            over.add(k)
        if prev and new:
            for i, l in enumerate(LAYERS):
                if prev[i] != new[i]:
                    left[l].add(prev[i])
        picks.append(new)
        prev = new
    return picks, lefts


def _first_flip_back(picks: list) -> tuple | None:
    """(layer index, id, last tier with it before leaving, tier it comes back) of the earliest return."""
    first = None
    for i in range(len(LAYERS)):
        seen, last, cur = {}, None, None
        for k, ids in enumerate(picks):
            if ids is None:
                continue
            x = ids[i]
            if x != cur and x in seen and (first is None or k < first[3]):
                first = (i, x, seen[x], k)
                break
            seen[x], cur = k, x
    return first


def _changes(picks: list) -> int:
    """How many times the path changes technology on any layer, tier to tier."""
    ids = [x for x in picks if x]
    return sum(a[i] != b[i] for a, b in zip(ids, ids[1:]) for i in range(len(LAYERS)))


def _growth_path(kb: dict, p: dict, d: dict, own: dict | None = None) -> tuple[list, list, list, list, set]:
    """Recommendations at every scale tier with no technology left and then picked again.

    The path is walked from the smallest tier up. Where a layer leaves a technology and comes back to
    it at a larger tier, the technology is held through the tiers in between if it stays within
    RETURN_MARGIN of the top stack there; otherwise the return is left to choose(), which avoids it when
    a stack that does not go back is within RETURN_MARGIN. Every tier gives the same path, so the
    recommendation at one user count agrees with the recommendation at any other."""
    options = _tier_options(kb, p, d, own)
    holds = [dict() for _ in options]
    forbids = [dict() for _ in options]
    # Tiers where the budget guard may not look past the top K (so may not change the backend or
    # database). A budget swap at one tier marks the replaced technology as left for every larger tier,
    # which can push those tiers onto a third choice (PostgreSQL -> SQLite for the budget, then MySQL
    # above). So the swap is allowed tier by tier, smallest first, only where the whole path changes
    # technology no more often than without it.
    nowide = {k for k, opt in enumerate(options) if opt is not None}
    over: set = set()
    picks, lefts = _walk(p, options, holds, forbids, nowide, over)
    for k in sorted(over):  # where the pick fits the budget the guard never widens
        wpick = _tier_pick(p, options[k], lefts[k], holds[k], forbids[k], True)
        if (combo_ids(wpick) if wpick else None) == picks[k]:
            continue  # widening changes nothing at this tier, so nothing above it either
        trial = nowide - {k}
        tpicks, tlefts = _walk(p, options, holds, forbids, trial)
        if tpicks[k] != picks[k] and _changes(tpicks) <= _changes(picks):
            nowide, picks, lefts = trial, tpicks, tlefts
    for _ in range(GROWTH_PATH_REPAIRS):
        fb = _first_flip_back(picks)
        if fb is None:
            break
        i, x, a, b = fb
        layer = LAYERS[i]
        span = [k for k in range(a + 1, b) if options[k] is not None]
        trial = [dict(h) for h in holds]
        for k in span:
            trial[k][layer] = x
        tpicks, tlefts = _walk(p, options, trial, forbids, nowide)
        if all(tpicks[k] and tpicks[k][i] == x for k in span):
            holds, picks, lefts = trial, tpicks, tlefts
            continue
        # The technology is too far behind in between: avoid going back to it instead.
        ftrial = [{l: set(v) for l, v in f.items()} for f in forbids]
        for k in range(b, len(options)):
            ftrial[k].setdefault(layer, set()).add(x)
        fpicks, flefts = _walk(p, options, holds, ftrial, nowide)
        if fpicks[b] and fpicks[b][i] == x:
            # The move away may be the budget guard's: without its backend/database changes at the tiers
            # in between, the path may leave later (or not at all), so avoiding the return can work.
            wtrial = nowide | set(range(a + 1, b))
            wpicks, wlefts = _walk(p, options, holds, ftrial, wtrial) if wtrial != nowide else (fpicks, flefts)
            if not (wpicks[b] and wpicks[b][i] != x):
                break  # no stack without it is close enough: keep the path as it is
            nowide, fpicks, flefts = wtrial, wpicks, wlefts
        forbids, picks, lefts = ftrial, fpicks, flefts
    return picks, lefts, holds, forbids, nowide


def _core(raw: dict, kb: dict | None = None, light: bool = False) -> dict:
    """Run the pipeline without counterfactuals. Returns an internal result dict. `kb` replaces the
    knowledge base (used only by the score-noise study, which passes a perturbed copy). `light` is for
    callers that read only the picks: the per-criterion breakdowns are not built and only the stacks
    that can still be picked are returned (the first of them is the same stack as without `light`)."""
    kb = kb or load_kb()
    p, assumptions, warnings = normalize(raw)
    d = derive(p, assumptions, warnings)
    warnings += detect(p, d)
    w = build_weights(p, d)

    layer_scored, layer_excluded, relaxed = _score_layers(kb, p, d, w, light=light)

    infeasible = [l for l in LAYERS if not layer_scored[l]]
    if infeasible:
        for l in infeasible:
            reasons = sorted({r for e in layer_excluded[l] for r in e["reasons"]})
            warnings.append(_warn("NO_FEASIBLE_OPTION", "critical", f"No {l} option satisfies the hard constraints",
                                  "Blocking reasons: " + "; ".join(reasons[:4]),
                                  "Relax a compliance, residency or deployment requirement.", [l]))
        return {"p": p, "d": d, "w": w, "assumptions": assumptions, "warnings": warnings,
                "scored": layer_scored, "excluded": layer_excluded, "combos": [], "infeasible": infeasible}

    combos = search(layer_scored, kb["rules"], p, d, window=WALK_WINDOW if light else None)
    _, lefts, holds, forbids, nowide = _growth_path(kb, p, d, layer_scored)
    k = own_step(p, d)
    best = _budget_guard(p, d, combos, choose(combos, lefts[k], holds[k], _fits(p, d, layer_scored["database"]),
                                              forbids[k]), layer_scored["database"], lefts[k],
                         wide=None if k in nowide else _wider(kb, p, d, layer_scored), hold=holds[k])
    combos[:] = [c for c in combos if c is not best]
    combos.insert(0, best)
    for layer in relaxed:  # the statement asks for exactly which constraints were relaxed: the pick's own waived limits
        item = best["picks"][layer]["item"]
        waived = [r for r in hard_constraints(layer, item, p, d) if r[2]]
        warnings.append(_warn("RELAXED_CONSTRAINT", "warning", f"No {layer} option met every constraint",
                              f"All {layer} options were excluded by hard constraints, so {item['name']} is kept with "
                              f"these limits relaxed: {'; '.join(r[0] for r in waived)}.",
                              "Compliance, residency, cloud and deployment rules are never relaxed.",
                              list(dict.fromkeys(r[1] for r in waived))))
    pref_warning = _cloud_pref_warning(p, combos, layer_excluded["hosting"])
    if pref_warning:
        warnings.append(pref_warning)
    be = best["picks"]["backend"]["item"]
    if p["architecture"] == "monolith" and be.get("kind") in ("baas", "faas"):
        warnings.append(_warn("ARCHITECTURE_OVERRIDDEN", "warning", "Monolith requested, but the backend is not one deployable",
                              f"{be['name']} still scored highest after the monolith penalty: it replaces most server code, "
                              "so there is little left to put in a monolith.",
                              "Kept the pick; choose a server framework from the backend alternatives if one deployable "
                              "unit is a requirement.", ["architecture"]))
    return {"p": p, "d": d, "w": w, "assumptions": assumptions, "warnings": warnings,
            "scored": layer_scored, "excluded": layer_excluded, "combos": combos, "infeasible": [],
            "relaxed": relaxed}


# One writable server per relational database: past ~10 TB a single primary gets slow to back up, restore and
# re-index, and managed services stop at 64 TiB per instance (Amazon RDS for PostgreSQL / MySQL).
SHARD_PLAN_GB = 10_000
SINGLE_WRITER_SQL = SINGLE_PRIMARY_SQL + ("sqlserver", "sqlite")
SHARD_SOURCES = ("https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html",
                 "https://vitess.io/docs/overview/",
                 "https://docs.citusdata.com/en/stable/get_started/what_is_citus.html")
# Users on another continent than the one region the database writes in: P50 round trips between Azure regions
# (East US - West Europe ~85 ms, Southeast Asia - West Europe ~170 ms, Southeast Asia - East US ~225 ms).
CROSS_REGION_LATENCY_MS = 100
RTT_SOURCE = "https://learn.microsoft.com/en-us/azure/networking/azure-network-latency"
CONTINENT = {"north_america": "North America", "europe": "Europe", "india": "Asia", "southeast_asia": "Asia"}


def _scale_warnings(p: dict, d: dict, stack: dict, have: list[dict]) -> list[dict]:
    """Architect warnings that need the picks: a single-primary relational database past ~10 TB, and a tight
    latency target for users on several continents."""
    out = []
    db = stack["database"]
    if db["id"] in SINGLE_WRITER_SQL and d["data_12mo_gb"] > SHARD_PLAN_GB:
        out.append(_warn("SHARDING_PLAN", "warning", f"{d['data_12mo_gb'] / 1000:,.0f} TB on one {db['name']} primary",
                         f"{db['name']} writes through one primary server; at ~{d['data_12mo_gb']:,.0f} GB within 12 months, "
                         "backups, restores, index builds and vacuum take hours, and managed instances stop at 64 TiB "
                         f"(Amazon RDS: {SHARD_SOURCES[0]}).",
                         "Plan sharding before you need it: pick a shard key (tenant or customer id), then use Citus for "
                         f"PostgreSQL ({SHARD_SOURCES[2]}) or Vitess for MySQL ({SHARD_SOURCES[1]}), or a distributed SQL "
                         "database (CockroachDB, YugabyteDB, Spanner; not scored by StackSense). Move old rows to cheaper "
                         "storage if they are rarely read.", ["data_volume_gb", "data_growth_gb_month"]))
    continents = {CONTINENT.get(r) for r in p["regions"]}
    many = "global" in p["regions"] or len(continents) > 1
    if p["latency_target_ms"] < CROSS_REGION_LATENCY_MS and many and stack["backend"].get("kind") != "none" and not any(w["code"] == "LATENCY_PHYSICS" for w in have):
        where = "users worldwide" if "global" in p["regions"] else "users in " + " and ".join(sorted(c for c in continents if c))
        out.append(_warn("CROSS_REGION_LATENCY", "warning", f"{p['latency_target_ms']:.0f} ms target for {where}",
                         f"The stack as shown runs its API and {db['name']} in one region. A round trip between continents "
                         f"alone takes ~85 ms (US East - West Europe) to ~170-225 ms (Southeast Asia - Europe or US East), "
                         f"measured between cloud regions ({RTT_SOURCE}), so users far from that region miss a "
                         f"{p['latency_target_ms']:.0f} ms target before any work is done.",
                         "Deploy the API in a region per continent with read replicas (or a multi-region database for "
                         "writes), cache reads at the edge (CDN or edge functions), or treat the target as per-region.",
                         ["latency_target_ms", "regions"]))
    return out


# A stack whose estimated minimum bill exceeds the budget gives way to the best stack that fits the
# budget, if that one scores at most this many stack points lower. Without it, raising the budget
# could move the pick to a pricier stack that no longer fits (the budget would stop being monotone).
BUDGET_GUARD_POINTS = 5.0
# Stacks scoring more than this below the top stack at a tier can never be picked there: choose() looks
# at most FORWARD_MARGIN below the top, and the budget guard at most BUDGET_GUARD_POINTS below that.
WALK_WINDOW = FORWARD_MARGIN + BUDGET_GUARD_POINTS
# Cheapest options per layer added to the search when nothing in the top K fits. Hosts are ordered by the floor of
# their price band, and several free plans ($0 floors) can come before a $5 host that the stack actually fits on
# (a free plan without a disk cannot hold a file database), so four are taken, not two.
BUDGET_GUARD_EXTRA = 4
BUDGET_GUARD_LAYER_GAP = 35.0  # an option this far below its layer's best never makes a stack within the guard's reach
BUDGET_GUARD_SLACK = 2.0  # points a widened search may top the narrow one by before the window is widened
BUDGET_GUARD_MAX_STACKS = 60  # combos are score-sorted; the window rarely holds more
# The cheaper stack may not trade the budget for a known fit problem: a compatibility rule of this
# many layer points or worse (e.g. a large framework on Lambda) that the over-budget stack lacks.
BUDGET_GUARD_MAX_NEW_PENALTY = -10


def _hard_penalties(combo: dict) -> set:
    return {r["id"] for r in combo["rules"] if r["delta"] <= BUDGET_GUARD_MAX_NEW_PENALTY}


def _stack_cost(p: dict, d: dict, combo: dict, db_scored: list[dict], memo: dict | None = None) -> float:
    """Minimum monthly bill from the price bands of the scale tier. The usage terms (per-operation
    pricing, stored GB, media and token volumes) grow with the exact user count inside a tier and are
    left out, so the guard decides the same way at every user count of one tier and the growth path
    agrees with every single run."""
    key = combo_ids(combo)
    if memo is not None and key in memo:  # `memo` belongs to one (answers, scale tier): same stack, same bill
        return memo[key]
    items = {l: combo["picks"][l]["item"] for l in LAYERS}
    kept, _, _ = apply_ops_budget(p, supporting_services(p, d, items, db_scored))
    cost = estimate_cost(p, d, items, kept, usage=False)["total_low"]
    if memo is not None:
        memo[key] = cost
    return cost


def _fits(p: dict, d: dict, db_scored: list[dict], memo: dict | None = None):
    """Predicate: the stack's minimum bill (price bands) fits the budget."""
    return lambda c: _stack_cost(p, d, c, db_scored, memo) <= d["budget_usd"]


def _cheapest_extras(scored: dict, p: dict, d: dict) -> dict:
    """Per layer, up to BUDGET_GUARD_EXTRA options the top-K search left out, cheapest first (price band
    at the scale tier). Options scoring more than BUDGET_GUARD_LAYER_GAP below the layer's best are not
    worth a stack. A managed backend (BaaS or functions) carries part of the database and hosting bill
    itself, so the best-scoring one of each such kind is added even if a server framework is cheaper."""
    out = {}
    for layer in LAYERS:
        if layer == "frontend":
            continue  # a frontend framework has no bill of its own; the extra stacks would only slow the search
        floor = scored[layer][0]["score"] - BUDGET_GUARD_LAYER_GAP
        rest = [c for c in scored[layer][TOP_K:] if c["score"] >= floor]
        if layer == "backend":
            def cost(c):
                return net_cost(c["item"], d["compute_tier"], p, d)[0]
        else:
            tier = d["compute_tier"] if layer in ("frontend", "hosting") else d["db_tier"]

            def cost(c, tier=tier):
                return tier_cost(c["item"], tier, p, d)[0]
        picked = sorted(rest, key=lambda c: (cost(c), -c["score"]))[:BUDGET_GUARD_EXTRA]
        if layer == "backend":
            for kind in ("baas", "faas"):
                if not any(c["item"].get("kind") == kind for c in picked):
                    picked += [c for c in rest if c["item"].get("kind") == kind][:1]
        out[layer] = picked
    return out


def _wider(kb: dict, p: dict, d: dict, scored: dict):
    """A function that returns the stacks of the top-K options plus the cheapest ones left out, within
    `window` points of the top stack. It searches only when the budget guard asks (the first time for each
    window) and remembers the result."""
    cache: dict = {}

    def wide(window: float = WALK_WINDOW) -> list[dict]:
        window = min(WALK_WINDOW, round(window, 1))
        if window not in cache:
            cache[window] = search(scored, kb["rules"], p, d, window=window, widen=_cheapest_extras(scored, p, d))
        return cache[window]
    return wide


def _budget_guard(p: dict, d: dict, combos: list[dict], best: dict, db_scored: list[dict], left: dict | None = None,
                  memo: dict | None = None, wide=None, hold: dict | None = None) -> dict:
    """If the chosen stack's estimated minimum bill is over the budget, take the best stack that keeps
    its backend and database, scores at most BUDGET_GUARD_POINTS lower and fits the budget (usually a
    cheaper host). When nothing with the same backend and database fits, the search is widened to the
    cheapest options of every layer (`wide`) and the best fitting stack of those, again within
    BUDGET_GUARD_POINTS, is taken even if it changes the backend or database."""
    budget = d["budget_usd"]
    over = _stack_cost(p, d, best, db_scored, memo)
    if over <= budget:
        return best
    core = (best["picks"]["backend"]["id"], best["picks"]["database"]["id"])
    known = _hard_penalties(best)
    # The growth path may hold a technology through these tiers so that it is not left and picked again;
    # no budget swap, narrow or wide, may give it up (a cheaper host at one tier, with the held host the only
    # one left at a larger tier, would be a move away and back).

    def find(pool, same_core, ok=None):
        return next(((c, cost) for c in pool[:BUDGET_GUARD_MAX_STACKS]
                     if c is not best and c["score"] >= best["score"] - BUDGET_GUARD_POINTS
                     and _hard_penalties(c) <= known and _returns(c, left) <= _returns(best, left)
                     and ((c["picks"]["backend"]["id"], c["picks"]["database"]["id"]) == core) == same_core
                     and (not hold or _holds(c, hold)) and (ok is None or ok(c))
                     for cost in [_stack_cost(p, d, c, db_scored, memo)] if cost <= budget), None)
    pick = find(combos, True)
    if pick is None and wide is not None:
        skills = set(d["skills"])

        def ok(c):
            # Changing the backend or database for the budget must not give up the team's skills.
            return not skills or all(skill_fit(c["picks"][l]["item"], skills) >= skill_fit(best["picks"][l]["item"], skills)
                                     for l in ("frontend", "backend"))
        # Only stacks within BUDGET_GUARD_POINTS of the stack being replaced matter; a candidate scoring above
        # the top stack of the narrow search by more than the slack would be cut, so that case searches wide.
        need = combos[0]["score"] - best["score"] + BUDGET_GUARD_POINTS
        wc = wide(need + BUDGET_GUARD_SLACK)
        if wc and wc[0]["score"] > combos[0]["score"] + BUDGET_GUARD_SLACK:
            wc = wide()
        pick = find(wc, True, ok) or find(wc, False, ok)
    if pick is None:
        return best
    c, cost = pick
    top = combos[0]
    c["tie_break"] = {
        "top_scorer": {l: x["name"] for l, x in top["picks"].items()},
        "top_score": top["score"], "margin": round(top["score"] - c["score"], 2),
        "decided_by": "a minimum bill that fits your budget", "kept_on_growth_path": False,
        "budget_guard": {"over_stack": {l: x["name"] for l, x in best["picks"].items()},
                         "over_score": best["score"], "over_cost": over, "cost": cost,
                         "changed": [l for l in LAYERS if c["picks"][l]["id"] != best["picks"][l]["id"]]}}
    return c


REGION_NAMES = {"india": "India", "southeast_asia": "Southeast Asia", "europe": "Europe", "north_america": "North America"}


def _db_region_note(p: dict, stack: dict, api_host: dict | None) -> str | None:
    """A managed database from a vendor other than the app's host (MongoDB Atlas, Timescale Cloud, ClickHouse
    Cloud ...) is created in a region of its own choosing: say to put it where the host runs the app, which
    for users in a region the host lacks is the host's nearest region, not the users' region."""
    db, host = stack["database"], api_host["item"] if api_host else stack["hosting"]
    offers = db.get("managed_offerings") or {}
    if (
        p["deployment"] != "cloud"
        or db.get("single_node")
        or db.get("static_only")
        or stack["backend"].get("bundled_database") == db["id"]
        or host.get("provider") in offers
        or "any" not in offers
    ):
        return None
    have = set(host.get("regions", []))
    missing = [r for r in p["regions"] if r != "global" and r not in have]
    where = ""
    if "india" in missing and "southeast_asia" in have:
        where = f" ({host['name']} has no India region, so that is Singapore, not Mumbai)"
    elif missing:
        where = f" ({host['name']} has no region in {', '.join(REGION_NAMES.get(r, r) for r in missing)})"
    return (f"{offers['any']} is a separate service from {host['name']}: create it in the cloud region where "
            f"{host['name']} runs your app{where}, or every query crosses between regions.")


def _cloud_pref_warning(p: dict, combos: list[dict], hosting_excluded: list[dict]) -> dict | None:
    """A stated cloud preference is soft: when the chosen host is elsewhere, say so and what it cost."""
    pref = p["cloud_preference"]
    if pref in ("none", "no_hyperscaler") or p["deployment"] == "on_prem" or p.get("cloud_required"):
        return None  # no preference, or a hard rule that the filters already enforced
    best = combos[0]
    host = best["picks"]["hosting"]
    if host["item"].get("provider") == pref:
        return None
    cloud = pref.upper()
    on_pref = next((c for c in combos if c["picks"]["hosting"]["item"].get("provider") == pref), None)
    if on_pref:
        names = " + ".join(on_pref["picks"][l]["name"] for l in LAYERS)
        gap = best["score"] - on_pref["score"]
        if gap > 0:
            detail = (f"The best stack on {cloud} ({names}) scores {points(gap)} lower than the pick, "
                      f"even with the preferred-cloud bonus.")
        else:
            detail = (f"The best stack on {cloud} ({names}) scores {points(gap)} higher than the pick, but it "
                      "would go back to, or move away from, a technology the recommendation keeps as users grow.")
    else:
        blocked = sorted({r for e in hosting_excluded if load_kb()["index"][e["id"]].get("provider") == pref
                          for r in e["reasons"]})
        detail = (f"No {cloud} hosting option passed the hard constraints"
                  + (": " + "; ".join(blocked[:3]) if blocked else "") + ".")
    return _warn("CLOUD_PREFERENCE_OVERRIDDEN", "warning", f"Preferred cloud ({cloud}) not used for hosting",
                 detail, f"Recommended {host['name']} instead; the cloud preference is a strong preference, not a hard filter.",
                 ["cloud_preference"])


def _picks(core: dict) -> dict[str, str]:
    if not core["combos"]:
        return {}
    return {l: c["id"] for l, c in core["combos"][0]["picks"].items()}


def _money(usd: float, p: dict) -> str:
    if p["currency"] == "INR":
        return f"₹{usd * INR_PER_USD:,.0f}/month"
    return f"${usd:,.0f}/month"


def _counterfactuals(raw_profile: dict, base_picks: dict, p: dict, d: dict, base_views: dict | None = None) -> list[dict]:
    kb = load_kb()
    tests = []
    b = p["budget_monthly"]
    cur = p["currency"]
    sym = "₹" if cur == "INR" else "$"
    if b > 0:
        tests.append((f"Budget cut to {sym}{b * 0.2:,.0f}/month (x0.2)", {"budget_monthly": b * 0.2}))
        tests.append((f"Budget raised to {sym}{b * 5:,.0f}/month (x5)", {"budget_monthly": b * 5}))
    else:
        amt = round(500 * INR_PER_USD) if cur == "INR" else 500
        tests.append((f"Budget of {sym}{amt:,}/month instead of zero", {"budget_monthly": amt}))
    conc = int(p["peak_concurrent"]) if p.get("peak_concurrent") else None  # users online scale with the users
    tests.append((f"10x more users ({p['dau'] * 10:,} DAU)", {"dau": p["dau"] * 10, "peak_rps": p["peak_rps"] * 10 if p.get("peak_rps") else None,
                                                             "peak_concurrent": conc * 10 if conc else None}))
    if p["dau"] >= 100:
        tests.append((f"10x fewer users ({p['dau'] // 10:,} DAU)", {"dau": p["dau"] // 10, "peak_rps": p["peak_rps"] / 10 if p.get("peak_rps") else None,
                                                                    "peak_concurrent": max(1, conc // 10) if conc else None}))
    if p["team_size"] > 1:
        tests.append(("A solo developer", {"team_size": 1}))
    if p["team_size"] < 12:
        tests.append(("A team of 15 engineers", {"team_size": 15}))
    tests.append(("4-week deadline" if p["timeline_weeks"] > 4 else "6-month timeline",
                  {"timeline_weeks": 4 if p["timeline_weeks"] > 4 else 26}))
    tests.append(("Realtime becomes core" if p["realtime"] != "core" else "No realtime needed",
                  {"realtime": "core" if p["realtime"] != "core" else "none"}))
    if p["seo"] != "critical":
        tests.append(("SEO becomes critical", {"seo": "critical"}))
    if p["deployment"] != "on_prem":
        tests.append(("Must run on-premises", {"deployment": "on_prem"}))
    if p["lock_in_tolerance"] != "low":
        tests.append(("Low tolerance for vendor lock-in", {"lock_in_tolerance": "low"}))
    if "hipaa" not in p["compliance"]:
        tests.append(("HIPAA compliance required", {"compliance": p["compliance"] + ["hipaa"]}))
    if "data_residency_india" not in p["compliance"]:
        tests.append(("Data must stay in India", {"compliance": p["compliance"] + ["data_residency_india"]}))
    if p["team_skills"]:
        tests.append(("Team has no relevant prior skills", {"team_skills": []}))

    out = []
    for label, change in tests:
        raw = deepcopy(raw_profile)
        raw.update(change)
        if raw.get("team_skills") == []:
            raw["team_skills"] = []
        c = _core(raw)
        picks = _picks(c)
        if not picks:
            out.append({"change": label, "effects": [], "note": "No feasible stack under this change."})
            continue
        # A host that is only an optional landing page on both sides is not a real change.
        before = _display_names(d, {l: kb["index"][base_picks[l]] for l in LAYERS})
        after = _display_names(c["d"], {l: kb["index"][picks[l]] for l in LAYERS})
        views = layer_views(c) if base_views else None
        effects = [{"layer": l, "from": before[l], "to": after[l],
                    "why": switch_reason(base_picks[l], picks[l], base_views[l], views[l]) if views else None}
                   for l in LAYERS if before[l] != after[l]]
        if effects:
            out.append({"change": label, "effects": effects})
    return out


def recommend(raw: dict | None, with_counterfactuals: bool = True) -> dict:
    """Turn raw answers into a full recommendation: stack, costs, reasons, rejected options and what-ifs."""
    kb = load_kb()
    core = _core(raw or {})
    p, d, w = core["p"], core["d"], core["w"]
    result = {
        "engine_version": __version__,
        "profile": p,
        "derived": {k: (sorted(v) if isinstance(v, set) else v) for k, v in d.items()},
        "assumptions": core["assumptions"],
        "warnings": core["warnings"],
        "weights": w.as_list(),
        "excluded": core["excluded"],
    }
    if core["infeasible"]:
        result.update({"feasible": False, "stack": {}, "summary": "No stack satisfies the hard constraints; see warnings."})
        return result

    best = core["combos"][0]
    stack_items = {l: best["picks"][l]["item"] for l in LAYERS}
    kept = [x for x in p["existing_systems"] if x in KEPT_DATABASES]
    if kept and stack_items["database"]["id"] not in kept:
        names = ", ".join(x for x in kept)
        result["warnings"].append(_warn(
            "EXISTING_SYSTEM_NOT_PICKED", "warning", "Your existing database was not picked",
            f"You must keep {names}, but {stack_items['database']['name']} fits your other answers better "
            f"(for example data shape {p['data_shapes'][0]} or the scale ceiling) even after a {EXISTING_SYSTEM_BONUS:.0f}-point bonus for staying.",
            f"Run {names} next to {stack_items['database']['name']} as a secondary store, or relax the data-shape and scale answers.",
            ["existing_systems"]))
    split_why = api_host_reasons(p, d, stack_items)
    api_host = pick_api_host(stack_items, core["scored"]["hosting"], kb["rules"],
                             lambda items, rules: matching_rules(items, rules, p, d)) if split_why else None
    language = None if api_host else _unlisted_language_warning(p, d, best, core["scored"]["backend"], kb["rules"])
    if language:  # with an API host of its own, the function platform's language rule does not bind the API
        result["warnings"].append(language)
    if api_host:
        # The frontend-platform caveats keep their points (two platforms to run is a cost too), but
        # their text now describes the split instead of functions-only hosting.
        best = dict(best, rules=[dict(r, note=split_note(stack_items, api_host, r["id"])) if r["id"] in SPLIT_RULES else r
                                 for r in best["rules"]])
    layers_out = {}
    for layer in LAYERS:
        pick = best["picks"][layer]
        alts = layer_alternatives(best, layer, core["scored"][layer], kb["rules"], p, d)
        exp = explain_pick(layer, pick, core["scored"][layer], w, best["rules"], alts, best["score"], bool(d["skills"]), best, p, d["skills"])
        managed = None
        if layer == "database":
            # The database sits next to the API: under split hosting, the offering is the API host's.
            managed = database_offering(pick["item"], api_host["item"] if api_host else stack_items["hosting"], p)
            if stack_items["backend"].get("bundled_database") == pick["id"]:
                managed = f"Included with {stack_items['backend']['name']}"
        layers_out[layer] = {
            "title": LAYER_TITLES[layer],
            "pick": _public(pick),
            "managed_offering": managed,
            "explanation": exp,
            "alternatives": [{**_public(a["candidate"]), "stack_score": a["stack_score"],
                              "delta_vs_pick": a["delta_vs_pick"],
                              "note": _alt_note(a, best, layer)} for a in alts],
            "ranking": [{"id": c["id"], "name": c["name"], "score": c["score"]} for c in core["scored"][layer]],
            "why_not": why_not_list(layer, best, core["scored"][layer], core["excluded"][layer], kb["rules"], p, d, kb[layer],
                                    alts[0]["candidate"]["id"] if alts else None),
            "excluded": core["excluded"][layer],
        }

    for layer in ("backend", "database"):
        if stack_items[layer].get("static_only"):
            nxt = next((c for c in core["scored"][layer] if not c["item"].get("static_only")), None)
            if nxt:
                layers_out[layer]["fallback"] = nxt["name"]
                layers_out[layer]["explanation"]["why"].append(
                    f"If users start to sign in, post or pay: {nxt['name']} is the next-best {layer} that passes your constraints.")
    multi_region = "global" in p["regions"] or len(p["regions"]) > 1
    if stack_items["database"]["id"] in SINGLE_PRIMARY_SQL and multi_region and d["availability"] >= 99.99 \
            and p["consistency"] == "strong":
        layers_out["database"]["explanation"]["risks"].append(
            f"{stack_items['database']['name']} has one writable primary: across regions at {d['availability']:g}% with strong "
            "consistency, a region failover loses or delays writes. If writes must survive a region outage, evaluate a "
            "distributed SQL database (Google Spanner, CockroachDB or YugabyteDB; not scored by StackSense).")
    region_note = _db_region_note(p, stack_items, api_host)
    if region_note:
        layers_out["database"]["explanation"]["risks"].append(region_note)
    layers_out["hosting"]["runs_here"] = runs_here(d, stack_items, api_host)
    if api_host:
        layers_out["hosting"]["api_host"] = {k: v for k, v in api_host.items() if k != "item"}
        layers_out["hosting"]["api_host"]["why"] = (f"The {short_name(stack_items['backend'])} API gets its own long-running host: "
                                                    + "; ".join(split_why) + ".")
        layers_out["hosting"]["explanation"]["why"].append(
            f"Split hosting: {api_host['name']} runs the API (score {api_host['score']:.1f}, the best-scoring long-running "
            f"host that passes your constraints); " + "; ".join(split_why) + ".")
    if baas_hosts_everything(d, stack_items):
        _provided_by_baas(layers_out["hosting"], stack_items)

    companion = None
    if d["mobile"] and d["web"]:
        # The other half of a web + mobile project: a mobile app beside a web frontend, or (for a
        # mobile-first app whose primary frontend is a mobile toolkit) a web app beside the mobile app.
        mobile_primary = stack_items["frontend"].get("kind") == "mobile"
        want = "web" if mobile_primary else "mobile"
        other_items = [it for it in kb["frontend"] if it.get("kind", "web") == want]
        scored, _ = score_layer("frontend", other_items, p, d if mobile_primary else dict(d, web=False), w)
        best_other = None
        for cand in scored[:5]:
            items = dict(stack_items, frontend=cand["item"])
            sc = cand["score"] + sum(r["delta"] for r in matching_rules(items, kb["rules"], p, d))
            if best_other is None or sc > best_other[0]:
                best_other = (sc, cand)
        if best_other:
            c = best_other[1]
            shares = set(c['item'].get('skills', [])) & set(stack_items['frontend'].get('skills', []))
            if mobile_primary:
                role, why = "Web app", (f"You also target the web. {c['name']} scored best among web frameworks with the "
                                        "same weights and backend")
            else:
                role, why = "Mobile app (iOS/Android)", (f"You also target iOS/Android. {c['name']} scored best among "
                                                         "mobile toolkits with the same weights and backend")
            companion = {"id": c["id"], "name": c["name"], "score": round(min(100, best_other[0]), 1), "role": role,
                         "why": why + (f"; it shares skills/types with {stack_items['frontend']['name']}." if shares else "."),
                         "ranking": [{"name": x["name"], "score": x["score"]} for x in scored]}

    services, deferred, ops = apply_ops_budget(p, supporting_services(
        p, d, dict(stack_items, api_host=api_host["item"]) if api_host else stack_items, core["scored"]["database"]))
    cost = estimate_cost(p, d, dict(stack_items, api_host=api_host["item"]) if api_host else stack_items, services)
    arch = architecture(p, d, stack_items)
    arch["how_parts_fit"] = how_parts_fit(p, d, stack_items, services, api_host)

    for wn in core["warnings"]:
        if wn["code"] == "FREE_TIER_NO_SLA" and cost["total_low"] > 0:
            # The stack is not on free tiers: say what it costs instead of 'free tiers only'.
            wn["title"] = f"{p['availability']}% availability with a zero budget"
            wn["detail"] = (f"Your budget is {_money(0, p)}, but the cheapest stack that meets your requirements costs about "
                            f"{_money(cost['total_low'], p)} (see Cost). Only free plans fit a zero budget, and free plans "
                            "carry no uptime guarantee (no SLA); many pause or throttle idle projects.")
            wn["resolution"] = "Budget for the paid plans in the estimate to get a written SLA, or treat the target as a goal."
    min_cost = min_feasible_cost(p, d, core["scored"]["hosting"], core["scored"]["database"])
    if cost["total_low"] > d["budget_usd"]:
        sev = "critical" if min_cost > d["budget_usd"] else "warning"
        detail = (f"Estimated minimum spend {_money(cost['total_low'], p)} exceeds your budget of {_money(d['budget_usd'], p)}"
                  f" at {d['tier_label']} scale.")
        if d["data_estimated"] and d["data_tier"] == d["db_tier"]:
            # The data size sets the database tier, and the user never gave it: say the bill rests on a guess.
            detail += (f" The database is sized for ~{d['data_12mo_gb']:,.0f} GB of data in 12 months, an estimated size "
                       "(you gave no data volume); state your data volume for a firmer figure.")
        if min_cost > d["budget_usd"]:
            res = (f"No feasible combination fits: the cheapest compliant hosting + database alone costs about {_money(min_cost, p)}. "
                   "Cost was weighted up; the stack shown is the cheapest that still meets the hard constraints. Raise the budget or reduce scale/compliance scope.")
        else:
            res = "A cheaper stack exists but scored lower on your other priorities; see the 'Budget cut' scenario under 'What would change'."
        core["warnings"].append(_warn("BUDGET_INFEASIBLE" if min_cost > d["budget_usd"] else "BUDGET_STRETCH",
                                      sev, "Budget below estimated cost", detail, res, ["budget_monthly", "dau"]))

    core["warnings"] += _scale_warnings(p, d, stack_items, core["warnings"])

    best_picks = {l: best["picks"][l]["id"] for l in LAYERS}
    cfs = _counterfactuals(_raw_from_profile(p, d["defaulted"]), best_picks, p, d, layer_views(core)) if with_counterfactuals else []

    alt_stacks = []
    seen = {tuple(_display_names(d, stack_items).values())}
    for c in core["combos"][1:]:
        names = _display_names(d, {l: c["picks"][l]["item"] for l in LAYERS})
        key = tuple(names.values())
        if key in seen:
            continue
        seen.add(key)
        alt_stacks.append({"stack": names, "score": c["score"],
                           "delta": round(c["score"] - best["score"], 2)})
        if len(alt_stacks) == 3:
            break

    sources = []
    for layer in LAYERS:
        for s in stack_items[layer].get("sources", []):
            if s not in sources:
                sources.append(s)
    for r in best["rules"]:
        if r.get("source") and r["source"] not in sources:
            sources.append(r["source"])

    result.update({
        "feasible": True,
        "stack_score": round(max(0.0, min(100.0, best["score"])), 1),
        "stack": layers_out,
        "companion": companion,
        "compatibility": [{"id": r["id"], "kind": r["kind"], "delta": r["delta"], "note": r["note"],
                           "source": r.get("source"), "layers": sorted(rule_layers(r))} for r in best["rules"]],
        "architecture": arch,
        "supporting_services": [{k: v for k, v in s.items() if k not in ("cost_id", "cost_tier", "system", "trigger", "usage")}
                                for s in services],
        "deferred_services": [{k: v for k, v in s.items() if k not in ("cost_id", "cost_tier", "system", "usage")}
                              for s in deferred],
        "ops_budget": ops,
        "cost": cost,
        "counterfactuals": cfs,
        "alternative_stacks": alt_stacks,
        "sources": sources,
        "relaxed_layers": core.get("relaxed", {}),
        "tie_break": _tie_break_out(best, p, d),
    })
    provided = baas_hosts_everything(d, stack_items)
    for layer in LAYERS:
        layers_out[layer]["explanation"]["paragraph"] = justification(
            layer, layers_out[layer], stack_items, p, d, cost, provided and layer == "hosting",
            api_host["item"] if api_host else None)
    # The unit is defined once, in the first paragraph that uses it.
    defined = False
    for layer in LAYERS:
        para = layers_out[layer]["explanation"]["paragraph"]
        if STACK_POINTS_DEF in para:
            if defined:
                layers_out[layer]["explanation"]["paragraph"] = para.replace(STACK_POINTS_DEF, "")
            defined = True
    result["warnings"] = core["warnings"]
    result["summary"] = _summary(result, p, d)
    return result


def switch_reasons(before_raw: dict, after_raw: dict) -> dict:
    """For each layer whose pick differs between two answer sets: from, to and the cause (used by the
    UI's what-if note after a slider change)."""
    kb = load_kb()
    a, b = _core(deepcopy(before_raw or {})), _core(deepcopy(after_raw or {}))
    pa, pb = _picks(a), _picks(b)
    if not pa or not pb:
        return {}
    va, vb = layer_views(a), layer_views(b)
    return {l: {"from": kb["index"][pa[l]]["name"], "to": kb["index"][pb[l]]["name"],
                "why": switch_reason(pa[l], pb[l], va[l], vb[l])} for l in LAYERS if pa[l] != pb[l]}


def _display_names(d: dict, stack: dict) -> dict:
    """Layer names as shown to the user: a mobile-only app on a BaaS shows hosting as provided by the BaaS."""
    names = {l: stack[l]["name"] for l in LAYERS}
    if baas_hosts_everything(d, stack):
        names["hosting"] = f"Provided by {short_name(stack['backend'])}"
    return names


def _provided_by_baas(h: dict, stack: dict) -> None:
    """Mobile-only app on a BaaS: show hosting as provided by the BaaS, with the scored web host
    kept only as an optional landing-page host."""
    baas = short_name(stack["backend"])
    host = "Firebase Hosting" if stack["backend"]["id"] == "firebase" else stack["hosting"]["name"]
    h["optional_host"] = host
    h["pick"] = dict(h["pick"], name=f"Provided by {baas}",
                     summary=f"{baas} hosts the backend; the app itself ships through the app stores.")
    e = h["explanation"]
    h["explanation"] = dict(e, why=[h["runs_here"]], strengths=[],
                            tradeoffs=[f"Backend quotas, regions and pricing are {baas}'s; see the Backend card."],
                            risks=[], vs_runner_up=None)
    h["alternatives"] = []
    h["why_not"] = []


def _tie_break_out(best: dict, p: dict, d: dict) -> dict | None:
    """When the chosen stack is not the single highest-scoring one, say which stack scored higher,
    by how much, and which tie-break preference decided."""
    tb = best.get("tie_break")
    if not tb:
        return None
    top = " + ".join(tb["top_scorer"][l] for l in LAYERS)
    if tb.get("budget_guard"):
        g = tb["budget_guard"]
        over = " + ".join(g["over_stack"][l] for l in LAYERS)
        changed = g.get("changed") or []
        kept = ("keeps its backend and database" if not {"backend", "database"} & set(changed) else
                "changes the " + " and ".join(changed))
        return dict(tb, text=(
            f"The stack that would otherwise be chosen ({over}, {g['over_score']:.1f}) has a minimum of about "
            f"{_money(g['over_cost'], p)}, above your budget of {_money(d['budget_usd'], p)}; this stack {kept}, "
            f"scores {points(g['over_score'] - best['score'])} lower and fits the budget "
            f"(about {_money(g['cost'], p)}), so it was chosen (a stack that fits is preferred when it is within "
            f"{BUDGET_GUARD_POINTS:g} points)."))
    if tb.get("avoided_return"):
        back = ", ".join(f"{name} ({layer})" for layer, name in tb["avoided_return"])
        return dict(tb, text=(
            f"The highest-scoring stack ({top}, {tb['top_score']:.1f}) would go back to {back}, which the recommendation "
            f"at a smaller scale had already moved away from. This stack scores {points(tb['margin'])} lower and "
            f"avoids that switch back, so it was chosen (a switch back is avoided when the alternative is within "
            f"{tb.get('return_margin', RETURN_MARGIN):g} points)."))
    if tb.get("kept_on_growth_path"):
        held = ", ".join(f"{name} ({layer})" for layer, name in tb.get("held", []))
        return dict(tb, text=(
            f"The highest-scoring stack ({top}, {tb['top_score']:.1f}) is {points(tb['margin'])} ahead, but it "
            f"would move away from {held}, which the recommendation at a larger scale comes back to. This stack keeps it, so "
            f"a growing team does not migrate away and back (a pick is held when it stays within {RETURN_MARGIN:g} points)."))
    text = (f"The highest-scoring stack ({top}, {tb['top_score']:.1f}) is only {points(tb['margin'])} ahead, "
            f"inside the {TIE_MARGIN:g}-point tie margin, so StackSense treats it as a tie")
    if tb.get("decided_by"):
        text += f" and chose this stack on {tb['decided_by']}."
    else:
        text += f" and chose this stack on {TIE_ORDER_TEXT}."
    return dict(tb, text=text)


def _raw_from_profile(p: dict, defaulted: set | None = None) -> dict:
    """Answers to re-run with a change: unanswered questions stay unanswered, so their defaults (and estimates that
    follow the scale, such as the data volume) are worked out again for the changed answers."""
    return {k: deepcopy(v) for k, v in p.items() if k not in (defaulted or set())}


def _public(c: dict) -> dict:
    it = c["item"]
    return {"id": c["id"], "name": c["name"], "score": c["score"], "base": c["base"], "summary": it.get("summary"),
            "breakdown": c["breakdown"], "adjustments": c["adjustments"], "sources": it.get("sources", [])}


def _alt_note(a: dict, best: dict, layer: str) -> str:
    my = {r["id"] for r in best["rules"]}
    theirs = {r["id"]: r for r in a["rules"]}
    gained = [theirs[i]["note"] for i in theirs if i not in my and layer in rule_layers(theirs[i])]
    lost = [r["note"] for r in best["rules"] if r["id"] not in theirs and layer in rule_layers(r) and r["kind"] == "synergy"]
    parts = []
    if lost:
        parts.append("Loses: " + lost[0])
    if gained:
        parts.append("Note: " + gained[0])
    gap = a["delta_vs_pick"]
    where = "ahead of" if gap > 0 else "behind"
    return " ".join(parts) or f"Scores {a['candidate']['score']:.1f} on its own; its stack is {points(gap)} {where} the pick."


def _article(label: str) -> str:
    """'a' or 'an' by sound: acronyms go by letter name (an ML product, a B2B app), words by first vowel."""
    word = (label.split() or [""])[0].strip("'\"(")
    if not word:
        return "a"
    letters = word.replace("-", "").replace("/", "")
    if letters[:2].isupper() or (len(letters) > 1 and letters[0].isupper() and letters[1].isdigit()):
        return "an" if word[0] in "AEFHILMNORSX" else "a"
    return "an" if word[0].lower() in "aeiou" else "a"


def _summary(r: dict, p: dict, d: dict) -> str:
    s = r["stack"]
    names = " + ".join(s[l]["pick"]["name"] for l in LAYERS)
    if s["hosting"].get("api_host"):
        names += f" (API on {s['hosting']['api_host']['name']})"
    crit = [x for x in r["warnings"] if x["severity"] == "critical"]
    from .export import _num
    from .kb import field_specs
    app_label = next((o["label"] for o in field_specs()["app_type"]["options"] if o["value"] == p["app_type"]), p["app_type"])
    lo, hi = r["cost"]["total_low"], r["cost"]["total_high"]
    k, fx = ("₹", INR_PER_USD) if p["currency"] == "INR" else ("$", 1)
    lo, hi = lo * fx, hi * fx
    cost_txt = f"{k}{lo:,.0f}" if round(lo) == round(hi) else f"{k}{lo:,.0f}-{k}{hi:,.0f}"
    txt = (f"For {_article(app_label)} '{app_label}' project at {d['tier_label']} scale (~{_num(d['peak_rps']) if d['peak_rps'] else '<0.1'} peak req/s) built by "
           f"{p['team_size']} engineer(s) in {p['timeline_weeks']} weeks, StackSense recommends {names} "
           f"(architecture: {r['architecture']['style']}). Estimated infrastructure cost: "
           f"{cost_txt}/month ({r['cost']['status']} budget).")
    if r.get("tie_break"):
        txt += " " + r["tie_break"]["text"]
    if crit:
        txt += f" {len(crit)} critical issue(s) need attention: " + "; ".join(x["title"] for x in crit) + "."
    return txt
