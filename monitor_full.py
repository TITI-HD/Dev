#!/usr/bin/env python3
"""
Script complet WordPress : surveillance + sauvegarde + rapports
- Notifications email
- Rapport détaillé + solutions
- Fonctionnement autonome ou planifié
"""
import os, sys, time, json, glob, smtplib, hashlib, re, ssl, socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

# --- Vérification des dépendances ---
MISSING = []
try: import requests
except ImportError: MISSING.append("requests")
try: import schedule
except ImportError: MISSING.append("schedule")
try: from dateutil import parser, tz
except ImportError: MISSING.append("python-dateutil")
if MISSING:
    print("ERREUR: modules Python manquants :", ", ".join(MISSING))
    sys.exit(1)

# Import backup
try: from backup import backup_wordpress_content
except ImportError:
    print("[ERREUR] Impossible d'importer backup_wordpress_content depuis backup.py")
    sys.exit(1)

# --- Configuration ---
class Config:
    def __init__(self):
        self.SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")
        self.ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "danieltiti882@gmail.com")
        self.SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        self.SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
        self.SMTP_USER = os.environ.get("SMTP_USER", self.ALERT_EMAIL)
        self.SMTP_PASS = os.environ.get("SMTP_PASS", "")
        self.MONITOR_DIR = "monitor_data"
        self.INCIDENT_HISTORY_FILE = os.path.join(self.MONITOR_DIR, "incident_history.json")
        self.LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", 30))
        self.CHECK_INTERVAL_HOURS = int(os.environ.get("CHECK_INTERVAL_HOURS", 3))
        self.USE_EMOJI = os.name != "nt"
        Path(self.MONITOR_DIR).mkdir(exist_ok=True)
        if not self.SITE_URL.startswith(('http://','https://')):
            print("ATTENTION: SITE_URL invalide")
        if not self.SMTP_PASS:
            print("ATTENTION: SMTP_PASS non défini, emails désactivés")
config = Config()

# --- Gestion incidents ---
class IncidentManager:
    def __init__(self, history_file:str): self.history_file=history_file
    def load_incident_history(self)->List[Dict]:
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file,'r',encoding='utf-8') as f: return json.load(f)
            except: return []
        return []
    def save_incident_history(self,history:List[Dict]):
        try:
            with open(self.history_file,'w',encoding='utf-8') as f: json.dump(history,f,ensure_ascii=False,indent=2)
        except IOError as e: log(f"ERREUR sauvegarde historique: {e}","ERROR")
    def add_incident(self,type:str,details:Dict,severity:str="medium")->Dict:
        history=self.load_incident_history()
        incident={"timestamp":datetime.now().isoformat(),"type":type,"severity":severity,"details":details}
        history.append(incident)
        if len(history)>100: history=history[-100:]
        self.save_incident_history(history)
        return incident
incident_manager=IncidentManager(config.INCIDENT_HISTORY_FILE)

# --- Logging ---
def log(msg:str,level:str="INFO"):
    line=f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {msg}"
    print(line)
    try:
        with open(os.path.join(config.MONITOR_DIR,"monitor.log"),"a",encoding="utf-8") as f: f.write(line+"\n")
    except IOError as e: print(f"ERREUR log: {e}")

# --- Utilitaires ---
def compute_hash(content:str)->str: return hashlib.sha256(content.encode('utf-8')).hexdigest()
def emoji(sym:str)->str: return sym if config.USE_EMOJI else ""
def send_alert(subject:str,body:str,incident_type:str="general")->bool:
    if not all([config.SMTP_SERVER,config.SMTP_USER,config.SMTP_PASS,config.ALERT_EMAIL]):
        log("SMTP incomplet","WARNING"); return False
    try:
        msg=MIMEMultipart(); msg['From']=config.SMTP_USER; msg['To']=config.ALERT_EMAIL; msg['Subject']=subject
        msg.attach(MIMEText(body,'plain','utf-8'))
        with smtplib.SMTP(config.SMTP_SERVER,config.SMTP_PORT) as s: s.starttls(); s.login(config.SMTP_USER,config.SMTP_PASS); s.send_message(msg)
        incident_manager.add_incident(incident_type,{"subject":subject,"body":body,"sent_via":"email"})
        log("Alerte envoyée","INFO"); return True
    except Exception as e: log(f"ERREUR SMTP: {e}","ERROR"); return False

