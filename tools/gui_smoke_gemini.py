"""Gemini uses the common two-ring row and colored dock metrics."""
import os, sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication,QLabel
from quotaboard.providers.gemini_provider import GeminiProvider
from quotaboard.ui.floating_window import _Row,_Donut
app=QApplication([])
p=GeminiProvider({})
p._get_cookies=lambda:{}
p._query=lambda _: [2,[[None,.02,1,[[1793629740,0]]],[None,0,2,[[1793687340,0]]]],False]
r=p.fetch()
assert r.ok and [m['label'] for m in r.metrics]==['5h','周']
assert [m['percent'] for m in r.metrics]==[98,100]
row=_Row(r)
assert len(row.findChildren(_Donut))==2
assert not any('PRO' in label.text() for label in row.findChildren(QLabel))
print('Gemini common row passed')
