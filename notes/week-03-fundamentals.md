# Week 3 fundamentals, explained with your exercise

Every number below comes from `classical_ml/notebooks/03_gbm_shap_and_nn.ipynb` and the scripts `classical_ml/reports/week3_gbm.py` and `week3_nn.py`, on the credit-card fraud data (284,807 transactions, 492 frauds = **0.17%**, 30 numeric columns). As in Week 2, the validation and test splits hold only about 74 frauds each, so small gaps are noise.

Contents: 1. Gradient boosting in detail · 2. HistGB vs XGBoost vs LightGBM · 3. Settings that matter · 4. SHAP · 5. Neural-network basics · 6. PyTorch · 7. Learning rate · 8. Trees vs neural networks on tables · 9. GBM vs LLM · 10. Interview check

---

## 1. Gradient boosting in detail

You met the one-paragraph version in Week 2. Here is the mechanism.

A **decision tree** is a flowchart of yes/no questions on the features (`V14 < -5?`) ending in a number at each leaf. One small tree is weak. **Boosting** adds many of them *in sequence*, each one trained to fix what the previous ones got wrong.

```
start:     every transaction gets the same score = log-odds of the fraud rate
round 1:   measure the error of the current scores on every training row
           fit a small tree that predicts those errors from the features
           add  learning_rate x tree  to every row's score
round 2:   re-measure the errors (they're smaller now), fit another tree, add it
...
final score = start + learning_rate x (tree 1 + tree 2 + ... + tree N)
```

- **What "error" means.** For a yes/no target, the model works in **log-odds** (a stretched probability, any number from -infinity to +infinity). The "error" for each row is the slope of the loss at its current score (the **gradient**, which is where the name comes from). For the standard fraud loss that is roughly `actual - predicted probability`: a missed fraud has a large positive error, a correctly ignored normal row has an error near zero.
- **Why many small trees.** Each tree only has to correct a little, so no single tree needs to be clever. Together they build a complicated rule out of simple ones. Trees can express "*V14 very negative AND V4 very positive*", an interaction a straight-line model like logistic regression cannot.
- **Learning rate (shrinkage).** Each tree's contribution is multiplied by a small number (0.05 here). Smaller steps need more trees (cost: time) but no single tree can drag the scores far (benefit: safety, usually better generalization).
- **Number of trees** is the other half of the same trade-off. Too few underfits; too many can overfit. Early stopping (Week 2) picks the number from a validation set.

### Why default boosting went haywire on rare fraud (the Week 2 puzzle)

Boosting does not just average the errors in a leaf. It takes a **Newton step**: roughly

```
leaf value  =  sum of gradients in the leaf  /  (sum of hessians in the leaf + lambda)
```

The *hessian* (the curvature of the loss) for a normal row the model already scores near 0% fraud is about `p(1 - p)`, which is tiny. A leaf containing a handful of frauds among tens of thousands of confidently-scored normals has a decent gradient sum but an almost-zero hessian sum, so the division gives a gigantic value and scores jump to nearly exactly 1.0 after a few rounds. That is what you saw.

`lambda` (L2 regularization, `l2_regularization` / `reg_lambda`) sits in the denominator and keeps it from collapsing. `min_samples_leaf` / `min_child_weight` / `min_child_samples` forbid tiny leaves. **These two settings were not optional on this data**, which is why all three libraries needed them.

### Overfitting in boosting

The training score climbs to a perfect 1.000 almost by definition (enough trees can memorize every training row). A big train-validation gap is therefore *not* proof of harmful overfitting. The real test: does the validation score get **worse** as trees are added? In Week 2 it flattened near 0.82 and did not fall.

---

## 2. HistGradientBoosting vs XGBoost vs LightGBM

Three programs, one algorithm. What they share and where they differ:

| | HistGradientBoosting | XGBoost | LightGBM |
|---|---|---|---|
| Maker | scikit-learn | XGBoost project | Microsoft |
| Install | built in | `xgboost` | `lightgbm` |
| Speed trick | **histograms**: each feature is sorted into at most about 255 buckets, so a split search looks at ~255 candidates, not every unique value | `tree_method="hist"` does the same | histograms (its original selling point) |
| How trees grow | best-first (the leaf with the biggest loss reduction is split next), capped by `max_leaf_nodes` | depth-wise by default (a full level at a time), capped by `max_depth` | **leaf-wise** / best-first, capped by `num_leaves` |
| Handles NaN natively | yes | yes | yes |
| scikit-learn API | native | wrapper (`XGBClassifier`) | wrapper (`LGBMClassifier`) |

