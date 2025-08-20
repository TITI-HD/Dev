# Recréez test_load.py correctement
$testLoadContent = @'
import requests
import time
from concurrent.futures import ThreadPoolExecutor

def test_site(url, num_requests=50, concurrency=5):
    print(f"🚀 Test de charge: {num_requests} requêtes, {concurrency} concurrents")
    
    start_time = time.time()
    
    def make_request(_):
        try:
            response = requests.get(url, timeout=10)
            return response.status_code
        except Exception as e:
            return str(e)
    
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = list(executor.map(make_request, range(num_requests)))
    
    end_time = time.time()
    total_time = end_time - start_time
    
    success_count = sum(1 for r in results if r == 200)
    avg_time = total_time / num_requests
    requests_per_second = num_requests / total_time
    
    print(f"📊 Résultats:")
    print(f"   Temps total: {total_time:.2f}s")
    print(f"   Requêtes réussies: {success_count}/{num_requests}")
    print(f"   Temps moyen par requête: {avg_time:.2f}s")
    print(f"   Requêtes par seconde: {requests_per_second:.2f}")
    
    return success_count == num_requests

if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://httpbin.org/get"
    test_site(url)
'@

Set-Content -Path "test_load.py" -Value $testLoadContent -Encoding UTF8

# Exécutez les tests
python -m unittest test_notifications.py
python test_load.py https://httpbin.org/get