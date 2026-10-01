# Week 1: The week I learned not to fool myself

## The question

Which loan applicants will default? That was the whole job. But the real lesson of the week turned
out to be a second question hiding behind the first: **how would I know if my answer was any good?**

## Chapter 1: Looking before modelling

I started with a synthetic dataset of 5,000 applicants, built from a formula I could read. About
12% default. Employment type told the first story: salaried applicants defaulted 9.3% of the time,
unemployed ones 30.9%. Some cells were blank (about 5% of income and credit history), and a good
pipeline has to survive that.

Then a trap. I was asked which of `region` and `owns_home` was pure noise. I said `owns_home`,
because its gap between groups (1.7 points) looked smaller than region's (2.5 points). I was wrong.
Region was the noise. With 200,000 rows, region's gap collapsed to 0.2 points while `owns_home`
held at 2.7. **Noise shrinks as you add data. Real effects stay.** On 5,000 rows, I couldn't tell
them apart by eye. A four-group spread also looks bigger than a two-group one just by chance.

## Chapter 2: Speed, and two kinds of learning

NumPy ran the debt-to-income ratio about 300 times faster than my loop (2.3 µs vs 720 µs):
whole-array operations, no Python loop. k-means found four applicant groups without ever seeing who
defaulted, and their default rates ranged from 6% to 23%. That's supervised vs unsupervised: one
learns from labels, the other finds structure without them.

## Chapter 3: The villain is leakage

This was the centre of the week. I gave a model 200 rows of **pure random noise**, 5,000 features,
random labels. Nothing could predict them. Done the wrong way (choose the 20 "best" features using
all the rows, then cross-validate), it scored **0.79**. Done right (the selector inside the
pipeline), it scored **0.51**, which is coin-flip, the truth.

The wrong way "found signal" because the selector had already seen the validation labels. The rule
that came out of it: **anything that learns from the data goes inside the pipeline**, so each
cross-validation fold refits it on training rows only.

I also learned that leakage isn't the only way to fool yourself. A random forest scored a perfect
1.000 ROC-AUC on the rows it trained on, and 0.662 on rows it had never seen. That's
overfitting, not leakage: nothing slipped in, I just graded the model on its own homework.

## Chapter 4: The numbers

All with 5-fold stratified cross-validation and ROC-AUC (0.5 = coin flip, 1.0 = perfect):

| Model | CV AUC |
|---|---|
| Dummy (always predicts the majority class) | 0.500 |
| Logistic regression | 0.751 ± 0.034 |
| + `debt_to_income` feature | **0.762** ± 0.032 |
| Random forest (with debt-to-income) | 0.713 ± 0.032 |
| *The true formula, the ceiling for any model* | *0.767* |

Three things stand out:

- **The ceiling.** The default label is a weighted coin flip drawn from a probability, so no model
  can reach 1.0. Feature engineering got me from 0.751 to 0.762, which closed most of the 0.016 of
  room that existed. A "mediocre" 0.76 was nearly the best possible.
- **Simpler won.** The forest lost to logistic regression on every one of the five folds. With
  about 4,250 rows and a pattern that is close to linear, the flexible model mostly fit noise.
- **A gain this small needs care.** The +0.011 from debt-to-income is below the ± spread. Both
  models used the same folds, so comparing them fold by fold is fairer: four folds improved, one
  got slightly worse. Probably real, but small.

## Chapter 5: Things that changed nothing (and why that's an answer)

- **Dropping `region`** (the noise column): 0.762 → 0.761. Logistic regression gives a useless
  column a weight near zero. Dropping `employment_type` cost 0.018 and `num_late_payments` cost
  0.034, which is what a real change looks like.
- **Breaking it on purpose** (scaling all rows before cross-validation): 0.729 → 0.730. The leak
  was real but tiny, because a scaler learns two numbers per column from thousands of rows and
  never touches the labels. The feature selector chose among 5,000 columns *using* the labels. To
  see the leak at all, I had to remove the scaler from the pipeline. Otherwise the pipeline's own
  scaler re-standardizes the data and cancels it.

The question to ask of any step: **does it use the labels, and how much freedom does it have to fit
them?** Target encoding (a category replaced by its average default rate) would leak a lot,
especially for rare categories.

## What confused me

- I picked the wrong "noise" column and trusted a gap I could see over the wobble I couldn't.
- `DataFrame.assign` wants `name=values`, not a bare string. A trivial bug, but it cost two tries.
- I put `RandomForestClassifier` in `sklearn.linear_model` (it lives in `sklearn.ensemble`) and
  kept `max_iter` from the logistic version, which forests don't have.
- I called overfitting "leakage". They're cousins, not the same thing.

## One number that moved

Logistic regression, 0.751 → **0.762**, from one feature, `debt_to_income`, that I understood from
the formula. It was small, it was real-ish, and it was near the ceiling of 0.767.

## Interview questions I can now answer

**1. "What is data leakage and how do you prevent it?"**

Leakage is when information from the evaluation data gets into training, so the score looks better
than reality. The sneakiest kind hides in preprocessing: a feature selector, scaler or imputer fit
on all the rows before cross-validation has already seen the validation rows. The fix is to put
every step that learns from data inside a `Pipeline`, so cross-validation refits it on each
training fold only, and to keep a test set untouched until the end. It matters most for steps that
use the labels or choose among many options, like feature selection and target encoding. For a
plain scaler the effect is usually tiny, but the habit costs nothing.

**2. "How do you tell whether a feature is real or just noisy?"**

I look for three clues: does the signal survive cross-validation, does the sign match the generator
or domain logic, and does it hold up when compared to more plausible alternatives? In this dataset,
`region` was noise because it should have had no true effect and its signal disappeared with more
rows; `debt_to_income` did not. The model's coefficients also helped. A positive coefficient for
`debt_to_income` and `num_late_payments` lines up with the underlying formula, while a negative
coefficient for `credit_history_months` and `owns_home` makes sense.

**3. "What is the difference between leakage and overfitting?"**

Leakage happens when the model sees information it should not have, usually from validation or test
rows. Overfitting is when the model memorises the training rows and performs poorly on unseen data.
I saw both: a feature selector that used the validation labels leaked information and inflated the
score, while a random forest scored 1.000 on training rows and only 0.662 on held-out rows because
it fit noise. Cross-validation and a clean pipeline help separate the two.

Exercise 5 is finished: I read the fitted logistic-regression coefficients and compared their signs to
`make_credit_applicants()`. The learned model agreed with the generator: higher debt-to-income and
more late payments pushed default risk up, while longer credit history and owning a home pushed it
down. That was the moment the coefficients stopped being abstract numbers and started feeling like
an explanation.
