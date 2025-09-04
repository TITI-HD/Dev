#!/usr/bin/env python3
"""
Générateur de rapports pour la surveillance WordPress
Consolide les logs, incidents et rapports en un document unique
"""

import os
import json
import glob
from datetime import datetime, timedelta
from typing import Dict, List

MONITOR_DIR = "monitor_data"

def load_incident_history() -> List[Dict]:
    """Charge l'historique des incidents"""
    incident_file = os.path.join(MONITOR_DIR, "incident_history.json")
    if os.path.exists(incident_file):
        try:
            with open(incident_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def load_recent_logs(days: int = 7) -> List[str]:
    """Charge les logs récents"""
    log_file = os.path.join(MONITOR_DIR, "monitor.log")
    logs = []
    if os.path.exists(log_file):
        cutoff_date = datetime.now() - timedelta(days=days)
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    # Extraire la date du log
                    log_date_str = line[1:20]  # Format: [YYYY-MM-DD HH:MM:SS]
                    log_date = datetime.strptime(log_date_str, "%Y-%m-%d %H:%M:%S")
                    if log_date >= cutoff_date:
                        logs.append(line.strip())
                except:
                    logs.append(line.strip())
    return logs

def generate_comprehensive_report(days: int = 7) -> str:
    """Génère un rapport complet consolidé"""
    incidents = load_incident_history()
    logs = load_recent_logs(days)
    
    # Filtrer les incidents récents
    cutoff_date = datetime.now() - timedelta(days=days)
    recent_incidents = [
        inc for inc in incidents 
        if datetime.fromisoformat(inc['timestamp']) >= cutoff_date
    ]
    
    # Compter les incidents par type
    incident_counts = {}
    for inc in recent_incidents:
        inc_type = inc['type']
        incident_counts[inc_type] = incident_counts.get(inc_type, 0) + 1
    
    # Générer le rapport
    report = "📈 RAPPORT COMPLET DE SURVEILLANCE WORDPRESS\n"
    report += f"📅 Période: {days} jours\n"
    report += f"⏰ Généré le: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    report += "="*60 + "\n\n"
    
    # Résumé des incidents
    report += "📊 RÉSUMÉ DES INCIDENTS:\n"
    if incident_counts:
        for inc_type, count in incident_counts.items():
            report += f"   - {inc_type}: {count} incident(s)\n"
    else:
        report += "   ✅ Aucun incident récent\n"
    report += "\n"
    
    # Derniers incidents détaillés
    report += "🔍 DERNIERS INCIDENTS (5 maximum):\n"
    for inc in recent_incidents[:5]:
        report += f"   - [{inc['timestamp']}] {inc['type']} ({inc['severity']})\n"
    report += "\n"
    
    # Statistiques de disponibilité (extrait des logs)
    availability_logs = [log for log in logs if "Site accessible" in log or "Site inaccessible" in log]
    up_count = len([log for log in availability_logs if "✅" in log or "accessible" in log])
    down_count = len([log for log in availability_logs if "❌" in log or "inaccessible" in log])
    
    report += "🌐 DISPONIBILITÉ:\n"
    report += f"   - Disponible: {up_count} fois\n"
    report += f"   - Indisponible: {down_count} fois\n"
    if up_count + down_count > 0:
        uptime_percent = (up_count / (up_count + down_count)) * 100
        report += f"   - Taux de disponibilité: {uptime_percent:.2f}%\n"
    report += "\n"
    
    # Recommandations
    report += "💡 RECOMMANDATIONS:\n"
    if down_count > 0:
        report += "   - Investiguer les causes d'indisponibilité du site\n"
    if any(inc['severity'] == 'high' for inc in recent_incidents):
        report += "   - Traiter en priorité les incidents de sécurité\n"
    if len(recent_incidents) > 10:
        report += "   - Réviser la configuration du site (trop d'incidents)\n"
    else:
        report += "   - Configuration globale satisfaisante\n"
    
    return report

def save_report(report: str, filename: str = None):
    """Sauvegarde le rapport dans un fichier"""
    if filename is None:
        filename = f"comprehensive_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    reports_dir = os.path.join(MONITOR_DIR, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    report_path = os.path.join(reports_dir, filename)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    return report_path

def cleanup_old_logs():
    """Nettoie les anciens fichiers de log selon la rétention configurée"""
    retention_days = int(os.environ.get("LOG_RETENTION_DAYS", 30))
    cutoff_time = datetime.now() - timedelta(days=retention_days)
    
    log_files = [
        os.path.join(MONITOR_DIR, "monitor.log"),
        *glob.glob(os.path.join(MONITOR_DIR, "report_*.txt")),
        *glob.glob(os.path.join(MONITOR_DIR, "reports", "comprehensive_report_*.txt"))
    ]
    
    for log_file in log_files:
        if os.path.exists(log_file):
            file_time = datetime.fromtimestamp(os.path.getmtime(log_file))
            if file_time < cutoff_time:
                os.remove(log_file)
                log(f"Fichier log nettoyé: {log_file}", "INFO")
                
if __name__ == "__main__":
    report = generate_comprehensive_report(7)
    print(report)
    report_path = save_report(report)
    print(f"\nRapport sauvegardé: {report_path}")