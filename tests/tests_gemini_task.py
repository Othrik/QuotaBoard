"""计划任务自愈：任务指向别的解释器（例如某个 python.exe）时必须拒绝执行，
否则每次触发都会弹一个管理员身份的黑底控制台窗口。"""
import unittest
from unittest.mock import patch

from quotaboard.providers import gemini_provider as gp

PYTHON_TASK_XML = """<Task><Actions Context="Author"><Exec>
<Command>C:\\Users\\HuZih\\AppData\\Local\\Doubao\\User Data\\sandbox_runtime\\python\\python.exe</Command>
<Arguments>-u "C:\\Users\\HuZih\\gemini_vss_helper.py"</Arguments>
</Exec></Actions></Task>"""


class TaskTarget(unittest.TestCase):
    def test_stale_python_task_rejected(self):
        self.assertFalse(gp._task_matches(PYTHON_TASK_XML))

    def test_own_executable_accepted(self):
        exe = gp._task_target()[0]
        xml = f"<Command>{exe.replace(chr(92), '/')}</Command>"
        self.assertTrue(gp._task_matches(xml))

    def test_empty_xml_rejected(self):
        self.assertFalse(gp._task_matches(""))

    def test_ensure_task_skips_when_rebuild_denied(self):
        # 重建失败（没有管理员权限）时，旧任务还在：必须返回 False，不能拿它去跑
        with patch.object(gp, "_schtasks_xml", return_value=PYTHON_TASK_XML), \
             patch.object(gp, "run_hidden") as run_helper:
            run_helper.return_value.returncode = 1
            self.assertFalse(gp._ensure_task())

    def test_ensure_task_ok_when_already_matching(self):
        exe = gp._task_target()[0]
        with patch.object(gp, "_schtasks_xml", return_value=f"<Command>{exe}</Command>"), \
             patch.object(gp, "run_hidden") as run_helper:
            self.assertTrue(gp._ensure_task())
            self.assertFalse(run_helper.called)


if __name__ == "__main__":
    unittest.main()
