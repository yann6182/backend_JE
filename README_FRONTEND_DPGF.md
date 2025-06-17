# Guide d'implémentation Frontend - Upload et Import DPGF

## Vue d'ensemble

Ce guide explique comment implémenter côté frontend l'upload et l'import automatique des fichiers DPGF Excel. Lorsqu'un fichier est uploadé, le backend lance automatiquement le script d'import qui :

1. Détecte automatiquement le client
2. Crée ou récupère le DPGF
3. Importe tous les lots, sections et éléments d'ouvrage
4. Classifie les éléments (avec IA optionnelle)

## Configuration de l'IA Gemini (optionnel)

Pour utiliser la classification avancée par IA, le serveur doit être configuré avec une clé API Google Gemini :

### Côté serveur (backend)

1. **Obtenir une clé API** : https://makersuite.google.com/app/apikey

2. **Configurer la variable d'environnement** :
   ```bash
   # Windows
   set GEMINI_API_KEY=votre_cle_api_ici
   
   # Linux/Mac
   export GEMINI_API_KEY=votre_cle_api_ici
   
   # Ou dans un fichier .env
   GEMINI_API_KEY=votre_cle_api_ici
   ```

3. **Installer le module** (si pas déjà fait) :
   ```bash
   pip install google-generativeai
   ```

4. **Tester la configuration** :
   ```bash
   python setup_gemini.py --test
   ```

5. **Redémarrer le serveur FastAPI**

### Côté frontend

Une fois Gemini configuré côté serveur, vous pouvez activer la classification IA en passant `use_gemini: true` :

```javascript
// Avec IA
formData.append('use_gemini', true);

// Sans IA (plus rapide)
formData.append('use_gemini', false);
```

### Avantages de Gemini

- **Classification intelligente** : Catégorise automatiquement les éléments d'ouvrage
- **Détection de patterns** : Reconnaît les types de travaux complexes  
- **Amélioration continue** : Apprend des patterns récurrents via le cache

### Inconvénients

- **Plus lent** : Ajoute du temps de traitement
- **Coût** : Utilise l'API payante de Google
- **Dépendance externe** : Nécessite une connexion internet

## Endpoints disponibles

### 1. Upload et Import automatique
```http
POST /api/v1/dpgf/upload
Content-Type: multipart/form-data

Parameters:
- file: File (required) - Fichier Excel DPGF
- use_gemini: boolean (optional, default: false) - Utiliser l'IA pour la classification
```

**Note importante**: Pour utiliser Gemini, la clé API doit être configurée côté serveur via la variable d'environnement `GEMINI_API_KEY`.

### 2. Vérifier le statut d'un DPGF
```http
GET /api/v1/dpgf/{dpgf_id}
```

### 3. Lister tous les DPGFs
```http
GET /api/v1/dpgf
```

## Implémentation Frontend

### React/JavaScript avec Axios

```javascript
// Composant d'upload de fichier DPGF
import React, { useState } from 'react';
import axios from 'axios';

const DPGFUploader = () => {
  const [file, setFile] = useState(null);
  const [useAI, setUseAI] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleFileChange = (event) => {
    setFile(event.target.files[0]);
    setError(null);
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Veuillez sélectionner un fichier');
      return;
    }

    // Vérifier que c'est un fichier Excel
    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
      setError('Veuillez sélectionner un fichier Excel (.xlsx ou .xls)');
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('use_gemini', useAI);

    try {
      const response = await axios.post('/api/v1/dpgf/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 300000, // 5 minutes timeout pour les gros fichiers
      });

      setResult(response.data);
      console.log('Import réussi:', response.data);
      
    } catch (err) {
      console.error('Erreur upload:', err);
      setError(err.response?.data?.detail || 'Erreur lors de l\'upload');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dpgf-uploader">
      <h3>Upload fichier DPGF</h3>
      
      <div className="file-input">
        <input
          type="file"
          accept=".xlsx,.xls"
          onChange={handleFileChange}
          disabled={loading}
        />
      </div>

      <div className="options">
        <label>
          <input
            type="checkbox"
            checked={useAI}
            onChange={(e) => setUseAI(e.target.checked)}
            disabled={loading}
          />
          Utiliser l'IA pour la classification avancée
        </label>
      </div>

      <button
        onClick={handleUpload}
        disabled={!file || loading}
        className="upload-btn"
      >
        {loading ? 'Import en cours...' : 'Importer DPGF'}
      </button>

      {loading && (
        <div className="loading">
          <p>⏳ Import en cours... Cela peut prendre plusieurs minutes</p>
          <div className="progress-bar">
            {/* Vous pouvez ajouter une barre de progression */}
          </div>
        </div>
      )}

      {error && (
        <div className="error">
          <p>❌ Erreur: {error}</p>
        </div>
      )}

      {result && (
        <div className="success">
          <h4>✅ Import réussi!</h4>
          <div className="result-details">
            <p><strong>Client:</strong> {result.client_name}</p>
            <p><strong>Projet:</strong> {result.project_name}</p>
            <p><strong>DPGF ID:</strong> {result.dpgf_id}</p>
            <div className="stats">
              <h5>Statistiques d'import:</h5>
              <ul>
                <li>Sections créées: {result.stats?.sections_created}</li>
                <li>Éléments créés: {result.stats?.elements_created}</li>
                <li>Lots créés: {result.stats?.lots_created}</li>
                <li>Erreurs: {result.stats?.errors}</li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DPGFUploader;
```

