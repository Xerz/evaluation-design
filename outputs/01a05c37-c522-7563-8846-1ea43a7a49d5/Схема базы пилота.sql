PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE source_documents (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    relative_path TEXT NOT NULL UNIQUE,
    document_type TEXT NOT NULL,
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
    notes TEXT
);

CREATE TABLE criteria (
    id INTEGER PRIMARY KEY,
    number INTEGER NOT NULL UNIQUE CHECK (number BETWEEN 1 AND 26),
    code TEXT NOT NULL UNIQUE,
    block_name TEXT NOT NULL,
    subblock_name TEXT,
    name TEXT NOT NULL,
    source_document_id INTEGER NOT NULL REFERENCES source_documents(id),
    source_locator TEXT
);

CREATE TABLE research_sources (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    citation_apa TEXT NOT NULL,
    doi TEXT,
    url TEXT,
    study_type TEXT,
    evidence_summary TEXT,
    access_notes TEXT,
    evidence_role TEXT,
    verification_status TEXT NOT NULL DEFAULT 'to_review' CHECK (verification_status IN (
        'to_review', 'source_register_checked', 'user_verified',
        'partially_verified', 'not_verified'
    )),
    registry_checked_on TEXT,
    provenance_document_id INTEGER REFERENCES source_documents(id),
    notes TEXT
);

CREATE TABLE criterion_research_sources (
    id INTEGER PRIMARY KEY,
    criterion_id INTEGER NOT NULL REFERENCES criteria(id) ON DELETE CASCADE,
    research_source_id INTEGER NOT NULL REFERENCES research_sources(id) ON DELETE CASCADE,
    relation_role TEXT NOT NULL,
    relevance_status TEXT NOT NULL DEFAULT 'to_review' CHECK (relevance_status IN (
        'to_review', 'confirmed', 'partially_confirmed', 'rejected'
    )),
    supported_claim TEXT,
    source_locator TEXT,
    notes TEXT,
    UNIQUE (criterion_id, research_source_id)
);

CREATE TABLE criterion_score_levels (
    id INTEGER PRIMARY KEY,
    criterion_id INTEGER NOT NULL REFERENCES criteria(id) ON DELETE CASCADE,
    score INTEGER NOT NULL CHECK (score IN (0, 1, 2)),
    description TEXT NOT NULL,
    source_document_id INTEGER NOT NULL REFERENCES source_documents(id),
    source_locator TEXT,
    UNIQUE (criterion_id, score)
);

CREATE TABLE data_types (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN (
        'recording', 'transcript', 'materials', 'survey', 'platform',
        'metadata', 'annotation', 'outcome', 'external'
    )),
    description TEXT NOT NULL,
    contains_personal_data INTEGER NOT NULL DEFAULT 0 CHECK (contains_personal_data IN (0, 1)),
    default_format TEXT
);

CREATE TABLE criterion_data_requirements (
    criterion_id INTEGER NOT NULL REFERENCES criteria(id) ON DELETE CASCADE,
    data_type_id INTEGER NOT NULL REFERENCES data_types(id),
    requirement_role TEXT NOT NULL CHECK (requirement_role IN ('required', 'supplemental', 'reference')),
    reason TEXT NOT NULL,
    source_document_id INTEGER REFERENCES source_documents(id),
    PRIMARY KEY (criterion_id, data_type_id, requirement_role)
);

CREATE TABLE instruments (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    instrument_kind TEXT NOT NULL CHECK (instrument_kind IN ('llm', 'video_analytics', 'audio_analytics', 'human')),
    description TEXT NOT NULL
);

CREATE TABLE instrument_versions (
    id INTEGER PRIMARY KEY,
    instrument_id INTEGER NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
    version_code TEXT NOT NULL,
    version_name TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL CHECK (lifecycle_status IN ('historical', 'prototype', 'active', 'retired', 'reference')),
    model_name TEXT,
    prompt_version TEXT,
    implementation_ref TEXT,
    config_summary TEXT,
    limitations TEXT,
    methodology_status TEXT NOT NULL CHECK (methodology_status IN ('documented', 'partial', 'not_documented', 'not_applicable')),
    source_document_id INTEGER REFERENCES source_documents(id),
    UNIQUE (instrument_id, version_code)
);

