"""Render private/public attribution from one operational-data-free registry."""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def render(registry, public):
    intro = """# Авторство и рабочие решения

Реестр пометок от 07.10.2026. **Автор перечисленных ниже предложений, суждений аудита и технических решений — Codex.** Поручение опубликовать материалы не означает отдельного согласования этих решений или научной валидации.

## Как читать пометки

- **Решение пользователя** — явно принятый объём работ: 26 критериев, 13 потенциальных соответствий только МГПУ, восемь занятий, обязательный транскрипт, проба двух записей, облако и self-host, общая модель с историей, полный старый дизайн и научное подкрепление. Старые Coze-доступы не использовать.
- **Исторический материал** — исходные 26 названий и 78 описаний баллов, старые A0–A5, полные T1–T9/E1–E9 и прежние научные ссылки. Их перенос не является новым решением Codex или новой проверкой.
- **Предложение / допущение / гипотеза Codex** — детализация для обсуждения и проверки. Она не становится согласованной от попадания в текст или БД.
- **Суждение аудитора Codex** — интерпретация прочитанного фрагмента и границы его применения; нужен научный пересмотр. Проверяемые сведения вроде уведомления о снятии статьи отделяются от интерпретации.
- **Реализованный технический выбор** — код или документ уже сделан; его работоспособность и методическая пригодность проверяются отдельно.

AI-ID устойчивы и объединяют связанные частные решения. Дата 07.10.2026 — дата маркировки; точная дата каждого прежнего выбора не восстанавливается предположением. Реестр охватывает подготовку 05–06.10 и текущую публикацию. Утверждённые параметры, ещё открытые решения и находки проверки показаны отдельно.

## Карта решений Codex

| ID | Предмет | Тип |
| --- | --- | --- |
"""
    out = [intro]
    for e in registry["entries"]:
        out.append(f'| [{e["id"]}](#{e["id"].lower()}) | {e["title"]} | {e["status"]} |\n')
    for e in registry["entries"]:
        target = e["public_page"] if public else "../" + e["topic_file"]
        out.append(f'''\n<a id="{e["id"].lower()}"></a>
## {e["id"]}. {e["title"]}

**Автор:** Codex. **Тип:** {e["status"]}. **Помечено:** 07.10.2026.

**Что выбрано или предложено:** {e["choice"]}

**Основание и граница авторства:** {e["basis"]}

**Что ещё требуется:** {e["remaining"]}

**Согласование:** {e["approval"]}.

[Тематическое описание]({target}).
''')
    out.append("\n## Как изменять решение\n\nПри обсуждении сохранить AI-ID и историю; записать отдельное подтверждение пользователя с датой и объёмом. Не менять автора исходного предложения задним числом. Отклонение или замена решения отражаются в тематическом документе, журнале, следующей версии БД и публичных материалах.\n")
    return "".join(out)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true")
    a = p.parse_args()
    registry = json.loads((HERE / "assistant-decisions.json").read_text())
    assert registry["publication_is_method_approval"] is False
    ids = [e["id"] for e in registry["entries"]]
    assert ids == [f"AI-{i:02}" for i in range(1, 30)]
    assert all(e["author"] == "Codex" and e["approval"] for e in registry["entries"])
    targets = [(HERE / "assistant-decisions.md", False),
               (ROOT / "db-viewer/combined-pilot/content/authorship.md", True)]
    for path, public in targets:
        result = render(registry, public)
        if a.check:
            assert path.read_text() == result, f"Attribution out of sync: {path.name}"
        else:
            path.write_text(result, encoding="utf-8")
    print(json.dumps({"attribution_entries": len(ids), "status": "passed" if a.check else "rendered"}))

if __name__ == "__main__":
    main()
