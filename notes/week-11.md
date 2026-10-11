# Week 11: observability and drift (in progress)

Roadmap items: OpenTelemetry to Application Insights (a span per model call with latency, tokens, cost, retrieval hits); a dashboard and alerts (p95 latency, error rate, cost per day, groundedness); user feedback stored with a trace id; drift (query and embedding shift, retrieval-quality decay, PSI and KS for the classical model); **deliverable: a live Application Insights dashboard, with a screenshot in the README.**

## Status against the roadmap

| Item | Status |
|---|---|
| OpenTelemetry spans to Application Insights | **Code done and tested; not yet live in production.** Needs one app setting and a deploy (see "Not done") |
| Application Insights, workspace, dashboard, alerts | **Deployed and checked in Azure.** The dashboard has **not been seen rendering**, and its queries have not yet run against real data |
| Alerts: p95 latency, error rate, cost per day, groundedness | **Two of four, as free metric alerts** (average latency, failed requests). p95, cost per day and answer support are on the dashboard only |
| Feedback stored with a trace id | **Done in code**: the trace id is the request id, and a rating is logged with it. Not durable storage (see below) |
| Drift: PSI and KS for the classical model | **Done** (real data, with a control) |
| Drift: query and embedding shift, retrieval-quality decay | **Done** (real embeddings with a null; a controlled decay experiment) |
| Deliverable: live dashboard with a README screenshot | **Not done** |

## What was built

| Piece | What it does |
|---|---|
| `telemetry.py` | Spans via OpenTelemetry, a no-op when it is not installed or not configured. One span per model call (`llm.chat`, `embedding`) with the deployment, `gen_ai.usage.input_tokens` and `output_tokens`, and an **estimated** cost; a retrieval span with hits, document ids, best score and whether the semantic ranker fell back; spans for the two guard stages; per-request totals put on the request span |
| `api.py` | The trace id becomes the request id (so a rating sent later joins its trace). The request span carries tokens, cost, refused or not, the reason (a fixed phrase or a guard code), question length, source count. `/feedback` logs a trace record with the request id, the rating and whether there was a comment, **never the comment text** |
| `guardrails/output.py` | Now reports the weakest sentence's support (`payrag.support_min`), the cheap online proxy for groundedness |
| `infra/week11.bicep` | Log Analytics workspace with a **0.1 GB daily cap**; workspace-based Application Insights with **key authentication disabled**; the web app's identity as the only publisher; the workbook; an action group; two metric alerts |
| `infra/week11-workbook.json` | 11 queries: at a glance, requests and failures, latency p50/p95/p99, cost and tokens per day, why answers were refused, answer support, model-call latency, retrieval quality, feedback, drift signals, telemetry volume |
| `drift.py` | PSI, categorical PSI, two-sample KS (checked against SciPy), embedding drift (centroid distance and a classifier AUC), `quality_decay` |

Cost safety, from Microsoft's pricing page (fetched 2026-10-12): the first 5 GB a month of Log Analytics ingestion per billing account is free; the first 10 monitored metric time series and 1,000 alert emails a month are free. The unit prices on that page are masked, so I rely only on those free quantities. This service sends kilobytes, and the daily cap bounds the worst case. **Not verified:** whether workbooks are free (no charge is listed, but I did not find a statement), and the real telemetry volume (it is zero until production is switched on). The cost shown on the dashboard is **tokens times list prices written in `telemetry.py` on 2026-10-12; they were not read from the invoice**, so treat it as an estimate and compare it with Cost Management.

Verified from Azure itself after deployment: the workspace is pay-as-you-go with 30-day retention and the cap; the component has local authentication disabled and ingestion mode LogAnalytics; the web app's identity holds "Monitoring Metrics Publisher" on it; both alerts are enabled with the intended metric, operator and threshold.

## The image was tested before it could reach production

The deploy job switches the app to the new image before it checks health, so an image that fails to boot would take the live app down until fixed. The telemetry package adds 27 libraries (no existing pin moved; the image grew from 492 MB to 504 MB). I built it locally and started it twice, once with telemetry unset and once with a deliberately fake connection string: both stayed healthy, served the page, still returned 401 without the key, and logged no errors. A telemetry failure also cannot stop the app (`start_telemetry` catches it, and a test proves it).

## Drift results

### The Week 3 fraud model across two days (`classical_ml/reports/week11_drift.md`)

Reference = the first 142,403 transactions by time (269 fraud); current = the next 142,404 (223 fraud).