# --- Vérifications ---
def check_site_availability()->Dict:
    log("Vérification disponibilité","INFO")
    res={'available':False,'status_code':None,'response_time':None,'error':None}
    try:
        start=datetime.now(); resp=requests.get(config.SITE_URL,timeout=15)
        res['status_code']=resp.status_code
        res['response_time']=(datetime.now()-start).total_seconds()
        res['available']=resp.status_code==200
        if not res['available']: incident_manager.add_incident("site_unavailable",{"status_code":resp.status_code},"high")
    except Exception as e: res['error']=str(e); incident_manager.add_incident("site_unavailable",{"error":str(e)},"high")
    return res

def check_content_integrity()->Dict:
    log("Vérification intégrité","INFO")
    res={'changed':False,'changes':[],'error':None}
    for url,name in [(config.SITE_URL,"homepage"),(config.SITE_URL+"/feed/","rss"),(config.SITE_URL+"/comments/feed/","comments")]:
        try:
            r=requests.get(url,timeout=10)
            if r.status_code==200:
                h=compute_hash(r.text); f=os.path.join(config.MONITOR_DIR,f"{name}.ref")
                if os.path.exists(f):
                    with open(f,'r',encoding='utf-8') as file: old=file.read().strip()
                    if h!=old: res['changed']=True; change={'endpoint':name,'url':url,'timestamp':datetime.now().isoformat(),'old_hash':old,'new_hash':h}
                        res['changes'].append(change); incident_manager.add_incident("content_changed",change,"medium"); with open(f,'w',encoding='utf-8') as file: file.write(h)
                else: open(f,'w',encoding='utf-8').write(h)
        except Exception as e: res['error']=str(e); log(f"Erreur intégrité {name}: {e}","ERROR")
    return res

def check_for_malicious_patterns()->Dict:
    log("Recherche patterns suspects","INFO"); res={'suspicious_patterns':[],'error':None}
    patterns=[(r'eval\s*\(', "eval()"),(r'base64_decode\s*\(', "base64_decode"),(r'exec\s*\(', "exec"),(r'system\s*\(', "system"),(r'shell_exec\s*\(', "shell_exec"),(r'<script>[^<]*(alert|prompt|confirm)[^<]*</script>',"JS alert"),(r'<iframe[^>]*src=[^>]*>',"iframe suspect")]
    try:
        r=requests.get(config.SITE_URL,timeout=10)
        if r.status_code==200:
            for p,d in patterns:
                m=re.findall(p,r.text,re.IGNORECASE)
                if m: res['suspicious_patterns'].append({'pattern':p,'description':d,'matches_count':len(m)}); incident_manager.add_incident("suspicious_code",{'pattern':p,'description':d,'matches_count':len(m)},"high")
    except Exception as e: res['error']=str(e); log(f"Erreur pattern: {e}","ERROR")
    return res

def check_ssl_certificate()->Dict:
    log("Vérification SSL","INFO"); res={"valid":False,"error":None,"expires_in":None}
    try:
        host=config.SITE_URL.replace("https://","").split("/")[0]; ctx=ssl.create_default_context()
        with socket.create_connection((host,443),timeout=10) as sock:
            with ctx.wrap_socket(sock,server_hostname=host) as ss:
                cert=ss.getpeercert(); res["valid"]=True
                expire=parser.parse(cert['notAfter']); res["expires_in"]=(expire-datetime.utcnow()).days
                if res["expires_in"]<7: incident_manager.add_incident("ssl_expiring_soon",{"hostname":host,"expire_date":cert['notAfter'],"days_until_expire":res["expires_in"]},"medium")
    except Exception as e: res["error"]=str(e); log(f"Erreur SSL: {e}","ERROR"); incident_manager.add_incident("ssl_error",{"error":str(e)},"high")
    return res

