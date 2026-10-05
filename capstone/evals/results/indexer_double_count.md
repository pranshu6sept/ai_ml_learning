Items processed by each consecutive incremental run (no reset) on `faqs.md`. 'Fresh': the first run starts right after the edit. 'Aged': it starts 120 s after.

| Case | Wait before run 1 | Run 1 | Run 2 | Run 3 | Run 4 |
|---|---|---|---|---|---|
| none (control) | 0 s | 0 | 0 | 0 | 0 |
| fresh | 0 s | 1 (+31 s) | 1 (+36 s) | 0 (+102 s) | 0 (+167 s) |
| aged | 120 s | 1 (+131 s) | 0 (+136 s) | 0 (+201 s) | 0 (+267 s) |
