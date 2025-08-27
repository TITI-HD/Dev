from flask import Flask, render_template, request, jsonify
import requests
from requests.auth import HTTPBasicAuth
import os

app = Flask(__name__)

# Désactiver le mode debug en production
if os.environ.get('FLASK_ENV') == 'production':
    app.config['DEBUG'] = False
else:
    app.config['DEBUG'] = True

# Page principale avec l'interface d'authentification
@app.route('/')
def wordpress_auth_tool():
    return render_template('wordpress_auth_tool.html')

# API endpoint pour tester la connexion WordPress
@app.route('/test-wordpress-auth', methods=['POST'])
def test_wordpress_auth():
    data = request.json
    site_url = data.get('siteUrl')
    username = data.get('username')
    app_password = data.get('appPassword')
    endpoint = data.get('endpoint', '/wp-json/wp/v2/posts')
    
    if not site_url or not username or not app_password:
        return jsonify({'error': 'Paramètres manquants'}), 400
    
    try:
        # Construire l'URL complète
        api_url = site_url + endpoint
        
        # Effectuer la requête avec l'authentification basic
        response = requests.get(
            api_url, 
            auth=HTTPBasicAuth(username, app_password),
            timeout=10
        )
        
        if response.status_code == 200:
            return jsonify({
                'success': True,
                'data': response.json(),
                'message': 'Connexion réussie!'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Erreur HTTP: {response.status_code} - {response.reason}'
            })
            
    except requests.exceptions.RequestException as e:
        return jsonify({
            'success': False,
            'message': f'Erreur de connexion: {str(e)}'
        })

if __name__ == '__main__':
    # Utiliser le port depuis les variables d'environnement ou 5000 par défaut
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    app.run(debug=False, port=5000)