"""Repair the pinned host's popup anchor, click capture and rotating snapshots."""
from pathlib import Path
import sys
root=Path(sys.argv[1]);p=root/'src/native/taskbar-hook/taskbar_widgets_hook.cpp';s=p.read_text(encoding='utf8')
def replace_once(old,new):
 global s
 assert s.count(old)==1, 'Pinned popup source changed: '+old[:80]
 s=s.replace(old,new)
replace_once('#include <winrt/Windows.UI.Xaml.Media.h>','#include <winrt/Windows.UI.Xaml.Media.h>\n#include <winrt/Windows.UI.Xaml.Markup.h>')
replace_once('thread_local wuxc::Flyout g_dynamicWidgetPopup{nullptr};','''struct QuotaDisplayedFrame {
    wdj::JsonObject context{nullptr};
    wdj::JsonObject layout{nullptr};
    double width = 360;
    double height = 240;
};
thread_local std::unordered_map<std::wstring, QuotaDisplayedFrame> g_quotaDisplayedFrames;
thread_local wuxc::Flyout g_dynamicWidgetPopup{nullptr};''')
start=s.index('void UpdateDynamicWidgetPanel(');end=s.index('\nclass MediaVisualizerReader',start)
block=s[start:end]
a=block.index('        if (_wcsicmp(definition->renderer.c_str(), L"native") == 0 &&');b=block.index('    } catch (...) {',a)
replacement='''        if (_wcsicmp(definition->renderer.c_str(), L"native") == 0 && definition->expandedLayout) {
            // Keep the button and flyout anchor alive across state refreshes.
            g_quotaDisplayedFrames[instance.instanceId] = QuotaDisplayedFrame{
                context, definition->expandedLayout,
                definition->expandedWidth, definition->expandedHeight};
            auto button = panel.Child().try_as<wuxc::Button>();
            if (!button || button.Name() != L"TaskbarWidgetsNativeExpandButton") {
                button = wuxc::Button();
                button.Name(L"TaskbarWidgetsNativeExpandButton");
                button.Width(definition->width);
                button.Height(definition->height);
                button.Padding(wux::ThicknessHelper::FromUniformLength(0));
                button.BorderThickness(wux::ThicknessHelper::FromUniformLength(0));
                button.Background(MakeBrush(0, 0, 0, 0));
                button.HorizontalContentAlignment(wux::HorizontalAlignment::Stretch);
                button.VerticalContentAlignment(wux::VerticalAlignment::Stretch);
                auto weakRoot = winrt::make_weak(root);
                const std::wstring widgetId = instance.designId;
                const std::wstring instanceId = instance.instanceId;
                button.Click([weakRoot, widgetId, instanceId](auto const&, wux::RoutedEventArgs const&) {
                    if (auto anchor = weakRoot.get()) {
                        ShowDynamicWidgetPopup(anchor, widgetId, instanceId);
                    }
                });
                panel.Child(button);
            }
            button.Content(compact);
        } else {
            panel.Child(compact);
        }
        // An open detail view is a snapshot of the clicked AI. Never replace
        // it with a different AI when the compact view rotates.
'''
block=block[:a]+replacement+block[b:];s=s[:start]+block+s[end:]
start=s.index('bool ShowDynamicWidgetPopup(const wux::UIElement& anchor,',s.index('thread_local wuxc::Flyout'))
end=s.index('\nvoid UpdateDynamicWidgetPanel(',start)
block=s[start:end]
block=block.replace('        wuxc::Border shell;', '''        auto displayed = g_quotaDisplayedFrames.find(instanceId);
        const auto frame = displayed != g_quotaDisplayedFrames.end()
            ? displayed->second
            : QuotaDisplayedFrame{ReadDynamicWidgetContext(instance),
                definition->expandedLayout, definition->expandedWidth, definition->expandedHeight};
        wuxc::Border shell;''')
block=block.replace('shell.Width(definition->expandedWidth);','shell.Width(frame.width);').replace('shell.Height(definition->expandedHeight);','shell.Height(frame.height);').replace('shell.Padding(wux::ThicknessHelper::FromUniformLength(12));','shell.Padding(wux::ThicknessHelper::FromUniformLength(0));').replace('shell.Background(MakeBrush(0xFA, 0x08, 0x12, 0x20));','shell.Background(MakeBrush(0xFF, 0xFF, 0xFF, 0xFF));').replace('shell.BorderBrush(MakeBrush(0x90, 0x22, 0xD3, 0xEE));','shell.BorderBrush(MakeBrush(0xFF, 0xDD, 0xE3, 0xEB));')
block=block.replace('definition->expandedLayout, ReadDynamicWidgetContext(instance), &instance','frame.layout, frame.context, &instance')
block=block.replace('        popup.Content(shell);','''        popup.Content(shell);
        try {
            auto style = winrt::Windows::UI::Xaml::Markup::XamlReader::Load(LR"XAML(
<Style xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" TargetType="FlyoutPresenter">
 <Setter Property="Padding" Value="0" />
 <Setter Property="BorderThickness" Value="0" />
 <Setter Property="Background" Value="White" />
 <Setter Property="MaxWidth" Value="520" />
 <Setter Property="MaxHeight" Value="640" />
</Style>)XAML").as<wux::Style>();
            popup.FlyoutPresenterStyle(style);
        } catch (...) {
            Wh_Log(L"Native flyout presenter style fallback");
        }''')
s=s[:start]+block+s[end:]
# The button owns a normal click. Capture at the root only after a real drag.
replace_once('''        RefreshTaskbarObstacleCacheForDrag(root.as<wux::UIElement>(), host);
        root.CapturePointer(args.Pointer());''','''        RefreshTaskbarObstacleCacheForDrag(root.as<wux::UIElement>(), host);
        if (!HasNativeExpandedWidget(GetWidgetDesignFromRoot(root.as<wux::UIElement>()))) {
            root.CapturePointer(args.Pointer());
        }''')
replace_once('''        dragState->dragging = true;
        double width = root.ActualWidth()''','''        if (!dragState->dragging) root.CapturePointer(args.Pointer());
        dragState->dragging = true;
        double width = root.ActualWidth()''')
replace_once('''    root.PointerCaptureLost([root, dragState](auto const&, wuxi::PointerRoutedEventArgs const&) {
        if (dragState->pressed) {''','''    root.PointerCaptureLost([root, dragState](auto const&, wuxi::PointerRoutedEventArgs const& args) {
        auto original = args.OriginalSource().try_as<wux::UIElement>();
        if (!original || original != root.as<wux::UIElement>()) return;
        if (dragState->pressed) {''')
p.write_text(s,encoding='utf8')
print('Applied stable taskbar popup snapshot and click capture fix')
