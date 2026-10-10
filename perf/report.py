"""Build the performance report from perf/run.sh output.

Inputs (per stage N = number of concurrent users, in the results folder):
  uN_stats.csv, uN_stats_history.csv, uN_failures.csv  (Locust)
  uN_docker_stats.txt                                   (container CPU/RAM samples)
  uN_container.json                                     (OOM / restarts)
Outputs:
  summary.md   - tables (also appended to the GitHub job summary)
  report.html  - self-contained report with charts
"""

import base64
import csv
import html
import io
import json
import os
import re
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "perf-results"
GREEN, DARK, AMBER, RED, GREY = "#16A34A", "#0E5E2D", "#D97706", "#DC2626", "#64748B"

# Service-level objectives used for the verdict column
SLO_P95_MS = 1000  # 95% of requests answered within 1 s
SLO_FAIL_PCT = 1.0  # fewer than 1% failed requests


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def num(value, default=0.0):
    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return default


_UNITS = {
    "b": 1,
    "kib": 1024,
    "kb": 1000,
    "mib": 1024**2,
    "mb": 1000**2,
    "gib": 1024**3,
    "gb": 1000**3,
}


def to_mib(text):
    m = re.match(r"\s*([\d.]+)\s*([a-zA-Z]+)", text or "")
    if not m:
        return 0.0
    return float(m.group(1)) * _UNITS.get(m.group(2).lower(), 1) / 1024**2


def load_stage(n):
    stats = read_csv(os.path.join(OUT, f"u{n}_stats.csv"))
    agg = next((r for r in stats if r.get("Name") == "Aggregated"), {})
    endpoints = [r for r in stats if r.get("Name") != "Aggregated"]
    history = [
        r
        for r in read_csv(os.path.join(OUT, f"u{n}_stats_history.csv"))
        if r.get("Name") == "Aggregated"
    ]
    failures = read_csv(os.path.join(OUT, f"u{n}_failures.csv"))

    samples = []
    path = os.path.join(OUT, f"u{n}_docker_stats.txt")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8", errors="ignore"):
            ts, _, payload = line.partition("|")
            m = re.search(r"\{.*\}", payload)  # drop terminal control codes around the JSON
            if not m:
                continue
            try:
                d = json.loads(m.group(0))
            except ValueError:
                continue
            samples.append(
                {
                    "t": num(ts),
                    "cpu": num(d.get("CPUPerc")),
                    "mem": to_mib((d.get("MemUsage") or "").split("/")[0]),
                    "mem_limit": to_mib((d.get("MemUsage") or "/").split("/")[1]),
                    "pids": num(d.get("PIDs")),
                }
            )
    container = {}
    cpath = os.path.join(OUT, f"u{n}_container.json")
    if os.path.exists(cpath):
        try:
            container = json.load(open(cpath, encoding="utf-8"))
        except ValueError:
            container = {}

    total = num(agg.get("Request Count"))
    failed = num(agg.get("Failure Count"))
    fail_pct = 100 * failed / total if total else 0.0
    p95 = num(agg.get("95%"))
    cpus = [s["cpu"] for s in samples] or [0]
    mems = [s["mem"] for s in samples] or [0]
    pids = [s["pids"] for s in samples] or [0]

    if container.get("oom_killed") or not total:
        verdict = "❌ crashed / no traffic"
    elif fail_pct < SLO_FAIL_PCT and p95 <= SLO_P95_MS:
        verdict = "✅ healthy"
    elif fail_pct < 5 and p95 <= 3 * SLO_P95_MS:
        verdict = "⚠️ degraded"
    else:
        verdict = "❌ overloaded"

    return {
        "users": n,
        "requests": int(total),
        "failed": int(failed),
        "fail_pct": fail_pct,
        "rps": num(agg.get("Requests/s")),
        "p50": num(agg.get("50%")),
        "p95": p95,
        "p99": num(agg.get("99%")),
        "max": num(agg.get("Max Response Time")),
        "cpu_avg": sum(cpus) / len(cpus),
        "cpu_peak": max(cpus),
        "mem_avg": sum(mems) / len(mems),
        "mem_peak": max(mems),
        "mem_limit": max((s["mem_limit"] for s in samples), default=0),
        "threads_peak": int(max(pids)),
        "oom": bool(container.get("oom_killed")),
        "verdict": verdict,
        "endpoints": endpoints,
        "history": history,
        "samples": samples,
        "failures": failures,
    }


def chart_png(fig):
    fig.tight_layout(w_pad=4)  # room for the secondary axes between charts
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def style(ax, title, ylabel):
    ax.set_title(title, fontsize=10, loc="left", color="#0B4523", fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=8, color=GREY)
    ax.grid(axis="y", color="#E5EFE8")
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8, colors=GREY)


