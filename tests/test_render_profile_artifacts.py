import render_profile_artifacts as rpa


def test_soft_block_contains_canonical_sections():
    block = rpa.render_soft_block()
    assert "## Workflow: New Feature" in block
    assert "## Working Principles" in block
    assert "## Documentation Map" in block


def test_soft_block_links_docs_index():
    # The Documentation Map section points at docs/index.md; must survive into the block.
    assert "docs/index.md" in rpa.render_soft_block()


def test_soft_block_ends_with_single_newline():
    block = rpa.render_soft_block()
    assert block.endswith("\n")
    assert not block.endswith("\n\n")


def test_plain_profiles_return_bare_block():
    block = rpa.render_soft_block()
    assert rpa.render_for_profile("claude") == block
    assert rpa.render_for_profile("codex") == block
    assert rpa.render_for_profile("generic") == block


def test_cursor_profile_wraps_block_in_mdc_frontmatter():
    out = rpa.render_for_profile("cursor")
    assert out.startswith("---\n")
    assert "alwaysApply: true" in out
    assert "## Workflow: New Feature" in out  # block content preserved
    # frontmatter then a blank line then the block
    assert out.startswith(rpa.CURSOR_FRONTMATTER + "\n")
    assert out.endswith(rpa.render_soft_block())
