# -*- coding: utf-8 -*-
"""gemini_vss_helper：以管理员身份运行，VSS 卷影复制被锁的 Gemini Cookies 到 %TEMP%。

只做「创建卷影 → 复制文件 → 删除卷影」，不含任何解密（DPAPI 需原用户上下文，
解密一律在主进程完成）。由 GeminiProvider._run_vss_helper 以 UAC 提权调用。
"""
import io
import os
import shutil
import sys
from quotaboard.background_process import run_hidden

TARGET = os.path.join(os.environ.get("TEMP", "."), "gemini_cookies_vss.db")
SRC = os.path.join(os.environ.get("APPDATA", ""), "gemini", "Network", "Cookies")
VOLUME = "C:\\"
_PWSH = (r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
         if os.path.isfile(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
         else "powershell.exe")


def _wmi_create_shadow() -> str | None:
    """Invoke-CimMethod 创建 C: 卷影，返回 ShadowID（失败返回 None）。"""
    ps = (
        "$c = Invoke-CimMethod -Namespace root\\cimv2 -ClassName Win32_ShadowCopy "
        "-MethodName Create -Arguments @{Volume='%s'};"
        "if ($c.ReturnValue -eq 0 -and $c.ShadowID) { $c.ShadowID }" % VOLUME
    )
    r = run_hidden([_PWSH, "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, text=True, timeout=120)
    out = (r.stdout or "").strip()
    return out if r.returncode == 0 and out else None


def _shadow_device(shadow_id: str) -> str | None:
    ps = (
        "$s = Get-WmiObject Win32_ShadowCopy | Where-Object { $_.ID -eq '%s' };"
        "if ($s) { $s.DeviceObject }" % shadow_id
    )
    r = run_hidden([_PWSH, "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, text=True, timeout=60)
    out = (r.stdout or "").strip()
    return out if r.returncode == 0 and out else None


def _delete_shadow(shadow_id: str) -> None:
    try:
        run_hidden(["cmd", "/c", "vssadmin delete shadows /shadow=%s /quiet"
                       % shadow_id], capture_output=True, timeout=60)
    except Exception:
        pass


def main() -> int:
    log = io.open(r"C:\Users\HuZih\AppData\Local\Temp\gemini_helper_debug.txt",
                  "w", encoding="utf-8")
    log.write("SRC=%s exists=%s\n" % (SRC, os.path.isfile(SRC)))
    log.write("TARGET=%s\n" % TARGET)
    if not os.path.isfile(SRC):
        log.write("rc=2 no-src\n")
        log.close()
        return 2
    try:
        shutil.copyfile(SRC, TARGET)
        if os.path.isfile(TARGET) and os.path.getsize(TARGET) > 0:
            log.write("rc=0 direct-copy\n")
            log.close()
            return 0
    except OSError as e:
        log.write("direct-copy OSError: %r\n" % (e,))
    shadow_id = _wmi_create_shadow()
    log.write("shadow_id=%s\n" % (shadow_id or "NONE"))
    if not shadow_id:
        log.write("rc=3 no-shadow\n")
        log.close()
        return 3
    try:
        device = _shadow_device(shadow_id)
        log.write("device=%s\n" % (device or "NONE"))
        if not device:
            log.write("rc=4 no-device\n")
            log.close()
            return 4
        src_ss = os.path.join(device, "Users", os.environ.get("USERNAME", ""),
                              "AppData", "Roaming", "gemini", "Network", "Cookies")
        log.write("src_ss=%s\n" % src_ss)
        ps = ("Copy-Item -LiteralPath '%s' -Destination '%s' -Force"
              % (src_ss, TARGET))
        try:
            if os.path.exists(TARGET):
                os.remove(TARGET)
        except OSError:
            pass
        r = run_hidden([_PWSH, "-NoProfile", "-NonInteractive", "-Command", ps],
                           capture_output=True, timeout=120)
        log.write("copy rc=%s stderr=%r\n" % (r.returncode, (r.stderr or b"")[:300]))
        if r.returncode == 0 and os.path.isfile(TARGET) and os.path.getsize(TARGET) > 0:
            log.write("rc=0 vss-copy size=%d\n" % os.path.getsize(TARGET))
            log.close()
            return 0
        log.write("rc=5 vss-copy-fail\n")
        log.close()
        return 5
    finally:
        _delete_shadow(shadow_id)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(9)
