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
