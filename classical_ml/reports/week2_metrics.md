Test split: 42,722 transactions, 74 frauds (0.17%).
Chance PR-AUC = fraud rate = 0.0017. Cost = $500 per missed fraud + $5 per false alarm; flagging nothing costs $37,000.

| Model | PR-AUC (95% interval) | ROC-AUC | Val threshold | Flagged | Precision | Recall | Cost ($) |
|---|---|---|---|---|---|---|---|
| Logistic regression | 0.750 [0.659-0.854] | 0.956 | 0.020 | 101 | 0.594 | 0.811 | 7,205 |
| Logistic + class weights | 0.793 [0.706-0.887] | 0.968 | 0.855 | 293 | 0.215 | 0.851 | 6,650 |
| Logistic + SMOTE | 0.794 [0.706-0.888] | 0.968 | 0.907 | 272 | 0.232 | 0.851 | 6,545 |
| Gradient boosting (regularised) | 0.842 [0.775-0.922] | 0.970 | 0.002 | 336 | 0.190 | 0.865 | 6,360 |
