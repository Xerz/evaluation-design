"""Install integrity guards for revision-scoped operational and historical records."""

def install(con):
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for table in tables:
        columns = {r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}
        if "revision_id" in columns:
            for action, row in (("INSERT", "NEW"), ("UPDATE", "OLD"), ("DELETE", "OLD")):
                # UPDATE must guard both the previous and target revision.
                condition = f"(SELECT frozen FROM design_revisions WHERE id={row}.revision_id)=1"
                if action == "UPDATE":
                    condition += " OR (SELECT frozen FROM design_revisions WHERE id=NEW.revision_id)=1"
                con.execute(f'''CREATE TRIGGER "freeze_{table}_{action.lower()}"
                  BEFORE {action} ON "{table}" WHEN {condition}
                  BEGIN SELECT RAISE(ABORT,'frozen design cannot be modified'); END''')
    checks = {}
    for table, kind in {"lessons":"lesson", "artifacts":"artifact", "assignments":"assignment",
                        "runs":"run", "results":"result"}.items():
        checks[table] = [f"NOT EXISTS(SELECT 1 FROM entities WHERE id=NEW.id AND kind='{kind}' AND revision_id=NEW.revision_id)"]
    checks["lessons"] += [f"NOT EXISTS(SELECT 1 FROM entities WHERE id=NEW.{column} AND kind='{kind}' AND revision_id=NEW.revision_id)"
                            for column, kind in (("teacher_entity_id","teacher"),("group_entity_id","group"))]
    for table in ("artifacts", "assignments", "runs", "student_observations"):
        checks.setdefault(table, []).append("NOT EXISTS(SELECT 1 FROM lessons WHERE id=NEW.lesson_id AND revision_id=NEW.revision_id)")
    checks["artifacts"].append("NEW.parent_artifact_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM artifacts WHERE id=NEW.parent_artifact_id AND revision_id=NEW.revision_id AND lesson_id=NEW.lesson_id)")
    checks["assignments"] += [
        "NOT EXISTS(SELECT 1 FROM entities WHERE id=NEW.expert_entity_id AND kind='expert' AND revision_id=NEW.revision_id)",
        "NEW.pinned_ai_run_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM runs WHERE id=NEW.pinned_ai_run_id AND revision_id=NEW.revision_id AND lesson_id=NEW.lesson_id)"]
    checks["runs"].append("NEW.repeat_of IS NOT NULL AND NOT EXISTS(SELECT 1 FROM runs WHERE id=NEW.repeat_of AND revision_id=NEW.revision_id AND lesson_id=NEW.lesson_id AND condition_code=NEW.condition_code AND instrument_version_id=NEW.instrument_version_id AND prompt_version=NEW.prompt_version AND model_version IS NEW.model_version AND config_sha256=NEW.config_sha256)")
    checks["results"] += [
        "NEW.run_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM runs WHERE id=NEW.run_id AND revision_id=NEW.revision_id)",
        "NEW.assignment_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM assignments WHERE id=NEW.assignment_id AND revision_id=NEW.revision_id)"]
    checks["run_inputs"] = ["NOT EXISTS(SELECT 1 FROM runs r JOIN artifacts a ON a.id=NEW.artifact_id WHERE r.id=NEW.run_id AND r.revision_id=a.revision_id AND r.lesson_id=a.lesson_id)"]
    checks["link_reviews"] = ["NEW.source_review_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM source_reviews r JOIN scientific_links l ON l.revision_id=NEW.revision_id AND l.code=NEW.link_code WHERE r.id=NEW.source_review_id AND r.revision_id=l.revision_id AND r.source_code=l.source_code)"]
    checks["evidence"] = [
        "NOT EXISTS(SELECT 1 FROM results r JOIN artifacts a ON a.id=NEW.artifact_id LEFT JOIN runs ru ON ru.id=r.run_id LEFT JOIN assignments ass ON ass.id=r.assignment_id WHERE r.id=NEW.result_id AND r.revision_id=a.revision_id AND a.lesson_id=COALESCE(ru.lesson_id,ass.lesson_id))",
        "NEW.locator_kind='characters' AND NOT EXISTS(SELECT 1 FROM artifacts WHERE id=NEW.artifact_id AND character_count IS NOT NULL AND NEW.end_char<=character_count)",
        "NEW.locator_kind='milliseconds' AND NOT EXISTS(SELECT 1 FROM artifacts WHERE id=NEW.artifact_id AND duration_ms IS NOT NULL AND NEW.end_ms<=duration_ms)"]
    checks["split_memberships"] = ["NOT EXISTS(SELECT 1 FROM entities WHERE id=NEW.teacher_entity_id AND revision_id=NEW.revision_id AND kind='teacher')"]
    checks["metric_values"] = ["NOT EXISTS(SELECT 1 FROM runs r JOIN metric_definitions m ON m.id=NEW.metric_id WHERE r.id=NEW.run_id AND r.instrument_version_id=m.instrument_version_id)"]
    for table, expressions in checks.items():
        condition = " OR ".join(f"({expr})" for expr in expressions)
        for action in ("INSERT", "UPDATE"):
            con.execute(f'''CREATE TRIGGER "integrity_{table}_{action.lower()}"
              BEFORE {action} ON "{table}" WHEN {condition}
              BEGIN SELECT RAISE(ABORT,'{table} integrity violation'); END''')
    # Entities and version definitions retain their identity after creation.
    for table in ("entities", "instrument_versions", "metric_definitions"):
        con.execute(f'''CREATE TRIGGER "identity_{table}" BEFORE UPDATE ON "{table}"
          BEGIN SELECT RAISE(ABORT,'create a new identity/version instead'); END''')
