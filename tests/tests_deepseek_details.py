import unittest
from unittest.mock import patch
from urllib.error import URLError
from quotaboard.providers.deepseek_provider import DeepSeekProvider
from quotaboard.ui.floating_window import _dock_quota_text,_quota_details
from quotaboard.taskbar import rotation_candidates

def payload(available=True,**values):
    return {'is_available':available,'balance_infos':[{'currency':'CNY',**values}]}

class Details(unittest.TestCase):
    def parse(self,data):return DeepSeekProvider({})._parse(data)

    def test_paid_granted_and_status_are_distinct_from_lifetime_spend(self):
        result=self.parse(payload(total_balance='18.24015',topped_up_balance='17',granted_balance='1.24015'))
        self.assertTrue(result.ok)
        self.assertEqual(result.display,'¥18.2402')
        self.assertEqual(result.details[0],{'label':'充值余额 · CNY','value':'¥17.0000'})
        self.assertEqual(result.details[1],{'label':'赠送余额 · CNY','value':'¥1.2402'})
        self.assertTrue(result.account_available)
        self.assertIsNone(result.used);self.assertIsNone(result.total);self.assertIsNone(result.percent)

    def test_multiple_currencies_never_get_added(self):
        result=self.parse({'balance_infos':[
            {'currency':'CNY','total_balance':'12.34','granted_balance':'0'},
            {'currency':'USD','total_balance':'-1.58','topped_up_balance':'-1.58'}]})
        self.assertEqual(result.display,'¥12.3400 · -$1.5800')
        self.assertIsNone(result.available);self.assertEqual(result.unit,'')
        self.assertEqual(result.details[0]['label'],'赠送余额 · CNY')
        self.assertEqual(result.details[1]['label'],'充值余额 · USD')

    def test_unavailable_is_successful_query_with_attention_not_hidden_failure(self):
        result=self.parse(payload(False,total_balance='0',topped_up_balance='0',granted_balance='0'))
        self.assertTrue(result.ok);self.assertFalse(result.account_available)
        self.assertEqual(result.status_level(),'danger')
        self.assertEqual(rotation_candidates([result]),[result])
        self.assertIn('#E45D6A',_dock_quota_text(result))
        self.assertIn('充值余额',_quota_details(result))

    def test_missing_components_not_fabricated(self):
        result=self.parse(payload(total_balance='10'))
        self.assertTrue(result.ok)
        self.assertEqual(len(result.details),1)
        self.assertNotIn('充值余额',str(result.details))
        self.assertNotIn('赠送余额',str(result.details))

    def test_invalid_and_non_finite_values(self):
        for value in (None,'bad','NaN','Infinity',True):
            self.assertFalse(self.parse(payload(total_balance=value)).ok)
        self.assertFalse(self.parse({'balance_infos':['invalid']}).ok)
        self.assertFalse(self.parse({}).ok)
        self.assertFalse(self.parse(payload(currency='',total_balance='10')).ok)

    def test_one_public_get_only_and_errors_never_echo_key(self):
        with patch('quotaboard.providers.deepseek_provider.http_get_json',return_value=payload(total_balance='5')) as get:
            result=DeepSeekProvider({'api_key':'test-key'}).fetch()
        self.assertTrue(result.ok);self.assertEqual(get.call_count,1)
        self.assertEqual(get.call_args.args[0],'https://api.deepseek.com/user/balance')
        with patch('quotaboard.providers.deepseek_provider.http_get_json',side_effect=URLError('test-key')):
            self.assertNotIn('test-key',DeepSeekProvider({'api_key':'test-key'}).fetch().error)

if __name__=='__main__':unittest.main()
