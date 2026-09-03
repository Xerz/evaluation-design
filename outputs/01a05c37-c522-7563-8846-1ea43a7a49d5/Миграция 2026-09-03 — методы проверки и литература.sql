PRAGMA foreign_keys = ON;

BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS verification_method_research_sources (
    verification_method_id INTEGER NOT NULL REFERENCES verification_methods(id) ON DELETE CASCADE,
    research_source_id INTEGER NOT NULL REFERENCES research_sources(id) ON DELETE CASCADE,
    relation_role TEXT NOT NULL CHECK (relation_role IN (
        'methodological_basis', 'metric_definition', 'design_example', 'boundary_evidence'
    )),
    notes TEXT,
    PRIMARY KEY (verification_method_id, research_source_id)
);

CREATE INDEX IF NOT EXISTS idx_verification_method_sources_source
    ON verification_method_research_sources(research_source_id);

INSERT INTO research_sources
    (id, code, citation_apa, doi, url, study_type, evidence_summary, access_notes,
     evidence_role, verification_status, registry_checked_on, provenance_document_id, notes)
VALUES
    (36, 'S36', 'Messick, S. (1995). Validity of psychological assessment: Validation of inferences from persons'' responses and performances as scientific inquiry into score meaning. American Psychologist, 50(9), 741–749.', '10.1037/0003-066X.50.9.741', 'https://doi.org/10.1037/0003-066X.50.9.741', 'Теоретическая статья о валидности', 'Валидируется не инструмент сам по себе, а интерпретация результата; проверка должна исключать подмену педагогического конструкта похожим техническим признаком.', 'DOI/издатель.', 'Методическая основа конструктной валидности', 'to_review', NULL, NULL, 'Подобрано для T1 и T8; требуется пользовательская верификация.'),
    (37, 'S37', 'Sokolova, M., & Lapalme, G. (2009). A systematic analysis of performance measures for classification tasks. Information Processing & Management, 45(4), 427–437.', '10.1016/j.ipm.2009.03.002', 'https://doi.org/10.1016/j.ipm.2009.03.002', 'Методологический обзор метрик классификации', 'Систематизирует precision, recall, F1 и их варианты; помогает выбирать метрики отдельно для событий и трёх уровней оценки.', 'DOI/издатель.', 'Определение метрик классификации', 'to_review', NULL, NULL, 'Подобрано для T2 и T3; требуется пользовательская верификация.'),
    (38, 'S38', 'Caba Heilbron, F., Escorcia, V., Ghanem, B., & Niebles, J. C. (2015). ActivityNet: A large-scale video benchmark for human activity understanding. In Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition (pp. 961–970).', '10.1109/CVPR.2015.7298698', 'https://openaccess.thecvf.com/content_cvpr_2015/html/Heilbron_ActivityNet_A_Large-Scale_2015_CVPR_paper.html', 'Бенчмарк временной локализации событий', 'Даёт воспроизводимый пример оценки обнаружения событий во времени через перекрытие интервалов; перенос на педагогические события требует собственного правила сопоставления.', 'Открытая версия CVF.', 'Методическая опора temporal IoU', 'to_review', NULL, NULL, 'Подобрано для T2; требуется пользовательская верификация.'),
    (39, 'S39', 'Cohen, J. (1968). Weighted kappa: Nominal scale agreement provision for scaled disagreement or partial credit. Psychological Bulletin, 70(4), 213–220.', '10.1037/h0026256', 'https://doi.org/10.1037/h0026256', 'Методологическая статья', 'Вводит взвешенную каппу для порядковых категорий, где расхождение на один уровень отличается от расхождения на два.', 'DOI/издатель.', 'Определение метрики согласия порядковой шкалы', 'to_review', NULL, NULL, 'Подобрано для T3 и T9; требуется пользовательская верификация.'),
    (40, 'S40', 'Meyes, R., Lu, M., de Puiseau, C. W., & Meisen, T. (2019). Ablation studies in artificial neural networks [Preprint]. arXiv.', '10.48550/arXiv.1901.08644', 'https://arxiv.org/abs/1901.08644', 'Методическая работа об абляциях', 'Показывает логику удаления или добавления компонентов для оценки их отдельного вклада; в пилоте применяется к модальностям, а не к внутренним нейронам модели.', 'Открытый препринт arXiv.', 'Методическая основа абляционного сравнения', 'to_review', NULL, NULL, 'Подобрано для T4; требуется пользовательская верификация.'),
    (41, 'S41', 'Roberts, D. R., Bahn, V., Ciuti, S., Boyce, M. S., Elith, J., Guillera-Arroita, G., Hauenstein, S., Lahoz-Monfort, J. J., Schröder, B., Thuiller, W., Warton, D. I., Wintle, B. A., Hartig, F., & Dormann, C. F. (2017). Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure. Ecography, 40(8), 913–929.', '10.1111/ecog.02881', 'https://doi.org/10.1111/ecog.02881', 'Методологический обзор валидации', 'Обосновывает разбиение зависимых и иерархических данных блоками; занятия одного преподавателя нельзя распределять между настройкой и тестом как независимые строки.', 'DOI/издатель.', 'Методическая основа группового holdout', 'to_review', NULL, NULL, 'Подобрано для T5; требуется пользовательская верификация.'),
    (42, 'S42', 'Guo, C., Pleiss, G., Sun, Y., & Weinberger, K. Q. (2017). On calibration of modern neural networks. Proceedings of Machine Learning Research, 70, 1321–1330.', NULL, 'https://proceedings.mlr.press/v70/guo17a.html', 'Эмпирическая работа о калибровке', 'Различает качество предсказания и соответствие уверенности фактической вероятности ошибки; поддерживает отдельную проверку калибровки уверенности.', 'Открытая версия PMLR.', 'Методическая основа калибровки', 'to_review', NULL, NULL, 'Подобрано для T6; требуется пользовательская верификация.'),
    (43, 'S43', 'Geifman, Y., & El-Yaniv, R. (2017). Selective classification for deep neural networks. Advances in Neural Information Processing Systems, 30.', NULL, 'https://papers.neurips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html', 'Методологическая работа о selective prediction', 'Формализует компромисс риск–покрытие для системы с правом отказа; напрямую поддерживает оценку качества правильного отказа.', 'Открытая версия NeurIPS.', 'Методическая основа режима отказа', 'to_review', NULL, NULL, 'Подобрано для T6; требуется пользовательская верификация.'),
    (44, 'S44', 'Tschandl, P., Rinner, C., Apalla, Z., et al. (2020). Human–computer collaboration for skin cancer recognition. Nature Medicine, 26, 1229–1234.', '10.1038/s41591-020-0942-0', 'https://doi.org/10.1038/s41591-020-0942-0', 'Эксперимент human–AI collaboration', 'Показывает, что полезность ИИ нужно измерять на совместной работе человека и системы и отдельно контролировать риск того, что ошибочная подсказка ухудшает решение.', 'Страница издателя; полный текст может требовать доступ.', 'Пример проверки поддержки эксперта', 'to_review', NULL, NULL, 'Подобрано для T7; перенос из медицинской диагностики требует адаптации.'),
    (45, 'S45', 'Dwan, K., Li, T., Altman, D. G., & Elbourne, D. (2019). CONSORT 2010 statement: Extension to randomised crossover trials. BMJ, 366, l4378.', '10.1136/bmj.l4378', 'https://doi.org/10.1136/bmj.l4378', 'Методическая рекомендация по crossover-дизайну', 'Описывает прозрачную организацию и отчётность crossover-сравнения, где участник служит собственным контролем; в пилоте нужна адаптация к экспертам и кейсам.', 'Открытый текст BMJ.', 'Методическая основа crossover', 'to_review', NULL, NULL, 'Подобрано для T7; требуется пользовательская верификация.'),
    (46, 'S46', 'Vaidya, S., & Saini, J. R. (2026). Consistency evaluation protocol: A reproducible framework for assessing large language model output repeatability. MethodsX, 17, 104069.', '10.1016/j.mex.2026.104069', 'https://doi.org/10.1016/j.mex.2026.104069', 'Протокол повторяемости LLM', 'Предлагает повторный запуск одинаковых промптов и анализ семантической и структурной стабильности; в пилоте дополнительно нужны стабильность балла, отказа и таймкодов.', 'Открытая статья; электронная публикация 25.07.2026.', 'Методическая основа повторных прогонов LLM', 'to_review', NULL, NULL, 'Подобрано для T9; требуется пользовательская верификация.'),
    (47, 'S47', 'Shrout, P. E., & Fleiss, J. L. (1979). Intraclass correlations: Uses in assessing rater reliability. Psychological Bulletin, 86(2), 420–428.', '10.1037/0033-2909.86.2.420', 'https://doi.org/10.1037/0033-2909.86.2.420', 'Методологическая статья о надёжности', 'Даёт правила выбора внутриклассовой корреляции для повторных измерений; применима к числовой уверенности, но не заменяет проверку точного совпадения статусов и баллов.', 'DOI/издатель.', 'Определение метрики повторяемости', 'to_review', NULL, NULL, 'Подобрано для T9; требуется пользовательская верификация.');

