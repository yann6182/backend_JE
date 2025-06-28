# Guide de configuration des permissions Azure AD pour SharePoint

Ce guide vous aide à configurer correctement les permissions de votre application Azure AD pour accéder à SharePoint via Microsoft Graph API.

## Symptômes du problème de permissions

Si vous rencontrez l'une des erreurs suivantes, il s'agit très probablement d'un problème de permissions :

- Erreur 401 Unauthorized lors de l'accès aux drives SharePoint
- Message "General exception while processing" lors de l'accès via Graph API
- L'authentification réussit (token obtenu) mais les appels API échouent
- Aucun résultat retourné lors de la recherche de drives ou fichiers

## Étapes de correction des permissions

### 1. Connectez-vous au portail Azure

Accédez à [https://portal.azure.com](https://portal.azure.com) et connectez-vous avec un compte administrateur.

### 2. Accédez à votre application

1. Dans le portail, accédez à **Azure Active Directory**
2. Cliquez sur **Inscriptions d'applications**
3. Recherchez et sélectionnez votre application (CLIENT_ID = `017894bc-f3f5-4794-8111-a01570ad87b8`)

### 3. Vérifiez et mettez à jour les permissions API

1. Dans le menu de l'application, cliquez sur **Autorisations API**
2. Vérifiez les permissions actuellement configurées

3. Si les permissions nécessaires ne sont pas présentes, cliquez sur **+ Ajouter une autorisation**
   - Sélectionnez **Microsoft Graph**
   - Choisissez **Autorisations d'application** (pas les autorisations déléguées)
   - Recherchez et ajoutez les permissions suivantes :
     - **Files.Read.All** (Lire tous les fichiers auxquels l'utilisateur a accès)
     - **Files.ReadWrite.All** (Lire et écrire tous les fichiers)
     - **Sites.Read.All** (Lire les éléments dans tous les sites SharePoint)

4. Après avoir ajouté les permissions, cliquez sur **Accorder le consentement de l'administrateur**
   - Cette étape est **CRUCIALE** - sans consentement administrateur, l'application ne pourra pas utiliser ces permissions

### 4. Vérifiez le secret client

Si votre secret client est proche de l'expiration ou a expiré :

1. Dans le menu de l'application, cliquez sur **Certificats et secrets**
2. Vérifiez la date d'expiration du secret actuel
3. Si nécessaire, créez un nouveau secret en cliquant sur **+ Nouveau secret client**
   - Donnez un nom descriptif
   - Choisissez une durée de validité
   - **IMPORTANT** : Copiez immédiatement la VALEUR du secret (pas l'ID) car elle ne sera plus visible après
   - Mettez à jour votre fichier `.env` avec le nouveau secret

### 5. Vérifiez le Drive ID

Si l'accès au drive échoue avec une erreur 404, il est possible que l'ID de drive soit incorrect :

1. Exécutez le script `check_permissions.bat` qui tentera de lister les drives disponibles
2. Notez l'ID d'un drive accessible et mettez à jour votre fichier `.env`

### 6. Testez à nouveau la connexion

Après avoir effectué ces modifications :

1. Exécutez `test_sharepoint.bat` pour vérifier la connexion
2. Si tout fonctionne correctement, essayez `explore_sharepoint.bat` pour naviguer dans vos drives

## Problèmes courants

### Consentement administrateur manquant

**Symptôme** : La configuration semble correcte mais vous obtenez toujours des erreurs 401.

**Solution** : Assurez-vous que vous avez bien cliqué sur le bouton "Accorder le consentement de l'administrateur" après avoir ajouté les permissions. Ce bouton est situé en haut de la page des autorisations API.

### Type de permissions incorrect

**Symptôme** : Les permissions semblent être configurées mais ne fonctionnent pas.

**Solution** : Vérifiez que vous avez bien sélectionné les "Autorisations d'application" (Application permissions) et non les "Autorisations déléguées" (Delegated permissions). Pour une application serveur à serveur sans utilisateur, vous avez besoin des autorisations d'application.

### Propriétaire du site non accessible

**Symptôme** : Les drives sont visibles mais vous ne pouvez pas accéder à leur contenu.

**Solution** : Vérifiez que l'application a bien reçu les permissions pour le site SharePoint spécifique. Dans certains cas, il peut être nécessaire d'ajouter explicitement l'application comme propriétaire du site SharePoint.

## Ressources supplémentaires

- [Documentation Microsoft Graph pour SharePoint](https://learn.microsoft.com/fr-fr/graph/api/resources/sharepoint?view=graph-rest-1.0)
- [Autorisations Microsoft Graph](https://learn.microsoft.com/fr-fr/graph/permissions-reference)
- [Déboguer les erreurs d'authentification](https://learn.microsoft.com/fr-fr/azure/active-directory/develop/reference-aadsts-error-codes)
