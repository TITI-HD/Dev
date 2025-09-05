#!/usr/bin/env python3
"""
Générateur de rapports pour la surveillance WordPress
Consolide les logs, incidents et rapports en un document unique
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

# Dossiers de surveillance et rapports
MONITOR_DIR = Path("monitor_data")
REPORTS_DIR = MONITOR_DIR / "reports"
MONITOR_DIR.mkdir(exist_ok=True, parents=True)
REPORTS_DIR.mkdir(exist_ok=True, parents=True)

# === Logging ===
def log(message: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {message}"
    print(line)
    log_file = MONITOR_DIR / "report_generator.log"
    with log_file.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def clean_log_file():
    """Nettoie le fichier de log corrompu"""
    log_file = MONITOR_DIR / "monitor.log"
    if not log_file.exists():
        return
        
    backup_file = MONITOR_DIR / "monitor.log.backup"
    
    # Faire une copie de sauvegarde
    if backup_file.exists():
        backup_file.unlink()
    log_file.rename(backup_file)
    
    # Lire et réécrire proprement
    try:
        with backup_file.open('rb') as f:
            content = f.read()
        
        # Essayer de décoder avec différents encodages
        for encoding in ['latin-1', 'cp1252', 'iso-8859-1', 'utf-8']:
            try:
                decoded_content = content.decode(encoding, errors='replace')
                # Réécrire en UTF-8
                with log_file.open('w', encoding='utf-8') as f:
                    f.write(decoded_content)
                log(f"Fichier log converti de {encoding} vers UTF-8")
                return True
            except UnicodeDecodeError:
                continue
                
        # Si aucun encodage ne fonctionne, écrire un message d'erreur
        with log_file.open('w', encoding='utf-8') as f:
            f.write("[LOG FILE CORRUPTED - COULD NOT RECOVER]")
        return False
        
    except Exception as e:
        log(f"Erreur lors du nettoyage du log: {e}", "ERROR")
        return False

# Chargement de l'historique des incidents
def load_incident_history() -> List[Dict]:
    incident_file = MONITOR_DIR / "incident_history.json"
    if incident_file.exists():
        try:
            with incident_file.open('r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f"Erreur lecture incident_history.json: {e}", "ERROR")
            return []
    return []

# Chargement des logs récents
def load_recent_logs(days: int = 7) -> List[str]:
    log_file = MONITOR_DIR / "monitor.log"
    logs = []
    if not log_file.exists():
        return logs
        
    cutoff = datetime.now() - timedelta(days=days)
    
    # Essayer différents encodages
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'utf-8-sig']
    
    for encoding in encodings:
        try:
            with log_file.open('r', encoding=encoding, errors='replace') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Essayer d'extraire la date
                    try:
                        if line.startswith('[') and len(line) > 20:
                            log_date_str = line[1:20]
                            # Nettoyer la chaîne de date
                            log_date_str = ''.join(c for c in log_date_str if c.isdigit() or c in ' -:')
                            log_date = datetime.strptime(log_date_str, "%Y-%m-%d %H:%M:%S")
                            if log_date >= cutoff:
                                logs.append(line)
                        else:
                            logs.append(line)
                    except (ValueError, IndexError):
                        # Si le parsing échoue, ajouter quand même
                        logs.append(line)
            break  # Sortir de la boucle si la lecture réussit
            
        except UnicodeDecodeError:
            logs = []  # Réinitialiser pour le prochain essai
            continue
            
    return logs

# Génération d'un rapport complet
def generate_comprehensive_report(days: int = 7) -> str:
    incidents = load_incident_history()
    logs = load_recent_logs(days)
    cutoff = datetime.now() - timedelta(days=days)
    
    # Filtrer les incidents récents
    recent_incidents = []
    for inc in incidents:
        try:
            incident_date = datetime.fromisoformat(inc['timestamp'].replace('Z', '+00:00'))
            if incident_date >= cutoff:
                recent_incidents.append(inc)
        except (ValueError, KeyError):
            # Si le format de date est invalide, ignorer cet incident
            continue

    incident_counts = {}
    for inc in recent_incidents:
        incident_counts[inc['type']] = incident_counts.get(inc['type'], 0) + 1

    report = f"📈 RAPPORT COMPLET DE SURVEILLANCE WORDPRESS\n"
    report += f"📅 Période: {days} jours\n"
    report += f"⏰ Généré le: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    report += "="*60 + "\n\n"

    # Résumé incidents
    report += "📊 RÉSUMÉ DES INCIDENTS:\n"
    if incident_counts:
        for t, c in incident_counts.items():
            report += f"   - {t}: {c} incident(s)\n"
    else:
        report += "   ✅ Aucun incident récent\n"
    report += "\n"

    # Derniers incidents détaillés
    report += "🔍 DERNIERS INCIDENTS (5 max):\n"
    for inc in recent_incidents[:5]:
        report += f"   - [{inc['timestamp']}] {inc['type']} ({inc.get('severity', 'unknown')})\n"
    report += "\n"

    # Disponibilité - analyse améliorée
    availability_logs = [l for l in logs if any(keyword in l for keyword in 
                       ["Site accessible", "Site inaccessible", "accessible", "inaccessible", "✅", "❌"])]
    
    up_count = len([l for l in availability_logs if any(keyword in l for keyword in 
                   ["✅", "accessible", "SUCCES", "Site accessible"])])
    down_count = len([l for l in availability_logs if any(keyword in l for keyword in 
                     ["❌", "inaccessible", "ERREUR", "Site inaccessible"])])
    
    report += "🌐 DISPONIBILITÉ:\n"
    report += f"   - Disponible: {up_count} fois\n"
    report += f"   - Indisponible: {down_count} fois\n"
    if up_count + down_count > 0:
        availability_rate = (up_count / (up_count + down_count)) * 100
        report += f"   - Taux de disponibilité: {availability_rate:.2f}%\n"
    report += "\n"

    # Logs récents
    report += "📋 LOGS RÉCENTS (10 max):\n"
    for log_entry in logs[-10:]:
        report += f"   - {log_entry}\n"
    report += "\n"

    # Recommandations améliorées
    report += "💡 RECOMMANDATIONS:\n"
    
    if down_count > 0:
        report += "   - 🔍 Investiguer les causes d'indisponibilité du site\n"
    
    high_severity_incidents = [inc for inc in recent_incidents if inc.get('severity') == 'high']
    if high_severity_incidents:
        report += "   - 🚨 Traiter en priorité les incidents de sécurité (niveau high)\n"
        report += f"     ({len(high_severity_incidents)} incident(s) critique(s))\n"
    
    if len(recent_incidents) > 10:
        report += "   - ⚙️ Réviser la configuration du site (trop d'incidents)\n"
    
    ssl_incidents = [inc for inc in recent_incidents if 'ssl' in inc.get('type', '').lower()]
    if ssl_incidents:
        report += "   - 🔒 Vérifier le certificat SSL\n"
    
    content_incidents = [inc for inc in recent_incidents if 'content' in inc.get('type', '').lower()]
    if content_incidents:
        report += "   - 📝 Surveiller les modifications de contenu\n"
    
    if not any([down_count > 0, high_severity_incidents, len(recent_incidents) > 10, ssl_incidents, content_incidents]):
        report += "   - ✅ Configuration globale satisfaisante\n"
        report += "   - 🎯 Aucune action corrective nécessaire\n"

    # Statistiques supplémentaires
    report += "\n📊 STATISTIQUES:\n"
    report += f"   - Total incidents: {len(recent_incidents)}\n"
    report += f"   - Total logs analysés: {len(logs)}\n"
    report += f"   - Période analysée: du {cutoff.strftime('%Y-%m-%d')} au {datetime.now().strftime('%Y-%m-%d')}\n"

    return report

# Sauvegarde du rapport
def save_report(report: str, filename: str = None) -> str:
    if filename is None:
        filename = f"comprehensive_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    report_path = REPORTS_DIR / filename
    with report_path.open('w', encoding='utf-8') as f:
        f.write(report)
    return str(report_path)

# Point d'entrée principal
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Générateur de rapports de surveillance WordPress")
    parser.add_argument("--days", type=int, default=7, help="Nombre de jours à analyser (défaut: 7)")
    parser.add_argument("--output", help="Nom du fichier de sortie")
    parser.add_argument("--clean-logs", action="store_true", help="Nettoyer les fichiers de log corrompus")
    
    args = parser.parse_args()
    
    try:
        if args.clean_logs:
            log("Nettoyage des fichiers de log...")
            clean_log_file()
        
        log(f"Démarrage génération rapport pour {args.days} jours")
        report = generate_comprehensive_report(days=args.days)
        print(report)
        
        report_path = save_report(report, args.output)
        log(f"Rapport sauvegardé: {report_path}")
        
    except Exception as e:
        log(f"Erreur lors de la génération du rapport: {e}", "ERROR")