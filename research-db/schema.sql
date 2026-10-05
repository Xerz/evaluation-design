PRAGMA foreign_keys = ON;

CREATE TABLE schema_migrations (
  version INTEGER PRIMARY KEY, applied_on TEXT NOT NULL, source_sha256 TEXT NOT NULL
);
CREATE TABLE design_revisions (
  id TEXT PRIMARY KEY, status TEXT NOT NULL CHECK(status IN ('historical','draft','approved')),
  created_on TEXT NOT NULL, parent_id TEXT REFERENCES design_revisions(id),
  rationale TEXT NOT NULL, frozen INTEGER NOT NULL CHECK(frozen IN (0,1))
);
CREATE TABLE source_snapshots (
  id TEXT PRIMARY KEY, namespace TEXT NOT NULL, source_version TEXT NOT NULL,
  sha256 TEXT NOT NULL CHECK(length(sha256)=64), captured_on TEXT,
  completeness TEXT NOT NULL CHECK(completeness IN ('complete','incomplete','unknown')),
  provenance_json TEXT NOT NULL CHECK(json_valid(provenance_json)),
  UNIQUE(namespace,source_version,sha256)
);
CREATE TABLE historical_tables (
  snapshot_id TEXT NOT NULL REFERENCES source_snapshots(id), name TEXT NOT NULL,
  schema_sql TEXT NOT NULL, columns_json TEXT NOT NULL CHECK(json_valid(columns_json)),
  rows_json TEXT NOT NULL CHECK(json_valid(rows_json)), row_count INTEGER NOT NULL CHECK(row_count>=0),
  PRIMARY KEY(snapshot_id,name)
);
CREATE TABLE revision_snapshots (
  revision_id TEXT NOT NULL REFERENCES design_revisions(id),
  snapshot_id TEXT NOT NULL REFERENCES source_snapshots(id), role TEXT NOT NULL,
  PRIMARY KEY(revision_id,snapshot_id)
);
CREATE TABLE criteria (
  revision_id TEXT NOT NULL REFERENCES design_revisions(id), code TEXT NOT NULL,
  number INTEGER NOT NULL CHECK(number BETWEEN 1 AND 26), name TEXT NOT NULL,
  block_name TEXT, subblock_name TEXT, origin_json TEXT NOT NULL CHECK(json_valid(origin_json)),
  PRIMARY KEY(revision_id,code), UNIQUE(revision_id,number)
);
CREATE TABLE score_levels (
  revision_id TEXT NOT NULL, criterion_code TEXT NOT NULL, score INTEGER NOT NULL CHECK(score IN (0,1,2)),
  description TEXT NOT NULL, origin_json TEXT NOT NULL CHECK(json_valid(origin_json)),
  PRIMARY KEY(revision_id,criterion_code,score),
  FOREIGN KEY(revision_id,criterion_code) REFERENCES criteria(revision_id,code)
);
CREATE TABLE research_sources (
  revision_id TEXT NOT NULL REFERENCES design_revisions(id), code TEXT NOT NULL,
  citation TEXT NOT NULL, doi TEXT, url TEXT, bibliography_status TEXT NOT NULL,
  publication_status TEXT NOT NULL DEFAULT 'not_rechecked',
  historical_json TEXT NOT NULL CHECK(json_valid(historical_json)),
  PRIMARY KEY(revision_id,code)
);
CREATE TABLE source_reviews (
  id TEXT PRIMARY KEY, revision_id TEXT NOT NULL, source_code TEXT NOT NULL,
  checked_on TEXT NOT NULL, scope TEXT NOT NULL, url TEXT NOT NULL, locator TEXT NOT NULL,
  supported_statement TEXT NOT NULL, boundary TEXT NOT NULL,
  FOREIGN KEY(revision_id,source_code) REFERENCES research_sources(revision_id,code)
);
CREATE TABLE protocols (
  revision_id TEXT NOT NULL REFERENCES design_revisions(id), code TEXT NOT NULL,
  name TEXT NOT NULL, description TEXT NOT NULL, metrics TEXT NOT NULL, procedure TEXT NOT NULL,
  readiness TEXT NOT NULL, historical_json TEXT NOT NULL CHECK(json_valid(historical_json)),
  PRIMARY KEY(revision_id,code)
);
CREATE TABLE effects (
  revision_id TEXT NOT NULL REFERENCES design_revisions(id), code TEXT NOT NULL,
  name TEXT NOT NULL, hypothesis TEXT NOT NULL, status TEXT NOT NULL,
  historical_json TEXT NOT NULL CHECK(json_valid(historical_json)), PRIMARY KEY(revision_id,code)
);
CREATE TABLE effect_checks (
  revision_id TEXT NOT NULL, code TEXT NOT NULL, effect_code TEXT NOT NULL, method_code TEXT NOT NULL,
  unit_of_analysis TEXT NOT NULL, comparison_description TEXT NOT NULL, success_rule TEXT NOT NULL,
  historical_json TEXT NOT NULL CHECK(json_valid(historical_json)),
  PRIMARY KEY(revision_id,code),
  FOREIGN KEY(revision_id,effect_code) REFERENCES effects(revision_id,code),
  FOREIGN KEY(revision_id,method_code) REFERENCES protocols(revision_id,code)
);
CREATE TABLE scientific_links (
  revision_id TEXT NOT NULL, code TEXT NOT NULL, source_code TEXT NOT NULL,
  criterion_code TEXT, method_code TEXT, relation_role TEXT NOT NULL,
  historical_claim TEXT, historical_locator TEXT,
  historical_json TEXT NOT NULL CHECK(json_valid(historical_json)),
  PRIMARY KEY(revision_id,code),
  CHECK((criterion_code IS NOT NULL)+(method_code IS NOT NULL)=1),
  FOREIGN KEY(revision_id,source_code) REFERENCES research_sources(revision_id,code),
  FOREIGN KEY(revision_id,criterion_code) REFERENCES criteria(revision_id,code),
  FOREIGN KEY(revision_id,method_code) REFERENCES protocols(revision_id,code)
);
CREATE TABLE link_reviews (
  id TEXT PRIMARY KEY, revision_id TEXT NOT NULL, link_code TEXT NOT NULL,
  source_review_id TEXT REFERENCES source_reviews(id), checked_on TEXT NOT NULL,
  claim_proposal TEXT NOT NULL, review_status TEXT NOT NULL,
  supported_claim TEXT, verified_locator TEXT, applicability TEXT NOT NULL,
  FOREIGN KEY(revision_id,link_code) REFERENCES scientific_links(revision_id,code),
  CHECK(supported_claim IS NULL OR (source_review_id IS NOT NULL AND verified_locator IS NOT NULL))
);
CREATE TABLE instrument_versions (
  id TEXT PRIMARY KEY, instrument_code TEXT NOT NULL, version_code TEXT NOT NULL,
  readiness TEXT NOT NULL, model_version TEXT, contract_json TEXT NOT NULL CHECK(json_valid(contract_json)),
  UNIQUE(instrument_code,version_code)
);
CREATE TABLE conditions (
  revision_id TEXT NOT NULL REFERENCES design_revisions(id), code TEXT NOT NULL,
  name TEXT NOT NULL, readiness TEXT NOT NULL,
  components_json TEXT NOT NULL CHECK(json_valid(components_json)),
  required_inputs_json TEXT NOT NULL CHECK(json_valid(required_inputs_json)),
  missing_requirements_json TEXT NOT NULL CHECK(json_valid(missing_requirements_json)),
  PRIMARY KEY(revision_id,code)
);
CREATE TABLE legacy_condition_links (
  revision_id TEXT NOT NULL, condition_code TEXT NOT NULL, snapshot_id TEXT NOT NULL REFERENCES source_snapshots(id),
  legacy_code TEXT NOT NULL, equivalence TEXT NOT NULL,
  PRIMARY KEY(revision_id,condition_code,snapshot_id,legacy_code),
  FOREIGN KEY(revision_id,condition_code) REFERENCES conditions(revision_id,code)
);
CREATE TABLE comparisons (
  revision_id TEXT NOT NULL, code TEXT NOT NULL, method_code TEXT NOT NULL,
  left_condition TEXT NOT NULL, right_condition TEXT NOT NULL,
  changed_component TEXT NOT NULL, controls TEXT NOT NULL, eligibility TEXT NOT NULL,
  PRIMARY KEY(revision_id,code),
  FOREIGN KEY(revision_id,method_code) REFERENCES protocols(revision_id,code),
  FOREIGN KEY(revision_id,left_condition) REFERENCES conditions(revision_id,code),
  FOREIGN KEY(revision_id,right_condition) REFERENCES conditions(revision_id,code)
);
CREATE TABLE criterion_mappings (
  revision_id TEXT NOT NULL, code TEXT NOT NULL, criterion_code TEXT NOT NULL, condition_code TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('candidate','calibrated','validated','rejected')),
  signal TEXT NOT NULL, required_inputs TEXT NOT NULL, implementation_status TEXT NOT NULL,
  evidence_status TEXT NOT NULL, details_json TEXT NOT NULL CHECK(json_valid(details_json)),
  PRIMARY KEY(revision_id,code),
  FOREIGN KEY(revision_id,criterion_code) REFERENCES criteria(revision_id,code),
  FOREIGN KEY(revision_id,condition_code) REFERENCES conditions(revision_id,code)
);
CREATE TABLE metric_definitions (
  id TEXT PRIMARY KEY, instrument_version_id TEXT NOT NULL REFERENCES instrument_versions(id),
  code TEXT NOT NULL, name TEXT NOT NULL, unit TEXT, definition_status TEXT NOT NULL,
  details_json TEXT NOT NULL CHECK(json_valid(details_json)), UNIQUE(instrument_version_id,code)
);
CREATE TABLE technical_profiles (
  code TEXT PRIMARY KEY, purpose TEXT NOT NULL, status TEXT NOT NULL,
  details_json TEXT NOT NULL CHECK(json_valid(details_json))
);
CREATE TABLE entities (
  id TEXT PRIMARY KEY, revision_id TEXT NOT NULL REFERENCES design_revisions(id),
  kind TEXT NOT NULL CHECK(kind IN ('lesson','teacher','group','expert','artifact','assignment','run','result')),
  UNIQUE(id,revision_id)
);
CREATE TABLE external_links (
  snapshot_id TEXT NOT NULL REFERENCES source_snapshots(id), namespace TEXT NOT NULL,
  external_kind TEXT NOT NULL, external_id TEXT NOT NULL, internal_id TEXT NOT NULL REFERENCES entities(id),
  status TEXT NOT NULL CHECK(status IN ('proposed','verified','superseded')),
  PRIMARY KEY(snapshot_id,namespace,external_kind,external_id)
);
CREATE TABLE lessons (
  id TEXT PRIMARY KEY, revision_id TEXT NOT NULL, discipline_id TEXT NOT NULL,
  teacher_entity_id TEXT NOT NULL REFERENCES entities(id), group_entity_id TEXT NOT NULL REFERENCES entities(id),
  starts_at TEXT NOT NULL, timezone TEXT NOT NULL, lesson_type TEXT NOT NULL,
  slot_role TEXT NOT NULL CHECK(slot_role IN ('trial','primary','reserve')),
  state TEXT NOT NULL CHECK(state IN ('candidate','confirmed_for_recording','recorded','cancelled')),
  profile_code TEXT NOT NULL REFERENCES technical_profiles(code),
  metadata_json TEXT NOT NULL CHECK(json_valid(metadata_json)),
  FOREIGN KEY(id,revision_id) REFERENCES entities(id,revision_id)
);
CREATE TABLE artifacts (
  id TEXT PRIMARY KEY, revision_id TEXT NOT NULL, lesson_id TEXT NOT NULL REFERENCES lessons(id),
  kind TEXT NOT NULL, version_code TEXT NOT NULL, sha256 TEXT NOT NULL CHECK(length(sha256)=64),
  parent_artifact_id TEXT REFERENCES artifacts(id), duration_ms INTEGER CHECK(duration_ms>=0),
  character_count INTEGER CHECK(character_count>=0), qc_status TEXT NOT NULL,
  provenance_json TEXT NOT NULL CHECK(json_valid(provenance_json)),
  FOREIGN KEY(id,revision_id) REFERENCES entities(id,revision_id)
);
CREATE TABLE assignments (
  id TEXT PRIMARY KEY, revision_id TEXT NOT NULL, lesson_id TEXT NOT NULL REFERENCES lessons(id),
  expert_entity_id TEXT NOT NULL REFERENCES entities(id), condition_code TEXT NOT NULL,
  codebook_version TEXT NOT NULL, status TEXT NOT NULL,
  pinned_ai_run_id TEXT REFERENCES runs(id),
  FOREIGN KEY(id,revision_id) REFERENCES entities(id,revision_id),
  FOREIGN KEY(revision_id,condition_code) REFERENCES conditions(revision_id,code),
  CHECK((condition_code='EXP-AI' AND pinned_ai_run_id IS NOT NULL) OR
        (condition_code<>'EXP-AI' AND pinned_ai_run_id IS NULL))
);
CREATE TABLE runs (
  id TEXT PRIMARY KEY, revision_id TEXT NOT NULL, lesson_id TEXT NOT NULL REFERENCES lessons(id),
  condition_code TEXT NOT NULL, instrument_version_id TEXT NOT NULL REFERENCES instrument_versions(id),
  prompt_version TEXT NOT NULL, model_version TEXT, config_sha256 TEXT NOT NULL CHECK(length(config_sha256)=64),
  status TEXT NOT NULL, repeat_of TEXT REFERENCES runs(id),
  FOREIGN KEY(id,revision_id) REFERENCES entities(id,revision_id),
  FOREIGN KEY(revision_id,condition_code) REFERENCES conditions(revision_id,code)
);
CREATE TABLE run_inputs (
  run_id TEXT NOT NULL REFERENCES runs(id), artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  input_role TEXT NOT NULL, PRIMARY KEY(run_id,artifact_id,input_role)
);
CREATE TABLE results (
  id TEXT PRIMARY KEY, revision_id TEXT NOT NULL, criterion_code TEXT NOT NULL,
  run_id TEXT REFERENCES runs(id), assignment_id TEXT REFERENCES assignments(id),
  result_status TEXT NOT NULL CHECK(result_status IN ('scored','insufficient_data','not_applicable','error','invalid_output')),
  score INTEGER CHECK(score IN (0,1,2)), confidence REAL CHECK(confidence BETWEEN 0 AND 1),
  confidence_meaning TEXT, rationale TEXT, raw_json TEXT CHECK(raw_json IS NULL OR json_valid(raw_json)),
  CHECK((run_id IS NOT NULL)+(assignment_id IS NOT NULL)=1),
  CHECK((result_status='scored' AND score IS NOT NULL) OR (result_status<>'scored' AND score IS NULL)),
  CHECK(confidence IS NULL OR confidence_meaning IS NOT NULL),
  FOREIGN KEY(id,revision_id) REFERENCES entities(id,revision_id),
  FOREIGN KEY(revision_id,criterion_code) REFERENCES criteria(revision_id,code)
);
CREATE TABLE evidence (
  id TEXT PRIMARY KEY, result_id TEXT NOT NULL REFERENCES results(id), artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  locator_kind TEXT NOT NULL CHECK(locator_kind IN ('characters','milliseconds','document')),
  start_char INTEGER, end_char INTEGER, start_ms INTEGER, end_ms INTEGER, document_locator TEXT,
  quote TEXT, interpretation_status TEXT NOT NULL,
  CHECK((locator_kind='characters' AND start_char IS NOT NULL AND end_char>start_char AND start_char>=0
         AND start_ms IS NULL AND end_ms IS NULL AND document_locator IS NULL) OR
        (locator_kind='milliseconds' AND start_ms IS NOT NULL AND end_ms>start_ms AND start_ms>=0
         AND start_char IS NULL AND end_char IS NULL AND document_locator IS NULL) OR
        (locator_kind='document' AND document_locator IS NOT NULL AND start_char IS NULL AND end_char IS NULL
         AND start_ms IS NULL AND end_ms IS NULL))
);
CREATE TABLE metric_values (
  run_id TEXT NOT NULL REFERENCES runs(id), metric_id TEXT NOT NULL REFERENCES metric_definitions(id),
  status TEXT NOT NULL CHECK(status IN ('observed','missing','error','not_applicable')),
  raw_value REAL, observed_unit TEXT, denominator REAL CHECK(denominator>0),
  denominator_provenance TEXT, transformation_version TEXT,
  CHECK((status='observed' AND raw_value IS NOT NULL) OR (status<>'observed' AND raw_value IS NULL)),
  CHECK(denominator IS NULL OR denominator_provenance IS NOT NULL), PRIMARY KEY(run_id,metric_id)
);
CREATE TABLE time_logs (
  id TEXT PRIMARY KEY, assignment_id TEXT NOT NULL REFERENCES assignments(id), activity TEXT NOT NULL,
  elapsed_seconds REAL NOT NULL CHECK(elapsed_seconds>=0), notes TEXT
);
CREATE TABLE student_observations (
  id TEXT PRIMARY KEY, revision_id TEXT NOT NULL REFERENCES design_revisions(id),
  lesson_id TEXT NOT NULL REFERENCES lessons(id), anonymous_response_id TEXT NOT NULL,
  construct TEXT NOT NULL CHECK(construct IN ('success_experience','trust','other')),
  instrument_version TEXT NOT NULL, collected_at TEXT NOT NULL,
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
  UNIQUE(revision_id,lesson_id,anonymous_response_id,construct,instrument_version)
);
CREATE TABLE transformations (
  id TEXT PRIMARY KEY, revision_id TEXT NOT NULL REFERENCES design_revisions(id),
  code TEXT NOT NULL, version_code TEXT NOT NULL, status TEXT NOT NULL,
  specification_json TEXT NOT NULL CHECK(json_valid(specification_json)),
  training_split_version TEXT, UNIQUE(revision_id,code,version_code)
);
CREATE TABLE run_payloads (
  run_id TEXT PRIMARY KEY REFERENCES runs(id), elapsed_seconds REAL CHECK(elapsed_seconds>=0),
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
  provenance_json TEXT NOT NULL CHECK(json_valid(provenance_json))
);
CREATE TABLE split_memberships (
  revision_id TEXT NOT NULL REFERENCES design_revisions(id), split_version TEXT NOT NULL,
  teacher_entity_id TEXT NOT NULL REFERENCES entities(id), role TEXT NOT NULL CHECK(role IN ('calibration','test')),
  PRIMARY KEY(revision_id,split_version,teacher_entity_id)
);
CREATE TABLE visibility_policy (
  table_name TEXT PRIMARY KEY, visibility TEXT NOT NULL CHECK(visibility IN ('public_design','local_only')),
  public_columns_json TEXT NOT NULL CHECK(json_valid(public_columns_json)), reason TEXT NOT NULL
);

