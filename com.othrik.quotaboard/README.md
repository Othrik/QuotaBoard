# Legacy Taskbar Widgets extension

QuotaBoard 1.1.29 and later include their own managed taskbar helper. End users should enable **任务栏常驻额度** in QuotaBoard settings; they do not need to install this extension or Taskbar Widgets separately.

This directory retains the optional external-host adapter (1.0.6) for development/reference. It reads only QuotaBoard's credential-free taskbar-snapshot.json, rotates enabled AIs, and uses transparent artwork. Its PowerShell runtime requires the external host's full-access installation review. Native image loading requires the file-stream fix in tools/patch_taskbar_images.py.

The bundled implementation is quotaboard/taskbar.py and quotaboard/taskbar_layout.py. Its helper lifecycle patch is tools/patch_taskbar_managed.py. Build provenance, pinned upstream source, hash and MIT license are under assets/taskbar/. The bundled mode does not execute provider.ps1 or depend on this extension's approval state.
