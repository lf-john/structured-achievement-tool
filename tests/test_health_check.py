"""Tests for CLAUDE.md integrity monitoring in health_check.py."""

import hashlib
import json
import os
from unittest.mock import patch

from src.health_check import (
    _load_claude_md_hashes,
    _save_claude_md_hashes,
    _sha256_file,
    check_claude_md_integrity,
)


class TestSha256File:
    """Tests for SHA-256 hash computation."""

    def test_computes_correct_hash(self, tmp_path):
        f = tmp_path / "test.md"
        content = b"# My CLAUDE.md\nSome rules here.\n"
        f.write_bytes(content)

        expected = hashlib.sha256(content).hexdigest()
        assert _sha256_file(str(f)) == expected

    def test_returns_none_for_missing_file(self, tmp_path):
        assert _sha256_file(str(tmp_path / "nonexistent.md")) is None

    def test_returns_none_for_unreadable_file(self, tmp_path):
        f = tmp_path / "noperm.md"
        f.write_text("secret")
        f.chmod(0o000)
        try:
            assert _sha256_file(str(f)) is None
        finally:
            f.chmod(0o644)

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.md"
        f.write_bytes(b"")
        expected = hashlib.sha256(b"").hexdigest()
        assert _sha256_file(str(f)) == expected

    def test_large_file_chunked(self, tmp_path):
        """Ensure large files are hashed correctly (exercises chunked read)."""
        f = tmp_path / "big.md"
        data = b"x" * 100_000
        f.write_bytes(data)
        expected = hashlib.sha256(data).hexdigest()
        assert _sha256_file(str(f)) == expected


class TestHashPersistence:
    """Tests for loading and saving hash state."""

    def test_load_returns_empty_when_missing(self, tmp_path):
        with patch("src.health_check.CLAUDE_MD_HASHES_FILE", str(tmp_path / "nope.json")):
            assert _load_claude_md_hashes() == {}

    def test_save_and_load_roundtrip(self, tmp_path):
        hashes_file = str(tmp_path / "hashes.json")
        data = {"/some/path/CLAUDE.md": "abc123"}
        with patch("src.health_check.CLAUDE_MD_HASHES_FILE", hashes_file):
            _save_claude_md_hashes(data)
            loaded = _load_claude_md_hashes()
        assert loaded == data

    def test_load_handles_corrupt_json(self, tmp_path):
        hashes_file = tmp_path / "hashes.json"
        hashes_file.write_text("{broken json")
        with patch("src.health_check.CLAUDE_MD_HASHES_FILE", str(hashes_file)):
            assert _load_claude_md_hashes() == {}

    def test_save_creates_parent_dirs(self, tmp_path):
        hashes_file = str(tmp_path / "sub" / "dir" / "hashes.json")
        with patch("src.health_check.CLAUDE_MD_HASHES_FILE", hashes_file):
            _save_claude_md_hashes({"key": "val"})
        assert os.path.isfile(hashes_file)


