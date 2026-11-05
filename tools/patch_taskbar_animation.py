"""Cross-fade platform rotations; keep same-platform data updates motionless."""
from pathlib import Path
import sys
p=Path(sys.argv[1])/'src/native/taskbar-hook/taskbar_widgets_hook.cpp'
s=p.read_text(encoding='utf8')
s=s.replace('#include <winrt/Windows.UI.Xaml.Media.h>', '#include <winrt/Windows.UI.Xaml.Media.h>\n#include <winrt/Windows.UI.Xaml.Media.Animation.h>\n#include <winrt/Windows.UI.ViewManagement.h>')
old='        auto compact = BuildDynamicElement(definition->layout, context, &instance);'
assert s.count(old)==1
s=s.replace(old,'''        static thread_local std::unordered_map<std::wstring, std::wstring> visualVersions;
        static thread_local std::unordered_map<std::wstring, std::wstring> displayedPlatforms;
        auto data = context.GetNamedObject(L"data");
        const auto visual = JsonString(data, L"visualVersion", L"");
        const auto platform = JsonString(data, L"platform", L"");
        const bool hadFrame = panel.Child() != nullptr;
        if (!visual.empty() && hadFrame && visualVersions[instance.instanceId] == visual) {
            g_quotaDisplayedFrames[instance.instanceId] = QuotaDisplayedFrame{
                context, definition->expandedLayout, definition->expandedWidth, definition->expandedHeight};
            return;
        }
        const bool platformChanged = hadFrame && !platform.empty() &&
            displayedPlatforms.count(instance.instanceId) &&
            displayedPlatforms[instance.instanceId] != platform;
        visualVersions[instance.instanceId] = visual;
        displayedPlatforms[instance.instanceId] = platform;
        auto compact = BuildDynamicElement(definition->layout, context, &instance);
''')
content='            button.Content(compact);'
assert s.count(content)==1
s=s.replace(content,'''            bool transitionApplied = false;
            auto outgoingObject = button.Content();
            auto outgoing = outgoingObject ? outgoingObject.try_as<wux::UIElement>() : nullptr;
            if (platformChanged && outgoing) {
                try {
                    if (winrt::Windows::UI::ViewManagement::UISettings().AnimationsEnabled()) {
                        using namespace winrt::Windows::UI::Xaml::Media::Animation;
                        button.Content(nullptr);
                        wuxc::Grid stage;
                        compact.Opacity(0.0);
                        wuxm::TranslateTransform incomingTransform;
                        incomingTransform.X(5.0);
                        compact.RenderTransform(incomingTransform);
                        wuxm::TranslateTransform outgoingTransform;
                        outgoing.RenderTransform(outgoingTransform);
                        stage.Children().Append(outgoing);
                        stage.Children().Append(compact);
                        button.Content(stage);
                        Storyboard storyboard;
                        const auto duration = wux::DurationHelper::FromTimeSpan(
                            std::chrono::milliseconds(240));
                        DoubleAnimation fadeOut; fadeOut.From(1.0); fadeOut.To(0.0); fadeOut.Duration(duration);
                        Storyboard::SetTarget(fadeOut, outgoing); Storyboard::SetTargetProperty(fadeOut, L"Opacity");
                        storyboard.Children().Append(fadeOut);
                        DoubleAnimation slideOut; slideOut.From(0.0); slideOut.To(-5.0); slideOut.Duration(duration);
                        Storyboard::SetTarget(slideOut, outgoingTransform); Storyboard::SetTargetProperty(slideOut, L"X");
                        storyboard.Children().Append(slideOut);
                        DoubleAnimation fadeIn; fadeIn.From(0.0); fadeIn.To(1.0); fadeIn.Duration(duration);
                        Storyboard::SetTarget(fadeIn, compact); Storyboard::SetTargetProperty(fadeIn, L"Opacity");
                        storyboard.Children().Append(fadeIn);
                        DoubleAnimation slideIn; slideIn.From(5.0); slideIn.To(0.0); slideIn.Duration(duration);
                        Storyboard::SetTarget(slideIn, incomingTransform); Storyboard::SetTargetProperty(slideIn, L"X");
                        storyboard.Children().Append(slideIn);
                        auto weakButton = winrt::make_weak(button);
                        storyboard.Completed([weakButton, compact](auto const&, auto const&) {
                            if (auto current = weakButton.get()) {
                                compact.Opacity(1.0);
                                current.Content(compact);
                            }
                        });
                        storyboard.Begin();
                        transitionApplied = true;
                    }
                } catch (...) {
                    compact.Opacity(1.0);
                }
            }
            if (!transitionApplied) button.Content(compact);''')
p.write_text(s,encoding='utf8')
print('Applied platform cross-fade and motionless same-platform updates')