def stage_chart(s):
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.4))
    if s["history"]:
        t0 = num(s["history"][0]["Timestamp"])
        t = [num(r["Timestamp"]) - t0 for r in s["history"]]
        ax = axes[0]
        ax.plot(
            t, [num(r["Requests/s"]) for r in s["history"]], color=GREEN, lw=2, label="requests/s"
        )
        ax.plot(
            t, [num(r["Failures/s"]) for r in s["history"]], color=RED, lw=1.5, label="failures/s"
        )
        ax2 = ax.twinx()
        ax2.plot(
            t,
            [num(r["User Count"]) for r in s["history"]],
            color=GREY,
            lw=1,
            ls="--",
            label="users",
        )
        ax2.tick_params(labelsize=8, colors=GREY)
        ax2.spines[["top"]].set_visible(False)
        ax.legend(fontsize=7, loc="upper left", frameon=False)
        style(ax, "Throughput (dashed = users)", "per second")
        ax.set_xlabel("seconds", fontsize=8, color=GREY)

        ax = axes[1]
        ax.plot(t, [num(r["50%"]) for r in s["history"]], color=DARK, lw=1.5, label="median")
        ax.plot(t, [num(r["95%"]) for r in s["history"]], color=AMBER, lw=2, label="p95")
        ax.axhline(SLO_P95_MS, color=RED, lw=1, ls=":", label=f"SLO {SLO_P95_MS} ms")
        ax.legend(fontsize=7, loc="upper left", frameon=False)
        style(ax, "Response time", "ms")
        ax.set_xlabel("seconds", fontsize=8, color=GREY)
    if s["samples"]:
        t0 = s["samples"][0]["t"]
        t = [x["t"] - t0 for x in s["samples"]]
        ax = axes[2]
        ax.plot(t, [x["cpu"] for x in s["samples"]], color=GREEN, lw=2, label="CPU %")
        ax.set_ylim(bottom=0)
        ax2 = ax.twinx()
        ax2.plot(t, [x["mem"] for x in s["samples"]], color=DARK, lw=1.5, ls="--", label="RAM MiB")
        ax2.set_ylim(bottom=0)
        ax2.tick_params(labelsize=8, colors=GREY)
        ax2.set_ylabel("RAM (MiB, dashed)", fontsize=8, color=GREY)
        ax2.spines[["top"]].set_visible(False)
        style(ax, "Container resources", "CPU %")
        ax.set_xlabel("seconds", fontsize=8, color=GREY)
    return chart_png(fig)


def comparison_chart(stages):
    labels = [str(s["users"]) for s in stages]
    fig, axes = plt.subplots(1, 4, figsize=(13, 3))
    for ax, key, title, unit, color in (
        (axes[0], "rps", "Throughput", "requests/s", GREEN),
        (axes[1], "p95", "p95 response time", "ms", AMBER),
        (axes[2], "cpu_peak", "Peak CPU", "% of 1 vCPU", DARK),
        (axes[3], "mem_peak", "Peak RAM", "MiB", GREY),
    ):
        bars = ax.bar(labels, [s[key] for s in stages], color=color, width=0.55)
        ax.bar_label(bars, fmt="%.0f", fontsize=7, color="#0B4523")
        style(ax, title, unit)
        ax.set_xlabel("concurrent users", fontsize=8, color=GREY)
    axes[1].axhline(SLO_P95_MS, color=RED, lw=1, ls=":")
    axes[1].set_yscale("log")  # 50 ms and 20 s on the same chart
    axes[1].set_ylabel("ms (log scale)", fontsize=8, color=GREY)
    return chart_png(fig)


def md_tables(stages, run):
    lines = [
        "## 🚦 Performance test",
        "",
        f"Container limits: **{run.get('cpus')} vCPU / {run.get('memory')} RAM** · "
        f"{run.get('duration_s')} s per stage · commit `{str(run.get('git_sha'))[:7]}` · "
        f"SLO: p95 ≤ {SLO_P95_MS} ms and < {SLO_FAIL_PCT:.0f}% errors",
        "",
        "| Users | Verdict | Requests | Req/s | Errors | Median | p95 | p99 | Max | CPU avg / peak | RAM avg / peak | Threads peak |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in stages:
        lines.append(
            f"| {s['users']} | {s['verdict']} | {s['requests']:,} | {s['rps']:.1f} | {s['fail_pct']:.2f}% "
            f"| {s['p50']:.0f} ms | {s['p95']:.0f} ms | {s['p99']:.0f} ms | {s['max']:.0f} ms "
            f"| {s['cpu_avg']:.0f}% / {s['cpu_peak']:.0f}% | {s['mem_avg']:.0f} / {s['mem_peak']:.0f} MiB "
            f"| {s['threads_peak']} |"
        )
    lines += ["", "Full report with charts: **perf-report** artifact → `report.html`.", ""]
    return "\n".join(lines)


def endpoint_table(s):
    rows = "".join(
        "<tr><td>{}</td><td>{:,}</td><td>{:.1f}</td><td>{}</td><td>{:.0f}</td><td>{:.0f}</td><td>{:.0f}</td></tr>".format(
            html.escape(r["Name"]),
            int(num(r["Request Count"])),
            num(r["Requests/s"]),
            int(num(r["Failure Count"])),
            num(r["50%"]),
            num(r["95%"]),
            num(r["99%"]),
        )
        for r in sorted(s["endpoints"], key=lambda r: -num(r["Request Count"]))
    )
    fails = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            html.escape(f.get("Name", "")),
            html.escape(f.get("Error", "")[:160]),
            html.escape(f.get("Occurrences", "")),
        )
        for f in s["failures"][:10]
    )
    out = (
        "<table><thead><tr><th>Endpoint</th><th>Requests</th><th>Req/s</th><th>Errors</th>"
        "<th>Median ms</th><th>p95 ms</th><th>p99 ms</th></tr></thead><tbody>"
        + rows
        + "</tbody></table>"
    )
    if fails:
        out += (
            "<h4>Errors</h4><table><thead><tr><th>Endpoint</th><th>Error</th><th>Count</th></tr></thead><tbody>"
            + fails
            + "</tbody></table>"
        )
    return out


