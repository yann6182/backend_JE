# Documentation API DPGF Backend

## Vue d'ensemble

Cette API FastAPI fournit des endpoints pour gérer les données DPGF (Détail de Prix Global et Forfaitaire). L'API est configurée avec CORS pour permettre les requêtes depuis le frontend.

## Configuration de base

- **URL de base**: `http://localhost:8000`
- **Préfixe API**: `/api/v1`
- **CORS configuré pour**: `http://localhost:5173` et `http://127.0.0.1:5173`

## Configuration de l'environnement

### Prérequis
- Python 3.8+
- MySQL 8.0+
- Environnement virtuel (venv)

### Installation des dépendances
```bash
# Installer les dépendances
pip install -r requirements.txt
```

### Configuration de la base de données
Le projet utilise un fichier `.env` pour la configuration de la base de données. Assurez-vous que ce fichier est correctement configuré avec la chaîne de connexion à votre base de données MySQL :

```
DATABASE_URL=mysql+pymysql://utilisateur:mot_de_passe@hote:port/nom_db
```

**Note importante**: Le package `cryptography` est requis pour l'authentification MySQL avec les méthodes `sha256_password` ou `caching_sha2_password`. Il est inclus dans les dépendances du projet.

## Démarrage du serveur

```bash
# Activer l'environnement virtuel
# Windows:
venv\Scripts\activate

# Démarrer le serveur
uvicorn app.main:app --reload
```

Le serveur sera accessible sur `http://localhost:8000`

## Documentation interactive

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Endpoints disponibles

### 1. Gestion des Clients

#### Base URL: `/api/v1/clients`

- **GET** `/api/v1/clients/` - Récupérer tous les clients
- **POST** `/api/v1/clients/` - Créer un nouveau client
- **GET** `/api/v1/clients/{client_id}` - Récupérer un client spécifique
- **DELETE** `/api/v1/clients/{client_id}` - Supprimer un client

### 2. Gestion des DPGF

#### Base URL: `/api/v1/dpgf`

- **GET** `/api/v1/dpgf/` - Récupérer tous les DPGF
- **POST** `/api/v1/dpgf/` - Créer un nouveau DPGF
- **GET** `/api/v1/dpgf/{dpgf_id}` - Récupérer un DPGF spécifique
- **DELETE** `/api/v1/dpgf/{dpgf_id}` - Supprimer un DPGF

### 3. Gestion des Lots

#### Base URL: `/api/v1/lots`

- **GET** `/api/v1/lots/` - Récupérer tous les lots
- **POST** `/api/v1/lots/` - Créer un nouveau lot
- **GET** `/api/v1/lots/{lot_id}` - Récupérer un lot spécifique
- **DELETE** `/api/v1/lots/{lot_id}` - Supprimer un lot

### 4. Gestion des Sections

#### Base URL: `/api/v1/sections`

- **GET** `/api/v1/sections/` - Récupérer toutes les sections
- **POST** `/api/v1/sections/` - Créer une nouvelle section
- **GET** `/api/v1/sections/{section_id}` - Récupérer une section spécifique
- **DELETE** `/api/v1/sections/{section_id}` - Supprimer une section

### 5. Gestion des Éléments d'Ouvrage

#### Base URL: `/api/v1/element_ouvrages`

- **GET** `/api/v1/element_ouvrages/` - Récupérer tous les éléments d'ouvrage
  - Paramètres optionnels:
    - `include_section=true` - Inclure les détails de la section avec chaque élément
    - `skip` et `limit` - Pour la pagination

- **GET** `/api/v1/element_ouvrages/with_sections` - Récupérer tous les éléments avec leur section, ordonnés comme dans Excel
  - Paramètres optionnels:
    - `section_id` - Filtrer par ID de section
    - `skip` et `limit` - Pour la pagination

- **POST** `/api/v1/element_ouvrages/` - Créer un nouvel élément d'ouvrage

- **GET** `/api/v1/element_ouvrages/{element_id}` - Récupérer un élément spécifique
  - Paramètres optionnels:
    - `include_section=true` - Inclure les détails de la section avec l'élément

- **GET** `/api/v1/element_ouvrages/{element_id}/with_section` - Récupérer un élément avec sa section

- **DELETE** `/api/v1/element_ouvrages/{element_id}` - Supprimer un élément d'ouvrage

#### Exemples d'utilisation

