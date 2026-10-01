# Week 1 fundamentals, explained with your exercise

Every number below comes from `classical_ml/notebooks/01_pipelines_and_cv.ipynb` on the synthetic loan data (5,000 applicants, about 12% default).

---

## 1. pandas and NumPy: what each one is for

**pandas** holds a table with named columns of different types (numbers, text, missing values). You use it to *look* at data before modelling:

| Call | Question it answers |
|---|---|
| `df.info()` | Which columns exist, their types, how many values are missing |
| `df.describe()` | Ranges and averages; spots odd values (negative ages, huge incomes) |
| `df.isna().mean()` | Share missing per column (about 5% for income, history and employment here) |
| `df.groupby(col)[target].mean()` | How the target differs by group |

That last line already tells a story: unemployed applicants default 31% of the time, salaried ones only 9%.

**NumPy** is the fast array engine underneath pandas and scikit-learn. The key idea is **vectorisation**: write `loan / income` once instead of looping over rows. In the notebook the loop took about 690 µs and the vectorised version took about 4 µs, which is roughly 170 times faster, with the same answer. Under the hood every model is NumPy maths on arrays.

---

## 2. Supervised vs unsupervised learning

| | Supervised | Unsupervised |
|---|---|---|
| Has labels? | Yes (`defaulted`) | No |
| Goal | Learn features → label | Find structure (groups, outliers) |
| Your example | Logistic regression gives each applicant a P(default) | k-means puts applicants into 4 clusters |
| How you judge it | Compare predictions to true labels | Check whether the groups mean something |

k-means never saw `defaulted`, yet its clusters had default rates of 6%, 12%, 17% and 23%. It found real structure that happens to relate to risk. Banks use this for customer segmentation, and the same idea later helps with spotting unusual transactions.

---

## 3. Train / validation / test splits

Think of exam prep:

- **Train (70%)**: the textbook. The model learns from it.
- **Validation (15%)**: practice exams. You use them over and over to compare models and settings.
- **Test (15%)**: the real exam. You sit it **once**, at the end.

Why a separate test set? Each time you pick "the model that scored best on validation", you fit a little to the validation set. The test set is the only number you never tuned against, so it's the honest one.

**Stratified** splitting keeps the 12% default rate in every split (12.4%, 12.4% and 12.3% in the notebook). Without it, a small split could end up with very few defaulters by chance. That matters even more next week with fraud data, where positives can be under 1%.

---

## 4. Data leakage (the most important idea this week)

**Leakage** happens when information from the data you evaluate on sneaks into training. Your score then looks better than the model really is, and it falls apart in production.

The noise demo in the notebook:

- The data was 200 rows of random numbers with random labels, so nothing could be learned. The honest answer is 50%.
- **Leaky:** pick the 20 "best" features using *all* rows, then cross-validate. Result: **0.79 accuracy.**
- **Honest:** do the feature picking inside the pipeline, so it only sees the training fold each time. Result: **0.51.**

The leaky version "found signal" in pure noise because the feature picker had already seen the labels it was later tested on.

Common real-world leaks:
- **Preprocessing on all data:** scaling, imputing or selecting features before the split. Medians and means quietly carry information from the test rows.
- **Target leakage:** a feature that is only known *after* the outcome, like `days_in_collections` when predicting default.
- **Time leakage:** training on next month to predict last month. Financial data needs time-based splits.
- **Duplicate entities:** the same customer appearing in both train and test.

**The rule: anything that learns from data goes inside the pipeline.**

---

## 5. `Pipeline` and `ColumnTransformer`

A **Pipeline** chains steps so that `fit` learns every step from training data only, and `predict` just applies them. That is how the leakage rule gets enforced automatically.

A **ColumnTransformer** sends different columns through different steps. Yours (`build_preprocessor()`) does this:

```
numeric  (age, income, loan, history, late payments)
    → fill gaps with the median → scale to mean 0, std 1
categorical (employment_type, region, owns_home)
    → fill gaps with the most common value → one-hot encode
                    ↓
              logistic regression
```

- **Why impute?** Most models can't handle NaN.
- **Why scale?** Logistic regression, k-means and neural nets are sensitive to scale. Income in the tens of thousands would swamp late payments in single digits. Tree models don't care.
- **Why one-hot?** Models need numbers. `region="north"` becomes a column `region_north = 1`. Turning categories into 0, 1, 2, 3 would wrongly suggest an order.
- **`handle_unknown="ignore"`**: if production sends a category the model never saw (`region="mars"` in the tests), it becomes all zeros instead of crashing.

A bonus: the fitted pipeline is **one object** you can save and deploy, so training and serving can't drift apart.

---

## 6. k-fold cross-validation

One validation split gives one noisy number. **5-fold CV** splits the data into 5 parts. It trains 5 times, each time holding out a different part, and reports the mean ± spread.

Your results:

| Model | CV ROC-AUC |
|---|---|
| Dummy (always predicts the average) | 0.500 ± 0.000 |
| Logistic regression | 0.751 ± 0.034 |

Test set, used once: **0.742.** That's close to the CV score, which is a good sign that nothing leaked.

How to read it:
- **The ± matters.** If model B scores 0.76 ± 0.03, it isn't clearly better than 0.751. The gap is inside the noise.
- **Always compare with a dummy baseline.** "0.75" means nothing until you know chance is 0.5.
- **ROC-AUC** is the chance the model ranks a random defaulter above a random non-defaulter. **Accuracy is misleading here:** predicting "nobody defaults" scores 88% and catches no one. Week 2 covers this in depth.

---

## Interview check: can you answer these out loud?

1. What is data leakage? Give two examples and how you'd prevent each.
2. Why do we need a test set if we already have cross-validation?
3. Why wrap preprocessing in a `Pipeline` instead of transforming the data first?
4. When does feature scaling matter, and when doesn't it?
5. Why is accuracy a bad metric for default or fraud prediction?
6. Give one supervised and one unsupervised use case in banking.

When these feel easy, do the six "Your turn" tasks at the end of the notebook.
