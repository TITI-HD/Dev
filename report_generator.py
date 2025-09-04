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

MONITOR_DIR = Path("monitor_data")
REPORTS_DIR = MONITOR_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True, parents=True)

# === Logging ===
def log(message: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {message}"
    print(line)
    log_file = MONITOR_DIR / "report_generator.log"
    with log_file.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

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

def load_recent_logs(days: int = 7) -> List[str]:
    log_file = MONITOR_DIR / "monitor.log"
    logs = []
    if log_file.exists():
        cutoff = datetime.now() - timedelta(days=days)
        with log_file.open('r', encoding='utf-8') as f:
            for line in f:
                try:
                    log_date = datetime.strptime(line[1:20], "%Y-%m-%d %H:%M:%S")
                    if log_date >= cutoff:
                        logs.append(line.strip())
                except:
                    logs.append(line.strip())
    return logs

def generate_comprehensive_report(days: int = 7) -> str:
    incidents = load_incident_history()
    logs = load_recent_logs(days)
    cutoff = datetime.now() - timedelta(days=days)
    recent_incidents = [inc for inc in incidents if datetime.fromisoformat(inc['timestamp']) >= cutoff]

    incident_counts = {}
    for inc in recent_incidents:
        incident_counts[inc['type']] = incident_counts.get(inc['type'], 0) + 1

    report = f"📈 RAPPORT COMPLET DE SURVEILLANCE WORDPRESS\n📅 Période: {days} jours\n⏰ Généré le: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
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
        report += f"   - [{inc['timestamp']}] {inc['type']} ({inc['severity']})\n"
    report += "\n"

    # Disponibilité
    availability_logs = [l for l in logs if "Site accessible" in l or "Site inaccessible" in l]
    up_count = len([l for l in availability_logs if "✅" in l or "accessible" in l])
    down_count = len([l for l in availability_logs if "❌" in l or "inaccessible" in l])
    report += "🌐 DISPONIBILITÉ:\n"
    report += f"   - Disponible: {up_count} fois\n"
    report += f"   - Indisponible: {down_count} fois\n"
    if up_count + down_count > 0:
        report += f"   - Taux de disponibilité: {up_count / (up_count + down_count) * 100:.2f}%\n"
    report += "\n"

    # Recommandations
    report += "💡 RECOMMANDATIONS:\n"
    if down_count > 0:
        report += "   - Investiguer les causes d'indisponibilité du site\n"
    if any(inc['severity'] == 'high' for inc in recent_incidents):
        report += "   - Traiter en priorité les incidents de sécurité\n"
    if len(recent_incidents) > 10:
        report += "   - Réviser la configuration du site\n"
    else:
        report += "   - Configuration globale satisfaisante\n"

    return report

def save_report(report: str, filename: str = None) -> str:
    if filename is None:
        filename = f"comprehensive_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    report_path = REPORTS_DIR / filename
    with report_path.open('w', encoding='utf-8') as f:
        f.write(report)
    return str(report_path)

def cleanup_old_logs(retention_days: int = 30):
    cutoff = datetime.now() - timedelta(days=retention_days)
    log_files = list(MONITOR_DIR.glob("monitor.log")) + list(MONITOR_DIR.glob("report_*.txt")) + list(REPORTS_DIR.glob("comprehensive_report_*.txt"))
    for f in log_files:
        if f.exists() and datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
            f.unlink()
            log(f"Fichier log nettoyé: {f}", "INFO")

if __name__ == "__main__":
    report = generate_comprehensive_report(days=7)
    print(report)
    report_path = save_report(report)
    print(f"\nRapport sauvegardé: {report_path}")
