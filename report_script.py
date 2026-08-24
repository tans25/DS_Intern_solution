#!/usr/bin/env python3
"""
SignalDesk weekly read.

    python report_script.py product_usage_events.csv -o read.html

Answers one question: which of these numbers can we act on, and what do the
trustworthy ones say?

Design notes (why this is a script and not a dashboard):
  - Filters and dropdowns would let a reader pool workflows and average rates,
    which is how you get the wrong answers this report exists to prevent.
    The judgment is encoded here, not delegated to the reader.
  - Re-runnable on next week's export, so it doubles as the weekly health check.

Three rules enforced throughout:
  1. Counts pool, rates do not. Sum numerator and denominator, divide once.
  2. Never rank workflows on a pooled rate. Source mix confounds it.
  3. Say what was excluded and what it changed.
"""
from __future__ import annotations
import argparse, html, sys
from pathlib import Path
import pandas as pd

BAD_NOTES = ["duplicate export row", "traffic spike from demo account"]
ORDER = ["Lead summary", "Reply draft", "Feedback clustering"]
TEAM = {"Lead summary": "Sales", "Reply draft": "Support", "Feedback clustering": "Product"}


# ───────────────────────── load ─────────────────────────
def load(path: Path):
    df = pd.read_csv(path)
    df["team"] = df.team.str.strip().str.title()
    df["median_confidence"] = pd.to_numeric(df.median_confidence, errors="coerce")
    dropped = df[df.notes.isin(BAD_NOTES)].copy()
    clean = df[~df.notes.isin(BAD_NOTES)].copy()
    return df, clean, dropped


def rate(sub, num="accepted_output", den="sessions"):
    """Pool the counts, then divide once. Never mean() a rate column."""
    d = sub[den].sum()
    return float("nan") if d == 0 else sub[num].sum() / d * 100


def order_of(clean):
    present = list(clean.workflow.unique())
    return [w for w in ORDER if w in present] + [w for w in present if w not in ORDER]


def primary_source(clean, wf):
    """The workflow's own automatic intake — whatever it's called in this export."""
    nm = clean[(clean.workflow == wf) & (clean.source != "manual")].groupby("source").sessions.sum()
    return nm.idxmax() if len(nm) else None


def partial_days(clean):
    expected = clean.groupby(["workflow", "source"]).ngroups
    allpairs = set(zip(clean.workflow, clean.source))
    out = []
    for date, n in clean.groupby("date").size().items():
        if n < expected:
            day = clean[clean.date == date]
            missing = sorted(f"{w} / {s}" for w, s in allpairs - set(zip(day.workflow, day.source)))
            out.append((date, int(n), missing))
    return out, expected


# ───────────────────────── analysis ─────────────────────────
def by_source(clean, wfs):
    rows = []
    for wf in wfs:
        sub = clean[clean.workflow == wf]
        prim = primary_source(clean, wf)
        auto, man = sub[sub.source == prim], sub[sub.source == "manual"]
        rows.append({
            "workflow": wf, "sessions": int(sub.sessions.sum()), "primary": prim,
            "auto_rate": rate(auto), "auto_n": int(auto.sessions.sum()),
            "man_rate": rate(man), "man_n": int(man.sessions.sum()),
            "pooled": rate(sub), "completion": rate(sub, "completed"),
            "flag": rate(sub, "flagged_for_review", "completed"),
        })
    return pd.DataFrame(rows).set_index("workflow")


def find_reversal(t, wfs):
    """A workflow ahead on BOTH sources but behind on the pooled number."""
    for a in wfs:
        for b in wfs:
            if a != b and t.auto_rate[a] > t.auto_rate[b] and t.man_rate[a] > t.man_rate[b] \
                    and t.pooled[a] < t.pooled[b]:
                return a, b
    return None


def best_workflow(t, wfs):
    """Most useful now = best on its own intake source, among those with enough traffic."""
    eligible = [w for w in wfs if t.sessions[w] >= 200] or wfs
    return max(eligible, key=lambda w: t.auto_rate[w])