UPDATE effects SET hypothesis = 'Использование распознавания эмоций / вовлечённости, а также метрик, вычисленных по аудио, улучшает совпадение с оценками эксперта относительно анализа только транскрипта.'
WHERE code = 'E4';

UPDATE effects SET hypothesis = 'Качество оценки не зависит от преподавателей, дисциплин и форматов.'
WHERE code = 'E5';

UPDATE effects SET hypothesis = 'Скрытые состояния и содержательные свойства не угадываются по эмоциям или поведению; новые данные дают проверяемый прирост. (Вообще это похоже на отдельное исследование.)'
WHERE code = 'E8';

UPDATE effects SET hypothesis = 'Вывод ИИ устойчив при повторных прогонах.'
WHERE code = 'E9';

UPDATE verification_methods SET
    name = 'Экспертная проверка соответствия критерию',
    description = 'Эксперты проверяют, является ли каждый доказательный фрагмент проявлением именно заявленного критерия, а не похожим техническим прокси.',
    metrics = 'Доля подтверждённых фрагментов (construct precision); доля ложных прокси; межэкспертное согласие; распределение типов ошибок',
    procedure = 'Два эксперта независимо и вслепую кодируют фрагменты как «проявление критерия», «похожий след», «недостаточно данных» или «не относится». После независимой разметки расхождения согласуются, а ошибки разбираются по заранее заданной таксономии.'
