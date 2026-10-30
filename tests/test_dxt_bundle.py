"""
Tests that the built DXT bundle stays in sync with dxt/manifest.json.

The bundle is a generated artifact committed alongside its source. It has
drifted before: a committed .dxt predated the crossref_email field, so
one-click installs never offered it. Nothing caught that, because the
manifest and the bundle are only compared by rebuilding.
"""

import json
import os
import zipfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(REPO_ROOT, "dxt", "manifest.json")
BUNDLE_PATH = os.path.join(REPO_ROOT, "dxt", "academic-research-mcp.dxt")

pytestmark = pytest.mark.skipif(
    not os.path.exists(BUNDLE_PATH),
    reason="DXT bundle is not built in this checkout",
)


def _bundled_manifest() -> dict:
    with zipfile.ZipFile(BUNDLE_PATH) as bundle:
        return json.loads(bundle.read("manifest.json"))


def test_bundled_manifest_matches_source():
    """The manifest inside the .dxt is byte-for-byte the source manifest."""
    with open(MANIFEST_PATH, "rb") as f:
        source = f.read()
    with zipfile.ZipFile(BUNDLE_PATH) as bundle:
        bundled = bundle.read("manifest.json")

    assert bundled == source, (
        "dxt/academic-research-mcp.dxt is stale — rebuild it after editing "
        "dxt/manifest.json"
    )


def test_manifest_env_vars_have_user_config_entries():
    """Every ${user_config.X} referenced in the env block is actually declared."""
    manifest = _bundled_manifest()
    declared = set(manifest["user_config"])
    env = manifest["server"]["mcp_config"]["env"]

    for var, template in env.items():
        assert template.startswith("${user_config."), (
            f"{var} does not read from user_config: {template}"
        )
        key = template[len("${user_config.") : -1]
        assert key in declared, (
            f"{var} references undeclared user_config field {key!r}"
        )


def test_api_keys_are_marked_sensitive():
    """Credentials are masked in the install prompt; polite-pool emails are not."""
    user_config = _bundled_manifest()["user_config"]

    for key in ("s2_api_key", "ncbi_api_key"):
        assert user_config[key]["sensitive"] is True, (
            f"{key} is a credential and must be marked sensitive"
        )

    for key in ("openalex_email", "crossref_email"):
        assert user_config[key]["sensitive"] is False, (
            f"{key} is a polite-pool identifier, not a credential — leaving it "
            "masked hides the address the user typed and cannot be confirmed"
        )
