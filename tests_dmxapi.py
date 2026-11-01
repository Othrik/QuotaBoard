"""DMXAPI documented balance conversion and failure paths; no real credentials."""
import unittest
from unittest.mock import patch
from quotaboard.providers.dmxapi_provider import DMXAPIProvider
class DMXAPITest(unittest.TestCase):
 def test_balance(self):
  for quota,expected in [(500000,'¥1.0000'),(0,'¥0.0000'),(-500000,'¥-1.0000'),(1,'¥0.0000')]:
   with patch('quotaboard.providers.dmxapi_provider.http_get_json',return_value={'success':True,'data':{'quota':quota}}) as get:
    r=DMXAPIProvider({'system_token':'test-only','user_id':'123'}).fetch()
    self.assertTrue(r.ok);self.assertEqual(r.display,expected);self.assertIsNone(r.percent)
    self.assertEqual(get.call_args.args[1]['Dmx-Api-User'],'123')
 def test_invalid(self):
  self.assertFalse(DMXAPIProvider({}).fetch().ok)
  for data in [{'success':False},{'success':True,'data':{}},{'success':True,'data':{'quota':'NaN'}}]:
   with patch('quotaboard.providers.dmxapi_provider.http_get_json',return_value=data):
    self.assertFalse(DMXAPIProvider({'system_token':'test','user_id':'123'}).fetch().ok)
if __name__=='__main__': unittest.main()
