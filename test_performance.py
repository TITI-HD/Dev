# test_performance.py
import time
import requests
from concurrent.futures import ThreadPoolExecutor

def test_response_time():
    """Test du temps de réponse du site surveillé"""
    start_time = time.time()
    
    try:
        response = requests.get("https://httpbin.org/delay/1", timeout=5)
        end_time = time.time()
        response_time = end_time - start_time
        
        print(f"⏱️ Temps de réponse: {response_time:.2f}s")
        
        if response_time < 3:  # Seuil de 3 secondes
            print("✅ Performance acceptable")
            return True
        else:
            print("❌ Performance insuffisante")
            return False
            
    except requests.RequestException as e:
        print(f"❌ Erreur de performance: {e}")
        return False

def test_concurrent_requests():
    """Test de requêtes concurrentielles"""
    urls = ["https://httpbin.org/get"] * 5  # 5 requêtes identiques
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        start_time = time.time()
        results = list(executor.map(requests.get, urls))
        end_time = time.time()
    
    total_time = end_time - start_time
    avg_time = total_time / len(urls)
    
    print(f"🚀 Test de charge: {len(urls)} requêtes en {total_time:.2f}s")
    print(f"📊 Temps moyen par requête: {avg_time:.2f}s")
    
    success_count = sum(1 for r in results if r.status_code == 200)
    print(f"✅ Requêtes réussies: {success_count}/{len(urls)}")
    
    return success_count == len(urls)

if __name__ == "__main__":
    print("🧪 Début des tests de performance...")
    test1 = test_response_time()
    test2 = test_concurrent_requests()
    
    if test1 and test2:
        print("🎉 Tous les tests de performance passés")
    else:
        print("❌ Certains tests de performance ont échoué")
        exit(1)