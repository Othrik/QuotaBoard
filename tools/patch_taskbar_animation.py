"""Animate real quota changes; retain the native tree on detail-only refreshes."""
from pathlib import Path
import sys
p=Path(sys.argv[1])/'src/native/taskbar-hook/taskbar_widgets_hook.cpp'
s=p.read_text(encoding='utf8')
s=s.replace('#include <winrt/Windows.UI.Xaml.Media.h>', '#include <winrt/Windows.UI.Xaml.Media.h>\n#include <winrt/Windows.UI.Xaml.Media.Animation.h>\n#include <winrt/Windows.UI.ViewManagement.h>')
old='        auto compact = BuildDynamicElement(definition->layout, context, &instance);'
assert s.count(old)==1
s=s.replace(old,'''        static thread_local std::unordered_map<std::wstring, std::wstring> visualVersions;
        static thread_local std::unordered_map<std::wstring, std::wstring> changeTokens;
        auto data = context.GetNamedObject(L"data");
        const auto visual = JsonString(data, L"visualVersion", L"");
        const auto token = JsonString(data, L"changeToken", L"0");
        const bool hadFrame = panel.Child() != nullptr;
        if (!visual.empty() && hadFrame && visualVersions[instance.instanceId] == visual) {
            g_quotaDisplayedFrames[instance.instanceId] = QuotaDisplayedFrame{
                context, definition->expandedLayout, definition->expandedWidth, definition->expandedHeight};
            return;
        }
        const bool animate = hadFrame && token != L"0" &&
            changeTokens.count(instance.instanceId) && changeTokens[instance.instanceId] != token;
        visualVersions[instance.instanceId] = visual;
        changeTokens[instance.instanceId] = token;
        auto compact = BuildDynamicElement(definition->layout, context, &instance);
        // Let XAML own this short, finite animation; no polling, extra windows
        // or persistent highlights. Respect Windows' animation accessibility setting.
        if (animate) {
            try {
                if (winrt::Windows::UI::ViewManagement::UISettings().AnimationsEnabled()) {
                    using namespace winrt::Windows::UI::Xaml::Media::Animation;
                    Storyboard storyboard;
                    DoubleAnimation fade;
                    fade.From(0.45); fade.To(1.0);
                    fade.Duration(wux::DurationHelper::FromTimeSpan(std::chrono::milliseconds(550)));
                    Storyboard::SetTarget(fade, compact);
                    Storyboard::SetTargetProperty(fade, L"Opacity");
                    storyboard.Children().Append(fade);
                    wuxm::TranslateTransform transform;
                    compact.RenderTransform(transform);
                    DoubleAnimation rise;
                    rise.From(3.0); rise.To(0.0);
                    rise.Duration(wux::DurationHelper::FromTimeSpan(std::chrono::milliseconds(550)));
                    Storyboard::SetTarget(rise, transform);
                    Storyboard::SetTargetProperty(rise, L"Y");
                    storyboard.Children().Append(rise);
                    compact.as<wux::FrameworkElement>().Loaded([storyboard](auto const& sender, auto const&) {
                        try { storyboard.Begin(); }
                        catch (...) { sender.template as<wux::UIElement>().Opacity(1.0); }
                    });
                }
            } catch (...) { compact.Opacity(1.0); }
        }''')
p.write_text(s,encoding='utf8')
print('Applied quota change animation and stable single-platform rendering')
