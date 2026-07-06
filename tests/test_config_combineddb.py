"""Slice R config pins: combinedDBQues is the question-bank source by default.

These assert DEFAULTS, so each guard skips when the corresponding env override is
set in the developer's environment (config reads env at import time).
"""
import os
from pathlib import Path

import pytest

from samagra import config


def _no_env(*names):
    return pytest.mark.skipif(
        any(os.environ.get(n) for n in names), reason="env override set")


@_no_env("SAMAGRA_COMBINED_DB_ROOT")
def test_combined_db_root_default():
    assert config.COMBINED_DB_ROOT == Path(r"C:\SandBox\claude_khanak_box\combinedDBQues")


@_no_env("SAMAGRA_QX_SERVER_URL")
def test_qx_server_url_defaults_to_8790():
    assert config.QX_SERVER_URL == "http://127.0.0.1:8790"


@_no_env("SAMAGRA_COMBINED_DB_ROOT", "SAMAGRA_QX_BUILDER_DB", "SAMAGRA_QX_CONTENT_DB")
def test_qx_dbs_point_at_the_unified_sqlites():
    assert config.QX_BUILDER_DB == config.COMBINED_DB_ROOT / "app" / "qx" / "unified_builder.sqlite"
    assert config.QX_CONTENT_DB == config.COMBINED_DB_ROOT / "app" / "qx" / "unified_content.sqlite"


def test_chapter_map_is_a_committed_repo_root_artifact():
    assert config.CHAPTER_MAP == config.REPO_ROOT / "chapter_map.json"
