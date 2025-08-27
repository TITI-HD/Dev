#!/usr/bin/env python3
"""
Tests unitaires pour le module monitor
Version corrigée pour les mocks
"""

import unittest
from unittest.mock import patch, MagicMock
import monitor
import os

class TestNotifications(unittest.TestCase):
    
    def setUp(self):
        """Configuration avant chaque test"""
        # Sauvegarder la valeur originale de SITE_URL
        self.original_site_url = monitor.SITE_URL
        monitor.SITE_URL = "https://test.example.com"
    
    def tearDown(self):
        """Nettoyage après chaque test"""
        # Restaurer la valeur originale
        monitor.SITE_URL = self.original_site_url
    
    @patch('monitor.requests.get')
    @patch('monitor.send_alert')
    def test_send_alert_on_failure(self, mock_send_alert, mock_get):
        """Test que send_alert est appelé en cas d'échec"""
        # Simuler une exception de connexion
        mock_get.side_effect = Exception("Connection error")
        
        # Appeler la fonction
        result = monitor.check_site_availability()
        
        # Vérifier que send_alert a été appelé
        self.assertTrue(mock_send_alert.called)
        self.assertFalse(result['available'])
    
    @patch('monitor.requests.get')
    @patch('monitor.send_alert')
    def test_no_alert_on_success(self, mock_send_alert, mock_get):
        """Test que send_alert n'est pas appelé en cas de succès"""
        # Simuler une réponse réussie
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Appeler la fonction
        result = monitor.check_site_availability()
        
        # Vérifier que send_alert n'a pas été appelé
        self.assertFalse(mock_send_alert.called)
        self.assertTrue(result['available'])

class TestContentIntegrity(unittest.TestCase):
    
    def test_hash_computation(self):
        """Test que le hash est calculé correctement"""
        test_content = "Hello World"
        expected_hash = "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"
        
        self.assertEqual(monitor.compute_hash(test_content), expected_hash)

class TestMainMonitoring(unittest.TestCase):
    
    @patch('monitor.check_site_availability')
    @patch('monitor.check_content_integrity')
    @patch('monitor.check_for_malicious_patterns')
    @patch('monitor.send_alert')
    def test_main_monitoring_with_issues(self, mock_send_alert, mock_security, mock_integrity, mock_availability):
        """Test de la fonction principale avec des problèmes détectés"""
        # Configurer les mocks pour simuler des problèmes
        mock_availability.return_value = {
            'available': False,
            'status_code': 404,
            'response_time': None,
            'error': 'Site not found'
        }
        
        mock_integrity.return_value = {
            'changed': True,
            'changes': [{'endpoint': 'homepage', 'url': 'https://example.com', 'change_type': 'content_modified'}],
            'error': None
        }
        
        mock_security.return_value = {
            'suspicious_patterns': [{'pattern': 'eval', 'found': True}],
            'error': None
        }
        
        # Exécuter la fonction principale
        monitor.main_monitoring()
        
        # Vérifier que send_alert a été appelé
        self.assertTrue(mock_send_alert.called)
    
    @patch('monitor.check_site_availability')
    @patch('monitor.check_content_integrity')
    @patch('monitor.check_for_malicious_patterns')
    @patch('monitor.send_alert')
    def test_main_monitoring_no_issues(self, mock_send_alert, mock_security, mock_integrity, mock_availability):
        """Test de la fonction principale sans problèmes"""
        # Configurer les mocks pour simuler un fonctionnement normal
        mock_availability.return_value = {
            'available': True,
            'status_code': 200,
            'response_time': 1.5,
            'error': None
        }
        
        mock_integrity.return_value = {
            'changed': False,
            'changes': [],
            'error': None
        }
        
        mock_security.return_value = {
            'suspicious_patterns': [],
            'error': None
        }
        
        # Exécuter la fonction principale
        monitor.main_monitoring()
        
        # Vérifier que send_alert a été appelé pour le rapport d'inaction
        self.assertTrue(mock_send_alert.called)

if __name__ == '__main__':
    unittest.main()