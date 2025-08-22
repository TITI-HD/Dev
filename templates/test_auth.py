# test_auth.py
import unittest
import json
from app import app

class TestWordpressAuth(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_auth_endpoint_with_invalid_credentials(self):
        response = self.app.post('/test-wordpress-auth', 
            data=json.dumps({
                'siteUrl': 'https://example.com',
                'username': 'wronguser',
                'appPassword': 'wrongpass',
                'endpoint': '/wp-json/wp/v2/posts'
            }),
            content_type='application/json'
        )
        
        data = json.loads(response.get_data())
        self.assertEqual(response.status_code, 200)
        self.assertIn('success', data)
        self.assertFalse(data['success'])

if __name__ == '__main__':
    unittest.main()