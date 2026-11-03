"""Kinship tree of a taxon page (ALCANCE.md §11.2, Phase 3 H7): a small cladogram of
the page's neighbourhood in PBDB's classification, with each genus drawn over the
time it lived (first and last appearance, Ma) on the geological periods.

Only the neighbourhood is drawn (dbt mart fct_taxon_neighborhood), never the whole
tree. The SVG is static: links work without JavaScript, and app.js only adds the
period filter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from markupsafe import Markup, escape

from paleo.site.terms import PERIODS, TIME_UNITS

ROW = 22  # px per genus
TOP = 34  # room for the period names
CLADO_W = 150  # cladogram width
LABEL_W = 170  # genus names
TIME_W = 340  # time axis
ICON = 16  # PhyloPic silhouette


@dataclass
class Node:
    key: str
    name: str
    children: list[Node] = field(default_factory=list)
    member: dict[str, Any] | None = None  # set on leaves
    x: float = 0.0
    y: float = 0.0

    def leaves(self) -> list[Node]:
        return [self] if self.member else [n for c in self.children for n in c.leaves()]


def build(rows: list[dict[str, Any]]) -> Node:
    """Tree of one neighbourhood level: the level's clade, the clades in between
    (only those that branch) and one leaf per genus."""
    root = Node("root", rows[0]["level_clade_name"])
    index: dict[str, Node] = {}
    for row in rows:
        parent = root
        for step in row["path"] or []:
            node = index.get(step["clade_no"])
            if node is None:
                node = index[step["clade_no"]] = Node(step["clade_no"], step["name"])
                parent.children.append(node)
            parent = node
        parent.children.append(Node(row["member_key"], row["member_name"], member=row))
    _collapse(root)
    _sort(root)
    return root


def _collapse(node: Node) -> None:
    """Drop the clades with a single child: they add depth but no branching."""
    for i, child in enumerate(node.children):
        while not child.member and len(child.children) == 1:
            child = child.children[0]
        node.children[i] = child
        _collapse(child)


def _sort(node: Node) -> str:
    """Children ordered by their first genus name, so the order is stable."""
    keys = {id(c): (_sort(c) if not c.member else c.name) for c in node.children}
    node.children.sort(key=lambda c: keys[id(c)])
    return min(keys.values()) if keys else node.name


def _depth(node: Node) -> int:
    return 0 if node.member else 1 + max(_depth(c) for c in node.children)


def layout(root: Node) -> int:
    """Leaves one per row, inner nodes at the middle of their children; returns rows."""
    leaves = root.leaves()
    for i, leaf in enumerate(leaves):
        leaf.y = TOP + i * ROW + ROW / 2
        leaf.x = CLADO_W
    step = CLADO_W / max(_depth(root), 1)

    def place(node: Node, depth: int) -> None:
        if node.member:
            return
        node.x = depth * step
        for c in node.children:
            place(c, depth + 1)
        node.y = (node.children[0].y + node.children[-1].y) / 2

    place(root, 0)
    return len(leaves)


def _domain(members: list[dict[str, Any]]) -> tuple[float, float]:
    olds = [m["first_appearance_max_ma"] for m in members if m["first_appearance_max_ma"]]
    youngs = [
        m["last_appearance_min_ma"] for m in members if m["last_appearance_min_ma"] is not None
    ]
    if not olds:
        return 1.0, 0.0
    old, young = max(olds), min(youngs or [0.0])
    pad = max((old - young) * 0.06, 1.0)
    return old + pad, max(young - pad, 0.0)


def periods(old: float, young: float) -> list[tuple[float, float, str, str]]:
    """The geological periods the axis covers, clipped to it."""
    return [
        (min(o, old), max(y, young), en, es)
        for o, y, en, es in TIME_UNITS
        if en in PERIODS and o > young and y < old
    ]


def svg(
    rows: list[dict[str, Any]],
    *,
    lang: str,
    url,
    label: str,
    silhouettes: dict[str, str] | None = None,
) -> Markup:
    """The SVG of one neighbourhood level (rows of fct_taxon_neighborhood)."""
    root = build(rows)
    n = layout(root)
    members = [leaf.member for leaf in root.leaves()]
    old, young = _domain(members)
    x0 = CLADO_W + LABEL_W
    width, height = x0 + TIME_W + 10, TOP + n * ROW + 10

    def tx(ma: float) -> float:
        return x0 + (old - ma) / (old - young) * TIME_W if old > young else x0

    out = [
        f'<svg class="tree" viewBox="0 0 {width:.0f} {height:.0f}" role="img" '
        f'aria-label="{escape(label)}">'
    ]
    for p_old, p_young, en, es in periods(old, young):
        a, b = tx(p_old), tx(p_young)
        name = es if lang == "es" else en
        out.append(
            f'<g class="tree__period" data-period="{escape(en)}" data-old="{p_old:g}" '
            f'data-young="{p_young:g}"><rect x="{a:.1f}" y="{TOP - 6}" '
            f'width="{b - a:.1f}" height="{height - TOP - 4}"/>'
            f'<text x="{(a + b) / 2:.1f}" y="{TOP - 12}">{escape(name)}</text></g>'
        )

    def edges(node: Node) -> None:
        if node.member:
            return
        out.append(
            f'<line class="tree__edge" x1="{node.x:.1f}" y1="{node.children[0].y:.1f}" '
            f'x2="{node.x:.1f}" y2="{node.children[-1].y:.1f}"/>'
        )
        for c in node.children:
            out.append(
                f'<line class="tree__edge" x1="{node.x:.1f}" y1="{c.y:.1f}" '
                f'x2="{c.x:.1f}" y2="{c.y:.1f}"/>'
            )
            edges(c)
        if node is not root:
            out.append(
                f'<text class="tree__clade" x="{node.x + 3:.1f}" y="{node.y - 4:.1f}">'
                f"{escape(node.name)}</text>"
            )

    edges(root)
    for leaf in root.leaves():
        m = leaf.member
        assert m is not None
        cls = "tree__leaf is-self" if m["is_self"] else "tree__leaf"
        first, last = m["first_appearance_max_ma"], m["last_appearance_min_ma"]
        icon = (silhouettes or {}).get(m["member_key"])
        name_x = CLADO_W + 6 + (ICON + 4 if icon else 0)
        parts = [f'<g class="{cls}"']
        if first is not None:
            parts.append(f' data-from="{first}" data-to="{last if last is not None else first}"')
        parts.append(">")
        if icon:
            parts.append(
                f'<image href="{escape(icon)}" x="{CLADO_W + 4}" y="{leaf.y - ICON / 2:.1f}" '
                f'width="{ICON}" height="{ICON}" preserveAspectRatio="xMidYMid meet"/>'
            )
        parts.append(
            f'<a href="{escape(url("taxon", m["member_key"]))}"><text x="{name_x}" '
            f'y="{leaf.y + 4:.1f}"><tspan font-style="italic">{escape(m["member_name"])}'
            "</tspan></text></a>"
        )
        if first is not None:
            a, b = tx(first), tx(last if last is not None else first)
            parts.append(
                f'<rect class="tree__bar" x="{a:.1f}" y="{leaf.y - 5:.1f}" '
                f'width="{max(b - a, 2):.1f}" height="10" rx="2">'
                f"<title>{escape(m['member_name'])}: {first:g}\u2013{(last or 0):g} Ma"
                "</title></rect>"
            )
        parts.append("</g>")
        out.append("".join(parts))
    out.append("</svg>")
    return Markup("".join(out))


def tree_periods(rows: list[dict[str, Any]], lang: str) -> list[tuple[str, str]]:
    """(English key, name in ``lang``) of the periods the tree's axis covers."""
    old, young = _domain(rows)
    return [(en, es if lang == "es" else en) for _, _, en, es in periods(old, young)]
