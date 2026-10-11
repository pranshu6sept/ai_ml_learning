# Week 11: drift in the fraud data between day 1 and day 2

Reference = the first 142,403 transactions by time (269 fraud); current = the next 142,404 (223 fraud). Model = the Week 3 LightGBM settings, trained on 80% of the reference. One run; no production traffic exists, so this shows what the detectors report on real data, not that the world changed.

## Feature drift (top 10 by PSI of 29)

| Feature | PSI | Verdict | KS gap | KS p-value |
|---|---|---|---|---|
| V1 | 1.430 | major | 0.416 | 0.0e+00 |
| V3 | 1.384 | major | 0.511 | 0.0e+00 |
| V28 | 1.014 | major | 0.356 | 0.0e+00 |
| V25 | 0.429 | major | 0.292 | 0.0e+00 |
| V15 | 0.379 | major | 0.271 | 0.0e+00 |
| V5 | 0.345 | major | 0.265 | 0.0e+00 |
| V22 | 0.327 | major | 0.215 | 0.0e+00 |
| V11 | 0.298 | major | 0.173 | 0.0e+00 |
| V23 | 0.220 | moderate | 0.178 | 0.0e+00 |
| V24 | 0.201 | moderate | 0.091 | 0.0e+00 |

Across all 29 features: 14 stable, 7 moderate, 8 major (PSI cut-offs 0.1 and 0.25).

**Control** (two random halves of the same data, where nothing can have drifted): 29 of 29 features stable, largest PSI 0.0002, largest KS gap 0.0053. The detectors are quiet when nothing has moved, so the shifts above are real differences between the two days (why the days differ was not investigated).

## Does the model's output look different?

Score distribution (log-odds), held-out reference vs current: PSI 0.063, KS gap 0.091 (p 7.4e-173).

## Did quality fall?

| | Reference hold-out | Current |
|---|---|---|
| PR-AUC | 0.816 (95% interval 0.713 to 0.909) | 0.804 (0.751 to 0.857) |
| ROC-AUC | 0.971 | 0.984 |

Drop in PR-AUC +0.012; tolerance (half the wider bootstrap interval) 0.098; flagged as decay: **False**.
