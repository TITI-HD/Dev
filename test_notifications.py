<<<<<<< HEAD
=======
# test_notifications.py
>>>>>>> f187b1211e2b27bf3d01b368312f0f2bba2b0874
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
        
<<<<<<< HEAD
=======
        # Configurer les variables d'environnement pour le test
>>>>>>> f187b1211e2b27bf3d01b368312f0f2bba2b0874
        with patch.dict('os.environ', {
            'TWILIO_ACCOUNT_SID': 'test_sid',
            'TWILIO_AUTH_TOKEN': 'test_token',
            'TWILIO_WHATSAPP_FROM': 'test_from',
            'TWILIO_WHATSAPP_TO': 'test_to'
        }):
            result = monitor.send_whatsapp_notification("Test message")
            self.assertTrue(result)
    
    @patch('monitor.smtplib.SMTP')
    def test_email_alert(self, mock_smtp):
        """Test d'envoi d'alerte email"""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
<<<<<<< HEAD
        with patch.dict('os.environ', {
            'SMTP_SERVER': 'smtp.gmail.com',
=======
        # Configurer les variables d'environnement pour le test
        with patch.dict('os.environ', {
            'SMTP_SERVER': 'smtp.test.com',
>>>>>>> f187b1211e2b27bf3d01b368312f0f2bba2b0874
            'SMTP_PORT': '587',
            'SMTP_USER': 'test@test.com',
            'SMTP_PASS': 'testpass',
            'ALERT_EMAIL': 'alert@test.com'
        }):
            monitor.send_alert("Test Subject", "Test Message")
<<<<<<< HEAD
            mock_smtp.assert_called_once_with('smtp.gmail.com', 587)
=======
            mock_smtp.assert_called_once_with('smtp.test.com', 587)
>>>>>>> f187b1211e2b27bf3d01b368312f0f2bba2b0874

if __name__ == '__main__':
    unittest.main()