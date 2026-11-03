"""Patch pinned Taskbar Widgets native image loading; keep upstream MIT license."""
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/'src/native/taskbar-hook/taskbar_widgets_hook.cpp'
s=p.read_text(encoding='utf-8-sig')
s=s.replace('#include <windowsx.h>','#include <windowsx.h>\n#include <shcore.h>')
s=s.replace('#include <winrt/Windows.Storage.h>','#include <winrt/Windows.Storage.h>\n#include <winrt/Windows.Storage.Streams.h>')
a='''                wuxmi::BitmapImage bitmap;
                bitmap.UriSource(wf::Uri(ToFileUri(source)));
                wuxc::Image image;'''
b='''                // Explorer's XAML image URI loader can silently reject local
                // file URIs. Open the same local file directly and decode it.
                static thread_local std::unordered_map<std::wstring, wuxmi::BitmapImage> imageCache;
                auto cached = imageCache.find(source);
                if (cached == imageCache.end()) {
                    winrt::Windows::Storage::Streams::IRandomAccessStream stream{nullptr};
                    winrt::check_hresult(CreateRandomAccessStreamOnFile(
                        source.c_str(), 0,
                        winrt::guid_of<winrt::Windows::Storage::Streams::IRandomAccessStream>(),
                        winrt::put_abi(stream)));
                    wuxmi::BitmapImage decoded;
                    decoded.SetSource(stream);
                    cached = imageCache.emplace(source, decoded).first;
                    Wh_Log(L"Native widget image decoded from file stream");
                }
                auto bitmap = cached->second;
                wuxc::Image image;'''
assert s.count(a)==1, 'Pinned upstream image block changed'
s=s.replace(a,b)
a='''                frame.Child(image);
            } catch (...) {
            }
        }
        return frame;'''
b='''                frame.Child(image);
            } catch (winrt::hresult_error const& error) {
                Wh_Log(L"Native widget image stream decode failed: 0x%08X", static_cast<unsigned>(error.code().value));
            } catch (...) {
                Wh_Log(L"Native widget image stream decode failed: unknown error");
            }
        }
        return frame;'''
assert s.count(a)==1
p.write_text(s.replace(a,b),encoding='utf8')
p=root/'src/native/CMakeLists.txt';s=p.read_text(encoding='utf8');a='ole32 oleaut32 runtimeobject gdi32 gdiplus uiautomationcore)';assert s.count(a)==1;p.write_text(s.replace(a,'ole32 oleaut32 runtimeobject gdi32 gdiplus uiautomationcore shcore)'),encoding='utf8')
print('Applied local image stream decoding patch')
