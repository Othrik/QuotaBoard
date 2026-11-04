import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from PySide6.QtWidgets import QApplication
from quotaboard.config import Config
from quotaboard.model import PLATFORM_META,QuotaResult
from quotaboard.providers import PROVIDERS
from quotaboard.scheduler import Scheduler
from quotaboard.ui.dashboard import Dashboard
from quotaboard.ui.settings_dialog import SettingsDialog
from quotaboard.taskbar import taskbar_label

app=QApplication([])
config=Config(Path('dist/platform-catalog-test/config.json'))
config._data['platforms']={key:{'enabled':key in ('openai','kimi','volc'),'kept':'test-value'} for key in ('openai','kimi','volc',*PLATFORM_META)}
config._data['platform_order']=['openai','kimi','codex','volc','deepseek']
config._data['cache']={key:dict(platform=key,label='old label',display='¥10') for key in ('openai','deepseek','zhipu')}
config.save=lambda:None
expected={'deepseek':'DeepSeek开放平台','zhipu':'智谱开放平台'}
for key,title in expected.items():
    assert PLATFORM_META[key]['label']==title and PROVIDERS[key].label==title
    assert config.get_cache(key)['label']==title
    from quotaboard.deepseek_period import display_name
    assert taskbar_label(QuotaResult(key,'old label','¥10'))==display_name(title,key)
for key in ('openai','kimi','volc'):
    assert key not in PLATFORM_META and key not in PROVIDERS and key not in config.platform_order
    assert not config.is_enabled(key)
    assert config._data['platforms'][key]['enabled'] and config._data['platforms'][key]['kept']=='test-value'
config.platform_order=list(PLATFORM_META)
assert all(key in config._data['platform_order'] for key in ('openai','kimi','volc'))
scheduler=Scheduler(config);received=[]
scheduler.refreshed.connect(received.append);scheduler.refresh_all()
assert received==[{}] and not scheduler.running, 'paused enabled providers must never start requests'
dashboard=Dashboard(config,scheduler);settings=SettingsDialog(config)
assert len(dashboard.cards)==7 and all(key not in settings.nav_items for key in ('openai','kimi','volc'))
for key,title in expected.items():assert settings.nav_items[key].text()==title
settings._save()
assert config._data['platforms']['kimi']['kept']=='test-value'
assert config._data['platforms']['volc']['kept']=='test-value'
assert all(key not in config.platform_order for key in ('openai','kimi','volc'))
assert config._data['platforms']['openai']['kept']=='test-value'
assert 'codex' in PLATFORM_META and 'codex' in PROVIDERS
print('Canonical names, cached names, taskbar names, paused UI/background queries and retained configuration passed')
