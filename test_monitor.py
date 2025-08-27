# test_notifications.py
import unittest
from unittest.mock import patch, MagicMock, Mock
import sys
import os
import importlib

# Ajouter le répertoire parent au path pour importer monitor.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import monitor


class TestNotifications(unittest.TestCase):
    
    @patch('monitor.Client')
    def test_whatsapp_notification_success(self, mock_twilio):
        """Test d'envoi de notification WhatsApp réussi"""
        # Configurer le mock Twilio
        mock_client = Mock()
        mock_twilio.return_value = mock_client

        # Définir les variables d'environnement pour Twilio
        with patch.dict('os.environ', {
            'TWILIO_ACCOUNT_SID': 'test_sid',
            'TWILIO_AUTH_TOKEN': 'test_token',
            'TWILIO_PHONE_NUMBER': 'whatsapp:+14155238886',
            'ALERT_PHONE_NUMBER': 'whatsapp:+1234567890'
        }):
            importlib.reload(monitor)  # Recharger avec les nouvelles variables
            result = monitor.send_whatsapp_notification("Test message")

        # Vérifier que le client Twilio a bien été initialisé
        mock_twilio.assert_called_once_with('test_sid', 'test_token')

        # Vérifier que le message a été envoyé
        mock_client.messages.create.assert_called_once_with(
            from_='whatsapp:+14155238886',
            to='whatsapp:+1234567890',
            body="Test message"
        )

        # Vérifier que la fonction retourne True
        self.assertTrue(result)
    

    @patch('monitor.smtplib.SMTP')
    def test_email_alert(self, mock_smtp):
        """Test d'envoi d'alerte email"""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # Configurer les variables d'environnement pour l'email
        with patch.dict('os.environ', {
            'SMTP_SERVER': 'smtp.gmail.com',
            'SMTP_PORT': '587',
            'SMTP_USER': 'test@test.com',
            'SMTP_PASS': 'testpass',
            'ALERT_EMAIL': 'alert@test.com'
        }):
            importlib.reload(monitor)  # Recharger avec les nouvelles variables
            monitor.send_alert("Test Subject", "Test Message")

        # Vérifier que la connexion SMTP a bien été ouverte
        mock_smtp.assert_called_once_with('smtp.gmail.com', 587)


if __name__ == '__main__':
    unittest.main()
