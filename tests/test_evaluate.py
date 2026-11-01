import json
import zlib
from pathlib import Path

import httpx

from paleo.llm import LLM, Provider
from paleo.narrative import evaluate, gold
from paleo.narrative.sources import Chunk

ROOT = Path(__file__).resolve().parents[1]


def fake_embed(texts):
    """Bag-of-words vectors over hashed buckets: same words -> similarity 1."""
    vectors = []
    for text in texts:
        vector = [0] * 256
        for word in text.lower().strip(".").split():
            vector[zlib.crc32(word.encode()) % 256] += 1
        vectors.append(vector)
    return vectors


def test_cosine():
    assert evaluate.cosine([1, 0], [1, 0]) == 1
    assert evaluate.cosine([1, 0], [0, 1]) == 0
    assert evaluate.cosine([0, 0], [1, 1]) == 0


def test_recall_counts_reference_items_with_a_close_candidate():
    reference = ["it lived in niger", "it had a sail"]
    score, best = evaluate.recall(reference, ["it lived in niger"], fake_embed, threshold=0.9)
    assert score == 0.5
    assert best[0] > 0.99


def test_recall_edge_cases():
    assert evaluate.recall([], ["a"], fake_embed) == (1.0, [])
    assert evaluate.recall(["a"], [], fake_embed) == (0.0, [0.0])


def test_every_gold_page_is_well_formed():
    paths = sorted((ROOT / gold.GOLD_DIR).glob("*.json"))
    assert len(paths) >= 12
    for path in paths:
        doc = gold.load(path)
        ids = {f["fact_id"] for f in doc["facts"]}
        en, es = gold.sentences(doc, "en"), gold.sentences(doc, "es")
        assert len(en) == len(es), path.name
        assert all(set(f) <= ids and f for _, f in en), path.name


def test_evaluate_taxon_end_to_end_with_a_fake_model(tmp_path):
    chunks = [
        Chunk(
            "t:table:1",
            "wikipedia_table",
            "en",
            "T",
            None,
            "CC BY-SA 4.0",
            True,
            "Testosaurus lived in Niger. It had a large sail on its back.",
        ),
    ]
    doc = {
        "taxon": "Testosaurus",
        "taxon_key": "testosaurus",
        "facts": [
            {"fact_id": "F001", "statement": "It lived in Niger."},
            {"fact_id": "F002", "statement": "It had a large sail."},
        ],
    }
    answers = [
        {
            "facts": [
                {
                    "chunk_id": "t:table:1",
                    "statement": "It lived in Niger.",
                    "category": "time_and_habitat",
                    "quote": "Testosaurus lived in Niger.",
                }
            ]
        },
        {
            "sections": [
                {
                    "section": "time_and_habitat",
                    "sentences": [
                        {"text": "This animal made its home in Niger.", "fact_ids": ["F001"]}
                    ],
                }
            ]
        },
        {"sentences": [{"index": 1, "text": "Este animal vivía en Níger."}]},
    ]

    def handler(request):
        content = json.dumps(answers.pop(0))
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    llm = LLM(
        Provider("test", "https://llm.test/v1"),
        "m",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        cache_dir=tmp_path / "llm",
    )
    result = evaluate.evaluate_taxon(
        llm,
        doc,
        chunks,
        run_dir=tmp_path / "run",
        cache_root=tmp_path / "cache",
        scientific_names=set(),
        embed=fake_embed,
    )
    assert result.status == "done"
    assert (result.en, result.es) == ("verified", "verified")
    assert result.fact_recall == 0.5  # found "lived in Niger", missed "sail"
    summary = evaluate.summarize([result], llm)
    report = evaluate.write_report(summary, tmp_path / "reports", "test")
    assert "| Testosaurus | done | 1/0 | verified | verified |" in report.read_text()
