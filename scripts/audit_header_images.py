"""Mark the Commons pictures of the taxon pages that may not show the taxon, for a
review by eye (the result goes to the seed dbt/seeds/image_exclusions.csv).

Rules (a mark is a doubt, not a verdict: synonyms, typos and specimen numbers also
trip them):
  * the file name does not contain the genus;
  * it names another genus (paleo.names.mentions_other_taxon);
  * it reads like a map, a locality, a range or a stamp.

Writes, outside the repo, ``marked.json`` and contact sheets (``sheet-NN.png``,
ImageMagick ``montage``) with the page, the reason and the thumbnail.

    python scripts/audit_header_images.py ~/.local/state/paleo-atlas/maquetas-fotos
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

import duckdb
import httpx

from paleo.config import get_paths
from paleo.names import mentions_other_taxon

PLACE = re.compile(
    r"map|location|locality|localities|range|distribution|outcrop|formation_map|quarry|"
    r"stamp|site_|_site|geolog|stratigraph|country|island",
    re.IGNORECASE,
)


def marks(file_name: str, taxon: str, genus: str) -> list[str]:
    name = file_name.replace("_", " ")
    out = []
    if genus.lower() not in name.lower():
        out.append("sin el género")
    if mentions_other_taxon(name, taxon):
        out.append("otro taxón")
    if PLACE.search(file_name):
        out.append("mapa/lugar")
    return out


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    thumbs = out_dir / "thumbs"
    thumbs.mkdir(exist_ok=True)
    con = duckdb.connect(str(get_paths().warehouse), read_only=True)
    rows = con.sql("""
        select i.taxon_key, t.taxon_name,
               coalesce(t.genus_name, split_part(t.taxon_name, ' ', 1)) as genus,
               i.image_ref, i.image_url, i.source_page_url,
               case i.clade_position when 1 then 'tabla' else 'artículo' end as origin
        from main.int_image_best_per_taxon as i
        join main.dim_taxon as t using (taxon_key)
        where i.image_source = 'commons'
        order by i.taxon_key""").fetchall()
    con.close()
    marked = []
    for key, taxon, genus, ref, url, page, origin in rows:
        why = marks(ref, taxon, genus)
        if why:
            marked.append({"taxon_key": key, "taxon": taxon, "file": ref, "url": url,
                           "page": page, "origin": origin, "why": why})  # fmt: skip
    (out_dir / "marked.json").write_text(json.dumps(marked, ensure_ascii=False, indent=1))
    print(f"{len(rows)} Commons pictures, {len(marked)} marked")
    headers = {"User-Agent": "paleo-atlas-audit (https://github.com/AdayCuestaCorrea/paleo-atlas)"}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=60) as client:
        for i, m in enumerate(marked):
            path = thumbs / f"{i:04d}.jpg"
            if path.exists():
                continue
            url = re.sub(r"/\d+px-", "/330px-", m["url"]) if "/thumb/" in m["url"] else m["url"]
            for attempt in range(3):
                r = client.get(url)
                if r.status_code != 429:
                    break
                time.sleep(5 * (attempt + 1))
            raw = path.with_suffix(".src")
            raw.write_bytes(r.content if r.status_code == 200 else b"")
            subprocess.run(["magick", f"{raw}[0]", "-background", "white", "-flatten",
                            "-resize", "300x220", str(path)], check=False,
                           capture_output=True)  # fmt: skip
            raw.unlink()
            time.sleep(0.2)
    per_sheet = 20
    for s in range(0, len(marked), per_sheet):
        args = ["montage"]
        for i in range(s, min(s + per_sheet, len(marked))):
            m = marked[i]
            label = f"{i}. {m['taxon']} [{', '.join(m['why'])}]\\n{m['file'][:48]}"
            img = thumbs / f"{i:04d}.jpg"
            args += ["-label", label, str(img) if img.exists() else "xc:gray"]
        args += ["-tile", "5x", "-geometry", "300x220+6+6", "-pointsize", "11",
                 str(out_dir / f"sheet-{s // per_sheet:02d}.png")]  # fmt: skip
        subprocess.run(args, check=False, capture_output=True)
    print(f"Sheets in {out_dir}")


if __name__ == "__main__":
    main(Path(sys.argv[1]).expanduser())
