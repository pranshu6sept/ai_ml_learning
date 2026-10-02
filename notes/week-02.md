# Week 2: When 99.83% accurate means useless

## The question

Last week the question was "how do I know my score is honest?" This week it got harder: **what
does a good score even mean when the thing I'm hunting is rare?** The data was 284,807 credit-card
transactions from two days, and only **492 of them (0.17%) are fraud**.

## Chapter 1: The model that does nothing

A "model" that labels every transaction *not fraud* is **99.83% accurate** and catches **zero
fraud**. Accuracy was never going to work. Two numbers that can't be fooled this way:

- **Precision:** of the transactions I flagged, how many were really fraud?
- **Recall:** of the real frauds, how many did I catch?

They pull against each other through the **threshold**. A model outputs a probability, and I pick
the cutoff. Lower it and recall rises while precision falls, because more fraud is caught but so
are more innocent transactions.

## Chapter 2: ROC-AUC lies politely, PR-AUC doesn't

A plain logistic regression scored **ROC-AUC 0.957** (sounds excellent) but **PR-AUC 0.670**.
At a threshold of 0.02 the model made 53 false alarms. ROC measures that against all ~42,650
legitimate transactions: 0.12%, tiny. Precision measures it against the 113 transactions actually
flagged: 47% wrong. Same 53 mistakes, different denominators. Double the legitimate volume and the
false-positive rate halves while precision doesn't move. **ROC flatters you when one class
dominates.** PR-AUC doesn't.

Chance for PR-AUC is the fraud rate (0.0017), not 0.5. So 0.67 is about 390 times better than
guessing, and a model that gives every transaction the same score lands exactly on 0.002.

## Chapter 3: Three fixes for imbalance, compared with numbers

On the validation split (74 frauds):

| Fix | PR-AUC | At threshold 0.5: flagged / precision / recall |
|---|---|---|
| Nothing | 0.670 | 56 / 0.786 / 0.595 |
| Class weights | 0.630 | 969 / 0.067 / 0.878 |
| SMOTE (synthetic frauds) | 0.634 | 998 / 0.065 / 0.878 |

Class weights and SMOTE both tell the model "fraud is as common as normal", so they inflate its
probabilities (average predicted 0.066 vs a true rate of 0.0017) and it flags a thousand
transactions. Flagging the top 969 with the *plain* model gives nearly the same precision and
recall. **They mostly act like a lower threshold; they don't make the model rank better.**
SMOTE also has a rule: apply it only to each training fold, because a synthetic fraud is built
from real ones, and one built before splitting can sit right next to a validation fraud.

The third fix needs no retraining. **Threshold tuning**, picked on validation (never test), lets
me use real costs: with $500 per missed fraud and $5 per false alarm, flag a transaction when its
fraud probability exceeds about 1%. The best threshold depends on the cost ratio, not on F1.

## Chapter 4: Regularization, and a boosting surprise

L2 shrinks every weight and L1 pushes weak ones to exactly zero. On this data neither helped
logistic regression: C=1 (the default) is already on the plateau, with a validation PR-AUC of
0.673. L1 with a very strong penalty zeroed every weight, and its PR-AUC fell to 0.002, which is
chance.

Gradient boosting builds many small trees in sequence, each fixing the errors of the ones before.
With default settings it went haywire on this data: scores jumped to almost exactly 1.0 and the
training score collapsed. Leaves holding a handful of frauds among tens of thousands of normal
rows computed enormous corrections. `l2_regularization=10` fixed it, and validation PR-AUC rose
to about 0.82 to 0.83, against 0.67 for logistic regression. The training score reached 1.000
while the validation score flattened but never got worse, so it isn't harmful overfitting.
Early stopping means stopping when that plateau starts.

## Chapter 5: Feature engineering found nothing

Fraud is 10 times as common in the small hours (1.71% at hour 2 vs about 0.1% in the day), and
37% of all fraud is in transactions of $1 or less. I built `hour` and `is_tiny_amount` from that.
Boosting went 0.822 to 0.823, and logistic regression 0.670 to 0.677. A negative result: the
anonymized `V1`-`V28` columns already carry most of the signal, and these two columns added
little. (Week 1's `debt_to_income` helped because it combined two columns a linear model couldn't
combine itself.)

