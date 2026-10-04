The model chooses search filters by calling a `search_corpus` tool (forced, arguments validated). Judge: me, against labels I wrote before the run. One run, small sets: one question is worth 5.6 points on the labelled set.

## 1. Argument accuracy (18 labelled questions)

| Measure | Correct |
|---|---|
| Regions exactly as expected | 18 of 18 |
| Date limit set exactly when expected | 18 of 18 |
| Both | 18 of 18 |

Mistakes:

none

## 2. Would the chosen filters exclude the gold document? (69 answerable golden questions)

| Measure | Count |
|---|---|
| Questions where the model set any filter | 22 of 69 |
| Questions where the filter would exclude every gold document | 0 of 69 |

Questions whose gold document the filter would exclude (these become unanswerable if the filter is trusted):

none
