"""Hand fixes of verified texts (ALCANCE Phase 7), from an edits file:

    uv run python scripts/hand_fix.py EDITS.py   # then: uv run paleo recheck-texts

EDITS.py defines E = [(key, lang, locator, change), ...]:
- locator: a substring that occurs in exactly one sentence of that text, or
  "SECTION:<name>" to insert at the start of a section (created if missing, in the
  English order);
- change: new text (keeps the fact ids) | None (leave the sentence out) |
  (new text, [fact ids]) | (new text, [fact ids], "after") to insert after the located
  sentence.
Every number in a new sentence must be in the facts it cites (or in the old sentence);
otherwise nothing is written. The topic of an inserted sentence is copied from the
English sentence with the same fact ids. A page review record whose hash matched the
old text is updated, so the fix alone does not send the page back to review."""

import datetime
import json
import re
import runpy
import sys
from pathlib import Path

from paleo.config import get_paths
from paleo.narrative import review as rv
from paleo.narrative.write import _stored_sentences, _word_count

D = get_paths().data / "derived"
NUM = re.compile(r"\d+(?:[.,]\d+)?")


def nums(text: str) -> set[str]:
    return {n.replace(",", ".") for n in NUM.findall(text)}


def main(edits_path: str) -> None:
    edits = runpy.run_path(edits_path)["E"]
    keys = sorted({e[0] for e in edits})
    old_pairs = {k: rv.page_pairs(D, k) for k in keys}
    docs: dict[Path, dict] = {}
    errors = []
    for key, lang, locator, change in edits:
        path = D / "texts" / f"{key}.{lang}.json"
        doc = docs.setdefault(path, json.loads(path.read_text(encoding="utf-8")))
        en_doc = json.loads((D / "texts" / f"{key}.en.json").read_text(encoding="utf-8"))
        facts = {
            f["fact_id"]: f for f in json.loads((D / "facts" / f"{key}.json").read_text())["facts"]
        }

        def topic_of(ids: list[str], en_doc: dict = en_doc) -> dict:
            topic = next((s.get("topic") for sec in en_doc["sections"] for s in sec["sentences"]
                          if s["fact_ids"] == ids), None)  # fmt: skip
            return {"topic": topic} if topic else {}

        if locator.startswith("SECTION:"):
            name = locator[len("SECTION:") :]
            sec = next((x for x in doc["sections"] if x["section"] == name), None)
            if sec is None:
                order = [x["section"] for x in en_doc["sections"]]
                pos = sum(
                    1 for x in doc["sections"] if order.index(x["section"]) < order.index(name)
                )
                sec = {"section": name, "sentences": []}
                doc["sections"].insert(pos, sec)
            target = {"text": "", "fact_ids": change[1], **topic_of(change[1])}
            sec["sentences"].insert(0, target)
            change = change[:2]
        else:
            hits = [
                (sec, s)
                for sec in doc["sections"]
                for s in sec["sentences"]
                if locator in s["text"]
            ]
            if len(hits) != 1:
                errors.append(f"{key}.{lang}: {len(hits)} matches for {locator!r}")
                continue
            sec, target = hits[0]
            if change is None:
                sec["sentences"].remove(target)
                continue
            if isinstance(change, tuple) and len(change) == 3 and change[2] == "after":
                new = {"text": "", "fact_ids": change[1], **topic_of(change[1])}
                sec["sentences"].insert(sec["sentences"].index(target) + 1, new)
                target, change = new, change[:2]
        text, ids = change if isinstance(change, tuple) else (change, target["fact_ids"])
        have: set[str] = set()
        for i in ids:
            if i in facts:
                have |= nums(
                    (facts[i].get("statement") or "") + " " + (facts[i].get("quote") or "")
                )
        extra = nums(text) - have - nums(target["text"])
        if extra:
            errors.append(f"{key}.{lang}: numbers not in the facts {sorted(extra)}: {text[:80]}")
        target["text"], target["fact_ids"] = text, ids
    if errors:
        sys.exit("\n".join(errors))
    for path, doc in docs.items():
        doc["sections"] = [s for s in doc["sections"] if s["sentences"]]
        doc["word_count"] = _word_count(_stored_sentences(doc))
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for key in keys:
        record = rv.page_record(D, key)
        if record and record["text_hash"] == rv._text_hash(old_pairs[key]):
            record["text_hash"] = rv._text_hash(rv.page_pairs(D, key))
            record["hand_fixed"] = datetime.date.today().isoformat()
            rv.save_page_record(D, key, record)
    print(f"{len(edits)} edits on {len(docs)} files")


if __name__ == "__main__":
    main(sys.argv[1])
