# Guide de configuration de l'import SharePoint DPGF

Ce document vous guide à travers les étapes nécessaires pour configurer et utiliser l'import automatisé des fichiers DPGF depuis SharePoint.

## Prérequis

1. Accès administrateur à Azure Active Directory
2. Un compte Microsoft 365 avec accès au site SharePoint
3. Python 3.8+ installé sur la machine
4. Les dépendances requises (`pip install -r requirements_sharepoint.txt`)

## Configuration de l'application dans Azure AD

1. **Créer une application Azure AD**:
   - Accédez au [portail Azure](https://portal.azure.com)
   - Allez dans "Azure Active Directory" > "Inscriptions d'applications" > "Nouvelle inscription"
   - Donnez un nom à l'application (ex: "DPGF Import App")
   - Type de compte: "Comptes dans cet annuaire organisationnel uniquement"
   - URI de redirection: Laissez vide ou mettez "http://localhost"
   - Cliquez sur "S'inscrire"

2. **Noter les informations d'identification**:
   - ID de l'application (client) = `CLIENT_ID`
   - ID de l'annuaire (tenant) = `TENANT_ID`

3. **Créer un secret client**:
   - Dans votre application, allez à "Certificats & secrets"
   - "Nouveau secret client", donnez une description et choisissez l'expiration
   - Copiez immédiatement la VALEUR du secret (elle ne sera plus visible après) = `CLIENT_SECRET`

4. **Configurer les permissions API**:
   - Allez dans "Autorisations API" > "Ajouter une autorisation"
   - Choisir "Microsoft Graph" > "Autorisations d'application"
   - Ajouter les autorisations suivantes:
     - Files.Read.All
     - Files.ReadWrite.All
     - Sites.Read.All
   - Cliquez sur "Ajouter des autorisations"
   - **Important**: Cliquez sur "Accorder le consentement d'administrateur"

## Configuration des variables d'environnement

Créez un fichier `.env` à la racine du projet avec les variables suivantes:

```
# Configuration base de données et API (existante)
DATABASE_URL=postgresql://user:password@localhost/dbname
API_URL=http://localhost:8000
GEMINI_API_KEY=your_gemini_key

# Configuration SharePoint
TENANT_ID=votre_tenant_id
CLIENT_ID=votre_client_id
CLIENT_SECRET=votre_client_secret
GRAPH_DRIVE_ID=id_du_drive_sharepoint
GRAPH_DPFG_FOLDER=Documents   # Chemin du dossier contenant les DPGF
```

## Trouver l'ID du drive SharePoint

Pour trouver facilement l'ID du drive SharePoint à utiliser:

1. Exécutez le script de diagnostic:
   ```
   find_sharepoint_drive.bat
   ```
   
   Ou directement:
   ```
   python scripts\import_sharepoint_dpgf.py --list-drives
   ```

2. Le script affichera tous les drives disponibles avec leur ID.
   Copiez l'ID du drive approprié dans votre fichier `.env`.

## Résolution des problèmes courants

### Erreur 401 (Unauthorized)

1. **Vérifiez les identifiants**:
   - Assurez-vous que `TENANT_ID`, `CLIENT_ID` et `CLIENT_SECRET` sont corrects
   - Le secret client pourrait avoir expiré (créez-en un nouveau)

2. **Vérifiez les permissions**:
   - Assurez-vous d'avoir accordé le consentement administrateur pour les permissions
   - Vérifiez que les permissions incluent Files.Read.All et Sites.Read.All

3. **Vérifiez le compte d'application**:
   - L'application doit être enregistrée dans le même tenant que SharePoint

### Erreur 404 (Not Found)

1. **ID de drive incorrect**:
   - Utilisez le script de diagnostic pour trouver le bon ID de drive
   - Vérifiez que le drive existe toujours dans SharePoint

2. **Chemin de dossier incorrect**:
   - Le dossier spécifié dans `GRAPH_DPFG_FOLDER` n'existe pas
   - Essayez avec un autre dossier ou utilisez la racine ("root")

### Aucun drive trouvé

1. **Permissions insuffisantes**:
   - Vérifiez que l'application a les permissions Sites.Read.All
   - Assurez-vous que le consentement administrateur a été accordé

2. **Problème de tenant**:
   - Assurez-vous que l'application est enregistrée dans le bon tenant
   - Vérifiez que le tenant a accès à SharePoint

## Utilisation du script d'import

### Mode test (dry run)

Pour lister les fichiers DPGF disponibles sans les importer:

```
python scripts\import_sharepoint_dpgf.py --dry-run
```

### Import complet

Pour télécharger et importer tous les fichiers DPGF:

```
python scripts\import_sharepoint_dpgf.py
```

### Options supplémentaires

- `--folder "NomDuDossier"` : Spécifie un dossier SharePoint particulier
- `--limit 5` : Limite le nombre de fichiers à traiter
- `--list-drives` : Liste tous les drives disponibles
- `--verbose` : Affiche plus d'informations de débogage

## Support

En cas de problème persistant:

1. Exécutez avec l'option `--verbose` pour plus de détails
2. Vérifiez les journaux d'erreur
3. Contactez l'administrateur du système ou le développeur responsable
