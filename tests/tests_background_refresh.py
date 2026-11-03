"""Background refresh commands must not create or activate a console."""
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from quotaboard.background_process import run_hidden
from quotaboard.providers import gemini_provider as gemini
import gemini_vss_helper as vss


class BackgroundRefresh(unittest.TestCase):
    def test_windows_launch_has_no_console_and_hidden_startup(self):
        with patch('quotaboard.background_process.os.name', 'nt'), patch(
                'quotaboard.background_process.subprocess.run') as run:
            run_hidden(['test.exe'], capture_output=True, timeout=4)
        options = run.call_args.kwargs
        self.assertTrue(options['creationflags'] & subprocess.CREATE_NO_WINDOW)
        self.assertTrue(options['startupinfo'].dwFlags & subprocess.STARTF_USESHOWWINDOW)
        self.assertEqual(options['startupinfo'].wShowWindow, subprocess.SW_HIDE)
        self.assertEqual(options['timeout'], 4)

    def test_gemini_recovery_routes_both_commands_through_hidden_runner(self):
        with patch.object(gemini, 'run_hidden', return_value=SimpleNamespace(returncode=0)) as run:
            self.assertTrue(gemini._schtasks('/Query', '/TN', 'test'))
        self.assertIn('/Query', run.call_args.args[0])
        with patch.object(gemini, '_schtasks', return_value=False), patch.object(
                gemini, 'run_hidden', return_value=SimpleNamespace(returncode=0)) as run:
            self.assertTrue(gemini._ensure_task())
        self.assertIn('-NonInteractive', run.call_args.args[0])

    def test_vss_commands_remain_hidden_including_cleanup(self):
        result = SimpleNamespace(returncode=0, stdout='test-id')
        with patch.object(vss, 'run_hidden', return_value=result) as run:
            self.assertEqual(vss._wmi_create_shadow(), 'test-id')
            self.assertEqual(vss._shadow_device('test-id'), 'test-id')
            vss._delete_shadow('test-id')
        self.assertEqual(run.call_count, 3)


if __name__ == '__main__':
    unittest.main()
