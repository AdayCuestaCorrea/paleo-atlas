# Which reviewer? (Phase 7, step 5, 2026-11-23)

This study looks for the best way to have a model review the written pages, measured on the 15 hand-reviewed pages (`findings.csv`). It is measured after step 3, so the rules had already removed what they catch.
- **Target:** 42 high or medium text problems are still in those texts: 16 in English and 26 in Spanish.
- **Bar:** the reviewer finds at least 40 % of them and flags at most 10 % of the sentences with no known problem.
- **Everything runs locally on the GPU, at 0 €.** The scripts are in `scripts/reviewer_study/` and the results in `reviewer_study/`.

## Results

| Run | Model | What it reads | Found | Flags on clean sentences | Time (15 pages) |
|---|---|---|---|---|---|
| e1 | Qwen 3.5 9B | 3 sentences at a time, with their quotes, and their Spanish | 5/42 (12 %) | 4.5 % | ~4 min |
| — | Qwen 3.5 9B | the same, 8 sentences at a time | 0 on two pages | — | — |
| e4 | Qwen 3.5 9B | the same, writing the claims against the quotes before deciding | 5/42 (12 %) | 6.0 % | 11 min |
| e5 | gpt-oss 20B (low reasoning) | as e1 | 5/42 (12 %) | 4.2 % | 4 min |
| **e6** | **gpt-oss 20B** | **the whole English page at once: contradictions, repeated claims, missing context, claims about a relative or a formation** | **14/42 (33 %)** | 11.7 % | **1 min** |
| e7 | gpt-oss 20B | as e6, also allowed to use its own knowledge | 14/42 (33 %) | 13.1 % | 1 min |
| e6 + e5 (English only) | gpt-oss 20B | both | **17/42 (40.5 %)** | 13.4 % | 5 min |
| e9 | gpt-oss 20B | e6 a second time | adds nothing | — | — |

Medium reasoning returned empty answers.

## What the numbers say

1. **Per-sentence review is stuck at about 5 of 42, whatever the model or prompt.** Most of the remaining errors are faithful to their own quote:
   - two sentences contradict each other;
   - "these hollow spaces" with nothing before;
   - a Spanish Wikipedia error copied faithfully;
   - outdated science.

   A reviewer that only sees one sentence and its quote cannot see any of these.
2. **Reading the whole page finds three times as many**, in a quarter of the time.
3. **The "flags on clean sentences" overstate the errors**, because the hand review was not exhaustive. I judged 40 such flags from e5 and e6, drawn at random (`reviewer_study/judged_sample.json`):
   - **page-level flags:** 19 of 23 are real problems (≈ 83 %). Most are repeated claims ("named by Barnum Brown in 1908" twice) and real contradictions (*Pachycephalosaurus* 370–450 kg against 2,000 kg; three age ranges for *Allosaurus*).
   - **per-sentence flags:** 6 of 17 (≈ 35 %); English 3 of 8. The Spanish ones object to correct words ("ilion", "nidadas", "piso", "hueso de la suerte").
4. **The 9B model is no better than the 20B in any setup**, and is slower when it reasons.
5. **The model's own knowledge (e7) adds false flags, not finds.**

## Recommendation

- **Reviewer:** gpt-oss 20B, low reasoning.
  - **Page-level review** of every page: about 4 s per page, so ~3 h for the ~2,800 pages, one evening.
  - **Per-sentence review in English only**, against the quotes: ~15 s per page, ~12 h. It adds 3 of the 42, at lower precision.
  - **No per-sentence review in Spanish.** For Spanish, the rules of step 3 work better.
- **What to do with the flags:**
  - **Repeated claims:** leave out the later sentence. This is safe and needs no model.
  - **Contradictions and missing context:** rewrite the page on the GPU with the flags as feedback to the writer, using the retry that already passes problems to the model. Leaving both sentences out would lose good content half the time.
  - **Per-sentence flags:** treat them like contradictions (feedback for the rewrite), never as automatic cuts.
- **What it can't do:** outdated science and errors copied from Spanish Wikipedia stay out of reach for any reviewer that only reads the page. The rules cover part of them (step 3). The rest is what the "¿Ves un error?" link is for.
