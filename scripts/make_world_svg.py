"""Build site/static/world.svg, the base of every map of finds (§11.1), from Natural
Earth's 1:110m land polygons (public domain, https://www.naturalearthdata.com).

    uv run python scripts/make_world_svg.py ne_110m_land.geojson

Equirectangular projection: x = longitude, y = -latitude, so a page draws its points
straight from the coordinates (viewBox -180 -90 360 180). Coordinates are rounded to
0.1 degree: plenty for a small map, and the file stays small. The land is a <symbol>
that pages reference (<use href=".../world.svg#land">), so it is downloaded once.
"""

import json
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "site" / "static" / "world.svg"


def ring(coords: list[list[float]]) -> str:
    points = []
    for lon, lat in coords:
        p = f"{round(lon, 1):g},{round(-lat, 1):g}"
        if not points or points[-1] != p:
            points.append(p)
    return "M" + "L".join(points) + "Z"


def main(source: str) -> None:
    features = json.loads(Path(source).read_text(encoding="utf-8"))["features"]
    paths = []
    for feature in features:
        geometry = feature["geometry"]
        polygons = geometry["coordinates"]
        if geometry["type"] == "Polygon":
            polygons = [polygons]
        for polygon in polygons:
            paths.append("".join(ring(r) for r in polygon))
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-180 -90 360 180">'
        "<!-- Land: Natural Earth 1:110m, public domain. -->"
        f'<symbol id="land" viewBox="-180 -90 360 180"><path d="{"".join(paths)}"/></symbol>'
        "</svg>\n"
    )
    TARGET.write_text(svg, encoding="utf-8")
    print(f"{TARGET}: {len(svg) / 1024:.0f} KB, {len(paths)} polygons")


if __name__ == "__main__":
    main(sys.argv[1])