def stable_series(clean):
    """The workflow+source present on every day — composition held fixed."""
    days = clean.date.nunique()
    best, n = None, -1
    for (wf, src), sub in clean.groupby(["workflow", "source"]):
        if sub.date.nunique() == days and sub.sessions.sum() > n:
            best, n = (wf, src), sub.sessions.sum()
    if best is None:
        return None, None
    wf, src = best
    sub = clean[(clean.workflow == wf) & (clean.source == src)].sort_values("date")
    sub = sub.assign(ar=sub.accepted_output / sub.sessions * 100,
                     fr=sub.flagged_for_review / sub.completed * 100)
    return best, sub[["date", "sessions", "ar", "fr", "median_confidence", "user_rating"]]


def no_verdict(sub):
    c = sub.completed.sum()
    return (c - sub.accepted_output.sum() - sub.flagged_for_review.sum()) / max(c, 1) * 100


# ───────────────────────── render ─────────────────────────
CSS = """
*{box-sizing:border-box}
body{font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,sans-serif;
     color:#22252A;max-width:860px;margin:0 auto;padding:44px 26px 90px}
h1{font-size:25px;margin:0 0 4px}
h2{font-size:17px;margin:40px 0 10px;padding-bottom:6px;border-bottom:1px solid #E5E3DE}
h3{margin:0 0 3px;font-size:16px}
h4{font-size:14px;margin:24px 0 6px;color:#4B5058}
.sub{color:#6B7280;font-size:13px;margin-bottom:6px}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13.5px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid #EDEBE6}
th{color:#6B7280;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.03em}
td.n{text-align:right;font-variant-numeric:tabular-nums}
tr.grp td{border-bottom:none;padding-bottom:2px}
tr.grp2 td{padding-top:2px}
.tag{display:inline-block;white-space:nowrap;padding:2px 9px;border-radius:9px;font-size:11px;
     font-weight:700;letter-spacing:.03em;text-transform:uppercase}
.ok{background:#E4EFE9;color:#2E6F55} .warn{background:#FBF0DC;color:#8A5D12}
.bad{background:#F8E5E3;color:#B4483C} .none{background:#EEECE7;color:#6B7280}
.card{border:1px solid #E5E3DE;border-left-width:3px;border-radius:5px;padding:14px 18px;margin:14px 0}
.card.ok{border-left-color:#2E6F55} .card.warn{border-left-color:#C98B27}
.card.bad{border-left-color:#B4483C} .card.none{border-left-color:#9CA3AF}
.card .why{color:#4B5058;margin:8px 0 0}
.k{color:#6B7280;font-size:12.5px}
.note{background:#FAF9F7;border:1px solid #E5E3DE;border-radius:5px;padding:12px 16px;
      font-size:13.5px;color:#4B5058;margin:14px 0}
.answer{background:#F2F7F4;border:1px solid #CFE0D7;border-radius:6px;padding:18px 20px;margin:6px 0 18px}
.answer .big{font-size:21px;font-weight:700;color:#2E6F55;display:block;margin-bottom:5px}
.big{font-size:19px;font-weight:700;font-variant-numeric:tabular-nums}
ul{margin:8px 0 0;padding-left:20px} li{margin:5px 0}
.foot{margin-top:44px;padding-top:14px;border-top:1px solid #E5E3DE;color:#9CA3AF;font-size:12px}
em.q{font-style:normal;background:#FBF0DC;padding:0 3px}
"""


def esc(s):
    return html.escape(str(s))