CREATE TRIGGER historical_rows_no_update BEFORE UPDATE ON historical_tables
BEGIN SELECT RAISE(ABORT,'historical snapshot is immutable'); END;
CREATE TRIGGER historical_rows_no_insert_after_freeze BEFORE INSERT ON historical_tables
WHEN EXISTS(SELECT 1 FROM revision_snapshots rs JOIN design_revisions r ON r.id=rs.revision_id
            WHERE rs.snapshot_id=NEW.snapshot_id AND r.frozen=1)
BEGIN SELECT RAISE(ABORT,'historical snapshot is sealed by a frozen revision'); END;
CREATE TRIGGER historical_rows_no_delete BEFORE DELETE ON historical_tables
BEGIN SELECT RAISE(ABORT,'historical snapshot is immutable'); END;
CREATE TRIGGER snapshot_no_update BEFORE UPDATE ON source_snapshots
BEGIN SELECT RAISE(ABORT,'source snapshot is immutable; create a new snapshot'); END;
CREATE TRIGGER snapshot_no_delete BEFORE DELETE ON source_snapshots
BEGIN SELECT RAISE(ABORT,'source snapshot is immutable'); END;
CREATE TRIGGER frozen_revision_no_update BEFORE UPDATE ON design_revisions WHEN OLD.frozen=1
BEGIN SELECT RAISE(ABORT,'frozen revision is immutable'); END;
CREATE TRIGGER frozen_revision_no_delete BEFORE DELETE ON design_revisions WHEN OLD.frozen=1
BEGIN SELECT RAISE(ABORT,'frozen revision is immutable'); END;
CREATE TRIGGER result_revision_guard BEFORE INSERT ON results
WHEN (NEW.run_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM runs WHERE id=NEW.run_id AND revision_id=NEW.revision_id))
  OR (NEW.assignment_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM assignments WHERE id=NEW.assignment_id AND revision_id=NEW.revision_id))
BEGIN SELECT RAISE(ABORT,'result revision mismatch'); END;
CREATE TRIGGER evidence_revision_guard BEFORE INSERT ON evidence
WHEN NOT EXISTS(SELECT 1 FROM results r JOIN artifacts a ON a.id=NEW.artifact_id
                WHERE r.id=NEW.result_id AND r.revision_id=a.revision_id)
BEGIN SELECT RAISE(ABORT,'evidence revision mismatch'); END;

CREATE VIEW v_mapping_coverage AS
SELECT c.revision_id,c.code,c.name,count(m.code) AS candidate_mapping_count,
       sum(CASE WHEN m.status='validated' THEN 1 ELSE 0 END) AS validated_mapping_count
FROM criteria c LEFT JOIN criterion_mappings m ON m.revision_id=c.revision_id AND m.criterion_code=c.code
GROUP BY c.revision_id,c.code,c.name;
