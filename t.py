#!/usr/bin/env python3
"""
Script de test simplifié pour monitor.py
"""

import monitor

# Test de la fonction de hash
test_content = "Hello World"
expected_hash = "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"
result_hash = monitor.compute_hash(test_content)

print(f"Test de hash: {'SUCCÈS' if result_hash == expected_hash else 'ÉCHEC'}")
print(f"Attendu: {expected_hash}")
print(f"Obtenu:  {result_hash}")

# Test de la fonction de logging
print("\nTest de logging:")
monitor.log("Ceci est un test de log")

print("Tous les tests terminés")