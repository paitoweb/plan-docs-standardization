from pathlib import Path

import audit_docs_model as adm
import build_docs_alignment_plan as plan


def test_index_map_missing_routes_to_alter():
    result = {"findings": [
        {"code": "INDEX_MAP_MISSING", "path": "docs/index.md", "severity": "WARN"},
    ]}
    create, alter = plan.collect_actions(result)
    assert alter == ["docs/index.md"]
    assert create == []


def test_index_map_diff_appends_map_block(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir(parents=True)
    (docs / "index.md").write_text("# Docs\n\nno map\n", encoding="utf-8")
    result = {"findings": [
        {"code": "INDEX_MAP_MISSING", "path": "docs/index.md",
         "severity": "WARN", "message": "no map"},
    ]}
    items, deferred = plan.proposed_diffs(tmp_path, result, [], ["docs/index.md"], 10)
    index_items = [it for it in items if it["path"] == "docs/index.md"]
    assert len(index_items) == 1
    assert index_items[0]["type"] == "update"
    assert "## Documentation Map" in index_items[0]["diff"]


def test_pointer_missing_diff_appends_map_section(tmp_path):
    # CLAUDE.md has workflow + principles but no docs/index.md pointer.
    sections = adm.load_canonical_sections()
    text = "\n\n".join(sections[h] for h in adm.AI_INSTRUCTION_SECTION_HEADINGS) + "\n"
    (tmp_path / "CLAUDE.md").write_text(text, encoding="utf-8")
    diff = plan.ai_instruction_update_diff(tmp_path, "CLAUDE.md")
    assert "## Documentation Map" in diff
    assert "docs/index.md" in diff


def test_index_map_diff_appends_map_block_no_existing_file(tmp_path):
    result = {"findings": [{"code": "INDEX_MAP_MISSING", "path": "docs/index.md",
                            "severity": "WARN", "message": "no map"}]}
    items, _ = plan.proposed_diffs(tmp_path, result, [], ["docs/index.md"], 10)
    assert "## Documentation Map" in items[0]["diff"]
