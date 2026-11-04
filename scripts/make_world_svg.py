"""Build site/static/world.svg, the base of every map of finds (§11.1), from Natural
Earth's land polygons (public domain, https://www.naturalearthdata.com).

    uv run python scripts/make_world_svg.py ne_110m_land.geojson
    uv run python scripts/make_world_svg.py ne_50m_land.geojson --scale 50m \
        --out site/static/world-50m.svg --precision 0.05

The 1:110m map serves the small maps of the taxon pages; the home page map, which
can be zoomed in, uses 1:50m (it has the Canary and Balearic Islands, for example).

Equirectangular projection: x = longitude, y = -latitude, so a page draws its points
straight from the coordinates (viewBox -180 -90 360 180). Coordinates are rounded to
0.1 degree: plenty for a small map, and the file stays small. The land is a <symbol>
that pages reference (<use href=".../world.svg#land">), so it is downloaded once.
"""

import argparse
import json
from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "site" / "static" / "world.svg"


def simplify(points: list[list[float]], tolerance: float) -> list[list[float]]:
    """Douglas-Peucker: drop the points closer than ``tolerance`` degrees to the line
    between their neighbours (iterative, so long coastlines do not hit the recursion
    limit)."""
    if tolerance <= 0 or len(points) < 4:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        (x1, y1), (x2, y2) = points[first][:2], points[last][:2]
        dx, dy = x2 - x1, y2 - y1
        norm = (dx * dx + dy * dy) ** 0.5
        best, index = 0.0, None
        for i in range(first + 1, last):
            x, y = points[i][:2]
            d = (
                abs(dy * x - dx * y + x2 * y1 - y2 * x1) / norm
                if norm
                else ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
            )
            if d > best:
                best, index = d, i
        if index is not None and best > tolerance:
            keep[index] = True
            stack += [(first, index), (index, last)]
    return [p for p, k in zip(points, keep, strict=True) if k]


def ring(coords: list[list[float]], precision: float = 0.1, tolerance: float = 0.0) -> str:
    points = []
    for lon, lat in simplify(coords, tolerance):
        x, y = (
            round(round(lon / precision) * precision, 3),
            round(round(-lat / precision) * precision, 3),
        )
        p = f"{x:g},{y:g}"
        if not points or points[-1] != p:
            points.append(p)
    return "M" + "L".join(points) + "Z"


def main(
    source: str,
    target: Path = TARGET,
    precision: float = 0.1,
    scale: str = "110m",
    tolerance: float = 0.0,
) -> None:
    features = json.loads(Path(source).read_text(encoding="utf-8"))["features"]
    paths = []
    for feature in features:
        geometry = feature["geometry"]
        polygons = geometry["coordinates"]
        if geometry["type"] == "Polygon":
            polygons = [polygons]
        for polygon in polygons:
            paths.append("".join(ring(r, precision, tolerance) for r in polygon))
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-180 -90 360 180">'
        f"<!-- Land: Natural Earth 1:{scale}, public domain. -->"
        f'<symbol id="land" viewBox="-180 -90 360 180"><path d="{"".join(paths)}"/></symbol>'
        "</svg>\n"
    )
    target.write_text(svg, encoding="utf-8")
    print(f"{target}: {len(svg) / 1024:.0f} KB, {len(paths)} polygons")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", help="Natural Earth land GeoJSON")
    parser.add_argument("--out", type=Path, default=TARGET)
    parser.add_argument("--precision", type=float, default=0.1, help="degrees")
    parser.add_argument("--scale", default="110m", help="for the credit comment")
    parser.add_argument("--simplify", type=float, default=0.0, help="Douglas-Peucker, degrees")
    args = parser.parse_args()
    main(args.source, args.out, args.precision, args.scale, args.simplify)
