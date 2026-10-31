"""CA's profile over a fight, drawn as charts: one HTML page, no libraries.

    python -m Plugins.ca_plot <combat log> [out.html]          (from Server/)

Runs the log through the teammate's CharacteristicAnalyzer package, as
ca_feed.py does, and writes <log name>_ca.html next to the log (or to
out.html). Open it in any browser. Per player, two charts:

    the three traits, turn by turn, from -1 to +1:
        A  +1 all attack ... -1 all Block
        S  +1 all Powers (scaling) ... -1 all now-cards
        T  +1 all for the team ... -1 all for yourself
    CA's confidence in each, 0 to 100% - its own chart, since it is another
    scale (one axis per chart).

Hover or arrow-key a chart for every value at that turn; "Table" under each
player lists them all. The page also says whether CA and our analyzer agreed.
"""
import html
import json
import os
import sys

from .ca_feed import KEYS, feed

TRAITS = (
    ("A", "attack", "Block"),
    ("S", "Powers", "now-cards"),
    ("T", "team", "self"),
)


def chart_data(found, beta):
    """What the page draws: per player, CA's profile each turn."""
    players = []
    worst = 0.0
    for unit_id, rows in found.items():
        turns = []
        for number, theirs, same_beta, _ in rows:
            turns.append(dict({"turn": number}, **{k: round(theirs[k], 4) for k in KEYS}))
            worst = max([worst] + [abs(theirs[k] - same_beta[k]) for k in KEYS])
        players.append({"id": unit_id, "turns": turns})
    return {"beta": beta, "players": players, "agree": worst < 1e-9, "gap": worst,
            "traits": [{"key": k, "plus": plus, "minus": minus} for k, plus, minus in TRAITS]}


def write_html(data, title, path):
    page = PAGE.replace("__TITLE__", html.escape(title))
    # Inside a <script>: "</" must not appear raw, or a name could end the tag.
    page = page.replace("__DATA__", json.dumps(data).replace("</", "<\\/"))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(page)


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CA profile</title>
<style>
:root {
  color-scheme: light;
  --page: #f9f9f7;
  --surface-1: #fcfcfb;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --text-muted: #898781;
  --grid: #e1e0d9;
  --baseline: #c3c2b7;
  --border: rgba(11,11,11,0.10);
  --series-1: #2a78d6;
  --series-2: #eb6834;
  --series-3: #1baf7a;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d;
    --surface-1: #1a1a19;
    --text-primary: #f0efec;
    --text-secondary: #c3c2b7;
    --text-muted: #898781;
    --grid: #2c2c2a;
    --baseline: #383835;
    --border: rgba(255,255,255,0.10);
    --series-1: #3987e5;
    --series-2: #d95926;
    --series-3: #199e70;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d;
  --surface-1: #1a1a19;
  --text-primary: #f0efec;
  --text-secondary: #c3c2b7;
  --text-muted: #898781;
  --grid: #2c2c2a;
  --baseline: #383835;
  --border: rgba(255,255,255,0.10);
  --series-1: #3987e5;
  --series-2: #d95926;
  --series-3: #199e70;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 24px 16px 48px;
  background: var(--page); color: var(--text-primary);
  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif;
}
main { max-width: 860px; margin: 0 auto; }
h1 { font-size: 20px; font-weight: 600; margin: 0 0 4px; overflow-wrap: anywhere; }
h2 { font-size: 16px; font-weight: 600; margin: 0 0 12px; }
h3 { font-size: 13px; font-weight: 600; margin: 16px 0 6px; color: var(--text-secondary); }
.sub { color: var(--text-secondary); margin: 0 0 16px; }
.legend { display: flex; flex-wrap: wrap; gap: 8px 20px; margin: 0 0 20px; color: var(--text-secondary); }
.legend span { display: inline-flex; align-items: center; gap: 8px; }
.key { display: inline-block; width: 16px; height: 2px; border-radius: 1px; }
.card {
  background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 12px; padding: 16px; margin: 0 0 20px;
}
.chart { position: relative; }
.chart svg { display: block; width: 100%; height: auto; overflow: visible; }
.chart svg:focus { outline: none; }
.chart svg:focus-visible { outline: 2px solid var(--series-1); outline-offset: 4px; border-radius: 4px; }
.tip {
  position: absolute; pointer-events: none; display: none; min-width: 132px;
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 8px;
  padding: 8px 10px; box-shadow: 0 4px 16px rgba(0,0,0,0.12); font-size: 12px;
}
.tip .head { color: var(--text-secondary); margin-bottom: 4px; }
.tip .row { display: flex; align-items: center; gap: 8px; white-space: nowrap; }
.tip .row b { font-variant-numeric: tabular-nums; color: var(--text-primary); min-width: 44px; }
.tip .row span:last-child { color: var(--text-secondary); }
details { margin-top: 12px; }
summary { cursor: pointer; color: var(--text-secondary); }
table { border-collapse: collapse; margin-top: 8px; font-variant-numeric: tabular-nums; font-size: 13px; }
th, td { padding: 4px 10px; text-align: right; border-bottom: 1px solid var(--grid); }
th { color: var(--text-secondary); font-weight: 600; }
.note { color: var(--text-muted); font-size: 12px; }
</style>
</head>
<body>
<main>
  <h1>__TITLE__</h1>
  <p class="sub" id="sub"></p>
  <div class="legend" id="legend"></div>
  <div id="players"></div>
  <p class="note">A, S and T run from -1 to +1: +1 is all of the first side, -1 all of the second.
  Confidence is how sure CA is of each, from how many turns it has seen.</p>
