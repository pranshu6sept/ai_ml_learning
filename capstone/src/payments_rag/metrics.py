"""Ranking metrics for retrieval: recall@k and nDCG@k.

``evaluate_chunking.evaluate`` already reports Hit@k ("is any relevant chunk in the top k?") and MRR
("how high is the first one?"). These two add what those cannot see:

* **recall@k** asks how many of a question's gold passages the top k covered. Hit@k is satisfied by
  one of them; recall@k is the share found, so a question with two gold passages scores 0.5 when
  only one is retrieved.
* **nDCG@k** rewards putting *every* relevant chunk high, not just the first. A relevant chunk at
  rank r earns 1 / log2(r + 1); the sum is divided by the best possible sum (all relevant chunks
  first), so 1.0 means a perfect ordering and 0 means nothing relevant in the top k. Relevance here
  is binary: a chunk either contains a gold phrase or not.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def recall_at_k(covered: Sequence[bool], k: int) -> float:
    """``covered[i]`` says whether gold passage i is in the top k results (the caller works it out).

    Returns the share of gold passages covered. A question with no gold passages has no recall:
    ``nan``, so it cannot be averaged in by accident.
    """
    if not covered:
        return float("nan")
    return sum(covered) / len(covered)


def ndcg_at_k(relevant: Sequence[bool], total_relevant: int, k: int) -> float:
    """nDCG@k with binary relevance.

    ``relevant`` is the relevance of each result in rank order; ``total_relevant`` is how many
    relevant chunks exist in the whole index (it sets the best possible score). No relevant chunk
    anywhere gives ``nan``.
    """
    if total_relevant <= 0:
        return float("nan")
    gain = sum(1 / math.log2(rank + 1) for rank, hit in enumerate(relevant[:k], 1) if hit)
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(total_relevant, k) + 1))
    return gain / ideal