### Vue.js avec Axios

```vue
<template>
  <div class="dpgf-uploader">
    <h3>Upload fichier DPGF</h3>
    
    <div class="file-input">
      <input
        type="file"
        ref="fileInput"
        accept=".xlsx,.xls"
        @change="handleFileChange"
        :disabled="loading"
      />
    </div>

    <div class="options">
      <label>
        <input
          type="checkbox"
          v-model="useAI"
          :disabled="loading"
        />
        Utiliser l'IA pour la classification avancée
      </label>
    </div>

    <button
      @click="handleUpload"
      :disabled="!file || loading"
      class="upload-btn"
    >
      {{ loading ? 'Import en cours...' : 'Importer DPGF' }}
    </button>

    <div v-if="loading" class="loading">
      <p>⏳ Import en cours... Cela peut prendre plusieurs minutes</p>
    </div>

    <div v-if="error" class="error">
      <p>❌ Erreur: {{ error }}</p>
    </div>

    <div v-if="result" class="success">
      <h4>✅ Import réussi!</h4>
      <div class="result-details">
        <p><strong>Client:</strong> {{ result.client_name }}</p>
        <p><strong>Projet:</strong> {{ result.project_name }}</p>
        <p><strong>DPGF ID:</strong> {{ result.dpgf_id }}</p>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'DPGFUploader',
  data() {
    return {
      file: null,
      useAI: false,
      loading: false,
      result: null,
      error: null
    };
  },
  methods: {
    handleFileChange(event) {
      this.file = event.target.files[0];
      this.error = null;
    },

    async handleUpload() {
      if (!this.file) {
        this.error = 'Veuillez sélectionner un fichier';
        return;
      }

      if (!this.file.name.endsWith('.xlsx') && !this.file.name.endsWith('.xls')) {
        this.error = 'Veuillez sélectionner un fichier Excel (.xlsx ou .xls)';
        return;
      }

      this.loading = true;
      this.error = null;

      const formData = new FormData();
      formData.append('file', this.file);
      formData.append('use_gemini', this.useAI);

      try {
        const response = await axios.post('/api/v1/dpgf/upload', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          timeout: 300000,
        });

        this.result = response.data;
        this.$emit('upload-success', response.data);
        
      } catch (err) {
        console.error('Erreur upload:', err);
        this.error = err.response?.data?.detail || 'Erreur lors de l\'upload';
      } finally {
        this.loading = false;
      }
    }
  }
};
</script>
```

### Vanilla JavaScript (sans framework)

