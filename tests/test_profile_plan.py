import build_docs_alignment_plan as plan


def test_proposed_diff_routes_active_cursor_rule_through_canonical_block(tmp_path):
    (tmp_path / ".cursor" / "rules").mkdir(parents=True)
    rel = ".cursor/rules/docs-first.mdc"
    # present but missing the structural sections -> a BLOCKER the audit would raise
    (tmp_path / rel).write_text("---\nalwaysApply: true\n---\n\n# empty\n", encoding="utf-8")

    result = {
        "findings": [
            {
                "code": "AI_INSTRUCTION_SECTION_MISSING",
                "path": rel,
                "severity": "BLOCKER",
                "message": "missing workflow section",
            }
        ]
    }
    items, _deferred = plan.proposed_diffs(tmp_path, result, [], [rel], max_diffs=30)
    cursor_items = [i for i in items if i["path"] == rel]
    assert len(cursor_items) == 1
    assert cursor_items[0]["type"] == "update"
    # the canonical block is what gets appended
    assert "## Workflow: New Feature" in cursor_items[0]["diff"]


def test_inactive_cursor_rule_not_treated_as_ai_instruction(tmp_path):
    # no .cursor/ dir -> cursor profile inactive -> the path falls through to update-plan
    rel = ".cursor/rules/docs-first.mdc"
    result = {
        "findings": [
            {"code": "SOME_OTHER", "path": rel, "severity": "BLOCKER", "message": "x"}
        ]
    }
    items, _deferred = plan.proposed_diffs(tmp_path, result, [], [rel], max_diffs=30)
    assert items[0]["type"] == "update-plan"
