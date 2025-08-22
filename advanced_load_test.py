import requests
import time
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor, as_completed

def advanced_load_test(url, num_requests=100, concurrency=10):
    """Test de charge avancé avec visualisation"""
    print(f"🚀 Test de charge avancé: {num_requests} requêtes, {concurrency} concurrents")
    
    results = []
    start_time = time.time()
    
    def make_request(i):
        try:
            request_start = time.time()
            response = requests.get(url, timeout=10)
            request_time = time.time() - request_start
            
            return {
                "index": i,
                "status": response.status_code,
                "time": request_time,
                "success": response.status_code == 200
            }
        except Exception as e:
            return {
                "index": i,
                "status": "error",
                "time": 0,
                "success": False,
                "error": str(e)
            }
    
    # Exécution des requêtes
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(make_request, i) for i in range(num_requests)]
        
        for future in as_completed(futures):
            results.append(future.result())
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Analyse des résultats
    success_count = sum(1 for r in results if r['success'])
    avg_time = total_time / num_requests
    requests_per_second = num_requests / total_time
    
    # Temps de réponse
    response_times = [r['time'] for r in results if r['success']]
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    
    print(f"📊 Résultats:")
    print(f"   Temps total: {total_time:.2f}s")
    print(f"   Requêtes réussies: {success_count}/{num_requests}")
    print(f"   Temps moyen par requête: {avg_time:.2f}s")
    print(f"   Temps de réponse moyen: {avg_response_time:.2f}s")
    print(f"   Requêtes par seconde: {requests_per_second:.2f}")
    
    # Visualisation (optionnelle - nécessite matplotlib)
    try:
        plt.figure(figsize=(10, 6))
        plt.plot([r['index'] for r in results], [r['time'] for r in results], 'b.')
        plt.title('Temps de réponse par requête')
        plt.xlabel('Numéro de requête')
        plt.ylabel('Temps (s)')
        plt.savefig('load_test_results.png')
        print("📈 Graphique sauvegardé dans load_test_results.png")
    except:
        print("⚠️ matplotlib non installé, skip de la visualisation")
    
    return success_count == num_requests

if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://httpbin.org/get"
    advanced_load_test(url)