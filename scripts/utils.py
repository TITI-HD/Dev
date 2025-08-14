import configparser
import logging
import os
import sys
import pytest
from scripts.utils import load_config

def load_config(path="/opt/wordpress-scripts/config.ini"):
    """
    Charge la configuration depuis un fichier INI.
    Retourne un dict imbriqué.
    """
    config = configparser.ConfigParser()
    if not os.path.exists(path):
        logging.error(f"Fichier config manquant : {path}")
        sys.exit(1)
    config.read(path)
    conf_dict = {section: dict(config.items(section)) for section in config.sections()}
    return conf_dict

def log(message, level="info"):
    """
    Log simple vers stdout avec timestamp.
    """
    levels = {
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR
    }
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s',
        level=levels.get(level, logging.INFO)
    )
    logger = logging.getLogger()
    getattr(logger, level)(message)

def send_alert(message):
    """
    Envoi d’une alerte (exemple Slack ou email)
    TODO : implémenter webhook Slack ou autre.
    """
    print(f"ALERTE: {message}")
    # Exemple : requests.post(slack_webhook_url, json={"text": message})

def test_load_config():
    config = load_config("config/production.ini")
    assert "wordpress" in config
