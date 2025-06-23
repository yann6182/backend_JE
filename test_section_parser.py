"""
Test simplifié pour valider la détection des sections et des éléments
"""
import pandas as pd
from app.services.dpgf_import import ExcelParser
import sys

def test_section_detection():
    """Teste la détection des sections avec différents formats de test"""
    # Créer des exemples de sections qui poseraient problème
    test_sections = [
        "2.1 Escaliers métalliques",
        "FERRURES",
        "CHAPITRE 3: MENUISERIE EXTERIEURE",
        "LOT 06 - MÉTALLERIE",
        "SOUS-TOTAL Escaliers",
        "10.5.1 Fourniture et pose de garde corps",
        "TOTAL"
    ]
    
    # Créer un dataframe de test
    data = {
        0: test_sections
    }
    df = pd.DataFrame(data)
      # Créer un parser avec le dataframe de test
    parser = ExcelParser.__new__(ExcelParser)  # Crée une instance sans appeler __init__
    parser.df = df
    parser.col_designation = 0
    parser.col_unite = None
    parser.col_quantite = None
    parser.col_prix_unitaire = None
    parser.col_prix_total = None
    parser.headers_detected = True
    # Méthode safe_convert_to_float
    parser.safe_convert_to_float = lambda x: float(x) if pd.notna(x) else 0.0
    
    # Tester la détection
    for i, section_text in enumerate(test_sections):
        line_type, section_data = parser._classify_line(df.iloc[i], section_text, i)
        if line_type == 'section':
            print(f"Section: '{section_text}'")
            print(f"  → numero_section: '{section_data['numero_section']}'")
            print(f"  → titre_section: '{section_data['titre_section']}'")
            print(f"  → niveau: {section_data['niveau_hierarchique']}")
            print()

def test_element_detection():
    """Teste la détection des éléments avec différents formats de test"""
    # Créer des exemples d'éléments avec des prix
    test_elements = [
        "2.1.3 Fourniture et pose de garde-corps en acier",
        "Main d'œuvre pour pose des éléments métalliques",
        "a) Finition peinture époxy",
        "Escalier hélicoïdal en métal",
    ]
    
    # Créer un dataframe de test avec colonnes prix et quantité
    data = {
        0: test_elements,
        1: ["U", "h", "m²", "U"],       # Unité
        2: [3.0, 12.5, 25.0, 1.0],      # Quantité
        3: [1500.0, 65.0, 45.0, 3500.0], # Prix unitaire
        4: [4500.0, 812.5, 1125.0, 3500.0] # Prix total
    }
    df = pd.DataFrame(data)
    
    # Créer un parser avec le dataframe de test
    parser = ExcelParser.__new__(ExcelParser)  # Crée une instance sans appeler __init__
    parser.df = df
    parser.col_designation = 0
    parser.col_unite = 1
    parser.col_quantite = 2
    parser.col_prix_unitaire = 3
    parser.col_prix_total = 4
    parser.headers_detected = True
    
    # Méthode pour convertir les valeurs en float
    parser.safe_convert_to_float = lambda x: float(x) if pd.notna(x) else 0.0
    
    # Tester la détection
    for i, element_text in enumerate(test_elements):
        line_type, element_data = parser._classify_line(df.iloc[i], element_text, i)
        if line_type == 'element':
            print(f"Élément: '{element_text}'")
            print(f"  → designation_exacte: '{element_data['designation_exacte']}'")
            print(f"  → unite: '{element_data['unite']}'")
            print(f"  → quantite: {element_data['quantite']}")
            print(f"  → prix_unitaire_ht: {element_data['prix_unitaire_ht']}")
            print(f"  → prix_total_ht: {element_data['prix_total_ht']}")
            print()

def test_long_titles():
    """Teste spécifiquement la troncature des titres longs pour les sections"""
    parser = ExcelParser.__new__(ExcelParser)
    parser.safe_convert_to_float = lambda x: float(x) if pd.notna(x) else 0.0
    
    # Exemple 1: Titre très long qui dépasse 50 caractères
    long_title = "UNE SECTION AVEC UN TITRE EXTRÊMEMENT LONG QUI DÉPASSE LA LIMITE DE 50 CARACTÈRES AUTORISÉE EN BASE DE DONNÉES"
    section_data = parser._extract_section_data(long_title)
    print(f"\nTitre long: '{long_title}'")
    print(f"  → numero_section (max 50 car.): '{section_data['numero_section']}' ({len(section_data['numero_section'])} caractères)")
    print(f"  → titre_section: '{section_data['titre_section']}'")
    print(f"  → La longueur du numéro est valide: {len(section_data['numero_section']) <= 50}")
    
    # Exemple 2: Numéro + titre très long
    long_numbered_title = "1.2.3.4.5 Une section avec une numérotation complexe mais aussi un titre extrêmement long qui dépasse la limite autorisée"
    section_data = parser._extract_section_data(long_numbered_title)
    print(f"\nTitre numéroté long: '{long_numbered_title}'")
    print(f"  → numero_section: '{section_data['numero_section']}' ({len(section_data['numero_section'])} caractères)")
    print(f"  → titre_section: '{section_data['titre_section']}'")
    print(f"  → La longueur du numéro est valide: {len(section_data['numero_section']) <= 50}")

if __name__ == "__main__":
    print("=== Test de détection des SECTIONS ===")
    test_section_detection()
    
    print("=== Test de détection des ÉLÉMENTS ===")
    test_element_detection()
    
    print("=== Test de troncature des TITRES LONGS ===")
    test_long_titles()
