# test_notifications.py
import unittest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.append('.')

import monitor

class TestNotifications(unittest.TestCase):
    
    @patch('monitor.Client')
    def test_whatsapp_notification_success(self, mock_twilio):
        """Test d'envoi de notification WhatsApp réussi"""
        mock_instance = MagicMock()
        mock_twilio.return_value = mock_instance
        
        # Configurer les variables d'environnement pour le test
        with patch.dict('os.environ', {
            'TWILIO_ACCOUNT_SID': 'test_sid',
            'TWILIO_AUTH_TOKEN': 'test_token',
            'TWILIO_PHONE_NUMBER': 'whatsapp:+1234567890',
            'ALERT_PHONE_NUMBER': 'whatsapp:+0987654321'
        }):
            result = monitor.send_whatsapp_notification("Test message")
            self.assertTrue(result)
    
    @patch('monitor.smtplib.SMTP')
    def test_email_alert(self, mock_smtp):
        """Test d'envoi d'alerte email"""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        # Configurer les variables d'environnement pour le test
        with patch.dict('os.environ', {
            'SMTP_SERVER': 'smtp.gmail.com',
            'SMTP_PORT': '587',
            'SMTP_USER': 'test@test.com',
            'SMTP_PASS': 'testpass',
            'ALERT_EMAIL': 'alert@test.com'
        }):
            monitor.send_alert("Test Subject", "Test Message")
            mock_smtp.assert_called_once_with('smtp.gmail.com', 587)

import unittest
from unittest.mock import Mock, patch
import os
import sys
from monitor import send_whatsapp_notification
# Ajouter le répertoire parent au path pour importer monitor
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import monitor

class TestNotifications(unittest.TestCase):
    
    @patch('monitor.Client')
    def test_whatsapp_notification_success(self, mock_twilio):
        # Configurer le mock
        mock_client = Mock()
        mock_twilio.return_value = mock_client

        # Définir les variables d'environnement pour Twilio
        os.environ['TWILIO_SID'] = 'test_sid'
        os.environ['TWILIO_AUTH'] = 'test_auth'
        os.environ['TWILIO_FROM'] = 'whatsapp:+14155238886'
        os.environ['TWILIO_TO'] = 'whatsapp:+1234567890'

        # Recharger le module pour prendre en compte les nouvelles variables d'environnement
        import importlib
        importlib.reload(monitor)

        # Exécuter la fonction
        result = monitor.send_whatsapp_notification("Test message")

        # Vérifier que le client Twilio a été initialisé avec les bonnes credentials
        mock_twilio.assert_called_once_with('test_sid', 'test_auth')

        # Vérifier que le message a été envoyé
        mock_client.messages.create.assert_called_once_with(
            from_='whatsapp:+14155238886',
            to='whatsapp:+1234567890',
            body="Test message"
        )

        # Vérifier que la fonction retourne True
        self.assertTrue(result)

    # ... autres tests ...

if __name__ == '__main__':
    unittest.main()