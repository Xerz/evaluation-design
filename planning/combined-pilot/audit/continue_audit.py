"""Create a separate, bounded claim-review layer; never rewrite legacy links."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAY = "2026-10-06"

def read(name):
    return json.loads((HERE / name).read_text())

def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

def review(code, scope, url, locator, statement, boundary, targets):
    return dict(id=f"SR-{DAY}-{code}", source_code=code, checked_on=DAY,
                scope=scope, url=url, locator=locator, supported_statement=statement,
                boundary=boundary, applicable_targets=targets)

def build():
    previous = [dict(r, id=f"SR-2026-10-05-{r['source_code']}", checked_on="2026-10-05",
                     applicable_targets=[]) for r in read("content-review.json")]
    newer = [
        review("S01", "selected_full_text_fragments",
               "https://teach.ucmerced.edu/sites/g/files/ufvvjh1831/f/page/documents/smith-et-al-2017-the-classroom-observation-protocol-for-undergraduate-stem-copus-a-new-instrument-to-characterize.pdf",
               "pp. 619–623, Figure 1, Validity",
               "COPUS кодирует действия преподавателя и студентов в двухминутных интервалах; несколько кодов могут сосуществовать.",
               "Описание действий не является оценкой эффективности. Сложные суждения о познавательном уровне и внимании исключались из основного набора из-за проблем согласия; C18 не получает автоматический балл внимания.",
               ["C15", "C18", "C20", "C22"]),
        review("S02", "selected_full_text_fragments",
               "https://tdop.wceruw.org/TDOP-2.1-Users-Guide.pdf",
               "TDOP 2.1: pp. 3–5, 13, 16; code keys and interpretation",
               "Набор наблюдаемых кодов выбирают под задачу; наблюдателей обучают и проверяют согласие. Доли двухминутных интервалов не равны секундам действия и не обязаны суммироваться до 100%.",
               "Прямого перевода частот в качество 0–2 нет. Рекомендация авторов по согласованности не принята как порог нашего пилота. Индивидуальная адаптация и цифровая эффективность требуют отдельного основания.",
               ["C15", "C18", "C19", "C20", "C22"]),
        review("S08", "primary_abstract",
               "https://www.tandfonline.com/doi/abs/10.1080/03634523.2016.1202994",
               "Abstract: 566 students; 20 items; five factors",
               "Шкала ясности преподавания исследована по студенческим ответам; различаются уровни требуемого вывода.",
               "Пункты и полный анализ не прочитаны. Аннотация не подтверждает девять отдельных соответствий нашей рубрике и автоматическую оценку по транскрипту.", []),
        review("S10", "primary_abstract",
               "https://link.springer.com/article/10.1007/BF00138871",
               "Abstract: constructive alignment",
               "Цели, учебные действия и оценивание должны быть согласованы.",
               "Для проверки требуются реальные цели, задания и способы оценивания. Абстрактный принцип не подтверждает совпадение слов или эффективность цифрового средства.", ["C01", "C14", "C15"]),
        review("S12", "selected_full_text_fragments",
               "https://link.springer.com/article/10.1186/s40561-022-00200-2",
               "Background: multimedia learning principles; Discussion",
               "Эффект мультимедийных принципов зависит от материалов, задач и особенностей учащихся; показ материала нужно проверять отдельно.",
               "Поддерживает рассмотрение реальных слайдов/материалов, но не проверку физического комфорта аудитории C16 и не автоматический балл C12.", ["C12"]),
        review("S17", "selected_full_text_fragments",
               "https://www.educ.cam.ac.uk/research/programmes/analysingdialogue/LCSI_2016_post-print.pdf",
               "Author postprint, p. 4, §2: hierarchy, communicative act, temporal sequences",
               "SEDA рассматривает вклад одного участника и последовательность вкладов с учётом предшествующего контекста; выделяет функции рассуждения и диалога.",
               "Счёт вопросительных знаков не является анализом диалога. Аффект не составляет предмет схемы; взгляд/тон/жесты не заменяют анализ содержания. Выбранный фрагмент не является полным чтением 29 страниц.", ["C19", "C20"]),
        review("S18", "selected_full_text_fragments",
               "https://education.asu.edu/sites/default/files/lcl/chiwylie2014icap_2.pdf",
               "pp. 219–220, 235–236; caveats in knowledge-process account",
               "ICAP связывает виды наблюдаемой учебной деятельности с познавательной вовлечённостью. Работа в паре сама по себе не означает Interactive: требуется совместное построение содержания.",
               "Это не классификация эмоционального внимания или взгляда. Понятия ICAP не валидируют C07, перенаправление внимания C18 или цифровой инструмент C22. Контекст задания и предварительные знания существенны.", ["C15", "C19"]),
        review("S29", "selected_full_text_fragments",
               "https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2026.1655426/full",
               "Abstract; §2; §4.4 Limitations; Table 1 belongs to initial item pool",
               "TRUST: итоговый инструмент содержит девять пунктов и два фактора и исследован на прямых ответах студентов.",
               "Исходный пул из 38 пунктов нельзя выдавать за итоговую шкалу. Контекст STEM/life-science и COVID; русская адаптация, доверие к одному занятию и балл 0–2 не проверены.", ["C25", "T8"]),
        review("S32", "full_text_conceptual_review",
               "https://cyberleninka.ru/article/n/k-voprosu-o-psihologicheskoy-bezopasnosti-v-obrazovatelnoy-srede",
               "Текст статьи: психологическая безопасность, насилие, отношения участников",
               "Психологическая безопасность обсуждается как характеристика образовательной среды и отношений, включая защиту от психологического насилия.",
               "Теоретический контекст C23, не эмпирическая валидация распознавания эмоций или перевода в 0–2. Страницы и выпуск библиографически ещё уточняются.", ["C23"]),
        review("S34", "selected_full_text_fragments",
               "https://www.selfdeterminationtheory.org/SDT/documents/2000_RyanDeci_SDT.pdf",
               "pp. 68–71, especially p. 70: competence, autonomy, feedback",
               "Переживание компетентности и автономии связано с внутренней мотивацией; значение обратной связи зависит от контекста.",
               "Концептуальная связь с C24 не делает внутреннее переживание видимым по речи преподавателя. Статья не валидирует нашу шкалу и не предписывает конкретный exit-ticket.", ["C24", "T8"]),
        review("S41", "selected_full_text_fragments",
               "https://nsojournals.onlinelibrary.wiley.com/doi/10.1111/ecog.02881",
               "Abstract; Guidance: choosing blocks, steps 1–4",
               "При зависимых данных схема cross-validation должна учитывать структуру зависимости и цель переноса; случайное разбиение может давать оптимистическую оценку.",
               "Группировка по преподавателю/занятию — наша адаптация к образовательным данным. Статья об экологических данных не доказывает достаточность восьми занятий или межвузовскую переносимость.", ["T5"]),
        review("S42", "selected_full_text_fragments_and_rendered_equation",
               "https://proceedings.mlr.press/v70/guo17a/guo17a.pdf",
               "§2, pp. 2–3, equations 1–3; §4 calibration data",
               "ECE агрегирует разность эмпирической точности и вероятностной уверенности по корзинам с весом доли наблюдений.",
               "Баллы 0–2 и частота ответа не являются вероятностью правильности. Eval-2024 не выдаёт такую уверенность; ECE сейчас неприменима. Калибровка требует отдельной выборки.", ["T6"]),
        review("S43", "selected_full_text_fragments_and_rendered_equation",
               "https://arxiv.org/pdf/1705.08500",
               "v2, §§2–3, pp. 3–4, Eq. 1; §4 ranking",
               "Selective risk — средняя потеря среди принятых ответов, coverage — доля принятых. Теоретические гарантии предполагают соответствующую процедуру и i.i.d. условия.",
               "Компьютерное зрение, не педагогическая рубрика. Без ранжирования/порогов доступна только наблюдаемая точка отказов; нельзя заявить всю кривую risk–coverage или перенести гарантии на наш пилот.", ["T6"]),
    ]
    reviews = previous + newer
    write("source-content-checks-v2.json", dict(checked_on=DAY, reviews=reviews,
          all_full_texts_read=False, operational_data_included=False))
    latest = {r["source_code"]: r for r in reviews}
    latest["S27"]["applicable_targets"] = ["T1"]
    latest["S45"]["applicable_targets"] = ["T7"]
    # This amendment only drives the new claim layer, not the previous saved review.
    claims = []
    for old in read("link-review.json")["links"]:
        source = old["source_code"]
        target = old.get("criterion_code") or old.get("method_code")
        r = latest.get(source)
        status = "pending_full_text"
        supported = None
        locator = None
        if source == "S28":
            status = "excluded_withdrawn"
        elif source == "S40":
            status = "basis_mismatch"
        elif r and target in r.get("applicable_targets", []):
            status = "partial_support"
            supported, locator = r["supported_statement"], r["locator"]
        elif r:
            status = "specific_link_not_established"
        claims.append(dict(id=f"LR-{DAY}-{old['link_code']}", link_code=old["link_code"],
                           source_code=source, target=target, checked_on=DAY,
                           source_review_id=r["id"] if r else None,
                           review_status=status, claim_proposal=f"Основание связи {source} → {target}: требуется конкретный тезис и проверка переноса.",
                           supported_claim=supported, verified_locator=locator,
                           applicability=r["boundary"] if r else "Полный текст и поддерживающий фрагмент ещё не проверены; историческая запись не является основанием валидации."))
    for x in read("new-method-source-links.json")["links"]:
        r = latest["S27"]
        claims.append(dict(id=f"LR-{DAY}-{x['link_code']}", link_code=x["link_code"],
                           source_code=x["source_code"], target=x["method_code"], checked_on=DAY,
                           source_review_id=r["id"], review_status=x["review_status"],
                           claim_proposal=x["supported_claim"], supported_claim=x["supported_claim"],
                           verified_locator=x["verified_paper_locator"], applicability=x["applicability"]))
    counts = {s: sum(r["review_status"] == s for r in claims) for s in sorted({r["review_status"] for r in claims})}
    write("claim-checks-v2.json", dict(checked_on=DAY, historical_links=135, new_links=2,
          counts=counts, claims=claims, criteria_validation_claimed=False))
    lines = ["# Содержательная проверка оснований, второй проход", "", f"Дата: {DAY}. Исторические 135 связей сохранены; ниже отдельный слой проверки, а не замена прежних записей.", "",
             "Проверено доступное содержание для 18 из 47 исходных работ; объём чтения указан для каждой. Для остальных нужны тексты/фрагменты. Ни одно соответствие инструмент → 0–2 не объявлено валидированным.", "",
             "Полный текст, выбранные фрагменты и аннотация — разные уровни проверки. `partial_support` относится только к указанному тезису; не подтверждает всю связь критерия и инструмента.", "",
             "## Проверенные фрагменты", ""]
    for r in newer:
        lines += [f"### {r['source_code']}", "", f"[{r['scope']}]({r['url']}); {r['locator']}.", "", r["supported_statement"], "", "Граница: " + r["boundary"], ""]
    lines += ["## Проверка каждой связи", "", "| Связь | Статус | Проверенный локатор | Граница |", "| --- | --- | --- | --- |"]
    for c in claims:
        clean = lambda s: (s or "—").replace("|", "/").replace("\n", " ")
        lines.append(f"| {c['source_code']} → {c['target']} | {c['review_status']} | {clean(c['verified_locator'])} | {clean(c['applicability'])} |")
    lines += ["", "## Что ещё проверить", "", "Полные пункты и результаты S08; S25/S26 и другие педагогические связи; формулы/сопоставление S37–S39; выбор модели ICC S47; первичный текст S36; протокол совместной работы S44; статус и полный текст S46. S33 закрыт CAPTCHA, обход не выполнялся. Недоступность текста не означает отсутствие основания, но запрещает объявлять его проверенным.", "",
              "Для 41 метрики МГПУ всё ещё нужны определения, единицы, версия и пример экспорта. 13 потенциальных критериев не ограничивают общую матрицу из 36 кандидатных соответствий по C01–C26.", ""]
    (HERE / "claim-checks-v2.md").write_text("\n".join(lines))
    return counts

if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
