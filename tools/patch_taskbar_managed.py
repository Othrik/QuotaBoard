"""Make the MIT-licensed taskbar host a private QuotaBoard child process."""
from pathlib import Path
import sys
root=Path(sys.argv[1]);p=root/'src/loader/Program.cs';s=p.read_text(encoding='utf8')
a='        CommunityWidgetRegistry.Initialize();';assert s.count(a)==1
s=s.replace(a,'''        if (args.Length == 2 && args[0] == "--quotaboard-parent")
            return await RunQuotaBoardManagedAsync(int.Parse(args[1]));
'''+a)
pos=s.index('    private static async Task RunProviderIsolatedAsync(')
method='''    // No tray, settings app, network workers, extension runtime, or updater.
    // QuotaBoard supplies only its own native layout and credential-free state.
    private static async Task<int> RunQuotaBoardManagedAsync(int parentId)
    {
        using var mutex = new Mutex(true, @"Local\\QuotaBoardTaskbarHost", out var created);
        if (!created) return 0;
        using var parent = Process.GetProcessById(parentId);
        _ = parent.Handle;
        using var cancellation = new CancellationTokenSource();
        var hookPath = ExtractHookDll();
        var control = Path.Combine(AppDirectory, "managed-control.json");
        var watchdog = Task.Run(() => RunExplorerWatchdogAsync(hookPath, cancellation.Token));
        Log("QuotaBoard managed taskbar host started");
        try
        {
            while (!parent.HasExited && !watchdog.IsCompleted)
            {
                if (!File.Exists(control) ||
                    DateTime.UtcNow - File.GetLastWriteTimeUtc(control) > TimeSpan.FromSeconds(15)) break;
                using var state = JsonDocument.Parse(File.ReadAllText(control));
                if (!state.RootElement.GetProperty("enabled").GetBoolean()) break;
                await Task.Delay(500);
            }
            if (watchdog.IsFaulted) await watchdog;
            return 0;
        }
        finally
        {
            cancellation.Cancel();
            try { await watchdog; } catch (OperationCanceledException) { }
            DetachFromAllExplorers();
            Log("QuotaBoard managed taskbar host stopped");
        }
    }

'''
s=s[:pos]+method+s[pos:];p.write_text(s,encoding='utf8')
# Rebuild the private child under a QuotaBoard process name.
p=root/'src/loader/TaskbarWidgets.csproj';s=p.read_text(encoding='utf8').replace('<AssemblyName>TaskbarWidgets</AssemblyName>','<AssemblyName>QuotaBoard.TaskbarHost</AssemblyName>');p.write_text(s,encoding='utf8')
print('Applied QuotaBoard managed lifecycle')

# Native empty fields are intentionally blank, never repeated placeholder dashes.
p=root/'src/native/taskbar-hook/taskbar_widgets_hook.cpp'
s=p.read_text(encoding='utf8')
assert s.count('return text.empty() ? L"--" : text;')==1
s=s.replace('return text.empty() ? L"--" : text;', 'return text;')
p.write_text(s,encoding='utf8')
