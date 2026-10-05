"""Check source fidelity, local links and operational privacy in a Pages build."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from contextlib import closing
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from publish_combined import MGPU_CANDIDATES, PAGES, PRIVATE_REFERENCE
from server import DEFAULT_DB, PUBLIC_SCHEMA_ONLY_TABLES


def normalize(value: str) -> str:
    return " ".join(value.split())


class Page(HTMLParser):
    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.text: list[str] = []
        self.cards: dict[str, str] = {}
        self.card_ids: list[str] | None = None
        self.card_text: list[str] = []
        self.mgpu_labels = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "details":
            assert self.card_ids is None, "Nested reference cards"
            self.card_ids, self.card_text = [], []
        if "id" in data:
            identifier = data["id"]
            assert identifier not in self.ids, f"Duplicate anchor: {identifier}"
            self.ids.add(identifier)
            if self.card_ids is not None:
                self.card_ids.append(identifier)
        if tag == "a" and data.get("href"):
            self.links.append(data["href"])
        if tag in {"link", "script", "img"}:
            value = data.get("href", data.get("src"))
            if value:
                self.links.append(value)
        assert not any(key.startswith("on") for key in data), "Inline event handler"

    def handle_data(self, value):
        self.text.append(value)
        if value == "Кандидат МГПУ":
            self.mgpu_labels += 1
        if self.card_ids is not None:
            self.card_text.append(value)

    def handle_endtag(self, tag):
        if tag == "details":
            for identifier in self.card_ids or []:
                self.cards[identifier] = normalize(" ".join(self.card_text))
            self.card_ids = None


def check_site(site: Path, database: Path = DEFAULT_DB) -> dict:
    pages = {}
    for name, _ in PAGES:
        path = site / "combined-pilot" / f"{name}.html"
        text = path.read_text(encoding="utf-8")
        assert not PRIVATE_REFERENCE.search(text), f"Private reference: {path.name}"
        assert "Проект исследования" in text, f"Missing draft label: {path.name}"
        assert 'name="viewport"' in text, f"Missing responsive viewport: {path.name}"
        pages[path.resolve()] = Page(text)
    link_count = 0
    for path, page in pages.items():
        for link in page.links:
            parsed = urlsplit(link)
            assert parsed.scheme in {"", "https", "http"}, f"Unsafe URL: {link}"
            if parsed.scheme or parsed.netloc:
                continue  # Bibliographic/content review is a separate research task.
            target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            if target.is_dir():
                target /= "index.html"
            assert target.is_file(), f"Broken file link: {path.name}: {link}"
            if parsed.fragment and not parsed.fragment.startswith("/"):
                assert target in pages and unquote(parsed.fragment) in pages[target].ids, \
                    f"Broken anchor: {path.name}: {link}"
            link_count += 1

    criterion_page = pages[(site / "combined-pilot/criteria.html").resolve()]
    experiment_page = pages[(site / "combined-pilot/experiment.html").resolve()]
    sources_page = pages[(site / "combined-pilot/sources.html").resolve()]
    assert len([x for x in criterion_page.cards if re.fullmatch(r"c\d{2}", x)]) == 26
    assert criterion_page.mgpu_labels == len(MGPU_CANDIDATES) == 13
    assert len([x for x in sources_page.cards if re.fullmatch(r"s\d{2}", x)]) == 47
    assert len([x for x in experiment_page.cards if re.fullmatch(r"t\d", x)]) == 9
    assert "снят авторами" in sources_page.cards["s28"]
    assert "Исключён из действующего основания" in sources_page.cards["s28"]
    assert "10.1187/cbe.14-06-0095" in sources_page.cards["s05"]
    assert "Heather E. Sterling" in sources_page.cards["s13"]
    assert "S28 исключён" in experiment_page.cards["t4"]
    assert "S28 исключён" in criterion_page.cards["c23"]
    assert "ошибку/отказ от нуля" in " ".join(criterion_page.text)
    criterion_links = sum(link.startswith("sources.html#s") for link in criterion_page.links)
    method_links = sum(link.startswith("sources.html#s") for link in experiment_page.links)
    assert criterion_links == 111 and method_links == 24, "Missing historical scientific links"
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        scores = connection.execute(
            "SELECT c.code, c.name, s.description FROM criteria c "
            "JOIN criterion_score_levels s ON s.criterion_id=c.id"
        ).fetchall()
        assert len(scores) == 78
        for code, name, score in scores:
            card = criterion_page.cards[code.lower()]
            assert normalize(name) in card, f"Missing criterion name: {code}"
            assert normalize(score) in card, f"Missing original score text: {code}"
        methods = connection.execute(
            "SELECT m.code, m.name, m.description, m.metrics, m.procedure, "
            "e.code, e.unit_of_analysis, e.comparison_description, e.success_rule "
            "FROM verification_methods m JOIN effect_checks e ON e.verification_method_id=m.id"
        ).fetchall()
        assert len(methods) == 9
        for method in methods:
            card = experiment_page.cards[method[0].lower()]
            for field in method[1:5] + method[6:]:
                if field:
                    assert normalize(field) in card, f"Missing method field: {method[0]}: {field}"

    for name in PUBLIC_SCHEMA_ONLY_TABLES:
        path = site / "data/tables" / f"{name}.json"
        if path.exists():
            table = json.loads(path.read_text())
            assert table["rows"] == [] and table["total"] is None and table["restricted"], name
    for path in site.rglob("*"):
        if path.suffix in {".html", ".json", ".js", ".css", ".svg", ".mmd"}:
            assert not re.search(r"/Users/|/home/|file://", path.read_text()), \
                f"Absolute local path in snapshot: {path.relative_to(site)}"
    index = (site / "index.html").read_text()
    assert 'href="./combined-pilot/index.html"' in index
    assert "Историческая версия дизайна" in index
    return {"pages": len(pages), "local_links": link_count, "criteria": 26,
            "score_levels": 78, "mgpu_candidates": 13, "protocols": 9, "sources": 47,
            "criterion_source_links": criterion_links, "method_source_links": method_links,
            "original_method_fields": "preserved", "operational_export": "schema_only",
            "absolute_local_paths": 0, "status": "passed"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check_site(args.site), ensure_ascii=False, indent=2))