WHERE code = 'T1';

UPDATE verification_methods SET
    description = 'Автоматические и экспертные интервалы сопоставляются один-к-одному по заранее заданному порогу перекрытия и допуску границ.',
    metrics = 'Precision; recall; macro-F1; temporal IoU; медианная абсолютная ошибка начала и конца сегмента',
    procedure = 'Метрики рассчитываются отдельно по каждому критерию на независимой выборке. Порог temporal IoU, допуск таймкода и правило сопоставления одного события фиксируются до теста.'
WHERE code = 'T2';

UPDATE verification_methods SET
    description = 'После проверки согласия экспертов машинный балл сравнивается с согласованным экспертным референсом как порядковая, а не номинальная оценка.',
    metrics = 'Точное совпадение; расхождение на 1 и 2 балла; weighted kappa; macro-F1; MAE',
    procedure = 'Сначала оценивается межэкспертное согласие и формируется согласованный референс. Статусы insufficient_data, error и not_applicable анализируются отдельно и никогда не кодируются нулём.'
WHERE code = 'T3';

UPDATE verification_methods SET
    name = 'Парная абляция модальностей',
    description = 'На одних и тех же занятиях отдельно измеряется вклад аудио и вклад видео/визуальных сигналов относительно транскрипта.',
    metrics = 'Изменение точного совпадения, weighted kappa и macro-F1; изменение доли подтверждённых доказательств; 95% ДИ разницы',
    procedure = 'При фиксированных версии модели, промпте и наборе занятий парно сравниваются A2 → A3 → A4. Доверительные интервалы рассчитываются кластерным bootstrap по преподавателям и занятиям; результат приводится отдельно по критериям.'
