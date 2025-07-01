#!/usr/bin/env python3
"""
Script de configuration et test de l'API Google Gemini
"""

import os
import sys
from pathlib import Path

def check_gemini_availability():
    """Vérifie si Gemini est disponible et configuré"""
    print("🔍 Vérification de la configuration Gemini...")
    
    # Vérifier l'installation du module
    try:
        import google.generativeai as genai
        print("✅ Module google.generativeai installé")
    except ImportError:
        print("❌ Module google.generativeai non installé")
        print("   Installez-le avec: pip install google-generativeai")
        return False
    
    # Vérifier la clé API
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ Variable d'environnement GEMINI_API_KEY non configurée")
        print("   1. Obtenez votre clé sur https://makersuite.google.com/app/apikey")
        print("   2. Créez un fichier .env avec: GEMINI_API_KEY=votre_cle")
        print("   3. Ou définissez la variable: set GEMINI_API_KEY=votre_cle")
        return False
    
    print(f"✅ Clé API trouvée: {api_key[:10]}...")
    
    # Tester la connexion
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Test simple
        response = model.generate_content("Répondez simplement 'OK' si vous recevez ce message.")
        
        if response and hasattr(response, 'text') and response.text:
            print(f"✅ Test de connexion réussi: {response.text.strip()}")
            return True
        else:
            print("❌ Réponse vide ou invalide de Gemini")
            return False
            
    except Exception as e:
        print(f"❌ Erreur lors du test de connexion: {e}")
        return False

def configure_gemini():
    """Assistant de configuration de Gemini"""
    print("🛠️  Assistant de configuration Gemini")
    print("=" * 50)
    
    if check_gemini_availability():
        print("🎉 Gemini est correctement configuré!")
        return True
    
    print("\n📋 Étapes de configuration:")
    print("1. Installez le module si nécessaire:")
    print("   pip install google-generativeai")
    
    print("\n2. Obtenez votre clé API:")
    print("   https://makersuite.google.com/app/apikey")
    
    print("\n3. Configurez la variable d'environnement:")
    print("   Windows: set GEMINI_API_KEY=votre_cle")
    print("   Linux/Mac: export GEMINI_API_KEY=votre_cle")
    print("   Ou créez un fichier .env avec: GEMINI_API_KEY=votre_cle")
    
    print("\n4. Redémarrez votre serveur FastAPI")
    print("\n5. Relancez ce script pour vérifier")
    
    return False

def main():
    """Fonction principale"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Configuration et test de Gemini")
    parser.add_argument("--test", action="store_true", help="Tester seulement la configuration")
    parser.add_argument("--setup", action="store_true", help="Assistant de configuration")
    
    args = parser.parse_args()
    
    if args.test:
        success = check_gemini_availability()
        sys.exit(0 if success else 1)
    elif args.setup:
        configure_gemini()
    else:
        # Mode par défaut: vérification complète
        if not configure_gemini():
            sys.exit(1)

if __name__ == "__main__":
    main()
