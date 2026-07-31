"""Maintenance trap: editing the canonical block must force a version decision.

R021 lets consumers detect a stale copy of the block by comparing version numbers. The
number is a *claim* about content, and nothing verifies it: change guidelines.en.md without
bumping CANONICAL_BLOCK_VERSION and the skill ships new text still labelled with the old
version. Consumers then compare equal numbers and conclude they are current, so the very
mechanism built to catch a stale copy starts certifying it -- worse than no marker, which at
least reads as "unknown".

Consumer copies cannot be compared by content: they are legitimately translated or extended.
The source can. Hashing it here does not verify any consumer -- it verifies that whoever
edited the block did not walk past the version.
"""

import hashlib

import audit_docs_model as adm

# sha256 of assets/templates/ai-instructions/guidelines.en.md, per block version.
# Keyed by version so a bump cannot silently reuse a previous version's fingerprint, and so
# the history of what each version contained stays recorded.
BLOCK_FINGERPRINTS = {
    2: "1835bb90f55152d5e5a97869660d3bcccb0e69257c49b62affc581dcf6fb759d",
}


def test_editing_the_block_forces_a_version_decision():
    path = adm.skill_root() / adm.CANONICAL_GUIDELINES_REL
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    version = adm.CANONICAL_BLOCK_VERSION
    expected = BLOCK_FINGERPRINTS.get(version)

    assert expected is not None, (
        f"CANONICAL_BLOCK_VERSION is {version}, but no fingerprint is pinned for it.\n"
        f"Add to BLOCK_FINGERPRINTS in this file:\n    {version}: {digest!r},"
    )

    assert digest == expected, (
        "The canonical block changed but CANONICAL_BLOCK_VERSION is still "
        f"{version}.\n\n"
        "Consumer repositories carry this number in their CLAUDE.md/AGENTS.md. Leaving it "
        "put means they compare equal versions against different text and are told they "
        "are up to date when they are not.\n\n"
        "Pick one:\n"
        f"  - Consumers should update  -> bump CANONICAL_BLOCK_VERSION to {version + 1} in "
        "scripts/audit_docs_model.py and add its fingerprint below.\n"
        "  - Cosmetic change (typo, rewording that changes no instruction) -> keep the "
        f"version and replace the fingerprint for {version} with:\n"
        f"        {digest!r}\n\n"
        "Then regenerate the derived artifact:\n"
        "    python3 scripts/render_profile_artifacts.py cursor "
        "> assets/templates/cursor/rules/docs-first.mdc"
    )


def test_the_pinned_version_is_the_one_shipped_in_the_block():
    """The fingerprint guards the file; this guards the marker inside it."""

    workflow = adm.load_canonical_sections()["## Workflow: New Feature"]
    assert adm.installed_block_version(workflow) == adm.CANONICAL_BLOCK_VERSION
