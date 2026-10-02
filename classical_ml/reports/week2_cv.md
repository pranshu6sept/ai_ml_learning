5-fold stratified CV over all 284,807 transactions (492 frauds, each scored once out of fold).

| Model | PR-AUC mean ± std | per-fold PR-AUC | ROC-AUC mean | vs plain logistic (mean diff ± std, folds better) |
|---|---|---|---|---|
| Logistic regression | 0.758 ± 0.021 | 0.721 0.765 0.779 0.775 0.753 | 0.974 | baseline |
| Logistic + class weights | 0.730 ± 0.025 | 0.710 0.723 0.728 0.778 0.709 | 0.979 | -0.029 ± 0.021, 1/5 |
| Logistic + SMOTE | 0.729 ± 0.029 | 0.699 0.724 0.730 0.784 0.710 | 0.978 | -0.029 ± 0.021, 1/5 |
| Gradient boosting (regularised) | 0.859 ± 0.022 | 0.848 0.895 0.871 0.849 0.830 | 0.982 | +0.100 ± 0.024, 5/5 |