# --- Rapport ---
def generate_detailed_report(av,integ,sec,ssl)->str:
    r=f"📊 RAPPORT WORDPRESS\n📍 {config.SITE_URL}\n⏰ {datetime.now()}\n"+"="*40+"\n"
    r+="🌐 DISPONIBILITÉ:\n"+("✅ OK\n" if av['available'] else f"❌ KO {av.get('error','')}\n")
    r+="🔍 INTÉGRITÉ:\n"+("✅ OK\n" if not integ['changed'] else f"⚠️ {len(integ['changes'])} modifs\n")
    r+="🛡️ SÉCURITÉ:\n"+("✅ OK\n" if not sec['suspicious_patterns'] else f"⚠️ {len(sec['suspicious_patterns'])} suspects\n")
    r+="🔒 SSL:\n"+("✅ Valide\n" if ssl['valid'] else f"❌ {ssl.get('error')}\n")
    return r

def generate_solutions_report(issues:Dict)->str:
    sol=[]
    if not issues.get('available',True): sol.append("Vérifier serveur/connexion"); 
    if issues.get('content_changed',False): sol.append("Vérifier logs/restaurer backup")
    if issues.get('suspicious_patterns',False): sol.append("Scanner site/modifier mots de passe")
    if issues.get('ssl_invalid',False): sol.append("Renouveler certificat SSL")
    return "🔧 SOLUTIONS PROPOSÉES:\n"+"".join(f" - {s}\n" for s in sol)

# --- Monitoring principal ---
def main_monitoring()->str:
    log("=== DÉBUT SURVEILLANCE ===")
    av=check_site_availability(); integ=check_content_integrity(); sec=check_for_malicious_patterns(); ssl=check_ssl_certificate()
    report=generate_detailed_report(av,integ,sec,ssl)
    issues={'available':av['available'],'content_changed':integ['changed'],'suspicious_patterns':len(sec['suspicious_patterns'])>0,'ssl_invalid':not ssl['valid'] or (ssl['expires_in'] is not None and ssl['expires_in']<7)}
    full_report=report+"\n"+generate_solutions_report(issues)
    subject="RAPPORT WORDPRESS"
    if not av['available']: subject="🚨 Site inaccessible"
    elif issues['suspicious_patterns']: subject="⚠️ Code suspect détecté"
    elif issues['content_changed']: subject="ℹ️ Contenu modifié"
    elif issues['ssl_invalid']: subject="⚠️ SSL problème"
    send_alert(subject,full_report)
    try: f=os.path.join(config.MONITOR_DIR,f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"); open(f,'w',encoding='utf-8').write(full_report); log(f"Rapport sauvegardé {f}")
    except Exception as e: log(f"Erreur sauvegarde rapport: {e}","ERROR")
    log("=== FIN SURVEILLANCE ==="); return full_report

# --- Nettoyage ancien logs ---
def cleanup_old_logs():
    cutoff=datetime.now()-timedelta(days=config.LOG_RETENTION_DAYS)
    files=[os.path.join(config.MONITOR_DIR,"monitor.log"),*glob.glob(os.path.join(config.MONITOR_DIR,"report_*.txt"))]
    for f in files:
        if os.path.exists(f) and datetime.fromtimestamp(os.path.getmtime(f))<cutoff: os.remove(f); log(f"Fichier supprimé {f}")

# --- Exécution planifiée ---
def run_scheduled_monitoring():
    import schedule
    cleanup_old_logs()
    schedule.every(config.CHECK_INTERVAL_HOURS).hours.do(main_monitoring)
    schedule.every().day.do(cleanup_old_logs)
    main_monitoring()
    while True:
        try: schedule.run_pending(); time.sleep(60)
        except KeyboardInterrupt: log("Arrêt demandé"); break
        except Exception as e: log(f"Erreur boucle planification: {e}","ERROR"); time.sleep(300)

# --- Sauvegarde + Monitoring ---
def backup_and_monitor()->str:
    log("Sauvegarde WordPress")
    backup_wordpress_content()
    return main_monitoring()

# --- Main ---
if __name__=="__main__":
    try:
        if "--scheduled" in sys.argv: run_scheduled_monitoring()
        else: backup_and_monitor()
    except KeyboardInterrupt: log("Arrêt demandé"); sys.exit(0)
    except Exception as e: log(f"Erreur critique: {e}","ERROR"); send_alert("❌ Erreur critique",str(e),"system_error"); sys.exit(1)