```javascript
// HTML
/*
<div id="dpgf-uploader">
  <h3>Upload fichier DPGF</h3>
  <input type="file" id="file-input" accept=".xlsx,.xls">
  <label>
    <input type="checkbox" id="use-ai"> Utiliser l'IA
  </label>
  <button id="upload-btn">Importer DPGF</button>
  <div id="result"></div>
</div>
*/

// JavaScript
class DPGFUploader {
  constructor() {
    this.fileInput = document.getElementById('file-input');
    this.uploadBtn = document.getElementById('upload-btn');
    this.useAICheckbox = document.getElementById('use-ai');
    this.resultDiv = document.getElementById('result');
    
    this.uploadBtn.addEventListener('click', () => this.handleUpload());
  }

  async handleUpload() {
    const file = this.fileInput.files[0];
    
    if (!file) {
      this.showError('Veuillez sélectionner un fichier');
      return;
    }

    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
      this.showError('Veuillez sélectionner un fichier Excel');
      return;
    }

    this.setLoading(true);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('use_gemini', this.useAICheckbox.checked);

    try {
      const response = await fetch('/api/v1/dpgf/upload', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      this.showSuccess(result);
      
    } catch (error) {
      this.showError('Erreur lors de l\'upload: ' + error.message);
    } finally {
      this.setLoading(false);
    }
  }

  setLoading(loading) {
    this.uploadBtn.disabled = loading;
    this.uploadBtn.textContent = loading ? 'Import en cours...' : 'Importer DPGF';
    this.fileInput.disabled = loading;
  }

  showError(message) {
    this.resultDiv.innerHTML = `<div class="error">❌ ${message}</div>`;
  }

  showSuccess(result) {
    this.resultDiv.innerHTML = `
      <div class="success">
        <h4>✅ Import réussi!</h4>
        <p><strong>Client:</strong> ${result.client_name}</p>
        <p><strong>Projet:</strong> ${result.project_name}</p>
        <p><strong>DPGF ID:</strong> ${result.dpgf_id}</p>
      </div>
    `;
  }
}

// Initialiser quand le DOM est chargé
document.addEventListener('DOMContentLoaded', () => {
  new DPGFUploader();
});
```

## Gestion des erreurs

Le backend peut retourner différents types d'erreurs :

```javascript
// Gestion des erreurs courantes
const handleUploadError = (error) => {
  if (error.response) {
    // Erreur HTTP du serveur
    switch (error.response.status) {
      case 400:
        return 'Fichier invalide ou format non supporté';
      case 413:
        return 'Fichier trop volumineux';
      case 422:
        return 'Erreur de validation: ' + error.response.data.detail;
      case 500:
        return 'Erreur serveur lors du traitement du fichier';
      default:
        return `Erreur ${error.response.status}: ${error.response.data.detail}`;
    }
  } else if (error.request) {
    // Pas de réponse du serveur
    return 'Impossible de contacter le serveur';
  } else {
    // Erreur de configuration
    return 'Erreur de configuration: ' + error.message;
  }
};
```

## Format de la réponse

En cas de succès, l'API retourne :

```json
{
  "message": "DPGF importé avec succès",
  "dpgf_id": 123,
  "client_name": "CDC HABITAT",
  "project_name": "CDC HABITAT - Projet Example - Lot 2",
  "stats": {
    "total_rows": 450,
    "sections_created": 12,
    "elements_created": 380,
    "sections_reused": 3,
    "lots_created": 1,
    "lots_reused": 0,
    "errors": 2,
    "gemini_calls": 15
  }
}
```

## CSS suggéré

```css
.dpgf-uploader {
  max-width: 600px;
  margin: 20px auto;
  padding: 20px;
  border: 1px solid #ddd;
  border-radius: 8px;
}

.file-input {
  margin: 15px 0;
}

.upload-btn {
  background-color: #007bff;
  color: white;
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  margin: 10px 0;
}

.upload-btn:disabled {
  background-color: #6c757d;
  cursor: not-allowed;
}

.loading {
  color: #007bff;
  font-style: italic;
}

.error {
  color: #dc3545;
  background-color: #f8d7da;
  padding: 10px;
  border-radius: 4px;
  margin: 10px 0;
}

.success {
  color: #155724;
  background-color: #d4edda;
  padding: 10px;
  border-radius: 4px;
  margin: 10px 0;
}

.result-details {
  margin-top: 10px;
}

.stats ul {
  list-style-type: none;
  padding-left: 0;
}

.stats li {
  padding: 2px 0;
}
```

## Notes importantes

1. **Timeout**: Les imports peuvent prendre du temps (plusieurs minutes pour de gros fichiers). Configurez un timeout approprié.

2. **Taille de fichier**: Vérifiez les limites de taille côté serveur.

3. **Format**: Seuls les fichiers Excel (.xlsx, .xls) sont acceptés.

4. **IA optionnelle**: La classification par IA est optionnelle mais améliore la qualité des données.

5. **Feedback utilisateur**: Affichez toujours un feedback visuel pendant le traitement.

6. **Gestion d'état**: Considérez utiliser un store (Redux, Vuex, etc.) pour gérer l'état global des DPGFs importés.
