"""Markdown export of a recommendation (also used by the CLI and the report)."""
from __future__ import annotations

from .kb import LAYERS


def _num(x: float) -> str:
    """Thousands separators for large numbers; one decimal below 10 so small loads do not print as 0."""
    if x == 0:
        return "0"
    return f"{x:,.0f}" if abs(x) >= 10 else f"{x:.1f}" if abs(x) >= 0.1 else "<0.1"


MARGIN_WORDS = {"high": "clear (4+ points)", "medium": "solid (1.5-4 points)", "low": "close call (under 1.5)"}


def _margin_label(e: dict) -> str:
    vs = e.get("vs_runner_up")
    return f"{vs['margin']:.1f}, {MARGIN_WORDS[e['confidence']]}" if vs else "no runner-up"


def _fmt_value(v) -> str:
    if isinstance(v, list):
        return ", ".join(map(str, v)) or "none"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, int) and not isinstance(v, bool):
        return f"{v:,}"
    return str(v)


def to_markdown(r: dict) -> str:
    p = r["profile"]
    d = r["derived"]
    L = [f"# StackSense recommendation: {p.get('project_name', 'Project')}", ""]
    L.append(f"_Engine v{r['engine_version']}. Deterministic: the same inputs always give the same output._")
    L.append("")
    if not r.get("feasible"):
        L.append("**No feasible stack.**")
        for w in r["warnings"]:
            L.append(f"- [{w['severity']}] {w['title']}: {w['detail']} -> {w['resolution']}")
        return "\n".join(L)
    L += ["## Summary", "", r["summary"], ""]
    L += ["## Recommended stack", "", "| Layer | Pick | Score | Margin over runner-up | Runner-up |", "|---|---|---|---|---|"]
    for l in LAYERS:
        s = r["stack"][l]
        ru = s["explanation"]["vs_runner_up"]
        L.append(f"| {s['title']} | **{s['pick']['name']}**{' + API on ' + s['api_host']['name'] if s.get('api_host') else ''} | {s['pick']['score']:.1f} | {_margin_label(s['explanation'])} | "
                 f"{ru['runner_up'] + ' (' + format(-ru['margin'], '+.1f') + (', tie' if ru.get('tie') else '') + ')' if ru else '-'} |")
    if r.get("companion"):
        L.append(f"| {r['companion']['role']} | {r['companion']['name']} | {r['companion']['score']:.1f} | - | - |")
    L += ["", f"Stack score: **{r['stack_score']:.1f}** / 100 (average of layer scores plus compatibility adjustments).", ""]
    L += ["## Architecture", "", f"**{r['architecture']['style']}**: {r['architecture']['why']}", "",
          f"Availability approach: {r['architecture']['redundancy']}", ""]
    if r["architecture"].get("how_parts_fit"):
        L += ["### How the parts fit", ""]
        L += [f"{i}. **{s['step']}**: {s['text']}" for i, s in enumerate(r["architecture"]["how_parts_fit"], 1)]
        L.append("")

    L += ["## Inputs used", ""]
    L.append(f"- Scale tier: {d['tier_label']} (peak ~{_num(d['peak_rps']) if d['peak_rps'] else '<0.1'} req/s, {d['rps_source']}"
             + (f"; {_num(d['peak_concurrent'])} users online at once" if d.get("peak_concurrent") else "")
             + f"); database tier: {d['db_tier_label']} (~{_num(d['data_12mo_gb'])} GB in 12 months)")
    L.append(f"- Budget: ~${d['budget_usd']:,.0f}/month" + (f" ({d['fx_note']})" if d.get("fx_note") else ""))
    defaults = [a for a in r["assumptions"] if a.get("kind") == "default"]
    for a in r["assumptions"]:
        if a.get("kind") != "default":
            L.append(f"- Assumption: {a['field']} = {a['value']}: {a['reason']}")
    if defaults:
        L.append(f"- Defaults used ({len(defaults)}): " + "; ".join(
            f"{a.get('label', a['field'])} = {_fmt_value(a['value'])}" for a in defaults))
    L.append("")

    if r["warnings"]:
        L += ["## Warnings and how they were resolved", ""]
        for w in r["warnings"]:
            L.append(f"- **[{w['severity'].upper()}] {w['title']}**: {w['detail']} *Resolution:* {w['resolution']}")
        L.append("")

    L += ["## Per-layer reasoning", ""]
    for l in LAYERS:
        s = r["stack"][l]
        e = s["explanation"]
        L += [f"### {s['title']}: {s['pick']['name']} ({s['pick']['score']:.1f})", "", s["pick"]["summary"] or "", ""]
        if e.get("paragraph"):
            L += [e["paragraph"], ""]
        if s.get("managed_offering"):
            L += [f"Suggested offering: {s['managed_offering']}", ""]
        if s.get("runs_here") and not s.get("optional_host"):
            L += [s["runs_here"], ""]
        if s.get("api_host"):
            L += [f"API host: **{s['api_host']['name']}** ({s['api_host']['score']:.1f}). {s['api_host']['why']}", ""]
        L.append("**Why**")
        L += [f"- {x}" for x in e["why"]] + [f"- {x}" for x in e["strengths"]]
        L.append("")
        L.append("**Trade-offs**")
        L += [f"- {x}" for x in e["tradeoffs"]] or ["- None significant"]
        L.append("")
        if e["risks"]:
            L.append("**Risks**")
            L += [f"- {x}" for x in e["risks"]]
            L.append("")
        if e["vs_runner_up"]:
            L += [f"**Versus runner-up:** {e['vs_runner_up']['text']}", ""]
        L.append("**Inputs that drove this score** (points out of 100)")
        L += [f"- {c['label']}: {c['points']:+.1f}" for c in e["input_contributions"][:6]]
        L.append("")
        L += ["| Criterion | Score (1-5) | Weight | Points |", "|---|---|---|---|"]
        for b in sorted(s["pick"]["breakdown"], key=lambda b: -b["points"]):
            if b["weight"] > 0:
                L.append(f"| {b['label']} | {b['score']:.1f} | {b['weight']:.1f} | {b['points']:.1f} |")
        for x in s["pick"]["adjustments"]:
            L.append(f"| Adjustment: {x['reason']} | | | {x['delta']:+.1f} |")
        L.append("")
        if s["alternatives"]:
            L.append("**Alternatives**")
            for a in s["alternatives"]:
                L.append(f"- {a['name']} (stack {a['stack_score']:.1f}, {a['delta_vs_pick']:+.1f}): {a['note']}")
            L.append("")
        if s.get("why_not"):
            L.append("**Why not the others?**")
            L += [f"- Why not {x['name']}? ({x['role']}) {x['text']}" for x in s["why_not"]]
            L.append("")
        if s["excluded"]:
            L.append("**Excluded by hard constraints**")
            for x in s["excluded"]:
                L.append(f"- {x['name']}: {'; '.join(x['reasons'])}")
            L.append("")

    if r["compatibility"]:
        L += ["## Stack compatibility checks", ""]
        for c in r["compatibility"]:
            L.append(f"- ({c['kind']}, {c['delta']:+}) {c['note']}")
        L.append("")
    L += ["## Supporting services", ""]
    for s in r["supporting_services"]:
        L.append(f"- **{s['role']}**: {s['name']}: {s['why']}")
    L.append("")
    if r.get("deferred_services"):
        ob = r["ops_budget"]
        # A service held back for its own reason (advice.supporting_services "hold") states it; the rest wait on the cap.
        capped = any(not s.get("hold") for s in r["deferred_services"])
        L += ["### Add later (ops budget)" if capped else "### Add later", ""]
        if capped:
            L += [f"A team of {ob['team_size']} is kept to {ob['cap']} extra system(s) to operate. {ob['note']}", ""]
        for s in r["deferred_services"]:
            held = f"Held back: {s['hold']}. " if s.get("hold") else ""
            L.append(f"- **{s['role']}**: {s['name']}: add {s['trigger']}. {held}{s['why']}")
        L.append("")
    c = r["cost"]
    L += ["## Estimated monthly cost", "", "| Component | Low (USD) | High (USD) | Basis |", "|---|---|---|---|"]
    for x in c["lines"]:
        L.append(f"| {x['component']} | {x['low']:,.0f} | {x['high']:,.0f} | {x.get('basis', '')} |")
    L.append(f"| **Total** | **{c['total_low']:,.0f}** | **{c['total_high']:,.0f}** | |")
    L += ["", f"About ₹{c['total_low_inr']:,}-₹{c['total_high_inr']:,} per month. Budget status: **{c['status']}**. {c['note']}", ""]
    if r["counterfactuals"]:
        L += ["## What would change the recommendation", ""]
        for cf in r["counterfactuals"]:
            eff = "; ".join(f"{e['layer']}: {e['from']} -> {e['to']}" for e in cf["effects"]) or cf.get("note", "")
            L.append(f"- **{cf['change']}**: {eff}")
            L += [f"  - Why {e['layer']} changes: {e['why']}" for e in cf["effects"] if e.get("why")]
        L.append("")
    if r["alternative_stacks"]:
        L += ["## Next-best complete stacks", ""]
        for a in r["alternative_stacks"]:
            L.append(f"- {' + '.join(a['stack'][l] for l in LAYERS)} ({a['score']:.1f}, {a['delta']:+.1f})")
        L.append("")
    L += ["## Sources", ""] + [f"- {s}" for s in r["sources"]]
    return "\n".join(L) + "\n"


