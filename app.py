from flask import Flask, render_template, request, jsonify
import requests
from requests.auth import HTTPBasicAuth
import base64

app = Flask(__name__)

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

# Vos routes existantes pour le monitoring
@app.route('/monitor')
def monitor():
    # Votre logique de monitoring existante
    return "Page de monitoring"

if __name__ == '__main__':
    app.run(debug=True, port=5000)