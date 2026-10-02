# Week 2 fundamentals, explained with your exercise

Every number below comes from `classical_ml/notebooks/02_metrics_and_imbalance.ipynb` on the credit-card fraud data (284,807 transactions over two days, 492 frauds = **0.17%**). Validation and test splits hold only **about 74 frauds each**, so treat small gaps as noise.

---

## 1. Why a rare class changes everything

When one class is 99.83% of the data, the usual habits break:

- **Accuracy is meaningless.** A "model" that labels everything *not fraud* is **99.83% accurate** and catches **0 of 492** frauds.
- **Splits get thin.** A 15% test split holds only about 74 frauds, so every score computed on it wobbles (Week 1's ± matters more than ever).
- **Stratified splitting is essential** (you already have it from Week 1): it keeps the fraud rate the same in every split.

Fraud also isn't what you might imagine: the median fraud amount is *smaller* than the median normal transaction, and about 37% of frauds are for $1 or less (probably cards being tested).

---

## 2. Precision, recall and F1

Sort every call the model makes into four boxes:

|  | actually fraud | actually fine |
|---|---|---|
| **flagged** | TP (caught) | FP (false alarm) |
| **not flagged** | FN (missed) | TN |

| Metric | Formula | The question it answers | What it punishes |
|---|---|---|---|
| **Precision** | TP / (TP + FP) | Of what I flagged, how much was real? | false alarms |
| **Recall** | TP / (TP + FN) | Of the real frauds, how many did I catch? | misses |
| **F1** | 2PR / (P + R) | Are *both* high? (harmonic mean) | either being low |

Worked example: 600 flagged, 400 truly fraud, 492 frauds in total. Precision = 400/600 = **0.67**, recall = 400/492 = **0.81**. (Watch the rounding.)

The do-nothing model has recall 0, which is exactly the number accuracy hid.

---

## 3. The threshold is a dial

A model outputs a probability, and *you* choose the cutoff. On your baseline logistic regression:

| threshold | flagged | precision | recall |
|---|---|---|---|
| 0.90 | 47 | 0.766 | 0.486 |
| 0.50 | 56 | 0.786 | 0.595 |
| 0.10 | 75 | 0.707 | 0.716 |
| 0.02 | 113 | 0.531 | 0.811 |

Lower the threshold and recall rises while precision tends to fall (more caught, more false alarms). The 0.90 to 0.50 step shows precision going *up* slightly; with 74 frauds that's one or two transactions, so it's noise.

---

## 4. ROC-AUC vs PR-AUC (the hardest idea of the week)

Both summarize a model across every threshold. The difference is what they divide by:

| | measures | divides false alarms by |
|---|---|---|
| **ROC** | false-positive rate | **all legitimate** transactions (about 42,650) |
| **PR** | precision | **only the flagged** transactions |

At threshold 0.02 the model made **53 false alarms**:

```
ROC sees:       53 / 42,650 legit  = 0.12%   ← looks tiny
A reviewer sees: 53 / 113 flagged  = 47% wrong
```

Double the legitimate volume and the false-positive rate halves while precision doesn't move. **ROC flatters you when one class dominates.** Your baseline: ROC-AUC **0.957** ("excellent") vs PR-AUC **0.670**.

**Chance levels differ.** ROC-AUC's chance is 0.5. PR-AUC's chance is the **fraud rate** (0.0017). So 0.67 is about 390 times better than guessing. A model giving every transaction the same score lands exactly on 0.002.

Rule: on rare-event problems, compare models with PR-AUC and report precision and recall at the threshold you'd deploy.

---

## 5. Three ways to handle imbalance (and what they really do)

On validation, logistic regression at threshold 0.5:

| Fix | PR-AUC | flagged | precision | recall |
|---|---|---|---|---|
| nothing | 0.670 | 56 | 0.786 | 0.595 |
| class weights | 0.630 | 969 | 0.067 | 0.878 |
| SMOTE | 0.634 | 998 | 0.065 | 0.878 |

**Class weights** (`class_weight="balanced"`) make each fraud count about 580 times a normal transaction in the loss. **SMOTE** invents synthetic frauds by interpolating between real neighbours. Both tell the model "fraud is as common as normal", so both **inflate its probabilities** (average predicted 0.066 vs a true rate of 0.0017) and flag about a thousand transactions. At the *same number* of flags they match the plain model almost exactly (precision 0.064 vs 0.067, recall 0.838 vs 0.878). They mostly slide you along the same precision-recall curve; they don't rank better.

**SMOTE and leakage.** A synthetic fraud is built from real ones. Run it *before* splitting and a synthetic training point can sit next to a validation fraud. It must run **inside the pipeline, on training rows only** (use `imblearn`'s `Pipeline`), and never on validation or test.

**Threshold tuning** needs no retraining: keep the model, choose the cutoff on **validation** (not train, which the model has seen; not test, which you touch once). Two rules:

| Rule | Picks | Caveat |
|---|---|---|
| best F1 | where F1 peaks | treats a miss and a false alarm as equally bad |
| min cost | lowest total cost | needs real prices |

With a miss costing $500 and a false alarm $5, the break-even is P(fraud) x 500 > 5, i.e. **flag above about 1%**. If a miss cost $20 it would be about 20%. On validation the baseline's total cost was $15,060 at 0.5, $10,600 at the best-F1 threshold and **$6,765 at the min-cost threshold**, even though that one has the worst F1. F1 is a convenient score, not a business goal.

---

## 6. Regularization: L1 and L2

Regularization puts a **price on the weights**, so the model must justify each large one. `C` is the *inverse* strength: small `C` = steep price.

| | price charged | effect on a weak feature |
|---|---|---|
| **L2** | w² | shrinks all weights; weak ones stay small but non-zero |
| **L1** | \|w\| | pushes weak weights **exactly to zero** (a feature selector) |

Why: a weight of 0.1 costs 0.01 under L2 (not worth removing) but 0.10 under L1 (removed unless it earns it back).

What you saw:
- Neither helped logistic regression. Validation PR-AUC flattens from `C = 1` upward (about 0.673 to 0.674), so the default was already fine. A 30-feature model on 240,000 rows has little room to memorize noise.
- L1 at `C = 0.001` kept only 3 of 30 features and still reached about 0.60.
- L1 at `C = 0.0001` zeroed every weight: the model scores everyone the same, and PR-AUC = **0.002**, the chance level.

Regularization matters most when features are many and rows are few, or for flexible models (next section).

---

## 7. Gradient boosting and early stopping

A **decision tree** is a flowchart of yes/no questions that ends in a number. **Gradient boosting** builds many small trees *in sequence*, each fixing the errors left by all the trees before it:

```
start:     everyone gets the same score (the average fraud rate)
round 1:   find the errors → fit a small tree to them → add  learning_rate x tree
round 2:   recompute the errors → fit another tree → add  learning_rate x tree
...
final = start + learning_rate x (tree 1 + tree 2 + ... + tree N)
```

- A **round** is one more tree. The **learning rate** is the step size: smaller steps need more rounds (cost: time) but no single tree can dominate (benefit: safety).
- Trees can express *interactions* ("hour is 2 **and** amount under $1") that a straight-line model can't. That is why boosting scored **0.82 to 0.83** validation PR-AUC against **0.67** for logistic regression.

**The rare-class trap.** With default settings, boosting went haywire here. A leaf holding a handful of frauds among tens of thousands of normal rows computes a huge correction (a large error divided by a tiny quantity), so scores jumped to almost exactly 1.0 within a few rounds and the training curve collapsed. `l2_regularization=10` shrinks those corrections (and `min_samples_leaf` forbids tiny leaves), and the curve became sensible.

**Early stopping.** Training PR-AUC climbs to 1.000 while validation rises and then **plateaus** near 0.82. Early stopping stops when validation hasn't improved for N rounds. It saves time, and protects you where validation does turn down. Caveats:
- A big train-validation gap is *not* by itself overfitting. The test is whether validation gets **worse** as capacity grows. Here it only flattened.
- scikit-learn's built-in version carves the validation set out of the training data. With about 344 training frauds that's roughly 50 frauds to judge by: noisy.

---

## 8. Feature engineering (and a negative result)

Exploring training rows suggested two features: **hour of day** (fraud is about 10 times as common in the small hours; use sin/cos so it wraps) and a **tiny-amount flag** (`Amount <= 1`, with 37% of all frauds). Results:

| Model | before | after adding them |
|---|---|---|
| Boosting | 0.822 | 0.823 |
| Logistic regression | 0.670 | 0.677 |

A negative result. The anonymized `V1`-`V28` already carry most of the signal. Compare Week 1's `debt_to_income`: it helped because it *combined two columns* a linear model couldn't combine itself. **Feature engineering pays off when it adds information the model can't build on its own.**

A process lesson: exploring *all* rows (including validation and test) before choosing features is a small leak. Explore on training rows only.

---

## 9. Comparing models honestly

One split with 74 positives is too little to rank models. Evidence: plain logistic regression beat class weights and SMOTE on validation (0.670 vs 0.630 and 0.634) but *lost* to them on the test split (0.750 vs 0.793 and 0.794). The ranking flipped.

The fix is Week 1's cross-validation, now over all **492** frauds (each scored once, out of fold, by a model that never trained on it), comparing models on the **same folds**:

| Model | PR-AUC (5-fold CV) | vs plain logistic | folds better |
|---|---|---|---|
| Logistic regression | 0.758 ± 0.021 | baseline | n/a |
| + class weights | 0.730 ± 0.025 | -0.029 ± 0.021 | 1 of 5 |
| + SMOTE | 0.729 ± 0.029 | -0.029 ± 0.021 | 1 of 5 |
| **Gradient boosting** | **0.859 ± 0.022** | **+0.100 ± 0.024** | **5 of 5** |

How to read it: boosting's gain (+0.100) is about four times the spread of the gap (0.024), and it won on every fold, so it isn't noise. Class weights and SMOTE show no benefit. ROC-AUC (0.974 to 0.982) would have hidden all of this.

Also remember: each model's best threshold differs (about 0.02 for plain logistic, 0.9 for weighted/SMOTE, 0.002 for boosting), so tune each one separately.

---

## Interview check: can you answer these out loud?

1. Why is accuracy a bad metric for fraud, and what would you report instead?
2. Define precision and recall. What happens to each when you lower the threshold?
3. Why can ROC-AUC look excellent while a fraud model is poor? When do you prefer PR-AUC?
4. What's the chance level of PR-AUC, and why does it matter?
5. Compare class weights, SMOTE and threshold tuning. Why do the first two mostly shift the threshold?
6. Why must SMOTE run inside the pipeline? On which splits is it applied?
7. On which split do you choose the threshold, and why not the test set?
8. How do L1 and L2 differ, and when would you pick L1?
9. Explain gradient boosting to a non-engineer in two sentences. What does early stopping do?
10. Your validation and test results rank two models in opposite orders. What do you do?

When these feel easy, do the six "Your turn" tasks at the end of the notebook.