ADR_HEADINGS = ("Context", "Decision", "Alternatives considered", "Consequences", "Revisit when")


def to_adr(r: dict) -> str:
    """One architecture decision record (ADR) per layer: context, decision, alternatives considered,
    consequences and when to revisit, all taken from the recommendation."""
    p, d = r["profile"], r["derived"]
    name = p.get("project_name", "Project")
    L = [f"# Architecture decision records: {name}", "",
         f"_Generated by StackSense v{r['engine_version']} from the project's answers; the same answers give the same records._", ""]
    if not r.get("feasible"):
        return "\n".join(L + ["No feasible stack: see the warnings in the full report."]) + "\n"
    comp = ", ".join(p["compliance"]) or "none"
    context = (f"{p['team_size']} engineer(s), {p['timeline_weeks']} weeks, about {p['dau']:,} daily users "
               f"(~{_num(d['peak_rps']) if d['peak_rps'] else '<0.1'} requests/s at peak), about {_num(d['data_12mo_gb'])} GB of data "
               f"within 12 months, a {d['availability']:g}% availability target, a budget of about ${d['budget_usd']:,.0f}/month, "
               f"compliance: {comp}.")
    for i, l in enumerate(LAYERS, 1):
        s, e = r["stack"][l], r["stack"][l]["explanation"]
        L += [f"## ADR-{i:03d}: {s['title']}: {s['pick']['name']}", "", "Status: proposed", ""]
        L += ["### Context", "", context, ""]
        if s["excluded"]:
            L.append(f"Hard constraints rule out {len(s['excluded'])} option(s): "
                     + "; ".join(f"{x['name']} ({x['reasons'][0].rstrip('.')})" for x in s["excluded"][:4]) + ".")
            L.append("")
        L += ["### Decision", "", f"Use **{s['pick']['name']}** for the {l} (layer score {s['pick']['score']:.1f}/100).", ""]
        if e.get("paragraph"):
            L += [e["paragraph"], ""]
        L += ["### Alternatives considered", ""]
        alts = [f"- {x['name']} ({x['role']}): {x['text']}" for x in s.get("why_not", [])]
        if e.get("vs_runner_up") and not any(x["name"] == e["vs_runner_up"]["runner_up"] for x in s.get("why_not", [])):
            alts.insert(0, f"- {e['vs_runner_up']['runner_up']} (runner-up): {e['vs_runner_up']['text']}")
        L += alts or ["- No other option passes the hard constraints."]
        L += ["", "### Consequences", ""]
        L += [f"- Positive: {x}" for x in e["why"][:3]]
        L += [f"- Trade-off: {x}" for x in e["tradeoffs"]]
        L += [f"- Risk: {x}" for x in e["risks"]]
        L += ["", "### Revisit when", ""]
        rev = [f"- {cf['change']}: switch to {ef['to']}" + (f" ({ef['why']})" if ef.get("why") else "")
               for cf in r.get("counterfactuals", []) for ef in cf["effects"] if ef["layer"] == l]
        L += rev or ["- No single tested change (budget, users, team, deadline, realtime, SEO, on-premises, lock-in, "
                     "HIPAA, India residency, skills) switches this layer."]
        L.append("")
    return "\n".join(L)