CREATE TABLE instrument_version_data_types (
    instrument_version_id INTEGER NOT NULL REFERENCES instrument_versions(id) ON DELETE CASCADE,
    data_type_id INTEGER NOT NULL REFERENCES data_types(id),
    requirement_role TEXT NOT NULL CHECK (requirement_role IN ('required', 'optional', 'derived')),
    purpose TEXT NOT NULL,
    PRIMARY KEY (instrument_version_id, data_type_id, requirement_role)
);

CREATE TABLE instrument_version_criteria (
    instrument_version_id INTEGER NOT NULL REFERENCES instrument_versions(id) ON DELETE CASCADE,
    criterion_id INTEGER NOT NULL REFERENCES criteria(id) ON DELETE CASCADE,
    coverage_status TEXT NOT NULL CHECK (coverage_status IN (
        'reference', 'prototype_output', 'partial', 'indirect', 'not_covered'
    )),
    validation_status TEXT NOT NULL CHECK (validation_status IN ('validated', 'unvalidated', 'not_documented', 'reference')),
    output_type TEXT NOT NULL,
    notes TEXT,
    PRIMARY KEY (instrument_version_id, criterion_id)
);

CREATE TABLE studies (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    objective TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('design', 'calibration', 'independent_test', 'completed', 'archived')),
    design_version TEXT NOT NULL,
    source_document_id INTEGER REFERENCES source_documents(id)
);

CREATE TABLE study_criteria (
    study_id INTEGER NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    criterion_id INTEGER NOT NULL REFERENCES criteria(id) ON DELETE CASCADE,
    readiness_status TEXT NOT NULL CHECK (readiness_status IN ('prototype_now', 'conditional', 'not_from_recording')),
    platform_coverage_status TEXT NOT NULL CHECK (platform_coverage_status IN ('partial', 'indirect', 'not_covered')),
    notes TEXT,
    PRIMARY KEY (study_id, criterion_id)
);

CREATE TABLE comparison_conditions (
    id INTEGER PRIMARY KEY,
    study_id INTEGER NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    condition_order INTEGER NOT NULL,
    UNIQUE (study_id, code),
    UNIQUE (study_id, condition_order)
);

CREATE TABLE condition_instruments (
    condition_id INTEGER NOT NULL REFERENCES comparison_conditions(id) ON DELETE CASCADE,
    instrument_id INTEGER NOT NULL REFERENCES instruments(id),
    role TEXT NOT NULL CHECK (role IN ('primary', 'reference', 'assistant')),
    notes TEXT,
    PRIMARY KEY (condition_id, instrument_id)
);

CREATE TABLE condition_data_types (
    condition_id INTEGER NOT NULL REFERENCES comparison_conditions(id) ON DELETE CASCADE,
    data_type_id INTEGER NOT NULL REFERENCES data_types(id),
    requirement_role TEXT NOT NULL CHECK (requirement_role IN ('required', 'optional', 'supplemental', 'derived')),
    purpose TEXT NOT NULL,
    PRIMARY KEY (condition_id, data_type_id, requirement_role)
);

CREATE TABLE effects (
    id INTEGER PRIMARY KEY,
    study_id INTEGER NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    effect_order INTEGER NOT NULL,
    UNIQUE (study_id, code),
    UNIQUE (study_id, effect_order)
);

CREATE TABLE verification_methods (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    metrics TEXT NOT NULL,
    procedure TEXT NOT NULL
);

CREATE TABLE effect_checks (
    id INTEGER PRIMARY KEY,
    effect_id INTEGER NOT NULL REFERENCES effects(id) ON DELETE CASCADE,
    code TEXT NOT NULL UNIQUE,
    verification_method_id INTEGER NOT NULL REFERENCES verification_methods(id),
    unit_of_analysis TEXT NOT NULL,
    comparison_description TEXT NOT NULL,
    success_rule TEXT NOT NULL,
    preregistration_required INTEGER NOT NULL DEFAULT 1 CHECK (preregistration_required IN (0, 1)),
    UNIQUE (effect_id, verification_method_id)
);

