"""
Script d'analyse des performances simplifié pour identifier les goulots d'étranglement.
"""

import sys
import os
import time
import psutil
import pandas as pd
from pathlib import Path
import requests


def test_api_performance(base_url: str = "http://127.0.0.1:8000"):
    """Teste les performances de l'API"""
    print("🔍 Test performances API...")
    
    results = {
        'base_url': base_url,
        'connectivity': False,
        'response_times': {},
        'errors': []
    }
    
    # Test de connectivité
    try:
        start = time.time()
        response = requests.get(f"{base_url}/docs", timeout=10)
        results['connectivity'] = response.status_code == 200
        results['response_times']['docs'] = time.time() - start
        print(f"   ✅ Connectivité API: {results['response_times']['docs']:.3f}s")
    except Exception as e:
        results['errors'].append(f"Connectivité: {str(e)}")
        print(f"   ❌ Erreur connectivité: {e}")
    
    # Test des endpoints principaux
    endpoints = [
        '/api/v1/clients/',
        '/api/v1/dpgfs/',
        '/api/v1/lots/',
        '/api/v1/sections/',
        '/api/v1/elements/'
    ]
    
    for endpoint in endpoints:
        try:
            start = time.time()
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            response_time = time.time() - start
            results['response_times'][endpoint] = response_time
            
            status = "✅" if response_time < 1.0 else "⚠️" if response_time < 5.0 else "❌"
            print(f"   {status} {endpoint}: {response_time:.3f}s (HTTP {response.status_code})")
            
            if response.status_code not in [200, 404]:  # 404 peut être normal si pas de données
                results['errors'].append(f"{endpoint}: HTTP {response.status_code}")
                
        except Exception as e:
            results['errors'].append(f"{endpoint}: {str(e)}")
            print(f"   ❌ {endpoint}: {e}")
    
    return results


def analyze_local_test_files():
    """Analyse les fichiers de test locaux pour identifier les problèmes de performance"""
    print("\\n🔍 Analyse des fichiers de test locaux...")
    
    test_dir = Path("test_data")
    if not test_dir.exists():
        print("   ⚠️ Répertoire test_data non trouvé")
        return []
    
    results = []
    excel_files = list(test_dir.glob("*.xlsx")) + list(test_dir.glob("*.xls"))
    
    for file_path in excel_files:
        print(f"   📁 Analyse: {file_path.name}")
        
        result = {
            'file_path': str(file_path),
            'file_name': file_path.name,
            'success': False,
            'error': None,
            'timing': {},
            'file_stats': {},
            'sheet_info': {}
        }
        
        try:
            start_time = time.time()
            
            # Stats du fichier
            file_size = file_path.stat().st_size
            result['file_stats'] = {
                'size_bytes': file_size,
                'size_mb': round(file_size / (1024 * 1024), 2)
            }
            
            # Analyse des feuilles Excel
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            result['sheet_info'] = {
                'sheet_count': len(sheet_names),
                'sheet_names': sheet_names,
                'sheets_data': {}
            }
            
            # Analyser chaque feuille
            for sheet_name in sheet_names:
                try:
                    sheet_start = time.time()
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    sheet_time = time.time() - sheet_start
                    
                    result['sheet_info']['sheets_data'][sheet_name] = {
                        'rows': len(df),
                        'cols': len(df.columns),
                        'load_time': sheet_time,
                        'empty': len(df) == 0 or df.dropna(how='all').empty
                    }
                    
                except Exception as e:
                    result['sheet_info']['sheets_data'][sheet_name] = {
                        'error': str(e)
                    }
            
            total_time = time.time() - start_time
            result['timing']['total_time'] = total_time
            result['success'] = True
            
            # Identifier la feuille avec le plus de données
            max_rows = 0
            best_sheet = None
            for sheet_name, data in result['sheet_info']['sheets_data'].items():
                if 'rows' in data and data['rows'] > max_rows:
                    max_rows = data['rows']
                    best_sheet = sheet_name
            
            if best_sheet:
                print(f"      ✅ {total_time:.2f}s - {result['file_stats']['size_mb']}MB")
                print(f"         Meilleure feuille: '{best_sheet}' ({max_rows} lignes)")
                
                if total_time > 5:
                    print(f"      ⚠️ LENT: {total_time:.1f}s")
                    
                # Identifier les feuilles vides (souvent "page de garde")
                empty_sheets = [name for name, data in result['sheet_info']['sheets_data'].items() 
                              if data.get('empty', False)]
                if empty_sheets:
                    print(f"         Feuilles vides: {empty_sheets}")
            else:
                print(f"      ⚠️ Aucune feuille avec données trouvée")
                
        except Exception as e:
            result['error'] = str(e)
            result['timing']['total_time'] = time.time() - start_time
            print(f"      ❌ Erreur: {e}")
        
        results.append(result)
    
    return results