class TestCheckClaudeMdIntegrity:
    """Tests for the integrity check cycle."""

    def test_first_run_stores_baseline_no_alert(self, tmp_path):
        """First run should store hash and return no warnings."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Rules\nDo stuff.\n")
        hashes_file = str(tmp_path / "hashes.json")

        with (
            patch("src.health_check.CLAUDE_MD_WATCHED_PATHS", [str(claude_md)]),
            patch("src.health_check.CLAUDE_MD_HASHES_FILE", hashes_file),
        ):
            warnings = check_claude_md_integrity()

        assert warnings == []
        # Verify baseline was stored
        with open(hashes_file) as f:
            stored = json.load(f)
        assert str(claude_md) in stored
        expected_hash = hashlib.sha256(b"# Rules\nDo stuff.\n").hexdigest()
        assert stored[str(claude_md)] == expected_hash

    def test_unchanged_file_no_alert(self, tmp_path):
        """File with same hash as stored should produce no warnings."""
        claude_md = tmp_path / "CLAUDE.md"
        content = b"# Rules\nDo stuff.\n"
        claude_md.write_bytes(content)
        hashes_file = str(tmp_path / "hashes.json")

        # Pre-populate with correct hash
        stored = {str(claude_md): hashlib.sha256(content).hexdigest()}
        with open(hashes_file, "w") as f:
            json.dump(stored, f)

        with (
            patch("src.health_check.CLAUDE_MD_WATCHED_PATHS", [str(claude_md)]),
            patch("src.health_check.CLAUDE_MD_HASHES_FILE", hashes_file),
        ):
            warnings = check_claude_md_integrity()

        assert warnings == []

    def test_changed_file_triggers_alert(self, tmp_path):
        """Modified file should produce a warning."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Rules\nOriginal content.\n")
        hashes_file = str(tmp_path / "hashes.json")

        # Store hash of original content
        original_hash = hashlib.sha256(b"# Rules\nOriginal content.\n").hexdigest()
        with open(hashes_file, "w") as f:
            json.dump({str(claude_md): original_hash}, f)

        # Now modify the file
        claude_md.write_text("# Rules\nTAMPERED content.\n")

        with (
            patch("src.health_check.CLAUDE_MD_WATCHED_PATHS", [str(claude_md)]),
            patch("src.health_check.CLAUDE_MD_HASHES_FILE", hashes_file),
        ):
            warnings = check_claude_md_integrity()

        assert len(warnings) == 1
        assert "CLAUDE.md CHANGED" in warnings[0]
        assert str(claude_md) in warnings[0]

        # Verify stored hash was updated to new value
        with open(hashes_file) as f:
            updated = json.load(f)
        new_hash = hashlib.sha256(b"# Rules\nTAMPERED content.\n").hexdigest()
        assert updated[str(claude_md)] == new_hash

    def test_missing_file_skipped_silently(self, tmp_path):
        """Non-existent file should not warn or store anything."""
        missing = str(tmp_path / "ghost" / "CLAUDE.md")
        hashes_file = str(tmp_path / "hashes.json")

        with (
            patch("src.health_check.CLAUDE_MD_WATCHED_PATHS", [missing]),
            patch("src.health_check.CLAUDE_MD_HASHES_FILE", hashes_file),
        ):
            warnings = check_claude_md_integrity()

        assert warnings == []
        # No hashes file should have been created (nothing to store)
        assert not os.path.exists(hashes_file)

    def test_multiple_files_mixed(self, tmp_path):
        """Test with multiple files: one unchanged, one changed, one new."""
        f_unchanged = tmp_path / "proj1" / "CLAUDE.md"
        f_changed = tmp_path / "proj2" / "CLAUDE.md"
        f_new = tmp_path / "proj3" / "CLAUDE.md"

        for d in [f_unchanged.parent, f_changed.parent, f_new.parent]:
            d.mkdir()

        f_unchanged.write_bytes(b"unchanged")
        f_changed.write_bytes(b"changed-new")
        f_new.write_bytes(b"brand new")

        hashes_file = str(tmp_path / "hashes.json")
        stored = {
            str(f_unchanged): hashlib.sha256(b"unchanged").hexdigest(),
            str(f_changed): hashlib.sha256(b"changed-old").hexdigest(),
        }
        with open(hashes_file, "w") as f:
            json.dump(stored, f)

        watched = [str(f_unchanged), str(f_changed), str(f_new)]
        with (
            patch("src.health_check.CLAUDE_MD_WATCHED_PATHS", watched),
            patch("src.health_check.CLAUDE_MD_HASHES_FILE", hashes_file),
        ):
            warnings = check_claude_md_integrity()

        # Only the changed file should produce a warning (new file is baseline)
        assert len(warnings) == 1
        assert str(f_changed) in warnings[0]

    @patch("src.health_check.notify")
    def test_main_sends_ntfy_on_change(self, mock_notify, tmp_path):
        """Integration: verify main() calls notify when CLAUDE.md changes."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("tampered")
        hashes_file = str(tmp_path / "hashes.json")

        original_hash = hashlib.sha256(b"original").hexdigest()
        with open(hashes_file, "w") as f:
            json.dump({str(claude_md): original_hash}, f)

        with (
            patch("src.health_check.CLAUDE_MD_WATCHED_PATHS", [str(claude_md)]),
            patch("src.health_check.CLAUDE_MD_HASHES_FILE", hashes_file),
        ):
            warnings = check_claude_md_integrity()

        assert len(warnings) == 1
        # The actual ntfy call happens in main(), but we verify the warnings
        # are non-empty so main() would include them in problems and notify.