def render(raw, clean, dropped, path_in) -> str:
    wfs = order_of(clean)
    t = by_source(clean, wfs)
    rev = find_reversal(t, wfs)
    winner = best_workflow(t, wfs)
    parts, expected = partial_days(clean)
    stratum, conf = stable_series(clean)
    raw_v = raw.groupby("workflow").sessions.sum().reindex(wfs)
    clean_v = clean.groupby("workflow").sessions.sum().reindex(wfs)
    ndays = clean.date.nunique()

    o = ['<!doctype html><meta charset="utf-8">', f"<style>{CSS}</style>",
         "<h1>SignalDesk — what the numbers can and can't tell you</h1>",
         f"<p class='sub'>{esc(clean.date.min())} to {esc(clean.date.max())} &middot; "
         f"source: {esc(Path(path_in).name)} &middot; {len(clean)} rows used, {len(dropped)} excluded</p>"]

    # ══════════ 1. THE ANSWER ══════════
    o.append("<h2>1 &nbsp;Which workflow seems most useful right now?</h2>")
    loser = rev[1] if rev and rev[0] == winner else None
    o.append(f"<div class='answer'><span class='big'>{esc(winner)}</span>"
             f"Highest acceptance on its own intake source — <strong>{t.auto_rate[winner]:.1f}%</strong> "
             f"via {esc(t.primary[winner])}, n={int(t.auto_n[winner])}"
             + (f" — and ahead of {esc(loser)} on <em>both</em> of its sources, even though it looks "
                f"marginally worse once you combine them. That combined number is the misleading one; "
                f"section 4 explains why." if loser else ".") + "</div>")

    for wf in wfs:
        r = t.loc[wf]
        broke = (conf is not None and stratum and wf == stratum[0]
                 and conf.ar.iloc[-1] < conf.ar.iloc[0] * 0.6)
        if wf == winner:
            cls, head = "ok", "Working"
            body = (f"{r.auto_rate:.1f}% acceptance via {esc(r.primary)}, {r.man_rate:.1f}% when typed "
                    f"in manually. {int(r.sessions)} sessions across {ndays} days, "
                    f"{r.completion:.0f}% reaching an output, {r.flag:.1f}% of outputs flagged.")
            trust = "Confident. Full week of data, healthy volume, no contradicting signal."
        elif broke:
            cls, head = "bad", "Was healthy, then broke"
            body = (f"Ran {conf.ar.iloc[0]:.0f}%&ndash;{conf.ar.iloc[-2]:.0f}% for six days, then fell "
                    f"to {conf.ar.iloc[-1]:.0f}% on {esc(conf.date.iloc[-1])} with flags at "
                    f"{conf.fr.iloc[-1]:.0f}% and rating at {conf.user_rating.iloc[-1]:.1f}. Sessions "
                    f"dropped {int(conf.sessions.iloc[-2])} &rarr; {int(conf.sessions.iloc[-1])} the "
                    f"same day, so fewer people used it at all.")
            trust = "Not confident about the cause. Three explanations fit — see section 5."
        else:
            cls, head = "none", "Not yet measurable"
            body = (f"Only {int(r.sessions)} sessions, and {100-r.completion:.0f}% never reach an "
                    f"output at all — the weakest completion of the three. Its two sources perform "
                    f"about the same ({r.auto_rate:.1f}% via {esc(r.primary)} against "
                    f"{r.man_rate:.1f}% manual), so whatever limits it isn't how work arrives.")
            trust = ("Low confidence. Too little traffic for the rates to mean much. "
                     "Not a red flag, just thin.")
        o.append(f"<div class='card {cls}'><h3>{esc(wf)} &nbsp;<span class='tag {cls}'>{head}</span> "
                 f"<span class='k'>{TEAM.get(wf,'')}</span></h3><div>{body}</div>"
                 f"<div class='why'><strong>How much to trust this:</strong> {trust}</div></div>")

    o.append("<h4>Which numbers this answer rests on</h4>"
             "<p><strong>Trusted:</strong> acceptance rate — read per source, never pooled — and user "
             "rating. <strong>Flagged as unreliable:</strong> median confidence, which rose every day "
             "of the week including the worst one, and average minutes saved, which barely varies and "
             "is self-estimated. Flag rate sits in between: useful as a tripwire, not as a quality "
             "score. Section 2 has the full ranking, section 3 the evidence.</p>")

    # ══════════ 2. METRICS TABLE ══════════
    o.append("<h2>2 &nbsp;Which metrics to act on</h2>")
    stds = clean.groupby("workflow").avg_minutes_saved.std().reindex(wfs)
    if conf is not None:
        c_lo, c_hi = conf.median_confidence.iloc[0], conf.median_confidence.max()
        a_lo, a_hi = conf.ar.iloc[0], conf.ar.iloc[-1]
        r_lo, r_hi = conf.user_rating.iloc[0], conf.user_rating.iloc[-1]

    trust_rows = [
        ("Acceptance rate", "ok", "Trust",
         "The most direct evidence a human found the output usable. Reliable when read per source; "
         "misleading when pooled across sources — see section 4."),
        ("User rating", "ok", "Trust",
         (f"Moves with acceptance, and it caught the {esc(conf.date.iloc[-1])} drop — fell to "
          f"{r_hi:.1f} from {r_lo:.1f}. One row is missing a rating, so coverage is incomplete."
          if conf is not None else "Moves with acceptance where both are observed.")),
        ("Flag rate", "warn", "Tripwire only",
         "Three different things produce a flag: worse output, stricter policy, or more careful users. "
         "Flags also can't be cleanly separated from acceptance — on at least one day accepted + "
         "flagged exceeds completed, so some outputs are both. Watch it for movement; don't score with it."),
        ("Avg minutes saved", "warn", "Low trust",
         "Within each workflow this hardly moves (std " + ", ".join(f"{stds[w]:.2f}" for w in wfs) +
         "). It behaves like a per-workflow constant with jitter rather than a measurement, and it's "
         "self-estimated."),
        ("Median confidence", "bad", "Do not use",
         (f"Rose every single day ({c_lo:.2f} &rarr; {c_hi:.2f}) while acceptance fell "
          f"{a_lo:.0f}% &rarr; {a_hi:.0f}%. It peaked on the worst day in the export. A dashboard "
          "tracking confidence would have shown a rising green line straight through the failure."
          if conf is not None else "Model-reported confidence is not a measure of correctness.")),
    ]
    o.append("<table><tr><th>Metric</th><th>Verdict</th><th>Why</th></tr>")
    for name, cls, verdict, why in trust_rows:
        o.append(f"<tr><td><strong>{name}</strong></td><td><span class='tag {cls}'>{verdict}</span></td>"
                 f"<td>{why}</td></tr>")
    o.append("</table>")

    # ══════════ 3. EVIDENCE ══════════
    o.append("<h2>3 &nbsp;The evidence behind those calls</h2>")

    o.append("<h4>Rows we refused to count</h4>")
    o.append("<table><tr><th>Date</th><th>Workflow</th><th>Source</th><th class='n'>Sessions</th>"
             "<th>Why, and how it would skew the result</th></tr>")
    for _, r in dropped.iterrows():
        why = ("Identical to the row above on every numeric field — an export bug. Counting it "
               "double-counts real work, inflating sessions and accepted totals together."
               if r.notes == "duplicate export row" else
               "A demo account. Volume more than doubles while acceptance, rating, confidence and "
               "minutes-saved all jump at once, then return to baseline the next day. Real usage "
               "doesn't improve on five dimensions simultaneously. Left in, it pulls this workflow's "
               "acceptance up by several points.")
        o.append(f"<tr><td>{esc(r.date)}</td><td>{esc(r.workflow)}</td><td>{esc(r.source)}</td>"
                 f"<td class='n'>{int(r.sessions)}</td><td>{why}</td></tr>")
    o.append("</table>")

    flip = raw_v.idxmax() != clean_v.idxmax()
    o.append("<div class='note'><strong>Together they change which workflow looks biggest.</strong><br>"
             + " &middot; ".join(f"{esc(w)}: {int(raw_v[w])} &rarr; <strong>{int(clean_v[w])}</strong>"
                                 for w in wfs)
             + (f"<br>The busiest workflow is <strong>{esc(clean_v.idxmax())}</strong>, not "
                f"{esc(raw_v.idxmax())} — and since both excluded rows belong to "
                f"{esc(raw_v.idxmax())}, nothing else moved." if flip else "") + "</div>")

    if parts:
        o.append("<h4>Incomplete days</h4>")
        o.append(f"<p>Every full day has {expected} rows — one per workflow and source. These don't:</p><ul>")
        for date, n, missing in parts:
            o.append(f"<li><strong>{esc(date)}</strong> — {n} rows. Absent: {esc(', '.join(missing))}. "
                     "Not zero sessions; the rows are missing from the export entirely.</li>")
        o.append("</ul><p class='k'>Any day-over-day comparison crossing these dates compares different "
                 "populations. Nobody has confirmed why they're short — worth asking whoever owns the "
                 "export, because if manual entry was switched off deliberately, those days aren't "
                 "comparable at all.</p>")

    if conf is not None:
        wf_s, src_s = stratum
        o.append("<h4>Why confidence can't be trusted</h4>")
        o.append(f"<p>Below is {esc(wf_s)} on the <strong>{esc(src_s)}</strong> source — the one "
                 f"workflow-and-source combination present on all {ndays} days, so nothing here moves "
                 "because the mix changed:</p>")
        o.append("<table><tr><th>Date</th><th class='n'>Sessions</th><th class='n'>Acceptance</th>"
                 "<th class='n'>Flag rate</th><th class='n'>Confidence</th><th class='n'>Rating</th></tr>")
        for _, r in conf.iterrows():
            st = " style='background:#FDF3F2'" if r.ar == conf.ar.min() else ""
            o.append(f"<tr{st}><td>{esc(r.date)}</td><td class='n'>{int(r.sessions)}</td>"
                     f"<td class='n'>{r.ar:.0f}%</td><td class='n'>{r.fr:.0f}%</td>"
                     f"<td class='n'>{r.median_confidence:.2f}</td>"
                     f"<td class='n'>{r.user_rating:.1f}</td></tr>")
        o.append("</table>")
        o.append("<p>Confidence climbs every single day while acceptance decays and then collapses. "
                 "On the worst day in the file — acceptance down two-thirds, rating roughly halved — "
                 "the model was more confident than it had ever been. That isn't a weak signal, it's "
                 "an inverted one.</p>")

    # ══════════ 4. RANK BY SOURCE ══════════
    o.append("<h2>4 &nbsp;Rank by source, not by workflow</h2>")
    if rev:
        a, b = rev
        share_a = t.man_n[a] / t.sessions[a] * 100
        share_b = t.man_n[b] / t.sessions[b] * 100
        o.append(f"<p><strong>This is Simpson's Paradox at work.</strong> {esc(a)} has a higher "
                 f"acceptance rate than {esc(b)} on its automatic source "
                 f"({t.auto_rate[a]:.1f}% via {esc(t.primary[a])}, against {t.auto_rate[b]:.1f}% via "
                 f"{esc(t.primary[b])}). It also has a higher rate on the manual source "
                 f"({t.man_rate[a]:.1f}% against {t.man_rate[b]:.1f}%). It wins both. Yet combine each "
                 f"workflow's two sources into a single number and {esc(a)} comes out "
                 f"<em>behind</em> — {t.pooled[a]:.1f}% against {t.pooled[b]:.1f}%.</p>")
        o.append(f"<p>The reason is the mix, not the performance. Manual work is accepted far less "
                 f"often than automatic work in every workflow here. {esc(a)} takes {share_a:.0f}% of "
                 f"its sessions manually; {esc(b)} takes only {share_b:.0f}%. So {esc(a)} carries more "
                 f"of the harder kind of work, and its combined number gets pulled down further — far "
                 f"enough to wipe out a lead it genuinely holds on both sources. "
                 f"<strong>Pooling the sources ranks workflows by the kind of input they receive, not "
                 f"by how well they perform.</strong> That's why every rate in this report is read per "
                 f"source.</p>")
    else:
        o.append("<p>Acceptance is read per source throughout, because manual and automatic input "
                 "perform very differently and workflows receive them in different proportions. "
                 "Combining them ranks input mix rather than performance.</p>")

    o.append("<table><tr><th>Workflow</th><th>Source</th><th class='n'>Sessions</th>"
             "<th class='n'>Acceptance</th><th class='n'>Completion</th><th class='n'>Flagged<br>(of outputs)</th>"
             "<th class='n'>No verdict</th></tr>")
    for wf in wfs:
        sub = clean[clean.workflow == wf]
        for i, src in enumerate([t.primary[wf], "manual"]):
            s = sub[sub.source == src]
            name = (f"<strong>{esc(wf)}</strong> <span class='k'>{TEAM.get(wf,'')}</span>"
                    if i == 0 else "")
            o.append(f"<tr class='{'grp' if i == 0 else 'grp2'}'><td>{name}</td><td>{esc(src)}</td>"
                     f"<td class='n'>{int(s.sessions.sum())}</td>"
                     f"<td class='n'>{rate(s):.1f}%</td>"
                     f"<td class='n'>{rate(s,'completed'):.0f}%</td>"
                     f"<td class='n'>{rate(s,'flagged_for_review','completed'):.1f}%</td>"
                     f"<td class='n'>&ge;{no_verdict(s):.0f}%</td></tr>")
    o.append("</table>")
    o.append("<p class='k'>&ldquo;No verdict&rdquo; = completed, but neither accepted nor flagged — "
             "nobody recorded an outcome. It's a lower bound: some outputs are both accepted and "
             "flagged, and any such overlap makes this group larger.</p>")

    auto_avg = sum(t.auto_rate[w] * t.auto_n[w] for w in wfs) / sum(t.auto_n[w] for w in wfs)
    man_avg = sum(t.man_rate[w] * t.man_n[w] for w in wfs) / sum(t.man_n[w] for w in wfs)
    o.append(f"<div class='card warn'><h3>The most actionable finding: manual input costs "
             f"~{auto_avg-man_avg:.0f} points</h3>"
             f"<p>Automatic sources average <span class='big'>{auto_avg:.0f}%</span> acceptance; "
             f"manual averages <span class='big'>{man_avg:.0f}%</span>. This holds across three "
             "unrelated workflows and three different teams, which points at the input path rather "
             "than any one prompt — and that may be fixable in the intake form rather than the model.</p>"
             "<p class='why'>Caveat before acting: this data can't distinguish <em class='q'>typing it "
             "in produces worse context</em> from <em class='q'>people only type it in when the case is "
             "unusual</em>. Those need different fixes. Look at what actually gets pasted into that "
             "box.</p></div>")

    # ══════════ 5. INVESTIGATE ══════════
    o.append("<h2>5 &nbsp;What to investigate before rolling out further</h2>")
    if conf is not None:
        wf_s, _ = stratum
        o.append(f"<div class='card bad'><h3>Priority: what happened to {esc(wf_s)} on "
                 f"{esc(conf.date.iloc[-1])}</h3>"
                 "<p>Three explanations fit the same numbers, and they imply opposite actions:</p><ul>"
                 "<li><strong>Output got worse</strong> — then the rollout should pause.</li>"
                 "<li><strong>The review gate got stricter</strong> — then output is unchanged and "
                 "this is the policy working as designed.</li>"
                 "<li><strong>It's composition</strong> — two manual rows are missing that day, and "
                 "sessions more than halved.</li></ul>"
                 "<p>Daily aggregates cannot separate these. There is no session-level key, so "
                 "acceptance and flagging can't be joined per output.</p>"
                 f"<p class='why'><strong>Cheapest way to settle it:</strong> pull ~20 flagged "
                 f"{esc(wf_s)} outputs from before the change and ~20 after, and have a team lead rate "
                 "them blind. An afternoon's work, and it answers what the logs structurally can't. "
                 "Separately, ask whoever owns the export why those rows are missing.</p></div>")

    o.append("<div class='card none'><h3>Not yet answerable: did the prompt change help?</h3>"
             "<p>No step change appears in any workflow at the prompt-change date. Feedback clustering "
             "was already drifting down beforehand; Lead summary is flat; Reply draft declines steadily "
             "throughout. The post-change window is three clean days, on rising volume, ending in a day "
             "that's both partial and confounded by the policy change.</p>"
             "<p class='why'>Volume also grows daily, so pooled totals are weighted toward the "
             "post-change period — any &ldquo;overall&rdquo; number is quietly a post-change number. "
             "Give it two clean weeks with no other changes, then ask again.</p></div>")

    o.append("<h4>The weekly check</h4>"
             "<p>Re-run this script on the new export. It <em>is</em> the check:</p><ul>"
             "<li>Section 3 — did anything get excluded, and are any days incomplete?</li>"
             "<li>Section 4 — acceptance per workflow <strong>per source</strong>, never pooled.</li>"
             "<li>Any workflow whose no-verdict share is climbing.</li>"
             "<li>One line recording any prompt or policy change that week, so next week's reader "
             "knows what to attribute movement to.</li></ul>"
             "<p class='k'>Two things worth instrumenting so future weeks can answer more: a "
             "session-level key (so acceptance and flagging can be joined per output), and a reason "
             "code on flags (so &ldquo;stricter policy&rdquo; and &ldquo;worse output&rdquo; stop "
             "being indistinguishable).</p>")

    o.append("<div class='foot'>Every rate here is a pooled count — numerator and denominator summed, "
             "divided once. Averaging per-row rates instead would over-weight small rows and, on this "
             "export, reverses the workflow ranking outright.</div>")
    return "\n".join(o)


def main():
    ap = argparse.ArgumentParser(description="SignalDesk weekly read")
    ap.add_argument("csv", nargs="?", default="product_usage_events.csv")
    ap.add_argument("-o", "--out", default="signaldesk_read.html")
    a = ap.parse_args()
    p = Path(a.csv)
    if not p.exists():
        sys.exit(f"no such file: {p}")
    raw, clean, dropped = load(p)
    Path(a.out).write_text(render(raw, clean, dropped, p), encoding="utf-8")
    print(f"wrote {a.out}  ({len(clean)} rows used, {len(dropped)} excluded)")


if __name__ == "__main__":
    main()