WHERE code = 'T4';

UPDATE verification_methods SET
    name = 'Групповой holdout и анализ переносимости',
    description = 'Данные одного преподавателя или курса целиком остаются только в настройке либо только в тесте, чтобы исключить утечку зависимых наблюдений.',
    metrics = 'Метрики качества по преподавателям, дисциплинам и форматам; худшая страта; падение относительно общей выборки; доверительные интервалы',
    procedure = 'Используется групповой holdout по преподавателю и курсу. На независимом тесте отдельно считаются заранее заданные страты формата, дисциплины и качества записи; отсутствие значимого различия не трактуется как доказательство равенства.'
WHERE code = 'T5';

UPDATE verification_methods SET
    name = 'Selective prediction и проверка отказов',
    description = 'Проверяется, уменьшается ли риск ошибки при расширении зоны отказа и соответствует ли заявленная уверенность фактической точности.',
    metrics = 'Кривая risk–coverage; selective accuracy; точность статуса insufficient_data; доля корректных отказов; опасные уверенные ошибки; ECE/Brier при числовой уверенности',
    procedure = 'Порог отказа и калибровка выбираются только на калибровочной выборке и блокируются до независимого теста. На тесте публикуется вся кривая риск–покрытие, а не одна удобная точка.'
WHERE code = 'T6';

UPDATE verification_methods SET
    description = 'Одни эксперты работают с ИИ-подсказкой, другие без неё, а порядок и набор кейсов уравновешиваются, чтобы отделить эффект помощника от эффекта эксперта и сложности занятия.',
    metrics = 'Время; точное совпадение и weighted kappa с референсом; исправления; опасные пропуски; субъективная полезность и нагрузка',
    procedure = 'Рандомизировать и уравновесить порядок A0/A5 по экспертам и кейсам, не показывать одному эксперту один и тот же кейс рядом в двух условиях, фиксировать время и все изменения подсказки.'
WHERE code = 'T7';

UPDATE verification_methods SET
    name = 'Вложенная проверка границ и добавочных данных',
    description = 'В отдельном подпилоте для каждого критерия сравнивается запись без дополнительных данных с тем же анализом после добавления материалов, диагностики или прямого опроса.',
    metrics = 'Прирост качества и доли проверяемых выводов; корректные отказы; ложные выводы без прямых данных; изменение неопределённости',
    procedure = 'Сравнение проводится парно на тех же занятиях и раздельно по типу добавленных данных. Для C24 и C25 вывод без exit ticket и trust survey запрещён; эмоции и поведение не используются как замена прямым ответам студентов.'
WHERE code = 'T8';

UPDATE verification_methods SET
    name = 'Повторяемость идентичных прогонов',
    description = 'Один и тот же зафиксированный вход многократно обрабатывается одной версией модели с неизменными промптом и параметрами.',
    metrics = 'Доля идентичных статусов и баллов; попарная weighted kappa; разброс уверенности; ICC для числовой уверенности; Jaccard/temporal IoU доказательных фрагментов; доля изменившихся отказов',
    procedure = 'Для каждого выбранного занятия выполняется заранее заданное число независимых повторов A4. Версия модели, промпт, параметры генерации и checksum входов фиксируются; детерминированные и стохастические конфигурации анализируются отдельно. Повторяемость оценивается отдельно от правильности.'
WHERE code = 'T9';

UPDATE effect_checks SET
    unit_of_analysis = 'Доказательный фрагмент × критерий',
    comparison_description = 'A2–A4 против независимой слепой разметки A0.',
    success_rule = 'Минимальная доля подтверждённых фрагментов, максимальная доля ложных прокси и минимальное межэкспертное согласие фиксируются после калибровки.'
WHERE code = 'EC_E1';

