# Week 3: Same algorithm, different libraries, and a network that lost

## The story in one paragraph

Week 2 ended with boosted trees at 0.859 PR-AUC. This week I asked whether better tools would beat
that, tried to understand *why* the model flags what it flags, built a neural network from scratch to
see whether it could do better, and ended by arguing why a boosted-tree model, not an LLM, should sit
in the real-time path of a fraud check. The surprise: the three boosting libraries gave the same
answer to within 0.004, and what mattered was the kind of model, not the brand.

| Checklist item | Status |
|---|---|
| XGBoost or LightGBM beats Week 2 baseline (record delta) | done: LightGBM +0.003 (negligible) |
| SHAP global + local explanations | done |
| PyTorch: tensors, autograd, training loop, small NN on same data | done: 0.78 vs LightGBM 0.83 |
| Write-up: why a GBM beats an LLM (cost, latency, explainability, data shape) | done (below); latency is my pick |
| Write-up + push | notes done; not committed or pushed yet |

Companion files: `notes/week-03-fundamentals.md` (detailed concepts and interview questions),
`classical_ml/notebooks/03_gbm_shap_and_nn.ipynb`, and the scripts
`classical_ml/reports/week3_gbm.py` and `week3_nn.py`.


## Part 1: do XGBoost / LightGBM beat the Week 2 baseline?

Same data, same 5 folds (seed 42) and same 492 frauds as Week 2, so scores are directly comparable.

| Model | PR-AUC (5-fold CV) | vs Week 2 baseline | folds better |
|---|---|---|---|
| HistGB (Week 2) | 0.859 ± 0.022 | 0.000 (re-run reproduces Week 2) | n/a |
| XGBoost | 0.858 ± 0.025 | -0.001 ± 0.006 | 3 of 5 |
| **LightGBM** | **0.862 ± 0.022** | **+0.003 ± 0.001** | 5 of 5 |

**Recorded delta: +0.003 (LightGBM over Week 2 HistGB). Negligible.**

What it taught me:

1. **The model family matters more than the library.** Logistic regression to boosted trees was +0.10 in Week 2. Swapping boosting libraries moved the score by 0.003 or less. All three build many small trees, each fixing the previous ones' errors, with the same regularization ideas.
2. **A consistent gap can still be too small to matter.** LightGBM won every fold, but by about a tenth of the fold-to-fold spread of the scores. Judge a gap by its size *and* its consistency.
3. **Reproducing an old result is a free sanity check.** HistGB matching Week 2 exactly shows the folds and data are the same.
4. **Settings were hand-picked, not tuned.** "No difference" holds for these settings only.
5. **The regularization from Week 2 was needed in all three libraries.** The rare-fraud problem comes from the data, not from one library.
6. **Choosing among them:** any of the three works here. Tie-breakers are what's already installed (HistGB needs no extra dependency), speed, and team familiarity. XGBoost and LightGBM are the names you meet in production and job posts.

Settings used (300 trees, learning rate 0.05, L2 penalty 10, small-leaf limits, 80% row/feature sampling for XGBoost and LightGBM) are in `classical_ml/reports/week3_gbm.py`.

## Part 2: SHAP

SHAP gives each feature credit or blame for moving one transaction's score away from the model's
average score. Scores are in log-odds (a stretched version of probability). Model: LightGBM fitted
on train, explained on the 42,721 validation rows.