What the histogram trick buys: training cost depends on the number of buckets, not on the number of distinct values, so it scales to millions of rows. What it costs: values within a bucket are treated alike, a tiny loss of precision that almost never matters.

**Leaf-wise vs depth-wise.** A depth-wise tree splits every node at a level, producing balanced trees. A leaf-wise tree keeps splitting whichever single leaf helps most, producing lopsided deep branches where the data is hard. Leaf-wise can reach a lower loss with the same number of leaves but overfits more easily on small data, so it needs a limit on leaves and on leaf size.

### Your results (same 5 folds and 492 frauds as Week 2)

| Model | PR-AUC (5-fold CV) | vs Week 2 HistGB | folds better |
|---|---|---|---|
| HistGB (Week 2) | 0.859 ± 0.022 | 0.000 (re-run reproduces Week 2) | n/a |
| XGBoost | 0.858 ± 0.025 | -0.001 ± 0.006 | 3 of 5 |
| LightGBM | 0.862 ± 0.022 | +0.003 ± 0.001 | 5 of 5 |

How to read it:
- **A gap needs both size and consistency.** LightGBM won every fold, but by 0.003, a tenth of the fold-to-fold spread of the scores. Real, but negligible; not worth rewriting a pipeline for.
- **Same algorithm, same answer.** All three use the same loss, the same Newton-step leaves and the same regularization ideas, on the same 30 features. Switching *model family* (straight-line to trees) was worth +0.10 in Week 2. Switching *library* was worth +0.003.
- **The settings were hand-picked, not tuned.** "No difference" holds for these settings only.
- **Reproducing an old number is a free sanity check.** HistGB matched Week 2 exactly, so the folds and data are identical.

**Practical choice.** Any of the three is fine here. Tie-breakers: what is already installed (HistGB needs no extra dependency), training speed, team familiarity, and deployment support. XGBoost and LightGBM are the names you will meet in production systems and job posts.

---

## 3. The settings that matter

The same idea has different names in each library:

| What it controls | HistGB | XGBoost | LightGBM | Effect of raising it |
|---|---|---|---|---|
| Number of trees | `max_iter` | `n_estimators` | `n_estimators` | more fitting; more time; overfit risk |
| Step size | `learning_rate` | `learning_rate` | `learning_rate` | faster but less stable (needs fewer trees) |
| L2 penalty on leaf values | `l2_regularization` | `reg_lambda` | `reg_lambda` | smaller, safer corrections |
| Minimum leaf size | `min_samples_leaf` (rows) | `min_child_weight` (sum of hessians, **not** rows) | `min_child_samples` (rows) | fewer tiny, noisy leaves |
| Tree size | `max_leaf_nodes` | `max_depth` | `num_leaves` | more complex rules; overfit risk |
| Row sampling | not used | `subsample` | `subsample` (+ `subsample_freq=1` to switch it on) | each tree sees a random share; less overfit |
| Feature sampling | not used | `colsample_bytree` | `colsample_bytree` | each tree sees a random share of columns |

Used here: 300 trees, learning rate 0.05, L2 = 10, small-leaf limits, 80% row and column sampling for XGBoost and LightGBM. Note `min_child_weight=5` in XGBoost and `min_samples_leaf=100` in HistGB are **not** the same quantity, so these settings are comparable but not identical.

**Tuning order that usually pays off:** first the learning rate and number of trees (with early stopping), then tree size and minimum leaf size, then the regularization and sampling settings.

---

## 4. SHAP: explaining one prediction

**The question:** why did the model give *this* transaction a score of 0.93?

**The idea.** SHAP comes from game theory (**Shapley values**). Treat the features as players on a team and the prediction as the team's payout. A feature's fair share is its **average marginal contribution**: how much the prediction changes when the feature joins, averaged over every possible order in which features could be added. Trying every order is exponentially expensive in general, but for trees `shap.TreeExplainer` computes the exact values quickly by using the tree structure.

**What you get.** One number per feature per transaction, in the model's output units (**log-odds** for these classifiers). The key property, called *local accuracy*:

```
base value  +  (sum of all feature pushes)  =  the transaction's score (log-odds)
```

Your median-scored fraud: base -10.14 + pushes +12.74 = 2.60 log-odds = **P(fraud) 0.93**.

- The **base value** is the model's *average raw score* over the background data. It is -10 because it is dominated by the 99.8% normal rows. It is **not** a fraud rate.
- Positive push = pushed the score toward fraud. Negative = toward normal.

### Local view (one transaction)