UPDATE effect_checks SET
    unit_of_analysis = 'Событие или временной сегмент × критерий',
    comparison_description = 'A2–A4 против таймкодов независимой разметки A0.',
    success_rule = 'Пороги macro-F1, temporal IoU и ошибки границ фиксируются до независимого теста.'
WHERE code = 'EC_E2';

UPDATE effect_checks SET
    comparison_description = 'A1–A4 против согласованного экспертного A0.',
    success_rule = 'Пороги точного совпадения, weighted kappa, macro-F1 и MAE фиксируются после оценки межэкспертного согласия.'
WHERE code = 'EC_E3';

UPDATE effect_checks SET
    unit_of_analysis = 'Критерий × занятие × шаг добавления модальности',
    comparison_description = 'Основное сравнение A2 ↔ A3 ↔ A4; A1 используется как вторичная готовая база.',
    success_rule = 'Для заявленно полезной модальности нижняя граница 95% ДИ заранее выбранной основной метрики должна превышать ноль или заданную минимально важную разницу.'
WHERE code = 'EC_E4';

UPDATE effect_checks SET
    unit_of_analysis = 'Преподаватель или курс как группа; критерий × занятие как наблюдение',
    comparison_description = 'A1–A4 на групповом holdout по преподавателям и курсам с A0 как референсом.',
    success_rule = 'Падение качества в заранее заданных стратах не должно превышать зарегистрированную границу практической эквивалентности; простой p>0,05 не считается доказательством независимости.'
WHERE code = 'EC_E5';

UPDATE effect_checks SET
    unit_of_analysis = 'Вывод или отказ × критерий',
    comparison_description = 'A1–A4 против A0 по всей кривой risk–coverage.',
    success_rule = 'Опасные уверенные ошибки остаются ниже зарегистрированного предела, а риск монотонно снижается при уменьшении покрытия.'
WHERE code = 'EC_E6';

UPDATE effect_checks SET
    unit_of_analysis = 'Критерий × занятие × набор доступных данных',
    comparison_description = 'Запись-only A4 против того же A4 после добавления одного определённого типа данных.',
    success_rule = 'Без прямых данных система корректно отказывается; каждый добавочный источник даёт заранее определённый измеримый и интерпретируемый прирост.'
WHERE code = 'EC_E8';

UPDATE effect_checks SET
    unit_of_analysis = 'Один и тот же вход × критерий × повтор прогона',
    comparison_description = 'Независимые повторы A4 сравниваются между собой; A0 относится к проверке правильности в E1–E3, а не к повторяемости.',
    success_rule = 'Порог точного совпадения статусов и баллов, weighted kappa, допустимый разброс уверенности и перекрытие доказательств фиксируются до независимого теста.'
WHERE code = 'EC_E9';

UPDATE effect_check_conditions SET
    notes = 'Одна конфигурация A4 запускается повторно на идентичных входах.'
WHERE effect_check_id = (SELECT id FROM effect_checks WHERE code = 'EC_E9')
  AND condition_id = (SELECT id FROM comparison_conditions WHERE code = 'A4');

DELETE FROM effect_check_conditions
WHERE effect_check_id = (SELECT id FROM effect_checks WHERE code = 'EC_E9')
  AND condition_id = (SELECT id FROM comparison_conditions WHERE code = 'A0');

UPDATE effect_check_data_types SET
    notes = 'Checksum входов, версия модели, промпт и параметры генерации для подтверждения идентичности условий.'
WHERE effect_check_id = (SELECT id FROM effect_checks WHERE code = 'EC_E9')
  AND data_type_id = (SELECT id FROM data_types WHERE code = 'technical_metadata');

UPDATE effect_check_data_types SET
    notes = 'Используется только для отдельной проверки правильности: стабильный вывод всё равно может быть неверным.'
WHERE effect_check_id = (SELECT id FROM effect_checks WHERE code = 'EC_E9')
  AND data_type_id = (SELECT id FROM data_types WHERE code = 'expert_annotation');

UPDATE effect_check_criteria SET scope_role = 'primary'
WHERE effect_check_id = (SELECT id FROM effect_checks WHERE code = 'EC_E9')
  AND criterion_id = (SELECT id FROM criteria WHERE code = 'C26');