</main>
<script>
const DATA = __DATA__;
const COLORS = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];
const SVG = "http://www.w3.org/2000/svg";
const H = 220, M = {left: 44, right: 96, top: 14, bottom: 30};

function el(tag, attrs, parent) {
  const node = document.createElementNS(SVG, tag);
  for (const k in attrs) node.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(node);
  return node;
}
function div(cls, parent, text) {
  const node = document.createElement("div");
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  if (parent) parent.appendChild(node);
  return node;
}
const signed = v => Math.abs(v) < 0.005 ? "0.00" : (v > 0 ? "+" : "−") + Math.abs(v).toFixed(2);
const percent = v => Math.round(v * 1000) / 10 + "%";

function niceTop(max) {
  const steps = [0.05, 0.1, 0.2, 0.25, 0.5, 1];
  return steps.find(s => s >= max) || 1;
}

// One line chart: `series` is [{key, label, color}], each row has row[key].
function lineChart(parent, rows, series, opts) {
  const box = div("chart", parent);
  // Drawn at the width it is shown at, so the text keeps its size on a phone.
  const W = Math.max(300, Math.round(box.clientWidth));
  const svg = el("svg", {viewBox: `0 0 ${W} ${H}`, role: "img", tabindex: "0",
                         "aria-label": opts.aria}, box);
  const tip = div("tip", box);
  const iw = W - M.left - M.right, ih = H - M.top - M.bottom;
  const turns = rows.map(r => r.turn);
  const t0 = turns[0], t1 = turns[turns.length - 1];
  const x = t => t1 === t0 ? M.left + iw / 2 : M.left + (t - t0) / (t1 - t0) * iw;
  const y = v => M.top + (opts.max - v) / (opts.max - opts.min) * ih;

  for (const tick of opts.ticks) {
    const strong = tick === 0 && opts.min < 0;
    el("line", {x1: M.left, x2: M.left + iw, y1: y(tick), y2: y(tick),
                stroke: strong ? "var(--baseline)" : "var(--grid)", "stroke-width": 1}, svg);
    const label = el("text", {x: M.left - 8, y: y(tick) + 4, "text-anchor": "end",
                              "font-size": 11, fill: "var(--text-muted)"}, svg);
    label.textContent = opts.format(tick);
  }
  // As many turn labels as fit, about 56px apart, counted back from the
  // last turn so the latest one is always labelled.
  const every = Math.max(1, Math.ceil(turns.length / Math.max(2, Math.floor(iw / 56))));
  const last = turns.length - 1;
  turns.forEach((t, i) => {
    if ((last - i) % every) return;
    const label = el("text", {x: x(t), y: H - 10, "text-anchor": "middle",
                              "font-size": 11, fill: "var(--text-muted)"}, svg);
    label.textContent = "turn " + t;
  });

  const ends = [];
  series.forEach(s => {
    const d = rows.map((r, i) => (i ? "L" : "M") + x(r.turn).toFixed(1) + " " + y(r[s.key]).toFixed(1)).join(" ");
    el("path", {d, fill: "none", stroke: s.color, "stroke-width": 2,
                "stroke-linejoin": "round", "stroke-linecap": "round"}, svg);
    const last = rows[rows.length - 1];
    ends.push({s, x: x(last.turn), y: y(last[s.key]), v: last[s.key]});
  });
  // End labels: spread apart where lines end close together, a leader line
  // back to each end dot that had to move.
  const placed = ends.slice().sort((a, b) => a.y - b.y);
  for (let i = 1; i < placed.length; i++) {
    placed[i].ly = Math.max(placed[i].y, (placed[i - 1].ly ?? placed[i - 1].y) + 14);
  }
  placed[0].ly = placed[0].y;
  const overflow = placed[placed.length - 1].ly - (M.top + ih + 4);
  if (overflow > 0) placed.forEach(p => p.ly -= overflow);
  placed.forEach(p => {
    const lx = p.x + 14;
    if (Math.abs(p.ly - p.y) > 2) {
      el("line", {x1: p.x + 5, y1: p.y, x2: lx - 3, y2: p.ly, stroke: "var(--text-muted)", "stroke-width": 1}, svg);
    }
    el("circle", {cx: p.x, cy: p.y, r: 4, fill: p.s.color, stroke: "var(--surface-1)", "stroke-width": 2}, svg);
    const label = el("text", {x: lx, y: p.ly + 4, "font-size": 12, fill: "var(--text-secondary)"}, svg);
    label.textContent = p.s.key + " " + opts.format(p.v);
  });

  // Crosshair: snaps to the nearest turn; every series in one readout.
  const cross = el("line", {y1: M.top, y2: M.top + ih, stroke: "var(--baseline)",
                            "stroke-width": 1, visibility: "hidden"}, svg);
  const dots = series.map(s => el("circle", {r: 4, fill: s.color, stroke: "var(--surface-1)",
                                             "stroke-width": 2, visibility: "hidden"}, svg));
  const hit = el("rect", {x: M.left - 12, y: M.top, width: iw + 24, height: ih,
                          fill: "transparent"}, svg);
  let at = -1;
  function show(i) {
    at = i;
    const r = rows[i], cx = x(r.turn);
    cross.setAttribute("x1", cx); cross.setAttribute("x2", cx);
    cross.setAttribute("visibility", "visible");
    dots.forEach((dot, k) => {
      dot.setAttribute("cx", cx); dot.setAttribute("cy", y(r[series[k].key]));
      dot.setAttribute("visibility", "visible");
    });
    tip.replaceChildren();
    div("head", tip, "Turn " + r.turn);
    series.forEach(s => {
      const row = div("row", tip);
      const key = document.createElement("span");
      key.className = "key"; key.style.background = s.color; row.appendChild(key);
      const value = document.createElement("b");
      value.textContent = opts.format(r[s.key]); row.appendChild(value);
      const name = document.createElement("span");
      name.textContent = s.label; row.appendChild(name);
    });
    tip.style.display = "block";
    const scale = box.clientWidth / W;
    const left = cx * scale + 12;
    tip.style.left = Math.min(left, box.clientWidth - tip.offsetWidth) + "px";
    tip.style.top = (M.top * scale) + "px";
  }
  function hide() {
    at = -1;
    cross.setAttribute("visibility", "hidden");
    dots.forEach(dot => dot.setAttribute("visibility", "hidden"));
    tip.style.display = "none";
  }
  function nearest(evt) {
    const pt = svg.createSVGPoint();
    pt.x = evt.clientX; pt.y = evt.clientY;
    const local = pt.matrixTransform(svg.getScreenCTM().inverse());
    let best = 0;
    rows.forEach((r, i) => { if (Math.abs(x(r.turn) - local.x) < Math.abs(x(rows[best].turn) - local.x)) best = i; });
    return best;
  }
  hit.addEventListener("pointermove", e => show(nearest(e)));
  hit.addEventListener("pointerleave", hide);
  svg.addEventListener("focus", () => show(at < 0 ? rows.length - 1 : at));
  svg.addEventListener("blur", hide);
  svg.addEventListener("keydown", e => {
    if (e.key === "ArrowLeft") { show(Math.max(0, at - 1)); e.preventDefault(); }
    if (e.key === "ArrowRight") { show(Math.min(rows.length - 1, at + 1)); e.preventDefault(); }
  });
}

