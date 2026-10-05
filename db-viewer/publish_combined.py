"""Render the curated public research draft, never the private planning directory."""

from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

import markdown

SOURCE = Path(__file__).resolve().parent / "combined-pilot"
PAGES = (
    ("index", "Обзор"),
    ("product", "Продукт"),
    ("criteria", "26 критериев"),
    ("experiment", "Условия и проверки"),
    ("sources", "Научные основания"),
    ("technical", "Техника"),
    ("annotation", "Выборка и разметка"),
    ("database", "Модель БД"),
    ("roadmap", "Следующие этапы"),
)
MGPU_CANDIDATES = {
    "C02", "C07", "C09", "C13", "C14", "C15", "C16", "C17", "C18",
    "C19", "C20", "C21", "C23",
}
PRIVATE_REFERENCE = re.compile(
    r"/Users/|/home/|file://|localhost|127\.0\.0\.1|SRC-\d|"
    r"\b(?:DOC|CRIT|EXP|LIT|ANN|WEB|DATA|TECH|PRES|SAMPLE)-\d"
)


def render(text: str) -> str:
    result = markdown.markdown(
        text, extensions=["tables", "fenced_code", "sane_lists", "toc"],
        extension_configs={"toc": {
            "toc_depth": "2",
            "slugify": lambda text, separator: re.sub(r"[^\w-]+", separator, text.lower()).strip(separator),
        }}, output_format="html5",
    )
    return re.sub(
        r"<table>(.*?)</table>",
        r'<div class="table-scroll" tabindex="0" role="region" aria-label="Таблица, прокрутка по горизонтали"><table>\1</table></div>',
        result, flags=re.S,
    )


def render_content(name: str, text: str) -> str:
    """Fold long reference cards; explicit C/S/T/E anchors remain inside each card."""
    card_prefix = {"criteria": "c", "sources": "s", "experiment": "t"}.get(name)
    if card_prefix is None:
        return render(text)
    pattern = re.compile(
        rf'(?m)^<a id="{card_prefix}\d{{1,2}}"></a>\s*'
        r'(?:<a id="e\d"></a>\s*)?### ([^\n]+)\n'
    )
    matches = list(pattern.finditer(text))
    if not matches:
        raise ValueError(f"Missing reference cards: {name}")
    result = [render(text[:matches[0].start()])]
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end():end]
        # H2 starts a new section after the last reference card (bibliography/analysis).
        tail = re.search(r"(?m)^## ", block)
        remainder = ""
        if tail:
            remainder, block = block[tail.start():], block[:tail.start()]
        anchors = match.group(0).split("### ")[0]
        label = match.group(1)
        pill = ""
        if label[:3] in MGPU_CANDIDATES:
            pill = '<span class="tag hypothesis">Кандидат МГПУ</span>'
        result.append(
            '<details class="reference-card"><summary>'
            f'<span>{html.escape(label)}</span>{pill}</summary><div class="reference-body">'
            + render(anchors + block) + "</div></details>"
        )
        if remainder:
            result.append(render(remainder))
    return "\n".join(result)


def build_combined(output: Path) -> None:
    destination = output / "combined-pilot"
    destination.mkdir()
    template = (SOURCE / "page.html").read_text(encoding="utf-8")
    manifest: dict[str, str] = {}
    for name, label in PAGES:
        source_text = (SOURCE / "content" / f"{name}.md").read_text(encoding="utf-8")
        if PRIVATE_REFERENCE.search(source_text):
            raise ValueError(f"Private reference in public content: {name}")
        title = source_text.splitlines()[0].removeprefix("# ")
        navigation = "\n".join(
            f'<a href="{page}.html"'
            + (' aria-current="page"' if page == name else "")
            + f'>{html.escape(text)}</a>' for page, text in PAGES
        )
        content = render_content(name, source_text)
        page = template.replace("{{title}}", html.escape(title))
        page = page.replace("{{navigation}}", navigation).replace("{{content}}", content)
        page = page.replace("{{page}}", name)
        if "{{" in page or PRIVATE_REFERENCE.search(page):
            raise ValueError(f"Invalid public HTML: {name}")
        (destination / f"{name}.html").write_text(page, encoding="utf-8")
        manifest[f"{name}.html"] = title
    for filename in ("style.css", "reading.js", "icon.svg"):
        shutil.copy2(SOURCE / filename, destination / filename)
    (destination / "manifest.json").write_text(
        json.dumps({"status": "research_draft", "updated_on": "2026-10-05", "pages": manifest},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
