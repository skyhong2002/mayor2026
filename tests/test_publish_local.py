import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import publish_local


def tree(root):
    return {
        str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
        for path in sorted(root.rglob("*"))
    }


class CopySiteTests(unittest.TestCase):
    def make_site(self, root):
        site = root / "site"
        (site / "templates").mkdir(parents=True)
        (site / "templates" / "page.html").write_text("template")
        (site / "assets" / "_kit").mkdir(parents=True)
        (site / "assets" / "_kit" / "kit.css").write_text("kit")
        (site / "assets" / "app.css").write_text("css")
        (site / "assets" / ".DS_Store").write_text("finder")
        (site / "index.html").write_text("index")
        os.symlink("index.html", site / "home.html")
        return site

    def test_clone_and_fallback_copy_publish_the_same_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = self.make_site(root)
            publish_local.copy_site(site, root / "clone")
            with mock.patch.object(publish_local.sys, "platform", "linux"):
                publish_local.copy_site(site, root / "copy")
            expected = {
                "assets": None,
                "assets/app.css": b"css",
                "home.html": b"index",
                "index.html": b"index",
            }
            self.assertEqual(tree(root / "clone"), expected)
            self.assertEqual(tree(root / "copy"), expected)
            self.assertFalse((root / "clone" / "home.html").is_symlink())

    def test_failed_clone_falls_back_to_a_full_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = self.make_site(root)
            failed = mock.Mock(returncode=1, stderr="no clone")
            with mock.patch.object(publish_local.sys, "platform", "darwin"), \
                    mock.patch.object(publish_local.subprocess, "run", return_value=failed), \
                    mock.patch("sys.stderr"):
                publish_local.copy_site(site, root / "release")
            self.assertEqual(tree(root / "release")["index.html"], b"index")
            self.assertNotIn("templates", tree(root / "release"))


if __name__ == "__main__":
    unittest.main()
