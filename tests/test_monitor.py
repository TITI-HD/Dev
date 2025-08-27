# Assurez-vous que :
# 1. La simulation d'échec déclenche bien l'appel à send_alert
# 2. Le mock est correctement configuré
import unittest

@unittest.skip("Ignorer ce test pour le moment")
def test_send_alert_on_failure(self):
    # ... code du test
from unittest.mock import patch
from your_module import monitor  # Adaptez 'your_module' au nom de votre projet

def test_send_alert_on_failure(self):
    with patch('your_module.monitor.send_alert') as mock_send_alert:
        # Simuler un scénario d'échec
        monitor.check_website("http://fake-url.com")
        
        # Vérifier que send_alert a été appelé
        self.assertTrue(mock_send_alert.called)