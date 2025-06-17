#!/usr/bin/env python3
"""Script pour créer des fichiers Excel de test"""

import pandas as pd
import os

# Créer le dossier test_data s'il n'existe pas
os.makedirs('test_data', exist_ok=True)

# Fichier de test 1
data1 = {
    'A': ['Projet Rénovation École', '', 'LOT 01 – Gros œuvre', '', 'LOT 02 – Électricité', '', 'LOT 03 – Plomberie'],
    'B': ['', '', 'Description détaillée', '', 'Installation électrique', '', 'Sanitaires'],
    'C': ['', '', '50000€', '', '25000€', '', '15000€']
}
df1 = pd.DataFrame(data1)
df1.to_excel('test_data/renovation_ecole.xlsx', index=False)

# Fichier de test 2
data2 = {
    'Colonne1': ['Construction Maison Individuelle', '', '', 'LOT 1 - Terrassement', '', 'LOT 2 - Maçonnerie', '', 'LOT 3 - Charpente'],
    'Colonne2': ['', '', '', 'Préparation terrain', '', 'Murs et fondations', '', 'Structure bois'],
    'Colonne3': ['', '', '', '8000€', '', '45000€', '', '20000€']
}
df2 = pd.DataFrame(data2)
df2.to_excel('test_data/maison_individuelle.xlsx', index=False)

# Fichier de test 3 (sans lots pour tester la gestion d'erreur)
data3 = {
    'A': ['Projet sans lots', 'Description', 'Pas de lots ici'],
    'B': ['', 'Simple projet', 'Aucun format LOT']
}
df3 = pd.DataFrame(data3)
df3.to_excel('test_data/projet_sans_lots.xlsx', index=False)

print("✅ Fichiers Excel de test créés dans le dossier test_data/")
print("- renovation_ecole.xlsx (3 lots)")
print("- maison_individuelle.xlsx (3 lots)")  
print("- projet_sans_lots.xlsx (0 lot)")