INSERT INTO verification_method_research_sources
    (verification_method_id, research_source_id, relation_role, notes)
VALUES
    (1, 36, 'methodological_basis', 'Валидность интерпретации и риск подмены конструкта.'),
    (1, 27, 'design_example', 'Пример экспертной оценки конкретных доказательств и обратной связи.'),
    (2, 37, 'metric_definition', 'Precision, recall и F1 для событийной классификации.'),
    (2, 38, 'metric_definition', 'Temporal IoU и временная локализация событий.'),
    (2, 26, 'design_example', 'Автоматический анализ речи преподавателя с проверкой на размеченных данных.'),
    (3, 39, 'metric_definition', 'Weighted kappa для порядковой шкалы.'),
    (3, 37, 'metric_definition', 'Macro-F1 и различия между классами.'),
    (3, 25, 'design_example', 'Валидация автоматической оценки преподавания по экспертному референсу.'),
    (4, 40, 'methodological_basis', 'Логика абляции компонентов системы.'),
    (4, 25, 'design_example', 'Мультимодальная автоматическая оценка преподавания.'),
    (4, 28, 'design_example', 'Пример мультимодального анализа наблюдаемого климата.'),
    (5, 41, 'methodological_basis', 'Блочное разбиение и зависимые наблюдения.'),
    (5, 25, 'design_example', 'Проверка качества автоматической оценки на разных данных.'),
    (6, 42, 'metric_definition', 'Калибровка числовой уверенности.'),
    (6, 43, 'methodological_basis', 'Risk–coverage и право модели отказаться.'),
    (7, 44, 'design_example', 'Оценка совместной работы человека и ИИ и риска ошибочной подсказки.'),
    (7, 45, 'methodological_basis', 'Организация и отчётность crossover-сравнения.'),
    (8, 29, 'boundary_evidence', 'Прямой студенческий опрос для доверия.'),
    (8, 31, 'boundary_evidence', 'Самоотчёт как источник для когнитивной нагрузки.'),
    (8, 34, 'boundary_evidence', 'Скрытые мотивационные конструкты не выводятся напрямую из записи.'),
    (8, 36, 'methodological_basis', 'Валидность интерпретации при добавлении новых источников.'),
    (9, 46, 'design_example', 'Специализированный протокол повторных прогонов LLM.'),
    (9, 47, 'metric_definition', 'ICC для повторных числовых измерений.'),
    (9, 39, 'metric_definition', 'Weighted kappa для повторяемости баллов 0–2.');

DROP VIEW v_effect_check_plan;

CREATE VIEW v_effect_check_plan AS
SELECT
    e.code AS effect_code,
    e.name AS effect_name,
    ec.code AS check_code,
    vm.name AS verification_method,
    vm.metrics,
    ec.unit_of_analysis,
    ec.comparison_description,
    ec.success_rule,
    (
        SELECT group_concat(rs.code || ': ' || rs.citation_apa, '; ')
        FROM verification_method_research_sources AS vmrs
        JOIN research_sources AS rs ON rs.id = vmrs.research_source_id
        WHERE vmrs.verification_method_id = vm.id
    ) AS literature,
    (
        SELECT group_concat(cc.code || ' [' || ecc.role || ']', '; ')
        FROM effect_check_conditions AS ecc
        JOIN comparison_conditions AS cc ON cc.id = ecc.condition_id
        WHERE ecc.effect_check_id = ec.id
    ) AS conditions,
    (
        SELECT group_concat(dt.name || ' [' || ecd.role || ']', '; ')
        FROM effect_check_data_types AS ecd
        JOIN data_types AS dt ON dt.id = ecd.data_type_id
        WHERE ecd.effect_check_id = ec.id
    ) AS data_types
FROM effect_checks AS ec
JOIN effects AS e ON e.id = ec.effect_id
JOIN verification_methods AS vm ON vm.id = ec.verification_method_id
ORDER BY e.effect_order;

COMMIT;
