"""Draft design constants. Readiness states are requirements, not validation results."""
REVISION = "combined-draft-2026-10-06"
DAY = "2026-10-06"

def profiles():
    common = dict(status="draft_not_hardware_tested", trial_recordings=2,
                  original_preserved=True, sha256_required=True,
                  numeric_acceptance_thresholds=None,
                  recording_plan="проверить начало/середину/конец, речь студентов, шум, перекрытия; фиксировать пригодные и потерянные участки",
                  gates=["владелец записи и схема доступа", "проверка двух записей", "утверждение численных QC-порогов после пробы"])
    specs = [
        ("TP-AUDIO", "ASR и проверка речи; аудиопризнаки только при готовом обработчике",
         ["слышимость преподавателя", "слышимость вопросов/ответов студентов", "нет обрезанного начала/конца", "учёт шума/перекрытий", "реальное время, если нужны события"],
         "Микрофон преподавателя и отдельный источник студенческой речи при необходимости; проверить в конкретной аудитории. Не считать один петличный микрофон полным захватом диалога."),
        ("TP-EXPERT-VIDEO", "Независимый экспертный референс",
         ["значимые действия преподавателя", "слайды/доска читаемы для нужных критериев", "синхронный звук", "области вне кадра явно отмечены"],
         "Общий план преподавателя/доски; дополнительные ракурсы только для необходимых наблюдений. Эксперт отмечает непроверяемые критерии."),
        ("TP-MGPU-VIDEO", "Машинный видеовход МГПУ",
         ["официальные требования модуля получены", "нужные лица/ракурсы доступны", "освещение/закрытия", "экспорт и единицы показателей"],
         "Размещение камер определяется модулем. Готовность экспертного видео не означает пригодности для МГПУ; требований разрешения/частоты/числа лиц пока нет."),
        ("TP-CONTENT", "Предметные материалы и показ слайдов/доски",
         ["версия программы/целей", "фактическое задание", "слайд/экран действительно показан", "привязка к занятию и времени"],
         "Исходные файлы + подтверждение использования; файл презентации сам по себе не доказывает показ и использование."),
        ("TP-OA", "Собственный акустический обработчик — кандидат", ["версия обработчика", "вход/выход", "смысл показателей", "измерение времени/ресурсов"], "После проверки обработчика."),
        ("TP-OV", "Собственный видеопроцессор — кандидат", ["версия обработчика", "вход/выход", "смысл показателей", "измерение времени/ресурсов"], "После проверки обработчика."),
    ]
    return [dict(common, code=code, purpose=purpose, checks=checks, placement=placement,
                 storage_visibility="local_only", format_requirements="сохранить исходный формат; производные версии с отдельным хешем",
                 historical_platform_limit=dict(container="MP4", codec="H.264", resolution="720p",
                    duration_minutes=90, max_decimal_MB=512, status="historical_unconfirmed_current_limit"))
            for code, purpose, checks, placement in specs]

def conditions():
    out = []
    def add(code, name, components, inputs, missing, readiness="planned"):
        out.append(dict(code=code, name=name, components=components, inputs=inputs,
                        missing=missing, readiness=readiness))
    add("REF-REC", "Эксперт по записи и контексту", ["EXPERT"], ["recording", "codebook", "available_context"], ["эксперты", "проба и кодбук", "контракт импорта"], "trial_required")
    add("REF-LIVE", "Очное наблюдение", ["EXPERT"], ["in_person_observation"], ["решение Q-03"], "open_decision")
    add("EXP-AI", "Эксперт с закреплённым выходом ИИ", ["EXPERT", "pinned_ai_run"], ["recording", "pinned_run", "codebook"], ["бюджет", "независимый референс", "контракт платформы"], "trial_required")
    add("T", "Eval-2024: транскрипт", ["T"], ["transcript_txt"], ["действующая модель/доступ", "реальный прогон двух записей"], "local_shell_tested")
    add("T-CTX", "Транскрипт и предметный контекст", ["T", "CTX"], ["transcript_txt", "actual_context"], ["реализовать передачу контекста", "зафиксировать состав CTX", "реальная модель"], "not_implemented")
    for code, components, inputs in [("MA",["MA"],["audio"]), ("MV",["MV"],["video"]), ("MA-MV",["MA","MV"],["audio","video"])]:
        add(code, code + ": МГПУ", components, inputs, ["версия/определения/единицы/экспорт", "пригодность записи", "правило перевода признаков"], "supplier_contract_pending")
    for suffix, components in [("MA",["MA"]),("MV",["MV"]),("MA-MV",["MA","MV"])]:
        for context in (False, True):
            code = "T-" + ("CTX-" if context else "") + suffix
            inputs = ["transcript_txt"] + (["actual_context"] if context else []) + (["audio"] if "MA" in components else []) + (["video"] if "MV" in components else [])
            add(code, code, ["T"] + (["CTX"] if context else []) + components, inputs,
                ["исполняемые обработчики", "правило объединения", "одинаковый контекст в паре"], "not_implemented")
    for code, inputs in [("T-ROLE",["transcript_txt","verified_speaker_roles"]), ("T-TIMED",["transcript_txt","real_time_alignment"]), ("T-CTX-LONG",["transcript_txt","actual_context","repeated_observations"])]:
        add(code, code + ": требования к доказательствам", ["T"], inputs, ["проверить необходимые дополнительные данные"], "data_requirements_pending")
    add("MA/MV", "Неопределённый источник кандидатного соответствия МГПУ", ["MA_or_MV_unresolved"], [], ["уточнить модуль для каждого соответствия"], "placeholder_not_runnable")
    add("OA", "Собственный аудиоанализ", ["OA"], ["audio"], ["обработчик и контракт"], "candidate")
    add("OV", "Собственный видеоанализ", ["OV"], ["video"], ["обработчик и контракт"], "candidate")
    return out