- **Feature drift is large.** 8 of 29 features have a PSI above 0.25 (V1 1.43, V3 1.38, V28 1.01 are the biggest), 7 are moderate, 14 stable.
- **The control is quiet.** Two random halves of the same data: 29 of 29 stable, largest PSI 0.0002. So the day-to-day differences are real, and the detectors do not fire on noise. Why the two days differ was not investigated.
- **Yet the model did not get worse.** The score distribution barely moved (PSI 0.063, stable) and PR-AUC went from 0.816 (95% interval 0.713 to 0.909) to 0.804 (0.751 to 0.857): inside the noise, so not flagged as decay.

The lesson is the one the dashboard is built around: **input drift on its own is a poor stand-in for quality decay.** It tells you to look; it does not tell you the model is wrong.

### Do the assistant's questions drift? (`capstone/evals/results/drift.md`)

Real Azure OpenAI embeddings. Reference = the 48 development questions. Each set is read against a **null**: the same measurement between two random halves of the reference.

| Set | n | Distinguishable from the reference? |
|---|---|---|
| Held-out questions | 14 | no |
| Corpus-update questions | 6 | no |
| Independent (web-sourced wording) | 44 | no |
| Off-topic questions | 18 | no |
| **User attacks** | 68 | **yes** (AUC 0.97, null 95th percentile 0.64) |
| **Compound attacks** | 10 | **yes** (AUC 0.98, null 0.70) |

So the detector fires on a gross change (attack traffic) and stays quiet on mild ones. **It is also low-powered**: with sets of 6 to 44, "no" means "not detectable here", not "the same". Also: the null AUC sits below 0.5 for small sets (a known artefact of cross-validating tiny samples), which is why the null, and not 0.5, is the yardstick. **PSI on question length is unusable at these sizes**: for six questions, random draws from the same set give a PSI of up to 5.95, and the observed 5.99 is at that level.

### Would we notice retrieval quality decaying? (same file)

Offline BM25, baseline Hit@3 = 0.725 on 69 answerable questions; a document is removed from the index (a stand-in for stale data), the questions never change (input drift is zero by construction), and a fall of more than 3 questions counts as decay.

- **Removing 10 of the 11 documents is flagged as decay** (drops of 0.058 to 0.101). The 11th, `rbi_authentication_directions_2025`, drops 0.014 and is not flagged. A document that answers 4 questions costs exactly 4 of 69.
- **The label-free signal (PSI of each question's best retrieval score) is weak:** only 4 of the 10 flagged decays have a PSI above 0.1 (`faqs`, `upi_overview`, `cfpb_credit_card_disputes`, `pci_dss_overview`). The other 6 read as "stable" while Hit@3 fell by 0.058 to 0.072.

So catching retrieval decay needs a **labelled probe set run on a schedule** (the golden set does this), not only watching scores.

## Limits

- No production telemetry exists yet, so the dashboard, the alerts and the cost line are untested against real data.
- Alerts: metric alerts cannot use percentiles, so there is no p95 alert; a p95 or cost alert would be a paid log-search rule, which I did not create. No alert has been seen to fire, and the action group has **no email address** (see below).
- The groundedness figure is a lexical proxy (see `guardrails/support.py` for what it cannot see), not a model-judged score.
- Feedback is logged to Application Insights as a trace record; it is not a database, it follows the 30-day retention, and the in-memory store in the app still loses ratings on restart.
- Drift on the fraud data is day 1 against day 2 of one card issuer's 2013 data (anonymised features); it says nothing about real traffic.
- The retrieval-decay experiment simulates stale data by deleting a document; it is not an observed decay, and it uses the offline retriever, not the Azure index.

## Not done and open

- [ ] **Turn telemetry on in production.** Needs the connection string as an app setting (`APPLICATIONINSIGHTS_CONNECTION_STRING`, passed at deploy time, not stored in the repo) and a push, which deploys the new image. Both change the live app; neither is done.
- [ ] **Look at the dashboard and fix its queries.** After telemetry flows: run each query against real data, then open the workbook in the portal and take the README screenshot. I cannot sign in to the portal, so the screenshot needs you or a signed-in browser.
- [ ] **Alert emails.** The action group has no receivers; alerts will show in the portal only. Add an address with `AZURE_W11_ALERT_EMAIL` and redeploy `week11.bicep` (1,000 emails a month are free).
- [ ] **A p95 alert and a cost-per-day alert** would need a log-search alert rule, which is billed (the price is masked on Microsoft's page, so I do not know it).
- [ ] Durable feedback storage (a table or a database) if ratings must survive the 30-day retention.
- [ ] Delete `rg-payments-rag-w11` when finished.