const traits = DATA.traits.map((t, i) => ({
  key: t.key, color: COLORS[i], label: t.key + "  " + t.plus + " (+) vs " + t.minus + " (−)"}));
const confidence = DATA.traits.map((t, i) => ({
  key: "c" + t.key, color: COLORS[i], label: "confidence in " + t.key}));

document.getElementById("sub").textContent =
  DATA.players.length + (DATA.players.length === 1 ? " player" : " players") +
  " · CA beta " + DATA.beta + " · " +
  (DATA.agree ? "our analyzer gives the same numbers"
              : "our analyzer DIFFERS by up to " + DATA.gap.toPrecision(2));
const legend = document.getElementById("legend");
traits.forEach(s => {
  const item = document.createElement("span");
  const key = document.createElement("span");
  key.className = "key"; key.style.background = s.color;
  item.appendChild(key);
  item.appendChild(document.createTextNode(s.label));
  legend.appendChild(item);
});

// One top for every player's confidence chart, so they compare at a glance.
let cmax = 0;
DATA.players.forEach(p => p.turns.forEach(r => confidence.forEach(s => cmax = Math.max(cmax, r[s.key]))));
const ctop = niceTop(cmax);

const host = document.getElementById("players");
function render() {
host.replaceChildren();
DATA.players.forEach(p => {
  const card = div("card", host);
  const h = document.createElement("h2");
  h.textContent = p.id + " · " + p.turns.length + (p.turns.length === 1 ? " turn" : " turns");
  card.appendChild(h);
  const h1 = document.createElement("h3"); h1.textContent = "Traits"; card.appendChild(h1);
  lineChart(card, p.turns, traits, {min: -1, max: 1, ticks: [-1, -0.5, 0, 0.5, 1], format: signed,
                                    aria: p.id + ": traits A, S, T by turn"});
  const h2 = document.createElement("h3"); h2.textContent = "Confidence"; card.appendChild(h2);
  lineChart(card, p.turns, confidence, {min: 0, max: ctop, ticks: [0, ctop / 2, ctop], format: percent,
                                        aria: p.id + ": CA's confidence in each trait by turn"});
  const details = document.createElement("details");
  const summary = document.createElement("summary"); summary.textContent = "Table";
  details.appendChild(summary);
  const table = document.createElement("table");
  const head = table.insertRow();
  ["Turn", "A", "S", "T", "conf. A", "conf. S", "conf. T"].forEach(t => {
    const th = document.createElement("th"); th.textContent = t; head.appendChild(th);
  });
  p.turns.forEach(r => {
    const row = table.insertRow();
    row.insertCell().textContent = r.turn;
    ["A", "S", "T"].forEach(k => row.insertCell().textContent = signed(r[k]));
    ["cA", "cS", "cT"].forEach(k => row.insertCell().textContent = percent(r[k]));
  });
  details.appendChild(table);
  card.appendChild(details);
});
}
render();
let drawnWidth = host.clientWidth, pending = 0;
window.addEventListener("resize", () => {
  clearTimeout(pending);
  pending = setTimeout(() => {
    if (host.clientWidth !== drawnWidth) { drawnWidth = host.clientWidth; render(); }
  }, 150);
});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    log = sys.argv[1]
    found, beta = feed(log)
    if not found:
        sys.exit("No scored turns in that log.")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(log)[0] + "_ca.html"
    write_html(chart_data(found, beta), "CA profile - " + os.path.basename(log), out)
    print("written:", os.path.abspath(out))