I also made a process mistake. I looked at fraud rates by hour and amount across **all** rows,
including validation and test, before building features. Exploring should use the training rows
only. The effect was probably small, since the features didn't help, but it's the habit that
matters.

## Chapter 6: The numbers

One split (test set, 74 frauds), scored once, thresholds chosen on validation:

| Model | PR-AUC [95% interval] | Flagged | Precision | Recall | Cost |
|---|---|---|---|---|---|
| Logistic regression | 0.750 [0.659-0.854] | 101 | 0.594 | 0.811 | $7,205 |
| + class weights | 0.793 [0.706-0.887] | 293 | 0.215 | 0.851 | $6,650 |
| + SMOTE | 0.794 [0.706-0.888] | 272 | 0.232 | 0.851 | $6,545 |
| Gradient boosting | 0.842 [0.775-0.922] | 336 | 0.190 | 0.865 | $6,360 |

Flagging nothing costs $37,000. Every model cuts that by about 80%, but the intervals overlap, and
the order of plain logistic regression versus weights and SMOTE **flipped** between validation and
test. 74 frauds can't rank them.

So I ran 5-fold cross-validation over all 492 frauds, same folds for every model:

| Model | PR-AUC (5-fold CV) | vs plain logistic regression | folds better |
|---|---|---|---|
| Logistic regression | 0.758 ± 0.021 | baseline | n/a |
| + class weights | 0.730 ± 0.025 | -0.029 ± 0.021 | 1 of 5 |
| + SMOTE | 0.729 ± 0.029 | -0.029 ± 0.021 | 1 of 5 |
| **Gradient boosting** | **0.859 ± 0.022** | **+0.100 ± 0.024** | **5 of 5** |

Boosting wins on every fold, by about four times the spread. Weights and SMOTE give no benefit
and are probably slightly worse. ROC-AUC (0.974 to 0.982) would have hidden all of this.

## What confused me

*(Edit this so it's honest to you; this is my version of the stumbles.)*

- I asked for gradient boosting to be explained before I could follow the rounds and learning rate.
- L1 vs L2 was unclear until I saw them charge different "prices" for big and small weights.
- ROC-AUC vs PR-AUC was the hardest idea of the week: same mistakes, different denominators.
- I couldn't predict why the ranking flipped between splits. The answer is just too few frauds.

## One number that moved

PR-AUC in cross-validation: **0.758 to 0.859**, from switching plain logistic regression for
regularized gradient boosting. Nothing else this week (weights, SMOTE, features) beat it.

## One interview question I can now answer

**"Why is accuracy a bad metric for an imbalanced problem, and what would you use instead?"**

With 0.17% fraud, a model that flags nothing is 99.83% accurate and useless. I'd use precision
and recall at the operating point I'd actually deploy, and PR-AUC to compare models, because its
chance level is the fraud rate and it doesn't flatter a model the way ROC-AUC does. I'd choose the
threshold on validation using the real cost of a miss versus a false alarm, evaluate on test once,
and compare models with cross-validation, because with only a few dozen positives a single split
can't rank them.

## Reproducing this

The data isn't in git (it's 150 MB, and `data/raw/` is ignored). The quick way, `fetch_openml`,
**silently drops the `Time` column**, because OpenML marks it as a row ID. Download the raw file
instead, from the repo root:

```bash
mkdir -p data/raw
curl -sL -o data/raw/creditcard.arff "https://api.openml.org/data/v1/download/1673544"
uv run python -c "
import pandas as pd
from scipy.io import arff
data, _ = arff.loadarff('data/raw/creditcard.arff')
df = pd.DataFrame(data)
df['Class'] = df['Class'].str.decode('utf-8').astype(int)
df.to_csv('data/raw/creditcard.csv', index=False)
"
uv run python classical_ml/reports/week2_metrics.py   # the single-split table
uv run python classical_ml/reports/week2_cv.py        # the 5-fold comparison
```

## Still to do

- [ ] Commit and push (Week 2 changes are uncommitted: `imbalanced-learn` in `pyproject.toml` and
      `uv.lock`, the two report scripts and their `.md` outputs, and these notes)
- [ ] Optional: a paired comparison on the test split, and a test for `best_threshold`
