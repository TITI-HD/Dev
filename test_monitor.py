#!/usr/bin/env python3
"""
Tests unitaires pour le module monitor
Version mise à jour pour les fonctions actuelles
"""

import unittest
from unittest.mock import patch, MagicMock
import monitor
import os

class TestNotifications(unittest.TestCase):
    
    def setUp(self):
        """Configuration avant chaque test"""
        os.environ['SITE_URL'] = 'https://httpbin.org/html'
    
    @patch('monitor.send_alert')
    def test_send_alert_on_failure(self, mock_send_alert):
        """Test que send_alert est appelé en cas d'échec"""
        # Simuler un site inaccessible
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("Connection error")
            result = monitor.check_site_availability()
            
            # Vérifier que send_alert a été appelé
            self.assertTrue(mock_send_alert.called)
    
    @patch('monitor.send_alert')
    def test_no_alert_on_success(self, mock_send_alert):
        """Test que send_alert n'est pas appelé en cas de succès"""
        # Simuler un site accessible
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            result = monitor.check_site_availability()
            
            # Vérifier que send_alert n'a pas été appelé
            self.assertFalse(mock_send_alert.called)

class TestContentIntegrity(unittest.TestCase):
    
    def test_hash_computation(self):
        """Test que le hash est calculé correctement"""
        test_content = "Hello World"
        expected_hash = "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"
        
        self.assertEqual(monitor.compute_hash(test_content), expected_hash)

if __name__ == '__main__':
    unittest.main()