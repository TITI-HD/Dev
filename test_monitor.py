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

if __name__ == '__main__':
    unittest.main()