**Global** (average size of each feature's push, across all rows): V4 0.71, V14 0.35, V12 0.25,
V8 0.20, V26 0.19, Time 0.16, V15 0.16, Amount 0.13. The top 5 features carry only 42% of the total,
so the signal is spread over many columns.

**Local** (one median-scored fraud, P(fraud) = 0.93): V14 = -10.1 pushed the score up by 4.9, V4 = 9.65
by 2.4, V10 = -11.2 by 2.0, V12 = -13.1 by 1.4. The lowest-scoring normal row I looked at had only small pushes down (largest -0.58).

What it taught me:
1. **SHAP explains what the model relies on, not what causes fraud.** Correlated features share credit.
2. **Anonymized features limit the explanation.** "V14 was extremely negative" ranks the evidence but is
   not a reason a customer or regulator can read. With named features it would be.
3. **Time and Amount rank 6th and 8th**, yet adding hour and tiny-amount features in Week 2 did not
   help: the model was already using them.
4. **The base value (-10.1) is the average raw score, mostly from normal rows. It is not a fraud rate.**
   Per-row pushes add up to the row's score: base + pushes = log-odds.
## Part 3: Neural network basics (PyTorch)

### The building blocks

- **Tensor:** an array of numbers that PyTorch can track calculations on. `torch.tensor([2., 3.])`
  is a vector of 2 floats. Same idea as a NumPy array, plus gradients.
- **Neuron:** `z = w1*x1 + w2*x2 + ... + b`, then an **activation** function. The weights `w` and bias `b`
  are what the network learns. Example: x = [2, 3], w = [0.5, -1], b = 0.1 gives z = -1.9.
- **Activation function:** a bend applied to z. ReLU is `max(0, z)` (so -1.9 becomes 0). Sigmoid squashes
  z to 0-1 (so -1.9 becomes 0.13, a probability).
- **Why the bend matters:** without it, stacking layers collapses into one straight-line model. Two
  linear layers are mathematically the same as one. Activations are what let a network learn curves
  and interactions. (The notebook verifies this.)
- **Layer / network:** a layer is many neurons side by side. The fraud network is 30 inputs, then 64
  neurons, then 32, then 1 output = **4,097 weights** (30x64+64, 64x32+32, 32x1+1).
- **Loss:** one number for how wrong the predictions are. For fraud (yes/no) we use binary
  cross-entropy: a confident correct call (p = 0.9 for a fraud) costs 0.105, a confident wrong one
  (p = 0.1) costs 2.30. It punishes confident mistakes hardest.
- **Gradient:** for each weight, the slope of the loss: "if I raise this weight a little, does the loss go
  up or down, and how fast?" **Autograd** computes all of them automatically. Check: fitting one weight,
  PyTorch gave a slope of -19.5, equal to the hand calculation. Negative slope means "raise the weight".
- **Gradient descent:** nudge every weight a small step against its slope, repeat. The step size is the
  **learning rate**. **Adam** is a popular version that adapts the step per weight.
- **Epoch / batch:** an epoch is one pass over the training data. A batch is the small chunk (here 1,024
  rows) used for each nudge, which is faster and noisier than using all the data at once.

### The training loop (every network does this)

```
opt.zero_grad()                 # clear old slopes
loss = loss_fn(model(x), y)     # forward pass: predict, then measure the error
loss.backward()                 # autograd: slope of the loss for every weight
opt.step()                      # Adam moves each weight a little against its slope
```

Inputs must be **scaled** (mean 0, std 1; fitted on train only). Networks are far more sensitive to
scale than trees, which only care about the order of values.

### Result: small network vs LightGBM (validation split, 74 frauds)

| epoch | 1 | 5 | 10 | 20 | 30 |
|---|---|---|---|---|---|
| val PR-AUC | 0.487 | 0.643 | 0.617 | 0.759 | 0.771 |

Best 0.781 (epoch 24, chosen on validation, so optimistic). LightGBM on the same split: 0.831.
Plain logistic regression: 0.670.

What it taught me:
1. **My prediction held: a small network did not beat boosted trees on this table.** Trees need no
   scaling, handle sharp rules and interactions with little tuning, and train in seconds. The network
   has only 344 training frauds to learn from.
2. **But it's evidence, not proof.** One split, one seed and 74 frauds means a 0.05 gap is within the
   noise seen all through Week 2. Cross-validation over several seeds would settle it.
3. **Training is bumpy.** Validation PR-AUC fell from epoch 5 to 10 then recovered, because with ~0.17%
   fraud each batch holds very few frauds, so updates are noisy.
4. **Networks beat linear models (0.77 vs 0.67) because the hidden layers add the bends** that let
   them combine features.

Notebook: `classical_ml/notebooks/03_gbm_shap_and_nn.ipynb`. Script: `classical_ml/reports/week3_nn.py`.
## Part 4: Why a GBM beats an LLM for this problem

**Problem:** decide, for each card transaction, whether it is fraud (0.17% of 284,807 rows), using 30
numeric columns, while the customer waits at the till.

**Strongest argument (my pick): latency.** A payment is approved or declined in real time, so the
fraud check gets a small slice of the time budget. Measured on this laptop, one CPU thread, one
transaction at a time, model scoring only:

| Scoring one transaction | p50 | p95 | p99 |
|---|---|---|---|
| LightGBM, raw booster (numpy input) | 0.07 ms | 0.08 ms | 0.10 ms |
| LightGBM, scikit-learn API (numpy input) | 0.44 ms | 0.53 ms | 0.68 ms |
| LightGBM, scikit-learn API (DataFrame input) | 0.89 ms | 1.01 ms | 1.12 ms |
| scikit-learn HistGradientBoosting | 2.26 ms | 3.24 ms | 3.43 ms |
| Small PyTorch network (4,097 weights) | 0.04 ms | 0.06 ms | 0.08 ms |

Batch: LightGBM scored all 42,721 validation rows in 0.60 s, about **71,000 rows per second on one
thread**.

How to read it:
- Under a millisecond for the model in every LightGBM case, and the tail (p99) is barely above the median.
- **Most of the time is Python wrapper overhead, not the trees.** The raw booster is 13 times faster
  than the same model through the scikit-learn API with a DataFrame. HistGB is slowest here (2.3 ms)
  for the same reason. In production you would serve the booster or an exported model.
- **Not included:** network hops, fetching features about the card, and the rest of the payment
  system. Real latency is higher than these numbers. Measured on my machine, not a server.
- **An LLM was not measured here** (no API access). From general knowledge, not from this project: a
  hosted LLM call typically takes hundreds of milliseconds to seconds, depends on output length and
  load, and has a much wider tail. Check the figures for the provider you would actually use.
  Even at the optimistic end it is hundreds of times slower than the model above, and the whole
  authorization decision usually has a budget of only tens to a few hundred milliseconds.

**The other three arguments, briefly**
- **Cost:** the GBM trains on a laptop CPU with no GPU and has no per-call fee. An LLM is typically
  billed per token for every transaction, so cost scales with volume, and fraud systems score every
  transaction. (Pricing varies by provider: look it up before quoting a number.)
- **Explainability:** SHAP (Part 2) gives each prediction an exact breakdown that adds up to the score.
  An LLM's written explanation is a story it generates, and need not reflect how the score was made.
  Limitation: with anonymized features the SHAP reasons are not human-readable. Named features fix that.
- **Data shape:** 30 numeric columns, no text. Boosted trees are strong on tables (Week 2: 0.859 PR-AUC
  vs 0.758 for logistic regression; even a small neural net trailed them on the one split I tried).
  An LLM's strength is language, and there is no language here.

**Where an LLM would help instead:** reading free text (a dispute description, merchant notes),
drafting an analyst's case summary from the GBM's SHAP output, or answering policy questions. A common
design is a GBM making the real-time decision and an LLM working on the slower, text-heavy side.

**My honest caveats**
- I measured the GBM only. I did not benchmark any LLM or compare accuracy with one.
- "GBM beats an LLM" holds for *this* problem: real-time, numeric, high volume, explainable. It is not
  a general claim.

### In my own words

*(Draft written for me from the Week 3 work. Edit it into my own voice.)*

> A card payment is approved or declined while the customer stands at the till, so the fraud check
> gets a tiny slice of the time budget. A boosted-tree model scores a transaction in well under a
> millisecond on one CPU thread (0.07 ms for the raw LightGBM booster, p99 0.10 ms), and its slowest
> calls are barely slower than its median. A hosted LLM call typically takes hundreds of milliseconds
> to seconds, with a much wider tail, and I haven't measured one. The input is also 30 numbers with no
> text, which is where trees are strong and an LLM has no edge. I'd keep the GBM in the real-time path
> and use an LLM for the slow, text-heavy jobs, like summarizing a case from the SHAP output.

## What confused me

*(Draft from what came up this week. Edit it so it is honest to me.)*

- **The three libraries looked different but gave the same answer.** I expected one to win. The lesson
  was that the model *family* (trees vs straight-line) mattered 30 times more than the *library*.
- **"Won every fold" does not mean "meaningfully better".** LightGBM won 5 of 5 by +0.003, a tenth of the
  fold-to-fold spread. I had to judge a gap by size *and* consistency.
- **The learning-rate exercise.** I guessed `lr = 0.5` would "overshoot". It does, but each overshoot is
  bigger than the last, so it diverges. The distance from the answer gets multiplied by
  `1 - 13 x lr`, which is -5.5 at 0.5 but -0.3 at 0.1 (which converges, zigzagging).
- **Why an activation function is needed.** Two linear layers are just one linear layer. The notebook
  proved it with `torch.allclose`, which made it click.
- **SHAP on anonymized columns.** It ranks the evidence (V4, V14, V12...) but gives no reason a person
  could read. The base value (-10) is not a fraud rate either.
- **Confusing a loss with a score.** A normal transaction predicted at 0.9 costs the same as a fraud
  predicted at 0.1 (2.303): the loss only looks at the probability given to what actually happened.

## One number that moved

LightGBM over the Week 2 baseline: **+0.003 PR-AUC** (0.862 vs 0.859). Small on purpose: it showed me that
the algorithm, not the library, was doing the work. The bigger number of the week is the gap between
the small neural network (0.78 on validation) and LightGBM (0.831).

## One interview question I can now answer

**"Why use a gradient-boosted tree model instead of an LLM for real-time fraud scoring?"**

The decision is numeric, high-volume and made while the customer waits. A GBM scores a transaction in
well under a millisecond on a CPU, costs nothing per call, trains in minutes, and its predictions can be
broken down exactly with SHAP. An LLM is built for language, adds hundreds of milliseconds or more and a
per-token fee for every transaction, and its written explanation is generated text, not a decomposition
of the score. I'd use an LLM where there is text: dispute descriptions, case summaries, policy
questions. (Caveat: I benchmarked only the GBM, not an LLM.)

## Reproducing this

```bash
uv sync --all-groups                                   # xgboost, lightgbm, shap, torch, ipywidgets
uv run python classical_ml/reports/week3_gbm.py        # 5-fold GBM comparison (a few minutes)
uv run python classical_ml/reports/week3_nn.py         # the small network (about a minute)
uv run --all-groups jupyter lab                        # open notebooks/03_gbm_shap_and_nn.ipynb
```

Needs `data/raw/creditcard.csv` (see *Reproducing this* in `notes/week-02.md`). Use Python 3.11 for the venv.

## Still to do

- [ ] Edit the two drafted sections above ("In my own words", "What confused me") into my own voice
- [ ] Do the six "Your turn" tasks at the end of the notebook (seeds, `pos_weight`, size, overfitting, no scaling)
- [ ] Optional: cross-validate the network over several seeds to settle LightGBM vs NN properly
- [ ] Commit and push Weeks 1 to 3 (nothing is committed yet)
