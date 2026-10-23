import os

import pytest

from tuskr_mcp import attachments


@pytest.fixture
def attach_dir(tmp_path, monkeypatch):
    """An attachment root containing nothing yet."""
    root = tmp_path / "attachments"
    root.mkdir()
    monkeypatch.setenv(attachments.ATTACHMENT_DIR_ENV, str(root))
    return root


class TestLoadAttachments:
    """Cover the validation that runs before any request is sent."""

    def test_disabled_without_attachment_dir(self, monkeypatch):
        """No sandbox root configured means no file is ever read."""
        monkeypatch.delenv(attachments.ATTACHMENT_DIR_ENV, raising=False)

        with pytest.raises(ValueError, match="Attachments are disabled"):
            attachments.load_attachments(["a.txt"])

    def test_loads_name_bytes_and_mimetype(self, attach_dir):
        """A relative path resolves against the root and is read in full."""
        (attach_dir / "log.txt").write_bytes(b"boom")
        (attach_dir / "shot.png").write_bytes(b"\x89PNG")

        result = attachments.load_attachments(["log.txt", "shot.png"])

        assert result == [
            ("log.txt", b"boom", "text/plain"),
            ("shot.png", b"\x89PNG", "image/png"),
        ]

    def test_absolute_path_inside_root_is_accepted(self, attach_dir):
        """An absolute path is fine as long as it stays inside the root."""
        target = attach_dir / "log.txt"
        target.write_bytes(b"boom")

        assert attachments.load_attachments([str(target)])[0][0] == "log.txt"

    def test_unknown_extension_falls_back_to_octet_stream(self, attach_dir):
        (attach_dir / "dump.zzzunknown").write_bytes(b"x")

        assert attachments.load_attachments(["dump.zzzunknown"])[0][2] == (
            "application/octet-stream"
        )

    def test_more_than_two_files_rejected(self, attach_dir):
        for name in ("a.txt", "b.txt", "c.txt"):
            (attach_dir / name).write_bytes(b"x")

        with pytest.raises(ValueError, match="At most 2"):
            attachments.load_attachments(["a.txt", "b.txt", "c.txt"])

    def test_file_at_the_limit_is_accepted(self, attach_dir):
        (attach_dir / "big.bin").write_bytes(b"\0" * attachments.MAX_ATTACHMENT_BYTES)

        assert len(attachments.load_attachments(["big.bin"])) == 1

    def test_file_over_the_limit_is_rejected(self, attach_dir):
        (attach_dir / "big.bin").write_bytes(
            b"\0" * (attachments.MAX_ATTACHMENT_BYTES + 1)
        )

        with pytest.raises(ValueError, match="limit is"):
            attachments.load_attachments(["big.bin"])

    def test_missing_file_rejected(self, attach_dir):
        with pytest.raises(ValueError, match="not an existing file"):
            attachments.load_attachments(["nope.txt"])

    def test_directory_rejected(self, attach_dir):
        (attach_dir / "sub").mkdir()

        with pytest.raises(ValueError, match="not an existing file"):
            attachments.load_attachments(["sub"])

    def test_parent_traversal_rejected(self, attach_dir):
        (attach_dir.parent / "secret.txt").write_bytes(b"secret")

        with pytest.raises(ValueError, match="outside the allowed directory"):
            attachments.load_attachments(["../secret.txt"])

    def test_absolute_path_outside_root_rejected(self, attach_dir):
        outside = attach_dir.parent / "secret.txt"
        outside.write_bytes(b"secret")

        with pytest.raises(ValueError, match="outside the allowed directory"):
            attachments.load_attachments([str(outside)])

    def test_symlink_escaping_the_root_rejected(self, attach_dir):
        outside = attach_dir.parent / "secret.txt"
        outside.write_bytes(b"secret")
        try:
            os.symlink(outside, attach_dir / "link.txt")
        except (OSError, NotImplementedError):
            pytest.skip("symlinks are not available on this platform")

        with pytest.raises(ValueError, match="outside the allowed directory"):
            attachments.load_attachments(["link.txt"])
