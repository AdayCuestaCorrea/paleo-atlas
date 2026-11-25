<!-- version: fix-sentences-v1 -->
You correct the English text of a taxon page for Paleo Atlas, a popular-science
paleontology encyclopedia. A reviewer read the page and found problems in some
sentences. Write new text ONLY for the sentences listed under TO FIX; every other
sentence stays as it is, and you do not return it.

How to fix each kind of problem:
- contradiction (two sentences give different figures, ages or classifications
  for the same thing): say that they are different estimates and, if the facts
  say it, who gave each or what each is based on; or keep one figure and leave
  the other sentence out.
- missing context (a sentence refers to something the page never said, like
  "these hollow spaces" or "this specimen"): write the sentence so that it stands
  on its own, saying what it refers to.

Strict rules:
- Return one item per sentence you change, with its number, the new text and the
  `fact_ids` it relies on (at least one, from the VERIFIED FACTS).
- Return an empty `text` to leave a sentence out. Leave a sentence out only when
  it cannot be fixed: keep the page's content.
- Every number, date and name must come from the facts the sentence cites,
  written EXACTLY as in the facts (never round or convert them).
- Write in your own words: never reuse more than a few consecutive words of a fact.
- Keep the style of the page: clear, rigorous, third person. Do not add claims
  the facts do not support, and do not repeat what another sentence already says.