def main():
    run = json.load(open(os.path.join(OUT, "run.json"), encoding="utf-8"))
    users = [int(u) for u in str(run["users"]).replace(",", " ").split()]
    stages = [load_stage(n) for n in users]

    md = md_tables(stages, run)
    open(os.path.join(OUT, "summary.md"), "w", encoding="utf-8").write(md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(md)
    print(md)

    rows = "".join(
        f"<tr><td>{s['users']}</td><td>{s['verdict']}</td><td>{s['requests']:,}</td><td>{s['rps']:.1f}</td>"
        f"<td>{s['fail_pct']:.2f}%</td><td>{s['p50']:.0f}</td><td>{s['p95']:.0f}</td><td>{s['p99']:.0f}</td>"
        f"<td>{s['cpu_avg']:.0f}% / {s['cpu_peak']:.0f}%</td><td>{s['mem_avg']:.0f} / {s['mem_peak']:.0f}</td>"
        f"<td>{s['threads_peak']}</td></tr>"
        for s in stages
    )
    sections = "".join(
        f"<section><h2>{s['users']} concurrent users <span class='v'>{s['verdict']}</span></h2>"
        f"<img alt='charts for {s['users']} users' src='data:image/png;base64,{stage_chart(s)}'>"
        f"{endpoint_table(s)}<p class='raw'>Raw Locust report: <a href='u{s['users']}_locust.html'>u{s['users']}_locust.html</a></p></section>"
        for s in stages
    )
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>fihi-chifae — performance report</title>
<style>
body{{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:0;padding:1.5rem;color:#1f2d24;background:#f6faf7}}
main{{max-width:1150px;margin:auto}} h1{{color:#0B4523;margin:0 0 .3rem}} h2{{color:#0B4523;font-size:1.1rem;margin:0 0 .6rem}}
.meta{{color:#64748B;font-size:.85rem;margin-bottom:1.2rem}} section,.card{{background:#fff;border:1px solid #E3EDE6;border-radius:12px;padding:1rem 1.2rem;margin-bottom:1.2rem}}
img{{max-width:100%}} table{{border-collapse:collapse;width:100%;font-size:.82rem;margin-top:.6rem}}
th,td{{text-align:right;padding:.35rem .55rem;border-bottom:1px solid #EEF4EF;white-space:nowrap}} th:first-child,td:first-child{{text-align:left}}
th{{color:#64748B;font-weight:600}} .v{{font-size:.85rem;margin-left:.5rem}} .raw{{font-size:.8rem;color:#64748B}} .scroll{{overflow-x:auto}}
</style></head><body><main>
<h1>Performance report</h1>
<p class="meta">Container limits {html.escape(str(run.get('cpus')))} vCPU / {html.escape(str(run.get('memory')))} RAM ·
{run.get('duration_s')} s per stage · started {html.escape(str(run.get('started')))} · commit {html.escape(str(run.get('git_sha'))[:7])} ·
SLO p95 ≤ {SLO_P95_MS} ms and &lt; {SLO_FAIL_PCT:.0f}% errors</p>
<div class="card"><h2>Overview</h2><img alt="comparison across stages" src="data:image/png;base64,{comparison_chart(stages)}">
<div class="scroll"><table><thead><tr><th>Users</th><th>Verdict</th><th>Requests</th><th>Req/s</th><th>Errors</th><th>Median ms</th>
<th>p95 ms</th><th>p99 ms</th><th>CPU avg / peak</th><th>RAM avg / peak (MiB)</th><th>Threads peak</th></tr></thead><tbody>{rows}</tbody></table></div></div>
{sections}
<p class="meta">Shoppers browse the home page, catalog, static files and info page and place orders; one admin keeps the
dashboard, orders and archive open. CPU % is relative to one core (100% = 1 vCPU fully used).</p>
</main></body></html>"""
    open(os.path.join(OUT, "report.html"), "w", encoding="utf-8").write(page)
    print(f"report written to {os.path.join(OUT, 'report.html')}")


if __name__ == "__main__":
    main()
