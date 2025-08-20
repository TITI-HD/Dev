# test_monitor.py
import unittest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.append('.')

import monitor
import requests
url = "https://oupssecuretest.wordpress.com/wp-json/wp/v2/posts"
response = requests.get(url)
class TestMonitor(unittest.TestCase):
    
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

from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class MyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            # Envoyer le code HTML complet ici
            with open('wordpress_auth_tool.html', 'r', encoding='utf-8') as f:
                html_content = f.read()
            self.wfile.write(html_content.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def run_web_interface():
    server = HTTPServer(('localhost', 8000), MyHandler)
    print("Serveur démarré sur http://localhost:8000")
    server.serve_forever()

if __name__ == '__main__':
    run_web_interface()


from flask import Flask, render_template_string

app = Flask(__name__)

# Charger le contenu HTML depuis un fichier
with open('wordpress_auth_tool.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

@app.route('/wordpress-auth')
def wordpress_auth_tool():
    return render_template_string(html_content)

if __name__ == '__main__':
    app.run(port=8000)

if __name__ == '__main__':
    unittest.main()