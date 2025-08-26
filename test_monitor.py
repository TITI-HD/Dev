# test_monitor.py
import unittest
from unittest.mock import patch, MagicMock
import monitor

class TestMonitor(unittest.TestCase):
    def test_site_ok(self):
        """Test que main() retourne True si le site et l'API sont OK"""
        with patch('monitor.check_site', return_value=True), \
             patch('monitor.check_api', return_value=True), \
             patch('monitor.backup_and_monitor', return_value=None):
            result = monitor.main()
            self.assertTrue(result)

    @patch('monitor.requests.get')
    def test_check_site_success(self, mock_get):
        """Test de vérification de site avec succès"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = monitor.check_site("https://example.com")
        self.assertTrue(result)
    
    @patch('monitor.requests.get')
    def test_check_site_failure(self, mock_get):
        """Test de vérification de site en échec"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = monitor.check_site("https://example.com")
        self.assertFalse(result)
    
    @patch('monitor.send_alert')
    @patch('monitor.requests.get')
    def test_check_site_exception(self, mock_get, mock_alert):
        """Test de vérification de site avec exception"""
        mock_get.side_effect = Exception("Connection error")
        
        result = monitor.check_site("https://example.com")
        self.assertFalse(result)
        mock_alert.assert_called_once()

if __name__ == '__main__':
    unittest.main()
