# Guide d'identification SharePoint - Fonction de test rapide

## Vue d'ensemble

Cette documentation explique comment utiliser la nouvelle fonctionnalité de **test rapide** pour vérifier l'accès à SharePoint et lister les 10 premiers fichiers d'un dossier.

## Fonctionnalité de test rapide

### Objectif
- Tester rapidement la connectivité à SharePoint
- Vérifier l'accès à un dossier spécifique
- Lister les 10 premiers éléments (fichiers et dossiers) pour validation

### Utilisation

#### 1. Via le script batch interactif
```bash
# Lancer le script batch
identify_sharepoint_files.bat

# Choisir l'option 1 : "🧪 Tester l'accès SharePoint"
```

#### 2. Via la ligne de commande
```bash
# Test d'accès au dossier par défaut
python scripts/identify_relevant_files_sharepoint.py --source sharepoint --test-access

# Test d'accès à un dossier spécifique
python scripts/identify_relevant_files_sharepoint.py --source sharepoint --folder "/Documents partages/Projets" --test-access
```

#### 3. Via le code Python
```python
from scripts.identify_relevant_files_sharepoint import SharePointClient

# Créer une instance du client SharePoint
client = SharePointClient()

# Tester l'accès et lister les 10 premiers fichiers
files = client.list_first_10_files("/Documents partages")

# Afficher les résultats
for file_info in files:
    print(f"📄 {file_info['name']} ({file_info['size']} bytes)")
```

## Sortie de la fonction de test

### Format de sortie
```
🧪 Test d'accès au dossier SharePoint: /Documents partages
✅ Accès réussi! Trouvé 8 éléments:
  1. 📁 Projets (-)
  2. 📁 Archives (-)
  3. 📄 Document1.xlsx (2.1 MB)
  4. 📄 DPGF_Lot1.xlsx (1.5 MB)
  5. 📄 BPU_Projet_A.xlsx (3.2 MB)
  6. 📁 Templates (-)
  7. 📄 Notes.docx (0.8 MB)
  8. 📄 Rapport.pdf (5.1 MB)
```

### Informations retournées
- **Type** : 📁 (dossier) ou 📄 (fichier)
- **Nom** : Nom du fichier ou dossier
- **Taille** : Taille en MB (- pour les dossiers)
- **Chemin complet** : Chemin SharePoint complet
- **Dates** : Création et modification
- **URLs** : Lien de téléchargement et web

## Cas d'usage

### 1. Vérification d'accès initial
```bash
# Tester l'accès au dossier racine
python scripts/identify_relevant_files_sharepoint.py --source sharepoint --folder "/" --test-access
```

### 2. Exploration de structure
```bash
# Tester différents dossiers
python scripts/identify_relevant_files_sharepoint.py --source sharepoint --folder "/Documents partages" --test-access
python scripts/identify_relevant_files_sharepoint.py --source sharepoint --folder "/Documents partages/Projets" --test-access
```

### 3. Validation avant scan complet
```bash
# 1. Tester l'accès
python scripts/identify_relevant_files_sharepoint.py --source sharepoint --folder "/Documents partages" --test-access

# 2. Si OK, lancer le scan complet
python scripts/identify_relevant_files_sharepoint.py --source sharepoint --folder "/Documents partages" --mode deep
```

## Gestion des erreurs

### Erreurs courantes et solutions

#### 1. Accès refusé (401/403)
```
❌ Erreur lors du test d'accès: HTTP 401 - Unauthorized
```
**Solution** : Vérifier les credentials dans le fichier `.env`

#### 2. Dossier introuvable (404)
```
❌ Erreur lors du test d'accès: HTTP 404 - Not Found
```
**Solution** : Vérifier le chemin du dossier SharePoint

#### 3. Problème de réseau
```
❌ Erreur lors du test d'accès: Connection timeout
```
**Solution** : Vérifier la connectivité internet et les paramètres proxy

#### 4. Token expiré
```
❌ Erreur lors du test d'accès: Token expired
```
**Solution** : Le token sera automatiquement renouvelé lors du prochain appel

## Configuration

### Variables d'environnement requises
```env
# Fichier .env
TENANT_ID=votre-tenant-id
CLIENT_ID=votre-client-id
CLIENT_SECRET=votre-client-secret
GRAPH_DRIVE_ID=votre-drive-id
```

### Paramètres de la fonction
```python
def list_first_10_files(self, folder_path: str = "/") -> List[Dict]:
    """
    Args:
        folder_path: Chemin du dossier SharePoint
                    Exemples: "/", "/Documents partages", "/Documents partages/Projets"
    
    Returns:
        List[Dict]: Liste des 10 premiers fichiers avec métadonnées
    """
```

## Intégration avec l'existant

### Workflow recommandé
1. **Test d'accès** : Vérifier la connectivité
2. **Scan rapide** : Identifier les fichiers pertinents
3. **Scan approfondi** : Analyser le contenu des fichiers
4. **Téléchargement** : Récupérer les fichiers identifiés

### Exemple de script complet
```python
import sys
from scripts.identify_relevant_files_sharepoint import SharePointClient

def workflow_complet():
    client = SharePointClient()
    folder = "/Documents partages"
    
    # 1. Test d'accès
    print("🧪 Test d'accès...")
    files = client.list_first_10_files(folder)
    if not files:
        print("❌ Impossible d'accéder au dossier")
        return False
    
    print(f"✅ Accès OK, {len(files)} éléments trouvés")
    
    # 2. Scan complet si l'accès fonctionne
    print("🔍 Scan complet...")
    all_files = client.list_files_in_folder(folder, recursive=True)
    print(f"📊 {len(all_files)} fichiers trouvés au total")
    
    return True

if __name__ == "__main__":
    workflow_complet()
```

## Monitoring et logs

### Logs générés
- **Niveau INFO** : Accès réussi et nombre de fichiers
- **Niveau WARNING** : Dossier non trouvé
- **Niveau ERROR** : Erreurs d'accès ou de réseau

### Métriques utiles
- Temps de réponse de l'API SharePoint
- Nombre de fichiers accessibles
- Taille totale des fichiers
- Taux de succès des accès

## Bonnes pratiques

### 1. Toujours tester l'accès en premier
```python
# Mauvais : scanner directement
files = client.list_files_in_folder("/Documents partages", recursive=True)

# Bon : tester l'accès d'abord
test_files = client.list_first_10_files("/Documents partages")
if test_files:
    files = client.list_files_in_folder("/Documents partages", recursive=True)
```

### 2. Gérer les erreurs gracieusement
```python
try:
    files = client.list_first_10_files(folder_path)
    if files:
        print(f"✅ Accès réussi : {len(files)} éléments")
    else:
        print("⚠️ Dossier vide ou inaccessible")
except Exception as e:
    print(f"❌ Erreur : {str(e)}")
```

### 3. Utiliser pour la navigation
```python
# Explorer la structure SharePoint
def explore_sharepoint_structure(client, base_path="/"):
    elements = client.list_first_10_files(base_path)
    
    for element in elements:
        if element['type'] == 'folder':
            print(f"📁 {element['name']}")
            # Possibilité d'explorer récursivement
```

Cette fonctionnalité de test rapide permet une approche incrémentale et robuste pour l'accès à SharePoint, facilitant le débogage et la validation avant les opérations plus lourdes.