CREATE TABLE effect_check_conditions (
    effect_check_id INTEGER NOT NULL REFERENCES effect_checks(id) ON DELETE CASCADE,
    condition_id INTEGER NOT NULL REFERENCES comparison_conditions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('baseline', 'candidate', 'reference', 'assisted', 'ablation', 'recording_only')),
    notes TEXT,
    PRIMARY KEY (effect_check_id, condition_id)
);

CREATE TABLE effect_check_data_types (
    effect_check_id INTEGER NOT NULL REFERENCES effect_checks(id) ON DELETE CASCADE,
    data_type_id INTEGER NOT NULL REFERENCES data_types(id),
    role TEXT NOT NULL CHECK (role IN ('required', 'reference', 'supplemental', 'contrast')),
    notes TEXT,
    PRIMARY KEY (effect_check_id, data_type_id, role)
);

CREATE TABLE effect_check_criteria (
    effect_check_id INTEGER NOT NULL REFERENCES effect_checks(id) ON DELETE CASCADE,
    criterion_id INTEGER NOT NULL REFERENCES criteria(id) ON DELETE CASCADE,
    scope_role TEXT NOT NULL CHECK (scope_role IN ('primary', 'boundary', 'longitudinal')),
    PRIMARY KEY (effect_check_id, criterion_id)
);

CREATE TABLE experts (
    id INTEGER PRIMARY KEY,
    pseudonym TEXT NOT NULL UNIQUE,
    qualification TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    notes TEXT
);

CREATE TABLE instructors (
    id INTEGER PRIMARY KEY,
    pseudonym TEXT NOT NULL UNIQUE,
    discipline_area TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    notes TEXT
);

CREATE TABLE student_groups (
    id INTEGER PRIMARY KEY,
    pseudonym TEXT NOT NULL UNIQUE,
    approximate_size INTEGER CHECK (approximate_size IS NULL OR approximate_size >= 0),
    program_level TEXT,
    notes TEXT
);

CREATE TABLE lessons (
    id INTEGER PRIMARY KEY,
    public_id TEXT NOT NULL UNIQUE,
    study_id INTEGER NOT NULL REFERENCES studies(id),
    instructor_id INTEGER REFERENCES instructors(id),
    student_group_id INTEGER REFERENCES student_groups(id),
    discipline_code TEXT,
    lesson_format TEXT CHECK (lesson_format IS NULL OR lesson_format IN ('lecture', 'practice', 'seminar', 'mixed', 'other')),
    started_at TEXT,
    duration_ms INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0),
    room_code TEXT,
    status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'recorded', 'quality_checked', 'ready', 'excluded')),
    notes TEXT
);

CREATE TABLE dataset_splits (
    id INTEGER PRIMARY KEY,
    study_id INTEGER NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    purpose TEXT NOT NULL,
    is_locked INTEGER NOT NULL DEFAULT 0 CHECK (is_locked IN (0, 1)),
    locked_at TEXT,
    UNIQUE (study_id, code)
);

CREATE TABLE lesson_splits (
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    split_id INTEGER NOT NULL REFERENCES dataset_splits(id) ON DELETE CASCADE,
    assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (lesson_id, split_id)
);

CREATE TABLE lesson_artifacts (
    id INTEGER PRIMARY KEY,
    public_id TEXT NOT NULL UNIQUE,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    data_type_id INTEGER NOT NULL REFERENCES data_types(id),
    storage_uri TEXT NOT NULL,
    mime_type TEXT,
    sha256 TEXT CHECK (sha256 IS NULL OR length(sha256) = 64),
    size_bytes INTEGER CHECK (size_bytes IS NULL OR size_bytes >= 0),
    duration_ms INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0),
    captured_at TEXT,
    quality_status TEXT NOT NULL DEFAULT 'not_checked' CHECK (quality_status IN ('not_checked', 'suitable', 'limited', 'unsuitable', 'missing')),
    access_class TEXT NOT NULL DEFAULT 'restricted' CHECK (access_class IN ('restricted', 'research_team', 'deidentified', 'public')),
    metadata_json TEXT CHECK (metadata_json IS NULL OR json_valid(metadata_json))
);