```javascript
// Récupérer les éléments avec leur section, comme dans le fichier Excel
const fetchElementsWithSections = async () => {
  const response = await fetch('http://localhost:8000/api/v1/element_ouvrages/with_sections');
  return response.json();
}

// Filtrer les éléments par section
const fetchElementsBySection = async (sectionId) => {
  const response = await fetch(`http://localhost:8000/api/v1/element_ouvrages/with_sections?section_id=${sectionId}`);
  return response.json();
}
```

## Exemples d'utilisation avec JavaScript/Fetch

### 1. Récupérer tous les DPGF

```javascript
const fetchDPGFs = async () => {
  try {
    const response = await fetch('http://localhost:8000/api/v1/dpgf/', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const dpgfs = await response.json();
    console.log('DPGFs:', dpgfs);
    return dpgfs;
  } catch (error) {
    console.error('Erreur lors de la récupération des DPGFs:', error);
  }
};
```

### 2. Créer un nouveau DPGF

```javascript
const createDPGF = async (dpgfData) => {
  try {
    const response = await fetch('http://localhost:8000/api/v1/dpgf/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(dpgfData),
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const newDPGF = await response.json();
    console.log('DPGF créé:', newDPGF);
    return newDPGF;
  } catch (error) {
    console.error('Erreur lors de la création du DPGF:', error);
  }
};

// Exemple d'utilisation
const dpgfData = {
  nom: "DPGF Projet ABC",
  description: "Description du projet",
  client_id: 1,
  // autres champs selon votre schéma
};

createDPGF(dpgfData);
```

### 3. Récupérer un DPGF spécifique

```javascript
const fetchDPGFById = async (dpgfId) => {
  try {
    const response = await fetch(`http://localhost:8000/api/v1/dpgf/${dpgfId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('DPGF non trouvé');
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const dpgf = await response.json();
    console.log('DPGF:', dpgf);
    return dpgf;
  } catch (error) {
    console.error('Erreur lors de la récupération du DPGF:', error);
  }
};
```

### 4. Supprimer un DPGF

```javascript
const deleteDPGF = async (dpgfId) => {
  try {
    const response = await fetch(`http://localhost:8000/api/v1/dpgf/${dpgfId}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    console.log('DPGF supprimé avec succès');
    return true;
  } catch (error) {
    console.error('Erreur lors de la suppression du DPGF:', error);
    return false;
  }
};
```

## Exemples avec Axios

Si vous préférez utiliser Axios :

```javascript
import axios from 'axios';

// Configuration de base
const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Récupérer tous les DPGFs
const fetchDPGFs = async () => {
  try {
    const response = await api.get('/dpgf/');
    return response.data;
  } catch (error) {
    console.error('Erreur:', error.response?.data || error.message);
  }
};

// Créer un DPGF
const createDPGF = async (dpgfData) => {
  try {
    const response = await api.post('/dpgf/', dpgfData);
    return response.data;
  } catch (error) {
    console.error('Erreur:', error.response?.data || error.message);
  }
};
```

## Gestion des erreurs

### Codes de statut HTTP

- **200**: Succès
- **201**: Créé avec succès
- **204**: Supprimé avec succès (pas de contenu)
- **404**: Ressource non trouvée
- **422**: Erreur de validation des données
- **500**: Erreur interne du serveur

### Structure des erreurs

```javascript
{
  "detail": "Message d'erreur descriptif"
}
```

## Paramètres de requête

### Pagination

Pour les endpoints GET qui retournent des listes :

```javascript
// Récupérer les DPGFs avec pagination
const fetchDPGFsWithPagination = async (skip = 0, limit = 100) => {
  const response = await fetch(`http://localhost:8000/api/v1/dpgf/?skip=${skip}&limit=${limit}`);
  return response.json();
};
```

## Sécurité et bonnes pratiques

1. **Validation des données**: Toujours valider les données côté frontend avant envoi
2. **Gestion d'erreurs**: Implémenter une gestion d'erreurs robuste
3. **Loading states**: Afficher des indicateurs de chargement pendant les requêtes
4. **Timeout**: Configurer des timeouts appropriés pour vos requêtes

## Exemple complet avec React

```jsx
import React, { useState, useEffect } from 'react';

const DPGFList = () => {
  const [dpgfs, setDpgfs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const response = await fetch('http://localhost:8000/api/v1/dpgf/');
        
        if (!response.ok) {
          throw new Error('Erreur lors du chargement des DPGFs');
        }
        
        const data = await response.json();
        setDpgfs(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) return <div>Chargement...</div>;
  if (error) return <div>Erreur: {error}</div>;

  return (
    <div>
      <h1>Liste des DPGFs</h1>
      {dpgfs.map(dpgf => (
        <div key={dpgf.id}>
          <h3>{dpgf.nom}</h3>
          <p>{dpgf.description}</p>
        </div>
      ))}
    </div>
  );
};

export default DPGFList;
```

## Nouvelles fonctionnalités - Hiérarchie des données DPGF

Pour résoudre les problèmes d'éléments d'ouvrage qui apparaissaient dans les mauvaises sections ou DPGF, nous avons ajouté de nouveaux endpoints qui permettent de récupérer les données avec leur hiérarchie complète.

### 1. Structure complète d'un DPGF

#### Endpoint: `GET /api/v1/dpgf/{dpgf_id}/structure`

Cet endpoint retourne la structure complète d'un DPGF incluant tous ses lots, sections et éléments d'ouvrage organisés de manière hiérarchique, comme dans un fichier Excel. C'est la solution recommandée pour afficher correctement les données DPGF.

```javascript
const fetchDPGFStructure = async (dpgfId) => {
  const response = await fetch(`http://localhost:8000/api/v1/dpgf/${dpgfId}/structure`);
  return response.json();
}
```

La réponse suit une structure hiérarchique:
```json
{
  "id_dpgf": 1,
  "nom_projet": "Projet ABC",
  "date_dpgf": "2025-06-01",
  "statut_offre": "en_cours",
  "lots": [
    {
      "id_lot": 1,
      "numero_lot": "01",
      "nom_lot": "Gros-oeuvre",
      "sections": [
        {
          "id_section": 1,
          "numero_section": "01.01",
          "titre_section": "Fondations",
          "niveau_hierarchique": 1,
          "elements": [
            {
              "id_element": 1,
              "designation_exacte": "Béton de fondation",
              "unite": "m3",
              "quantite": 25.5,
              "prix_unitaire_ht": 120.0,
              "prix_total_ht": 3060.0,
              "offre_acceptee": false
            }
          ]
        }
      ]
    }
  ]
}
```

### 2. Éléments d'ouvrage par DPGF

#### Endpoint: `GET /api/v1/element_ouvrages/with_sections?dpgf_id={dpgf_id}`

Cet endpoint permet de récupérer tous les éléments d'ouvrage appartenant à un DPGF spécifique, avec les informations de leur section.

```javascript
const fetchElementsByDPGF = async (dpgfId) => {
  const response = await fetch(`http://localhost:8000/api/v1/element_ouvrages/with_sections?dpgf_id=${dpgfId}`);
  return response.json();
}
```

### 3. Éléments d'ouvrage par lot

#### Endpoint: `GET /api/v1/element_ouvrages/with_sections?lot_id={lot_id}`

Récupère tous les éléments d'ouvrage appartenant à un lot spécifique.

```javascript
const fetchElementsByLot = async (lotId) => {
  const response = await fetch(`http://localhost:8000/api/v1/element_ouvrages/with_sections?lot_id=${lotId}`);
  return response.json();
}
```

### 4. Arborescence des sections

#### Endpoint: `GET /api/v1/sections/tree?dpgf_id={dpgf_id}`

Récupère l'arborescence hiérarchique des sections pour un DPGF spécifique.

```javascript
const fetchSectionTree = async (dpgfId) => {
  const response = await fetch(`http://localhost:8000/api/v1/sections/tree?dpgf_id=${dpgfId}`);
  return response.json();
}
```

### Exemple d'utilisation avec React

```jsx
import React, { useState, useEffect } from 'react';

const DPGFViewer = ({ dpgfId }) => {
  const [dpgfStructure, setDpgfStructure] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const response = await fetch(`http://localhost:8000/api/v1/dpgf/${dpgfId}/structure`);
        
        if (!response.ok) {
          throw new Error(`Erreur ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        setDpgfStructure(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [dpgfId]);

  if (loading) return <div>Chargement...</div>;
  if (error) return <div>Erreur: {error}</div>;
  if (!dpgfStructure) return <div>Aucune donnée disponible</div>;

  return (
    <div>
      <h1>{dpgfStructure.nom_projet}</h1>
      <p>Date: {new Date(dpgfStructure.date_dpgf).toLocaleDateString()}</p>
      <p>Statut: {dpgfStructure.statut_offre}</p>
      
      {dpgfStructure.lots.map(lot => (
        <div key={lot.id_lot} className="lot">
          <h2>{lot.numero_lot} - {lot.nom_lot}</h2>
          
          {lot.sections.map(section => (
            <div key={section.id_section} className="section" style={{ marginLeft: `${section.niveau_hierarchique * 20}px` }}>
              <h3>{section.numero_section} - {section.titre_section}</h3>
              
              {section.elements.length > 0 ? (
                <table className="elements-table">
                  <thead>
                    <tr>
                      <th>Désignation</th>
                      <th>Unité</th>
                      <th>Quantité</th>
                      <th>Prix unitaire HT</th>
                      <th>Prix total HT</th>
                    </tr>
                  </thead>
                  <tbody>
                    {section.elements.map(element => (
                      <tr key={element.id_element}>
                        <td>{element.designation_exacte}</td>
                        <td>{element.unite}</td>
                        <td>{element.quantite}</td>
                        <td>{element.prix_unitaire_ht.toFixed(2)} €</td>
                        <td>{element.prix_total_ht.toFixed(2)} €</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p>Aucun élément dans cette section</p>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
};

export default DPGFViewer;
```

## Support

Pour toute question ou problème :
1. Vérifiez que le serveur backend est démarré
2. Consultez la documentation Swagger à `http://localhost:8000/docs`
3. Vérifiez les logs du serveur pour les erreurs détaillées
4. Assurez-vous que CORS est bien configuré pour votre domaine frontend

## Endpoints API

### Recherche d'éléments d'ouvrage

#### Recherche multicritères

```
GET /api/v1/element-search/search/
```

Permet de rechercher des éléments d'ouvrage avec filtrage multicritères et tri personnalisé.

**Paramètres de requête**:
- `q` (optionnel): Texte de recherche (recherche dans la désignation et description)
- `client_id` (optionnel): ID du client pour filtrer les éléments
- `dpgf_id` (optionnel): ID du DPGF pour filtrer les éléments
- `lot_id` (optionnel): ID du lot pour filtrer les éléments
- `section_id` (optionnel): ID de la section pour filtrer les éléments
- `lot_numero` (optionnel): Numéro de lot pour filtrer les éléments
- `min_price` (optionnel): Prix unitaire minimum
- `max_price` (optionnel): Prix unitaire maximum
- `sort_by` (optionnel, défaut="relevance"): Critère de tri, valeurs possibles: 
  - `relevance`: Par pertinence (défaut, uniquement si `q` est fourni)
  - `price`: Par prix unitaire
  - `date`: Par date de création
  - `designation`: Par ordre alphabétique de désignation
  - `dpgf`: Par nom du DPGF
  - `lot`: Par numéro et nom du lot
  - `section`: Par numéro et nom de la section
- `descending` (optionnel, défaut=true): Ordre décroissant si true, croissant si false
- `limit` (optionnel, défaut=100): Nombre maximum de résultats (1-500)
- `offset` (optionnel, défaut=0): Décalage pour la pagination

**Exemple de réponse**:
```json
{
  "total": 158,
  "offset": 0,
  "limit": 100,
  "results": [
    {
      "id": 123,
      "designation": "Béton de fondation",
      "description": "Béton dosé à 350kg/m3",
      "unite": "m³",
      "quantite": 15.5,
      "prix_unitaire": 120.0,
      "prix_total": 1860.0,
      "lot": {
        "id": 5,
        "numero": "03",
        "nom": "Gros œuvre"
      },
      "section": {
        "id": 12,
        "numero": "3.2",
        "titre": "Fondations"
      },
      "dpgf": {
        "id": 3,
        "nom": "Projet Résidence ABC"
      },
      "client": {
        "id": 2,
        "nom": "Client XYZ"
      },
      "created_at": "2025-06-20T15:30:45",
      "updated_at": "2025-06-21T10:15:20"
    },
    // ... autres éléments ...
  ]
}
```

#### Suggestions de recherche

```
GET /api/v1/element-search/suggestions/
```

Retourne des suggestions de recherche basées sur un texte partiel pour l'autocomplétion.

**Paramètres de requête**:
- `q` (requis): Texte partiel pour les suggestions (minimum 2 caractères)
- `limit` (optionnel, défaut=10): Nombre maximum de suggestions (1-20)

**Exemple de réponse**:
```json
[
  "Béton de fondation",
  "Béton armé",
  "Béton de propreté",
  "Béton désactivé"
]
```

#### Statistiques des éléments

```
GET /api/v1/element-search/statistics/
```

Retourne des statistiques sur les éléments d'ouvrage, éventuellement filtrées.

**Paramètres de requête**:
- `client_id` (optionnel): Filtrer par client
- `dpgf_id` (optionnel): Filtrer par DPGF
- `lot_id` (optionnel): Filtrer par lot

**Exemple de réponse**:
```json
{
  "total_count": 1245,
  "price_statistics": {
    "min_price": 0.5,
    "max_price": 15000.0,
    "avg_price": 257.85,
    "total_price": 321023.25
  },
  "units": {
    "m²": 458,
    "m³": 156,
    "ml": 125,
    "u": 387,
    "kg": 68,
    "ens": 51
  }
}
```
