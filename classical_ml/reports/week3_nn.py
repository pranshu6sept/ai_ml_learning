"""Week 3: a small PyTorch network on the fraud data, compared with LightGBM on validation.

Fitted on train only; the scaler is fitted on train too. The test split is not used.
Run from the repo root:  uv run python classical_ml/reports/week3_nn.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score
from sklearn.preprocessing import StandardScaler
from torch import nn

from classical_ml.data import train_val_test_split

ROOT = Path(__file__).resolve().parents[2]
EPOCHS = 30
BATCH = 1024


def main() -> None:
    torch.manual_seed(0)
    df = pd.read_csv(ROOT / "data" / "raw" / "creditcard.csv")
    train, val, _ = train_val_test_split(df, target="Class")
    scaler = StandardScaler().fit(train.drop(columns="Class"))

    def tensors(part: pd.DataFrame) -> tuple[torch.Tensor, torch.Tensor]:
        x = scaler.transform(part.drop(columns="Class"))
        return (
            torch.tensor(x, dtype=torch.float32),
            torch.tensor(part["Class"].to_numpy(), dtype=torch.float32),
        )

    x_tr, y_tr = tensors(train)
    x_v, y_v = tensors(val)

    model = nn.Sequential(
        nn.Linear(30, 64), nn.ReLU(), nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1)
    )
    loss_fn = nn.BCEWithLogitsLoss()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    print(f"parameters: {sum(p.numel() for p in model.parameters()):,}")

    best = (0.0, 0)
    for epoch in range(1, EPOCHS + 1):
        model.train()
        perm = torch.randperm(len(x_tr))
        total = 0.0
        for i in range(0, len(perm), BATCH):
            idx = perm[i : i + BATCH]
            opt.zero_grad()
            loss = loss_fn(model(x_tr[idx]).squeeze(1), y_tr[idx])
            loss.backward()
            opt.step()
            total += loss.item() * len(idx)
        model.eval()
        with torch.no_grad():
            p = torch.sigmoid(model(x_v).squeeze(1)).numpy()
        ap = average_precision_score(y_v.numpy(), p)
        best = max(best, (ap, epoch))
        if epoch in (1, 2, 5, 10, 20, 30):
            print(f"epoch {epoch:2d}: train loss {total / len(x_tr):.5f} | val PR-AUC {ap:.3f}")
    print(f"best val PR-AUC {best[0]:.3f} at epoch {best[1]}  (LightGBM on the same split: 0.831)")
    print(f"mean final P(fraud) {float(np.mean(p)):.4f} (true rate {float(y_v.mean()):.4f})")


if __name__ == "__main__":
    main()