| feature | value | push (log-odds) |
|---|---|---|
| V14 | -10.1 | +4.9 |
| V4 | 9.65 | +2.4 |
| V10 | -11.2 | +2.0 |
| V12 | -13.1 | +1.4 |
| V7 | -21.9 | +1.0 |

Several features had extreme values at once, and each pushed up. The lowest-scoring normal row I inspected had only small downward pushes (the largest was -0.58).

### Global view (the whole validation set)

Average of |push| across rows: **V4 0.71**, V14 0.35, V12 0.25, V8 0.20, V26 0.19, **Time 0.16**, V15 0.16, **Amount 0.13**. The top 5 features carry only 42% of the total, so the signal is **spread over many columns**. `Time` and `Amount` rank 6th and 8th: the model uses them, which fits Week 2's finding that engineered versions of them added nothing.

### What SHAP does not tell you

1. **What the model relies on, not what causes fraud.** It explains the model, not the world.
2. **Correlated features share credit.** If two columns carry the same information, the split between them is somewhat arbitrary.
3. **Anonymized features limit it.** "V14 was very negative" ranks the evidence but is not a reason you could give a customer or a regulator. With named features (`amount_vs_card_average`) the same output becomes a real explanation.
4. **It depends on the model.** A different model, even with equal accuracy, can give different explanations.
5. **Scores are in log-odds, not probabilities.** Pushes add in log-odds; they do not add in probability.

SHAP also gives *interaction values* (how pairs of features combine), not used here.

---

## 5. Neural-network basics

### The building blocks

- **Tensor.** An array of numbers that PyTorch can track calculations on. `torch.tensor([2., 3.])` is a vector of two floats (`float32`).
- **Neuron.** `z = w1*x1 + w2*x2 + ... + b`, then an **activation**. The weights `w` and bias `b` are what training learns. Example: x = [2, 3], w = [0.5, -1], b = 0.1 gives z = -1.9.
- **Activation function.** A bend applied to z.

| | formula | output range | use |
|---|---|---|---|
| ReLU | `max(0, z)` | 0 to infinity | hidden layers (z = -1.9 gives 0) |
| Sigmoid | `1 / (1 + e^-z)` | 0 to 1 | turns the final score into a probability (z = -1.9 gives 0.13) |

- **Why the bend matters.** Without an activation, stacked layers collapse: two linear layers are mathematically **one** linear layer (the notebook checks this with `torch.allclose`, which returns `True`). A ReLU between them breaks that shortcut, so the network can represent curves and combinations of features. That is the whole reason activations exist.
- **Layer / network.** A layer is many neurons side by side. The fraud network is 30 inputs, 64 neurons, 32 neurons, 1 output: `30x64+64` + `64x32+32` + `32x1+1` = **4,097 weights**.
- **Logits.** The last layer outputs a raw score (a "logit", the same log-odds idea as boosting). `BCEWithLogitsLoss` takes the logit directly and applies the sigmoid internally, which is more numerically stable than applying the sigmoid yourself. You only apply the sigmoid to read probabilities.

### Loss: how wrong is the prediction?

**Binary cross-entropy.** The cost depends only on how much probability the model gave to *what actually happened*:

| true outcome | model's P(fraud) | probability given to the truth | loss |
|---|---|---|---|
| fraud | 0.99 | 0.99 | 0.010 |
| fraud | 0.90 | 0.90 | 0.105 |
| fraud | 0.50 | 0.50 | 0.693 |
| fraud | 0.10 | 0.10 | 2.303 |
| fraud | 0.01 | 0.01 | 4.605 |
| **normal** | **0.90** | **0.10** | **2.303** (the same as the fraud scored at 0.1) |

Confident and correct is cheap; confident and wrong is expensive, from either side. On this data a model that says "almost never fraud" pays about 0.002 per normal row but about 6 per missed fraud, which is why even a plain network still tries to catch the rare class. `pos_weight` multiplies the fraud term's cost, the neural-network counterpart of Week 2's class weights.

### Gradient, backpropagation, gradient descent

- **Gradient.** For each weight, the slope of the loss: "if I raise this weight a little, does the loss go up or down, and how fast?"
- **Backpropagation / autograd.** The chain rule applied automatically. PyTorch records the maths during the forward pass and `loss.backward()` fills in a slope for every weight. Check from the notebook: fitting one weight, autograd gave a slope of **-19.5**, equal to the hand calculation. Negative slope means "raise the weight".
- **Gradient descent.** Step each weight a small amount against its slope: `w = w - learning_rate * slope`. Repeat.
- **Adam.** A popular variant that keeps a running average of recent slopes and adapts the step size separately for each weight. It needs less tuning than plain gradient descent.
- **Batch and epoch.** An *epoch* is one pass over the training data. A *batch* (1,024 rows here) is the chunk used for each nudge. Smaller batches are faster per step but noisier.

