# 🚀 Système d'Import Automatique DPGF

Ce système permet d'uploader et d'importer automatiquement des fichiers DPGF Excel via une API web.

## 📋 Fonctionnalités

- **Upload de fichiers** : Interface API pour uploader des fichiers Excel DPGF
- **Import automatique** : Traitement automatique en arrière-plan après upload
- **Détection intelligente** : Détection automatique des clients et création de DPGFs uniques
- **Support multi-formats** : Compatible avec .xlsx et .xls

## 🛠️ Installation et Démarrage

### 1. Démarrer l'API
```bash
python start_api_server.py
```

L'API sera accessible sur `http://localhost:8000`

### 2. Documentation API
Visitez `http://localhost:8000/docs` pour la documentation interactive Swagger

## 📤 Upload de Fichiers

### Via script Python
```bash
# Uploader un fichier DPGF
python test_upload_dpgf.py "test_data/802 DPGF Lot 2 - Curage.xlsx"

# Avec URL personnalisée
python test_upload_dpgf.py "mon_fichier.xlsx" "http://localhost:8000"
```

### Via curl
```bash
curl -X POST "http://localhost:8000/api/v1/dpgf/upload" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@test_data/802 DPGF Lot 2 - Curage.xlsx"
```

### Via interface web (Swagger)
1. Allez sur `http://localhost:8000/docs`
2. Trouvez l'endpoint `POST /api/v1/dpgf/upload`
3. Cliquez sur "Try it out"
4. Sélectionnez votre fichier Excel
5. Cliquez sur "Execute"

## 🔧 Import Manuel (Script classique)

Si vous préférez utiliser le script d'import classique :

```bash
# Import simple
python scripts/import_complete.py --file "test_data/802 DPGF Lot 2 - Curage.xlsx"

# Avec classification IA (Gemini)
python scripts/import_complete.py --file "mon_fichier.xlsx" --gemini-key "votre_cle_gemini"

# Avec paramètres personnalisés
python scripts/import_complete.py \
    --file "mon_fichier.xlsx" \
    --base-url "http://localhost:8000" \
    --lot-num "2" \
    --chunk-size 15
```

## 📊 Vérification des Résultats

### Via API
```bash
# Lister tous les DPGFs
curl "http://localhost:8000/api/v1/dpgf/"

# Obtenir la structure d'un DPGF
curl "http://localhost:8000/api/v1/dpgf/1/structure"

# Vérifier le statut d'import
curl "http://localhost:8000/api/v1/dpgf/import-status"
```

### Via interface web
Visitez `http://localhost:8000/docs` pour explorer tous les endpoints disponibles.

## ⚙️ Configuration

### Variables d'environnement
Créez un fichier `.env` avec :
```
DATABASE_URL=sqlite:///./test.db
GEMINI_API_KEY=votre_cle_api_gemini_optionnelle
```

### Paramètres d'import
- **Détection automatique** : Clients détectés automatiquement depuis le nom de fichier et le contenu
- **DPGFs uniques** : Chaque fichier crée un DPGF distinct même avec des noms similaires
- **Processing arrière-plan** : Les imports sont traités de manière asynchrone

## 🐛 Résolution de Problèmes

### Erreurs communes

1. **"Fichier non trouvé"**
   - Vérifiez le chemin du fichier
   - Utilisez des guillemets pour les noms avec espaces

2. **"Erreur de connexion API"**
   - Vérifiez que l'API est démarrée (`python start_api_server.py`)
   - Vérifiez l'URL (par défaut : `http://localhost:8000`)

3. **"Format de fichier non supporté"**
   - Utilisez uniquement des fichiers .xlsx ou .xls
   - Vérifiez que le fichier n'est pas corrompu

### Logs et debug
- Les logs de l'API apparaissent dans le terminal où vous avez lancé `start_api_server.py`
- Les messages d'import apparaissent en temps réel
- Utilisez l'endpoint `/docs` pour tester manuellement les APIs

## 📁 Structure des Fichiers

```
├── app/
│   ├── api/v1/dpgf.py          # API d'upload et import
│   ├── main.py                 # Application FastAPI principale
│   └── ...
├── scripts/
│   └── import_complete.py      # Script d'import principal
├── test_data/                  # Fichiers de test
├── start_api_server.py         # Script de démarrage
├── test_upload_dpgf.py         # Script de test d'upload
└── README_UPLOAD.md            # Cette documentation
```

## 🎯 Exemples Pratiques

### Workflow complet
1. **Démarrer l'API** : `python start_api_server.py`
2. **Uploader un fichier** : `python test_upload_dpgf.py "mon_dpgf.xlsx"`
3. **Vérifier les résultats** : Visitez `http://localhost:8000/docs`

### Import de plusieurs fichiers
```bash
# Terminal 1 : Démarrer l'API
python start_api_server.py

# Terminal 2 : Uploader plusieurs fichiers
python test_upload_dpgf.py "test_data/802 DPGF Lot 2 - Curage.xlsx"
python test_upload_dpgf.py "test_data/803 DPGF Lot 3 - Gros-oeuvre - Démolition.xlsx"
python test_upload_dpgf.py "test_data/DPGF-Lot 06 Métallerie-Serrurerie - Nov 2024.xlsx"
```

Chaque fichier créera automatiquement son propre client et DPGF unique ! 🎉