CREATE TABLE evaluation_runs (
    id INTEGER PRIMARY KEY,
    public_id TEXT NOT NULL UNIQUE,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    condition_id INTEGER NOT NULL REFERENCES comparison_conditions(id),
    expert_id INTEGER REFERENCES experts(id),
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    started_at TEXT,
    completed_at TEXT,
    randomization_order INTEGER,
    configuration_json TEXT CHECK (configuration_json IS NULL OR json_valid(configuration_json)),
    error_message TEXT
);

CREATE TABLE run_instruments (
    run_id INTEGER NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
    instrument_version_id INTEGER NOT NULL REFERENCES instrument_versions(id),
    role TEXT NOT NULL CHECK (role IN ('primary', 'reference', 'assistant')),
    PRIMARY KEY (run_id, instrument_version_id)
);

CREATE TABLE run_inputs (
    run_id INTEGER NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
    artifact_id INTEGER NOT NULL REFERENCES lesson_artifacts(id),
    input_role TEXT NOT NULL CHECK (input_role IN ('required', 'optional', 'supplemental', 'reference')),
    PRIMARY KEY (run_id, artifact_id)
);

CREATE TABLE criterion_evaluations (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
    criterion_id INTEGER NOT NULL REFERENCES criteria(id),
    result_status TEXT NOT NULL CHECK (result_status IN ('scored', 'insufficient_data', 'error', 'not_applicable')),
    score INTEGER CHECK (score IS NULL OR score IN (0, 1, 2)),
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    rationale TEXT,
    model_output_json TEXT CHECK (model_output_json IS NULL OR json_valid(model_output_json)),
    duration_ms INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_id, criterion_id),
    CHECK (
        (result_status = 'scored' AND score IS NOT NULL)
        OR (result_status <> 'scored' AND score IS NULL)
    )
);

CREATE TABLE evidence_fragments (
    id INTEGER PRIMARY KEY,
    criterion_evaluation_id INTEGER NOT NULL REFERENCES criterion_evaluations(id) ON DELETE CASCADE,
    artifact_id INTEGER REFERENCES lesson_artifacts(id),
    start_ms INTEGER CHECK (start_ms IS NULL OR start_ms >= 0),
    end_ms INTEGER CHECK (end_ms IS NULL OR end_ms >= 0),
    locator TEXT,
    text_excerpt TEXT,
    description TEXT,
    evidence_role TEXT NOT NULL CHECK (evidence_role IN ('supports', 'contradicts', 'uncertainty')),
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    CHECK (start_ms IS NULL OR end_ms IS NULL OR end_ms >= start_ms)
);

CREATE TABLE evaluation_reviews (
    id INTEGER PRIMARY KEY,
    criterion_evaluation_id INTEGER NOT NULL REFERENCES criterion_evaluations(id) ON DELETE CASCADE,
    expert_id INTEGER NOT NULL REFERENCES experts(id),
    review_type TEXT NOT NULL CHECK (review_type IN ('independent', 'acceptance', 'adjudication')),
    verdict TEXT NOT NULL CHECK (verdict IN ('accepted', 'rejected', 'adjusted', 'insufficient_data')),
    revised_score INTEGER CHECK (revised_score IS NULL OR revised_score IN (0, 1, 2)),
    notes TEXT,
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((verdict = 'adjusted' AND revised_score IS NOT NULL) OR verdict <> 'adjusted')
);

CREATE TABLE effect_results (
    id INTEGER PRIMARY KEY,
    effect_check_id INTEGER NOT NULL REFERENCES effect_checks(id) ON DELETE CASCADE,
    criterion_id INTEGER REFERENCES criteria(id),
    split_id INTEGER REFERENCES dataset_splits(id),
    metric_name TEXT NOT NULL,
    estimate REAL,
    ci_low REAL,
    ci_high REAL,
    sample_size INTEGER CHECK (sample_size IS NULL OR sample_size >= 0),
    unit TEXT,
    result_status TEXT NOT NULL CHECK (result_status IN ('computed', 'insufficient_data', 'not_applicable')),
    decision TEXT,
    analysis_version TEXT NOT NULL,
    calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    CHECK (ci_low IS NULL OR ci_high IS NULL OR ci_high >= ci_low)
);

