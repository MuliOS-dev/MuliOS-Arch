"""Tests for the mulios-profile integration. Run: python -m unittest discover tests"""
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from backend import native_installer_worker as nw  # noqa: E402
from config.settings import SUPPORTED_PROFILES  # noqa: E402
from pages.profile_page import ProfilePage  # noqa: E402

APP = QApplication.instance() or QApplication([])
SIX = ("gaming", "code", "ai", "study", "privacy", "casual")


class ProfilePageTests(unittest.TestCase):
    def test_six_profiles_one_selected(self):
        page = ProfilePage()
        self.assertEqual(tuple(page.available_profiles()), SIX)
        self.assertEqual(sum(b.isChecked() for b in page.button_group.buttons()), 1)
        self.assertEqual(page.selected_profile(), "casual")
        self.assertEqual(page.selected_profile_name(), "Casual")

    def test_click_selects_exactly_one(self):
        page = ProfilePage()
        page._button_by_slug["ai"].click()
        self.assertEqual(page.selected_profile(), "ai")
        self.assertEqual(sum(b.isChecked() for b in page.button_group.buttons()), 1)

    def test_keyboard_navigation(self):
        page = ProfilePage()
        page.show()
        first = page._button_by_slug["gaming"]
        first.setChecked(True)
        first.setFocus()
        QTest.keyClick(first, Qt.Key_Right)
        self.assertEqual(page.selected_profile(), "code")
        QTest.keyClick(page._button_by_slug["code"], Qt.Key_Down)
        self.assertEqual(page.selected_profile(), "privacy")
        QTest.keyClick(page._button_by_slug["privacy"], Qt.Key_End)
        self.assertEqual(page.selected_profile(), "casual")
        QTest.keyClick(page._button_by_slug["casual"], Qt.Key_Right)  # edge: stay
        self.assertEqual(page.selected_profile(), "casual")
        QTest.keyClick(page._button_by_slug["casual"], Qt.Key_Home)
        self.assertEqual(page.selected_profile(), "gaming")

    def test_no_network_code(self):
        root = Path(__file__).resolve().parent.parent
        for rel in ("pages/profile_page.py", "backend/native_installer_worker.py",
                    "config/settings.py", "main.py"):
            text = (root / rel).read_text(encoding="utf-8")
            self.assertNotIn("MuliOS-dev/update", text, rel)
            self.assertNotIn("api.github.com", text, rel)
            self.assertNotIn("urllib", text, rel)


class FakeChrootTests(unittest.TestCase):
    """Run the real subprocess path with a fake arch-chroot and fake command."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        tmp = Path(self.tmp.name)
        self.bin = tmp / "bin"
        self.bin.mkdir()
        self.calls = tmp / "calls"
        self._exe("arch-chroot", 'shift\nexec "$@"\n')
        self._exe("sudo", 'exec "$@"\n')  # hermetic stand-in for real sudo
        self.old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{self.bin}:{self.old_path}"
        self.addCleanup(lambda: os.environ.__setitem__("PATH", self.old_path))
        self.old_log = nw.LOG_PATH
        nw.LOG_PATH = tmp / "install.log"
        self.addCleanup(lambda: setattr(nw, "LOG_PATH", self.old_log))

    def _exe(self, name, body, mode=0o755):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(mode)

    def worker(self, profile):
        w = nw.InstallWorker({"profile": profile})
        w.target = Path(self.tmp.name)
        return w

    def test_success_runs_apply_with_exact_argv(self):
        self._exe("mulios-profile", f'echo "$@" > {self.calls}\n')
        self.worker("gaming").install_selected_profile()
        self.assertEqual(self.calls.read_text().strip(), "apply gaming")

    def test_uses_sudo_when_present(self):
        sudo_log = Path(self.tmp.name) / "sudo_calls"
        self._exe("sudo", f'echo "$@" > {sudo_log}\nexec "$@"\n')
        self._exe("mulios-profile", f'echo "$@" > {self.calls}\n')
        self.worker("study").install_selected_profile()
        self.assertEqual(sudo_log.read_text().strip(), "mulios-profile apply study")
        self.assertEqual(self.calls.read_text().strip(), "apply study")

    def test_all_six_profiles_apply(self):
        self._exe("mulios-profile", f'echo "$@" >> {self.calls}\n')
        for p in SIX:
            self.worker(p).install_selected_profile()
        self.assertEqual(self.calls.read_text().split("\n")[:6],
                         [f"apply {p}" for p in SIX])

    def test_missing_command(self):
        # Hide any real mulios-profile; PATH only has fake bin + basics.
        with self.assertRaises(nw.InstallError) as cm:
            self.worker("code").install_selected_profile()
        self.assertIn("not installed", str(cm.exception))

    def test_not_executable(self):
        self._exe("mulios-profile", "exit 0\n", mode=0o644)
        with self.assertRaises(nw.InstallError) as cm:
            self.worker("code").install_selected_profile()
        self.assertTrue(
            "not executable" in str(cm.exception) or "not installed" in str(cm.exception))

    def test_nonzero_exit_reports_failure(self):
        self._exe("mulios-profile", "echo boom >&2; exit 3\n")
        with self.assertRaises(nw.InstallError) as cm:
            self.worker("ai").install_selected_profile()
        msg = str(cm.exception)
        self.assertIn("'ai'", msg)
        self.assertIn("exit code 3", msg)
        self.assertIn("boom", nw.LOG_PATH.read_text())

    def test_permission_error_exit_is_reported(self):
        self._exe("mulios-profile", "echo 'permission denied' >&2; exit 1\n")
        with self.assertRaises(nw.InstallError):
            self.worker("study").install_selected_profile()

    def test_unsupported_profile_never_runs_command(self):
        self._exe("mulios-profile", f"echo ran > {self.calls}\n")
        for bad in ("generic", "server", "", "gaming; rm -rf /", "../x"):
            with self.assertRaises(nw.InstallError, msg=bad):
                self.worker(bad).install_selected_profile()
        self.assertFalse(self.calls.exists())

    def test_profile_applied_even_when_mupdate_skipped(self):
        self._exe("mulios-profile", f'echo "$@" > {self.calls}\n')
        w = self.worker("privacy")
        w.state["skip_mupdate"] = True
        w.configure_mupdate()
        w.install_selected_profile()
        self.assertEqual(self.calls.read_text().strip(), "apply privacy")

    def test_kernel_independent_of_profile(self):
        for p in SIX:
            self.assertEqual(self.worker(p).kernel_paths()[0], "vmlinuz-linux-mulios-generic")

    def test_supported_matches(self):
        self.assertEqual(tuple(SUPPORTED_PROFILES), SIX)


if __name__ == "__main__":
    unittest.main()
