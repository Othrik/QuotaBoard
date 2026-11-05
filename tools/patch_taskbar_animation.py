"""Animate model switches without callbacks, stacked layers or button remounts."""
from pathlib import Path
import sys
p=Path(sys.argv[1])/'src/native/taskbar-hook/taskbar_widgets_hook.cpp'
s=p.read_text(encoding='utf8')
s=s.replace('#include <winrt/Windows.UI.Xaml.Media.h>', '#include <winrt/Windows.UI.Xaml.Media.h>\n#include <winrt/Windows.UI.Xaml.Media.Animation.h>\n#include <winrt/Windows.UI.ViewManagement.h>')
old='        auto compact = BuildDynamicElement(definition->layout, context, &instance);'
assert s.count(old)==1
s=s.replace(old,'''        static thread_local std::unordered_map<std::wstring, std::wstring> visualVersions;
        static thread_local std::unordered_map<std::wstring, std::wstring> displayedPlatforms;
        static thread_local std::unordered_map<std::wstring, wuxc::Grid> animationStages;
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
s=s.replace(content,'''            bool contentHandled = false;
            auto stageIt = animationStages.find(instance.instanceId);
            if (!hadFrame || stageIt == animationStages.end()) {
                wuxc::Grid stage;
                stage.Children().Append(compact);
                button.Content(stage);
                animationStages.insert_or_assign(instance.instanceId, stage);
                contentHandled = true;
            } else if (platformChanged) {
                try {
                    if (winrt::Windows::UI::ViewManagement::UISettings().AnimationsEnabled()) {
                        using namespace winrt::Windows::UI::Xaml::Media::Animation;
                        auto stage = stageIt->second;
                        wuxm::TranslateTransform incomingTransform;
                        compact.RenderTransform(incomingTransform);
                        if (stage.Children().Size() == 0) stage.Children().Append(compact);
                        else stage.Children().SetAt(0, compact);
                        Storyboard storyboard;
                        const auto duration = wux::DurationHelper::FromTimeSpan(
                            std::chrono::milliseconds(240));
                        DoubleAnimation fadeIn; fadeIn.From(0.0); fadeIn.To(1.0); fadeIn.Duration(duration);
                        Storyboard::SetTarget(fadeIn, compact); Storyboard::SetTargetProperty(fadeIn, L"Opacity");
                        storyboard.Children().Append(fadeIn);
                        DoubleAnimation slideIn; slideIn.From(6.0); slideIn.To(0.0); slideIn.Duration(duration);
                        Storyboard::SetTarget(slideIn, incomingTransform); Storyboard::SetTargetProperty(slideIn, L"Y");
                        storyboard.Children().Append(slideIn);
                        storyboard.Begin();
                        contentHandled = true;
                    }
                } catch (...) {
                    compact.Opacity(1.0);
                }
            }
            if (!contentHandled) {
                auto stage = stageIt->second;
                if (stage.Children().Size() == 0) stage.Children().Append(compact);
                else stage.Children().SetAt(0, compact);
            }''')
p.write_text(s,encoding='utf8')
print('Applied callback-free vertical platform transition and atomic updates')