CREATE TABLE automation_decision_types (
    code TEXT PRIMARY KEY CHECK (code IN ('A', 'B', 'C', 'D')),
    name TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE criterion_decisions (
    id INTEGER PRIMARY KEY,
    study_id INTEGER NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    criterion_id INTEGER NOT NULL REFERENCES criteria(id),
    decision_code TEXT NOT NULL REFERENCES automation_decision_types(code),
    based_on_effect_result_id INTEGER REFERENCES effect_results(id),
    scope_conditions TEXT NOT NULL,
    rationale TEXT NOT NULL,
    decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    UNIQUE (study_id, criterion_id, version)
);

CREATE INDEX idx_criterion_score_levels_criterion ON criterion_score_levels(criterion_id);
CREATE INDEX idx_criterion_research_sources_criterion ON criterion_research_sources(criterion_id);
CREATE INDEX idx_criterion_research_sources_source ON criterion_research_sources(research_source_id);
CREATE INDEX idx_criterion_data_requirements_data_type ON criterion_data_requirements(data_type_id);
CREATE INDEX idx_instrument_versions_instrument ON instrument_versions(instrument_id);
CREATE INDEX idx_instrument_version_criteria_criterion ON instrument_version_criteria(criterion_id);
CREATE INDEX idx_study_criteria_criterion ON study_criteria(criterion_id);
CREATE INDEX idx_conditions_study ON comparison_conditions(study_id);
CREATE INDEX idx_effects_study ON effects(study_id);
CREATE INDEX idx_effect_checks_effect ON effect_checks(effect_id);
CREATE INDEX idx_lessons_study ON lessons(study_id);
CREATE INDEX idx_lessons_instructor ON lessons(instructor_id);
CREATE INDEX idx_artifacts_lesson ON lesson_artifacts(lesson_id);
CREATE INDEX idx_runs_lesson ON evaluation_runs(lesson_id);
CREATE INDEX idx_runs_condition ON evaluation_runs(condition_id);
CREATE INDEX idx_evaluations_run ON criterion_evaluations(run_id);
CREATE INDEX idx_evaluations_criterion ON criterion_evaluations(criterion_id);
CREATE INDEX idx_evidence_evaluation ON evidence_fragments(criterion_evaluation_id);
CREATE INDEX idx_reviews_evaluation ON evaluation_reviews(criterion_evaluation_id);
CREATE INDEX idx_effect_results_check ON effect_results(effect_check_id);

CREATE VIEW v_criterion_scale AS
SELECT
    c.number AS criterion_number,
    c.code AS criterion_code,
    c.block_name,
    c.subblock_name,
    c.name AS criterion_name,
    l.score,
    l.description AS score_description
FROM criteria AS c
JOIN criterion_score_levels AS l ON l.criterion_id = c.id
ORDER BY c.number, l.score;

CREATE VIEW v_instrument_coverage AS
SELECT
    i.code AS instrument_code,
    i.name AS instrument_name,
    v.version_code,
    v.version_name,
    c.number AS criterion_number,
    c.name AS criterion_name,
    ivc.coverage_status,
    ivc.validation_status,
    ivc.output_type,
    ivc.notes
FROM instrument_version_criteria AS ivc
JOIN instrument_versions AS v ON v.id = ivc.instrument_version_id
JOIN instruments AS i ON i.id = v.instrument_id
JOIN criteria AS c ON c.id = ivc.criterion_id
ORDER BY i.id, v.id, c.number;

CREATE VIEW v_condition_matrix AS
SELECT
    c.code AS condition_code,
    c.name AS condition_name,
    c.description,
    (
        SELECT group_concat(i.name || ' [' || ci.role || ']', '; ')
        FROM condition_instruments AS ci
        JOIN instruments AS i ON i.id = ci.instrument_id
        WHERE ci.condition_id = c.id
    ) AS instruments,
    (
        SELECT group_concat(dt.name || ' [' || cdt.requirement_role || ']', '; ')
        FROM condition_data_types AS cdt
        JOIN data_types AS dt ON dt.id = cdt.data_type_id
        WHERE cdt.condition_id = c.id
    ) AS data_types
FROM comparison_conditions AS c
ORDER BY c.condition_order;

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