### The training loop (every network does this)

```
opt.zero_grad()                 # clear the old slopes (they accumulate otherwise)
loss = loss_fn(model(x), y)     # forward pass: predict, then measure the error
loss.backward()                 # autograd: slope of the loss for every weight
opt.step()                      # Adam moves each weight a little against its slope
```

### Practical rules

- **Scale the inputs** (mean 0, std 1, fitted on **train only**: Week 1's leakage rule). Networks are very sensitive to scale; trees only care about the order of values. Unscaled `Amount` (up to 25,000) would swamp the other columns and destabilize training.
- **Overfitting tools** not used here but worth knowing: dropout (randomly switch off neurons during training), weight decay (an L2 penalty on weights, the same idea as Week 2), early stopping, smaller networks.
- **Initialization and random seeds.** Starting weights are random, so results vary run to run. Always fix a seed and, for conclusions, run several.

### Your result

| epoch | 1 | 5 | 10 | 20 | 30 |
|---|---|---|---|---|---|
| val PR-AUC | 0.487 | 0.643 | 0.617 | 0.759 | 0.771 |

Best 0.781 (epoch 24, picked on validation, so optimistic). For comparison on the same split: **LightGBM 0.831**, plain logistic regression 0.670.

- **Training is bumpy** (it fell from epoch 5 to 10, then recovered). With 0.17% fraud, a batch of 1,024 rows holds about two frauds, so the weight updates are noisy.
- **The network beats logistic regression** because the hidden layers add the bends from above, but it **did not beat LightGBM**.
- **Caveat:** one split, one seed and 74 frauds, so a gap of 0.05 is within the noise seen all through Week 2. Cross-validation over several seeds would settle it. The first "Your turn" exercise does that.

---

## 6. PyTorch in a page

| Piece | What it is |
|---|---|
| `torch.tensor(data)` | an array; use `dtype=torch.float32` for model inputs |
| `requires_grad=True` | "track maths on this so I can get slopes" |
| `loss.backward()` | compute slopes for everything that has `requires_grad` |
| `w.grad` | the stored slope; **accumulates** across calls, so clear it (`zero_grad`) each step |
| `nn.Linear(a, b)` | one layer: `a` inputs to `b` outputs (weights + bias) |
| `nn.Sequential(...)` | run layers in order |
| `nn.BCEWithLogitsLoss()` | sigmoid + binary cross-entropy, in one stable step |
| `torch.optim.Adam(params, lr=1e-3)` | the optimizer that updates the weights |
| `with torch.no_grad():` | don't track maths (for prediction and for manual weight updates) |
| `model.train()` / `model.eval()` | switch layers like dropout between training and prediction behaviour (no effect on this network, but a good habit) |

---

## 7. The learning rate (a worked example you ran)

Fit one weight `w` so `w * x` matches the target, with `x = [2, 3]`, target `[6, 9]` (correct answer w = 3), starting at w = 1.5. For this loss the slope is `13 x (w - 3)`, so each step does:

```
(w - 3)  becomes  (1 - 13 x lr) x (w - 3)
```

| lr | multiplier `1 - 13 x lr` | w after steps 1 to 5 | behaviour |
|---|---|---|---|
| 0.001 | 0.987 | 1.52, 1.54, 1.56, 1.58, 1.59 | crawls |
| 0.05 | 0.35 | 2.47, 2.82, 2.94, 2.98, 2.99 | converges smoothly |
| 0.1 | -0.3 | 3.45, 2.87, 3.04, 2.99, ... | converges, zigzagging |
| 0.15 | -0.95 | 4.43, 1.65, 4.29, 1.78, 4.16 | bounces, never settles |
| 0.5 | -5.5 | 11.25, -42.4, 252.6, -1369.6, 7552.3 | **diverges** |

Rule: the distance from the answer shrinks only if the multiplier is between -1 and 1, here `lr < 2/13`, about 0.154. The same idea holds in real networks: **there is a safe range for the learning rate, and it depends on the loss and on the scale of the inputs.** Unscaled inputs make the slopes huge, which acts like a learning rate that is far too big.

---

## 8. Why trees often beat neural networks on tables

Observed here: LightGBM (0.831) over the small network (0.78) over logistic regression (0.67), on one split. Commonly cited reasons (general knowledge, not proven by this one run):

- **Trees need no feature scaling** and handle skewed columns (`Amount` runs to $25,000) and missing values directly.
- **Trees express sharp rules and interactions** ("this column above a cutoff AND that one below another") with little tuning. A network has to learn smooth approximations of sharp edges and needs more data to do it.
- **Tables are not smooth, rotation-invariant data.** Columns have individual meaning; a network's strengths (images, audio, text) come from structure that tables lack. A well-known benchmark paper, Grinsztajn et al. (2022), studies exactly this question ("Why do tree-based models still outperform deep learning on typical tabular data?"). Worth reading yourself.
- **Small positive class.** 344 training frauds is little for a network to learn from.
- **Cost of tuning.** Trees work decently with defaults; networks need a learning rate, size, epochs, scaling and several seeds.

When a network *can* win on tabular data: very large datasets, many high-cardinality categorical columns (learned embeddings), or when the table is combined with text or images in one model.

---

## 9. Why a GBM, and not an LLM, for this problem

**The problem:** a yes/no decision, per card transaction, while the customer waits, from 30 numeric columns, at high volume, with 0.17% positives.

**Latency (my pick).** Measured on this laptop, one CPU thread, one transaction at a time, model scoring only:

| Scoring one transaction | p50 | p99 |
|---|---|---|
| LightGBM raw booster | 0.07 ms | 0.10 ms |
| LightGBM scikit-learn API, numpy input | 0.44 ms | 0.68 ms |
| LightGBM scikit-learn API, DataFrame input | 0.89 ms | 1.12 ms |
| HistGradientBoosting | 2.26 ms | 3.43 ms |
| Small PyTorch network | 0.04 ms | 0.08 ms |

Batch: 42,721 rows in 0.60 s, about 71,000 rows per second on one thread. The tail is tight (p99 barely above p50), and most of the time is Python wrapper overhead, not the trees: the raw booster is 13 times faster than the same model through the scikit-learn API with a DataFrame. **Not included:** network hops, fetching features, the rest of the payment system. **An LLM was not measured** (no API access). From general knowledge, not from this project: a hosted LLM call typically takes hundreds of milliseconds to seconds with a wide tail, and a card authorization usually has a total budget of only tens to a few hundred milliseconds. Check the figures for the provider you would use.

**Cost.** The GBM trains on a laptop CPU with no GPU and has no per-call fee. LLMs are typically billed per token, per transaction, and a fraud system scores every transaction. (Look up current pricing before quoting a number.)

**Explainability.** SHAP gives an exact additive breakdown of the actual score. An LLM's written explanation is generated text and need not reflect how any score was produced. Caveat: with anonymized features the SHAP reasons are not human-readable.

**Data shape.** 30 numeric columns and no text. Boosted trees are strong on tables (Week 2: 0.859 PR-AUC vs 0.758 for logistic regression); an LLM's strength is language, and there is no language here.

**Where an LLM helps instead:** reading free text (dispute descriptions, merchant notes), drafting an analyst case summary from the GBM's SHAP output, answering policy questions. A common design: the GBM makes the real-time decision and an LLM works on the slower, text-heavy side.

**Honest caveats:** only the GBM was measured; no LLM was benchmarked or compared on accuracy. "GBM beats an LLM" holds for this real-time, numeric, high-volume, explainable problem, not in general.

---

## 10. Interview check: can you answer these out loud?

1. Explain gradient boosting in three sentences. What does each new tree try to predict?
2. What do the learning rate and the number of trees each control, and how do they trade off?
3. Why did boosting with default settings go haywire on rare fraud, and what fixed it?
4. XGBoost, LightGBM and HistGB scored within 0.004 of each other. Why? What actually differs between them?
5. LightGBM won all 5 folds by +0.003. Do you switch your pipeline to it? Why or why not?
6. What does a SHAP value mean? What is the "base value", and why isn't it a probability?
7. Give two limits of SHAP explanations.
8. Why do neural networks need an activation function? What happens without one?
9. Walk through the four lines of a PyTorch training loop. What does `zero_grad` do and why is it needed?
10. Why scale inputs for a neural network but not for a tree model? On which data do you fit the scaler?
11. A learning rate of 0.5 makes training blow up. Explain why, and what the safe range depends on.
12. Why might gradient-boosted trees beat a neural network on a table of 30 numeric columns? When would the network win?
13. Argue for a GBM over an LLM for real-time fraud scoring. Which argument is strongest, and what did you (not) measure?
14. Your validation and test scores rank two models in opposite orders. What do you do?

When these feel easy, do the six "Your turn" tasks at the end of the notebook.
