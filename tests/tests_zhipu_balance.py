import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from quotaboard.providers.zhipu_provider import ZhipuProvider,BALANCE_URL,BALANCE_FALLBACK_URL

def report(**fields):
    return dict(code=200,success=True,data=fields)

class Balance(unittest.TestCase):
    def query(self, payload):
        with patch('quotaboard.providers.zhipu_provider.http_get_json',return_value=payload):
            return ZhipuProvider({'api_key':'test-key'}).fetch()

    def test_available_balance_and_details_without_quota_percentage(self):
        result=self.query(report(availableBalance='8.663060440',balance='9.2',
                                 rechargeAmount='10',totalSpendAmount='1.336939560',frozenBalance='0'))
        self.assertTrue(result.ok)
        self.assertEqual(result.display,'¥8.6631')
        self.assertAlmostEqual(result.available,8.663060440)
        self.assertIsNone(result.percent)
        self.assertIsNone(result.total)
        self.assertIn('累计充值 ¥10.00',result.sub_note)

    def test_zero_and_negative_are_real_balances(self):
        self.assertEqual(self.query(report(availableBalance=0,balance=20)).display,'¥0.00')
        self.assertEqual(self.query(report(availableBalance='-0.1234')).display,'¥-0.1234')

    def test_null_balance_fallback_and_missing_data(self):
        self.assertEqual(self.query(report(availableBalance=None,balance='12.34')).display,'¥12.34')
        for fields in ({},{'availableBalance':'NaN'},{'availableBalance':True},{'availableBalance':'Infinity'}):
            self.assertFalse(self.query(report(**fields)).ok)

    def test_application_failures_do_not_appear_as_zero(self):
        self.assertFalse(self.query(dict(code=401,success=False,data={})).ok)
        self.assertFalse(self.query(dict(code=200,success=False,data={'balance':100})).ok)
        self.assertFalse(self.query({'unexpected':'shape'}).ok)

    def test_official_host_fallback_and_auth_header(self):
        with patch('quotaboard.providers.zhipu_provider.http_get_json',side_effect=[
                HTTPError(BALANCE_URL,403,'blocked',None,None),report(availableBalance=1)]) as get:
            result=ZhipuProvider({'api_key':'test-key'}).fetch()
        self.assertTrue(result.ok)
        self.assertEqual([call.args[0] for call in get.call_args_list],[BALANCE_URL,BALANCE_FALLBACK_URL])
        self.assertEqual(get.call_args.args[1],{'Authorization':'Bearer test-key'})

    def test_invalid_key_rate_limit_and_connection_failures(self):
        for status in (401,429):
            with patch('quotaboard.providers.zhipu_provider.http_get_json',side_effect=HTTPError(BALANCE_URL,status,'x',None,None)) as get:
                self.assertFalse(ZhipuProvider({'api_key':'test-key'}).fetch().ok)
                self.assertEqual(get.call_count,1)
        with patch('quotaboard.providers.zhipu_provider.http_get_json',side_effect=URLError('secret=test-key')):
            result=ZhipuProvider({'api_key':'test-key'}).fetch()
            self.assertFalse(result.ok);self.assertNotIn('test-key',result.error)

if __name__=='__main__':unittest.main()