def comparisons():
    controls = "Те же пригодные занятия и критерии, версия рубрики/модели/prompt/объединения; одинаковый фактический CTX кроме проверки CTX. Правило и split фиксировать до теста."
    out = []
    def add(code, method, left, right, changed, eligibility):
        out.append(dict(code=code, method=method, left=left, right=right, changed=changed,
                        controls=controls, eligibility=eligibility))
    add("CMP-CTX", "T4", "T", "T-CTX", "контекст", "После реализации T-CTX и наличия материалов")
    add("CMP-MGPU-VIDEO", "T4", "MA", "MA-MV", "MV", "После контракта MA/MV и пригодного видео")
    for ctx in ("", "-CTX"):
        for left, right, changed in [("", "-MA", "MA"),("", "-MV", "MV"),("-MA", "-MA-MV", "MV"),("-MV", "-MA-MV", "MA")]:
            a, b = "T"+ctx+left, "T"+ctx+right
            add("CMP-"+a+"-VS-"+b, "T4", a, b, changed, "Только после реализации входов и правила объединения")
    for condition in [c["code"] for c in conditions() if c["code"] not in ("REF-REC","REF-LIVE","EXP-AI","MA/MV")]:
        for method in ("T1","T2","T3","T6"):
            add(f"CMP-{method}-{condition}-REF", method, condition, "REF-REC", "машинный результат против независимого референса", "T2: реальные интервалы и независимые события; T6: статусы доступны, ECE только с вероятностной уверенностью; остальные: данные и референс")
        add(f"CMP-T9-{condition}", "T9", condition, condition, "повтор запуска", "Неизменные входы/версии; run.repeat_of связывает повторы")
    add("CMP-EXPERT-AI", "T7", "REF-REC", "EXP-AI", "доступ к ИИ", "После пробы затрат, балансировки кейсов и экспертов; независимый референс")
    add("CMP-LIVE-REC", "T3", "REF-LIVE", "REF-REC", "способ наблюдения", "Только после Q-03; очное наблюдение не объявлять абсолютным эталоном")
    add("CMP-GROUP-TRANSFER", "T5", "T", "REF-REC", "группа/преподаватель в удержанном split", "Разведочная подготовка; фиксировать split целыми преподавателями, объём расширения после пробы")
    add("CMP-CONSTRUCT-BOUNDARIES", "T8", "T", "REF-REC", "прокси и прямое подтверждение конструкта", "C24/C25: прямые студенческие данные; C26: принципы и повторные наблюдения")
    return out

LEGACY = {
    "REF-REC":("A0","адаптация референса; состав данных фиксировать"),
    "T":("A2","выделенная текстовая часть, не полная эквивалентность"),
    "T-CTX":("A2","тот же замысел, реализация и состав CTX требуют проверки"),
    "MA":("A1","выделенный аудиомодуль"), "MV":("A1","выделенный видеомодуль"),
    "MA-MV":("A1","два модуля, правила перевода ещё открыты"),
    "T-MA":("A3","вариант без CTX"), "T-CTX-MA":("A3","с явно указанным CTX"),
    "T-MA-MV":("A4","вариант без CTX"), "T-CTX-MA-MV":("A4","с явно указанным CTX"),
    "EXP-AI":("A5","эксперт видит закреплённый запуск")}