def check_database_performance():
    """Vérifie les performances de la base de données"""
    print("\\n🔍 Test performance base de données...")
    
    base_url = "http://127.0.0.1:8000"
    
    # Test des requêtes courantes
    test_queries = [
        ("/api/v1/clients/", "Clients"),
        ("/api/v1/dpgfs/", "DPGFs"), 
        ("/api/v1/lots/", "Lots"),
        ("/api/v1/sections/", "Sections"),
        ("/api/v1/elements/?limit=10", "Éléments (10 premiers)")
    ]
    
    for endpoint, desc in test_queries:
        try:
            start = time.time()
            response = requests.get(f"{base_url}{endpoint}", timeout=30)
            query_time = time.time() - start
            
            if response.status_code == 200:
                data = response.json()
                count = len(data) if isinstance(data, list) else 1
                status = "✅" if query_time < 2.0 else "⚠️" if query_time < 10.0 else "❌"
                print(f"   {status} {desc}: {query_time:.3f}s ({count} enregistrements)")
                
                if query_time > 5:
                    print(f"      ⚠️ Requête lente - possible problème d'index")
                    
            else:
                print(f"   ❌ {desc}: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ {desc}: {e}")


def analyze_import_bottlenecks():
    """Analyse les goulots d'étranglement potentiels"""
    print("\\n🔍 Analyse des goulots d'étranglement...")
    
    bottlenecks = []
    
    # 1. Mémoire système
    memory = psutil.virtual_memory()
    if memory.percent > 80:
        bottlenecks.append("⚠️ Mémoire système élevée ({:.1f}%)".format(memory.percent))
    else:
        print(f"   ✅ Mémoire système: {memory.percent:.1f}%")
    
    # 2. Espace disque
    disk = psutil.disk_usage('.')
    disk_percent = (disk.used / disk.total) * 100
    if disk_percent > 90:
        bottlenecks.append("⚠️ Espace disque faible ({:.1f}%)".format(disk_percent))
    else:
        print(f"   ✅ Espace disque: {disk_percent:.1f}%")
    
    # 3. Processus Python actifs
    python_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            if 'python' in proc.info['name'].lower():
                python_processes.append(proc.info)
        except:
            pass
    
    if len(python_processes) > 5:
        bottlenecks.append(f"⚠️ Nombreux processus Python actifs ({len(python_processes)})")
    else:
        print(f"   ✅ Processus Python: {len(python_processes)}")
    
    # 4. Analyse des logs récents
    log_files = ['dpgf_import.log', 'celery_tasks.log']
    for log_file in log_files:
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    if len(lines) > 1000:
                        recent_lines = lines[-100:]  # 100 dernières lignes
                        error_count = sum(1 for line in recent_lines if 'ERROR' in line or 'ERREUR' in line)
                        if error_count > 5:
                            bottlenecks.append(f"⚠️ Nombreuses erreurs récentes dans {log_file} ({error_count})")
                        else:
                            print(f"   ✅ Log {log_file}: {error_count} erreurs récentes")
            except Exception as e:
                print(f"   ⚠️ Impossible de lire {log_file}: {e}")
    
    return bottlenecks


def generate_recommendations(api_results, file_results, bottlenecks):
    """Génère des recommandations d'optimisation"""
    print("\\n💡 RECOMMANDATIONS D'OPTIMISATION")
    print("=" * 50)
    
    recommendations = []
    
    # API Performance
    if not api_results['connectivity']:
        recommendations.append("🔧 API non accessible - vérifier que l'API FastAPI est démarrée")
    
    slow_endpoints = [ep for ep, time in api_results.get('response_times', {}).items() if time > 2]
    if slow_endpoints:
        recommendations.append(f"🔧 Endpoints lents détectés: {slow_endpoints}")
        recommendations.append("   → Ajouter des index sur les colonnes fréquemment requêtées")
        recommendations.append("   → Implémenter la pagination pour les gros résultats")
    
    # File Processing
    if file_results:
        slow_files = [r for r in file_results if r['success'] and r['timing']['total_time'] > 10]
        if slow_files:
            recommendations.append(f"🔧 {len(slow_files)} fichier(s) lent(s) à traiter (>10s)")
            recommendations.append("   → Augmenter les timeouts dans l'orchestrateur")
            recommendations.append("   → Implémenter un processing par chunks plus petit")
        
        # Analyser les feuilles multiples
        multi_sheet_files = [r for r in file_results if r['success'] and r['sheet_info']['sheet_count'] > 3]
        if multi_sheet_files:
            recommendations.append(f"🔧 {len(multi_sheet_files)} fichier(s) avec nombreuses feuilles")
            recommendations.append("   → Optimiser la détection de la feuille de données")
    
    # System Bottlenecks
    for bottleneck in bottlenecks:
        recommendations.append(f"🔧 {bottleneck}")
    
    # General Recommendations
    recommendations.extend([
        "",
        "📋 OPTIMISATIONS GÉNÉRALES:",
        "• Implémenter un retry automatique avec backoff exponentiel",
        "• Ajouter des métriques de monitoring (temps par étape)",
        "• Utiliser un pool de workers pour le processing parallèle",
        "• Mettre en cache les patterns de classification Gemini",
        "• Implémenter une queue Redis/Celery pour les gros imports"
    ])
    
    for rec in recommendations:
        print(rec)


def main():
    """Analyse complète des performances"""
    print("🔍 ANALYSE DE PERFORMANCE DPGF")
    print("=" * 50)
    
    # 1. Test API
    api_results = test_api_performance()
    
    # 2. Analyse fichiers locaux
    file_results = analyze_local_test_files()
    
    # 3. Test performance base de données
    check_database_performance()
    
    # 4. Analyse des goulots d'étranglement
    bottlenecks = analyze_import_bottlenecks()
    
    # 5. Générer les recommandations
    generate_recommendations(api_results, file_results, bottlenecks)
    
    print("\\n" + "=" * 50)
    print("✅ Analyse terminée")


if __name__ == "__main__":
    main()
