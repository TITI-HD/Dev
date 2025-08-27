import unittest
from unittest.mock import patch
import monitor

class TestNotifications(unittest.TestCase):

    @patch('monitor.send_alert')
    def test_whatsapp_notification_success(self, mock_send_alert):
        """
        Teste que le wrapper send_whatsapp_notification appelle send_alert
        sans avoir besoin de Twilio ni WhatsApp.
        """
        message = "Message d'essai"
        monitor.send_whatsapp_notification(message)
        mock_send_alert.assert_called_once()
        args, kwargs = mock_send_alert.call_args
        self.assertIn("Notification WhatsApp", args[0])  # Sujet
        self.assertIn(message, args[1])  # Contenu

    @patch('monitor.send_alert')
    def test_send_restoration_option(self, mock_send_alert):
        """
        Vérifie que send_restoration_option appelle send_alert
        """
        monitor.send_restoration_option("Test", {"info": "details"})
        mock_send_alert.assert_called_once()
        args, kwargs = mock_send_alert.call_args
        self.assertIn("Test - Action Requise", args[0])
        self.assertIn("details", args[1])

if __name__ == "__main__":
    unittest.main()
