# Evaluation — groq/openai/gpt-oss-120b

2026-11-02T11:38:39+00:00 · gold set of 12 taxa · match threshold 0.75

Recall metrics compare meanings with sentence embeddings; by hand calibration they
can be off by one or two facts per taxon, so use them to compare configurations.

| Metric | Value |
|---|---|
| Taxa evaluated / pending quota / errors | 12 / 0 / 0 |
| EN pages verified | 12 / 12 |
| ES pages verified | 12 / 12 |
| Fact recall (gold facts found by extraction) | 0.385 |
| Text recall (gold facts said in the EN text) | 0.384 |
| Facts accepted / rejected | 188 / 90 |
| Mean EN words | 217.167 |
| Model calls (cached) | 0 (64) |
| Tokens (prompt + completion) | 0 + 0 |
| Model time (s) | 0.0 |

| Taxon | Status | Facts ok/rej | EN | ES | EN words | Fact recall | Text recall |
|---|---|---|---|---|---|---|---|
| Antusuchus | done | 11/4 | verified | verified | 144 | 0.2 | 0.26666666666666666 |
| Asio pythiotus | done | 6/1 | verified | verified | 59 | 0.4444444444444444 | 0.2222222222222222 |
| Bavaricarbo | done | 9/2 | verified | verified | 118 | 0.2857142857142857 | 0.5714285714285714 |
| Carinthiasuchus | done | 7/8 | verified | verified | 129 | 0.3333333333333333 | 0.3333333333333333 |
| Crocodylus lucivenator | done | 35/12 | verified | verified | 308 | 0.6111111111111112 | 0.3888888888888889 |
| Cryptarcus | done | 21/12 | verified | verified | 401 | 0.23529411764705882 | 0.29411764705882354 |
| Ctenosuchus | done | 12/5 | verified | verified | 150 | 0.5555555555555556 | 0.5555555555555556 |
| Haolong | done | 14/5 | verified | verified | 210 | 0.5 | 0.5 |
| Rexarthuria | done | 13/5 | verified | verified | 223 | 0.46153846153846156 | 0.3076923076923077 |
| Spinosaurus mirabilis | done | 23/18 | verified | verified | 390 | 0.16666666666666666 | 0.3333333333333333 |
| Tromerosaurus | done | 21/12 | verified | verified | 233 | 0.47058823529411764 | 0.4117647058823529 |
| Vegavis geitononesos | done | 16/6 | verified | verified | 241 | 0.35714285714285715 | 0.42857142857142855 |
