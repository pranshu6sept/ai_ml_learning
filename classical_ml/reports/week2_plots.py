# ruff: noqa: E501  (the HTML/JS template below has long lines)
"""Week 2 plots: ROC, precision-recall, threshold and cost curves as one standalone HTML page.

Models are fitted on the training split and drawn on the validation split. The test split is
not touched. Per-fold CV scores are read from week2_cv.md if it exists.

Run from the repo root:  uv run python classical_ml/reports/week2_plots.py
Then open classical_ml/reports/week2_plots.html in a browser (loads Chart.js from a CDN).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)
from week2_metrics import COST_FALSE_ALARM, COST_MISSED_FRAUD, DATA, models

from classical_ml.data import train_val_test_split

HERE = Path(__file__).resolve().parent
OUT = HERE / "week2_plots.html"
MAX_POINTS = 250
COLORS = ["#2a6fdb", "#e8833a", "#7a5cc7", "#1f9d6b"]


def thin(*arrays: np.ndarray) -> list[list[float]]:
    """Keep at most MAX_POINTS evenly spaced points so the page stays small."""
    n = len(arrays[0])
    idx = np.unique(np.linspace(0, n - 1, min(n, MAX_POINTS)).astype(int))
    return [np.round(a[idx].astype(float), 5).tolist() for a in arrays]


def xy(x: list[float], y: list[float]) -> list[dict[str, float]]:
    return [{"x": a, "y": b} for a, b in zip(x, y, strict=True)]


def cv_folds() -> dict[str, list[float]]:
    path = HERE / "week2_cv.md"
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and re.fullmatch(r"(\d\.\d{3} ?){5}", cells[2]):
            out[cells[0]] = [float(v) for v in cells[2].split()]
    return out


def build_payload() -> dict[str, Any]:
    df = pd.read_csv(DATA)
    train, val, _ = train_val_test_split(df, target="Class")
    x_train, y_train = train.drop(columns="Class"), train["Class"]
    x_val, y_val = val.drop(columns="Class"), val["Class"]
    y = y_val.to_numpy()

    payload: dict[str, Any] = {
        "n_val": len(y),
        "frauds": int(y.sum()),
        "rate": float(y.mean()),
        "cost_miss": COST_MISSED_FRAUD,
        "cost_alarm": COST_FALSE_ALARM,
        "models": [],
        "cv": cv_folds(),
    }
    for (name, build), color in zip(models().items(), COLORS, strict=True):
        print(f"fitting {name} ...", flush=True)
        p = build().fit(x_train, y_train).predict_proba(x_val)[:, 1]

        fpr, tpr, _ = roc_curve(y, p)
        prec, rec, thr = precision_recall_curve(y, p)

        order = np.argsort(-p)
        hits = y[order]
        k = np.arange(1, len(y) + 1)
        caught = np.cumsum(hits)
        cost = COST_MISSED_FRAUD * (hits.sum() - caught) + COST_FALSE_ALARM * (k - caught)
        best_k = int(np.argmin(cost)) + 1
        keep = min(len(y), 1500)

        entry: dict[str, Any] = {
            "name": name,
            "color": color,
            "roc_auc": float(roc_auc_score(y, p)),
            "pr_auc": float(average_precision_score(y, p)),
            "roc": xy(*thin(fpr, tpr)),
            "pr": xy(*thin(rec[:-1], prec[:-1])),
            "cost": xy(*thin(k[:keep].astype(float), cost[:keep].astype(float))),
            "best_k": best_k,
            "best_cost": float(cost[best_k - 1]),
            "best_precision": float(caught[best_k - 1] / best_k),
            "best_recall": float(caught[best_k - 1] / hits.sum()),
        }
        if name == "Logistic regression":
            t, pr_t, rc_t = thin(thr, prec[:-1], rec[:-1])
            entry["thr_precision"] = xy(t, pr_t)
            entry["thr_recall"] = xy(t, rc_t)
        payload["models"].append(entry)
    return payload


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Week 2: fraud model curves</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root { --bg:#fafafa; --card:#fff; --text:#1c1f26; --muted:#5b6270; --grid:#e3e6ec; --line:#d3d7df; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#14161b; --card:#1c1f26; --text:#e9ebf0; --muted:#9aa1ae; --grid:#2d323c; --line:#3a404c; }
  }
  * { box-sizing: border-box; }
  body { margin:0; padding:24px 16px 48px; background:var(--bg); color:var(--text);
         font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif; }
  main { max-width:1100px; margin:0 auto; }
  h1 { font-size:24px; margin:0 0 4px; }
  .sub { color:var(--muted); margin:0 0 24px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,480px),1fr)); gap:16px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px; }
  .card h2 { font-size:16px; margin:0 0 2px; }
  .card p { color:var(--muted); font-size:13px; margin:0 0 10px; }
  .box { position:relative; height:340px; }
  table { width:100%; border-collapse:collapse; font-size:13px; margin-top:6px; }
  th,td { text-align:right; padding:5px 8px; border-bottom:1px solid var(--grid); }
  th:first-child,td:first-child { text-align:left; }
  .dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; }
  .wide { grid-column:1 / -1; }
</style>
</head>
<body>
<main>
  <h1>Fraud model curves</h1>
  <p class="sub" id="sub"></p>
  <div class="grid">
    <section class="card"><h2>ROC curve</h2>
      <p>True-positive rate vs false-positive rate. Dashed line is chance (AUC 0.5). The x-axis divides
         false alarms by all legitimate transactions, so every curve hugs the top-left corner.</p>
      <div class="box"><canvas id="roc"></canvas></div></section>
    <section class="card"><h2>Precision-recall curve</h2>
      <p>Precision vs recall. Dashed line is chance: the fraud rate. This is where the models actually differ.</p>
      <div class="box"><canvas id="pr"></canvas></div></section>
    <section class="card"><h2>Threshold dial (plain logistic regression)</h2>
      <p>Lowering the threshold raises recall and lowers precision.</p>
      <div class="box"><canvas id="thr"></canvas></div></section>
    <section class="card"><h2>Total cost by number of transactions flagged</h2>
      <p id="costnote"></p>
      <div class="box"><canvas id="cost"></canvas></div></section>
    <section class="card wide" id="cvcard"><h2>PR-AUC per fold (5-fold cross-validation, 492 frauds)</h2>
      <p>Same folds for every model. Boosting is best on every fold.</p>
      <div class="box"><canvas id="cv"></canvas></div></section>
    <section class="card wide"><h2>Scores on the validation split</h2>
      <table id="tbl"></table></section>
  </div>
</main>
<script>
const D = __DATA__;
const css = getComputedStyle(document.documentElement);
const v = n => css.getPropertyValue(n).trim();
Chart.defaults.color = v('--muted');
Chart.defaults.borderColor = v('--grid');
Chart.defaults.font.family = 'system-ui,-apple-system,Segoe UI,sans-serif';

document.getElementById('sub').textContent =
  `${D.n_val.toLocaleString()} validation transactions, ${D.frauds} frauds (${(D.rate*100).toFixed(2)}%). ` +
  `Models fitted on the training split only; the test split is not used here.`;

const axis = (title, extra = {}) => ({ type:'linear', title:{display:true, text:title}, ...extra });
const line = (m, data, label) => ({ label: label || m.name, data, borderColor:m.color, backgroundColor:m.color,
  borderWidth:2, pointRadius:0, tension:0, parsing:false });
const base = (xt, yt, xo = {}, yo = {}) => ({ responsive:true, maintainAspectRatio:false, animation:false,
  interaction:{mode:'nearest', intersect:false},
  scales:{ x:axis(xt, xo), y:axis(yt, yo) },
  plugins:{ legend:{ position:'bottom', labels:{ usePointStyle:true, boxWidth:8 } } } });
const dashed = (data, label) => ({ label, data, borderColor:v('--muted'), borderDash:[6,5], borderWidth:1.5,
  pointRadius:0, parsing:false });

new Chart('roc', { type:'line',
  data:{ datasets:[ ...D.models.map(m => line(m, m.roc, `${m.name} (AUC ${m.roc_auc.toFixed(3)})`)),
                    dashed([{x:0,y:0},{x:1,y:1}], 'Chance (0.500)') ] },
  options: base('False-positive rate', 'True-positive rate (recall)', {min:0,max:1}, {min:0,max:1}) });

new Chart('pr', { type:'line',
  data:{ datasets:[ ...D.models.map(m => line(m, m.pr, `${m.name} (PR-AUC ${m.pr_auc.toFixed(3)})`)),
                    dashed([{x:0,y:D.rate},{x:1,y:D.rate}], `Chance (${D.rate.toFixed(4)})`) ] },
  options: base('Recall', 'Precision', {min:0,max:1}, {min:0,max:1}) });

const lr = D.models[0];
new Chart('thr', { type:'line',
  data:{ datasets:[ { ...line(lr, lr.thr_precision, 'Precision'), borderColor:'#e8833a', backgroundColor:'#e8833a' },
                    { ...line(lr, lr.thr_recall, 'Recall'), borderColor:'#2a6fdb', backgroundColor:'#2a6fdb' } ] },
  options: base('Threshold (flag when P(fraud) >= threshold)', 'Score', {type:'logarithmic', min:0.001, max:1}, {min:0,max:1}) });

document.getElementById('costnote').textContent =
  `A missed fraud costs $${D.cost_miss}, a false alarm $${D.cost_alarm}. Dots mark each model's cheapest point.`;
new Chart('cost', { type:'line',
  data:{ datasets:[ ...D.models.map(m => line(m, m.cost)),
    ...D.models.map(m => ({ label:`${m.name} best`, data:[{x:m.best_k, y:m.best_cost}], showLine:false,
        pointRadius:5, backgroundColor:m.color, borderColor:m.color, parsing:false })) ] },
  options: { ...base('Transactions flagged (highest scores first)', 'Total cost ($)', {min:0,max:1500}, {min:0}),
    plugins:{ legend:{ position:'bottom', labels:{ usePointStyle:true, boxWidth:8,
      filter: it => !it.text.endsWith(' best') } } } } });

const cvNames = Object.keys(D.cv);
if (cvNames.length) {
  const colorOf = n => (D.models.find(m => n.startsWith(m.name.split(' (')[0])) || {color:'#888'}).color;
  new Chart('cv', { type:'bar',
    data:{ labels:[1,2,3,4,5].map(i => 'Fold ' + i),
      datasets: cvNames.map(n => ({ label:n, data:D.cv[n], backgroundColor:colorOf(n) })) },
    options:{ responsive:true, maintainAspectRatio:false, animation:false,
      scales:{ y:{ min:0.6, max:0.95, title:{display:true, text:'PR-AUC'} } },
      plugins:{ legend:{ position:'bottom', labels:{ usePointStyle:true, boxWidth:8 } } } } });
} else {
  document.getElementById('cvcard').style.display = 'none';
}

document.getElementById('tbl').innerHTML =
  '<tr><th>Model</th><th>ROC-AUC</th><th>PR-AUC</th><th>Cheapest: flagged</th><th>Precision</th><th>Recall</th><th>Cost</th></tr>' +
  D.models.map(m => `<tr><td><span class="dot" style="background:${m.color}"></span>${m.name}</td>` +
    `<td>${m.roc_auc.toFixed(3)}</td><td>${m.pr_auc.toFixed(3)}</td><td>${m.best_k}</td>` +
    `<td>${m.best_precision.toFixed(3)}</td><td>${m.best_recall.toFixed(3)}</td>` +
    `<td>$${Math.round(m.best_cost).toLocaleString()}</td></tr>`).join('');
</script>
</body>
</html>
"""


def main() -> None:
    payload = build_payload()
    OUT.write_text(PAGE.replace("__DATA__", json.dumps(payload)), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
