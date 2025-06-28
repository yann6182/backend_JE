# Guide d'implémentation Frontend - Analyse de fichiers DPGF

Ce document détaille comment implémenter l'interface frontend pour permettre aux utilisateurs de déposer des fichiers DPGF, les analyser et visualiser les correspondances trouvées dans la base de données.

## Vue d'ensemble

L'interface permet aux utilisateurs de :
1. **Télécharger** un fichier DPGF (format Excel .xlsx/.xls)
2. **Analyser** automatiquement le contenu du fichier
3. **Visualiser** les correspondances trouvées sous forme de tableau
4. **Comparer** les éléments avec les données existantes
5. **Rechercher** manuellement des éléments spécifiques

## Architecture de l'API

### Endpoints disponibles

#### 1. Analyse complète de fichier
```http
POST /api/v1/dpgf-analysis/upload-analyze
Content-Type: multipart/form-data
```

**Paramètres :**
- `file` (fichier) : Fichier DPGF à analyser (.xlsx ou .xls)
- `threshold` (query, optionnel) : Seuil de correspondance en pourcentage (défaut: 70.0)

**Réponse :**
```json
{
  "success": true,
  "elements_count": 150,
  "matches": [
    {
      "element_id": 1234,
      "libelle": "Béton C25/30 pour dalle",
      "prix_unitaire": 120.50,
      "quantite": 25.0,
      "unite": "m³",
      "score": 85.5,
      "dpgf_source": "Projet ABC - Phase 1",
      "lot": "Lot 2 - Gros œuvre",
      "section": "2.1 Fondations → 2.1.1 Béton armé"
    }
  ],
  "error": null
}
```

#### 2. Recherche manuelle d'éléments
```http
GET /api/v1/dpgf-analysis/search-elements
```

**Paramètres :**
- `query` (string) : Texte à rechercher
- `threshold` (query, optionnel) : Seuil de correspondance en pourcentage (défaut: 70.0)

**Réponse :** Même format que l'analyse complète, mais uniquement les correspondances pour la requête.

## Implémentation Frontend

### 1. Interface de téléchargement

#### Structure HTML recommandée
```html
<div class="dpgf-analyzer">
  <!-- Zone de téléchargement -->
  <div class="upload-zone">
    <input type="file" id="dpgf-file" accept=".xlsx,.xls" />
    <div class="upload-area" onclick="document.getElementById('dpgf-file').click()">
      <div class="upload-icon">📁</div>
      <p>Cliquez ici ou glissez-déposez votre fichier DPGF</p>
      <small>Formats acceptés : .xlsx, .xls</small>
    </div>
  </div>

  <!-- Paramètres d'analyse -->
  <div class="analysis-settings">
    <label for="threshold">Seuil de correspondance :</label>
    <input type="range" id="threshold" min="50" max="100" value="70" />
    <span id="threshold-value">70%</span>
  </div>

  <!-- Bouton d'analyse -->
  <button id="analyze-btn" disabled>Analyser le fichier</button>

  <!-- Indicateur de progression -->
  <div class="progress-indicator" style="display: none;">
    <div class="spinner"></div>
    <p>Analyse en cours...</p>
  </div>
</div>
```

#### CSS recommandé
```css
.dpgf-analyzer {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.upload-zone {
  margin-bottom: 20px;
}

.upload-area {
  border: 2px dashed #ccc;
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.3s;
}

.upload-area:hover {
  border-color: #007bff;
}

.upload-area.dragover {
  border-color: #007bff;
  background-color: #f8f9fa;
}

.upload-icon {
  font-size: 48px;
  margin-bottom: 10px;
}

.analysis-settings {
  margin-bottom: 20px;
  padding: 15px;
  background-color: #f8f9fa;
  border-radius: 5px;
}

.progress-indicator {
  text-align: center;
  padding: 20px;
}

.spinner {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #3498db;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 2s linear infinite;
  margin: 0 auto 10px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
```

### 2. JavaScript pour la gestion des fichiers

```javascript
class DPGFAnalyzer {
  constructor() {
    this.initializeEventListeners();
    this.apiBaseUrl = '/api/v1/dpgf-analysis';
  }

  initializeEventListeners() {
    const fileInput = document.getElementById('dpgf-file');
    const uploadArea = document.querySelector('.upload-area');
    const analyzeBtn = document.getElementById('analyze-btn');
    const thresholdSlider = document.getElementById('threshold');
    const thresholdValue = document.getElementById('threshold-value');

    // Gestion du drag & drop
    uploadArea.addEventListener('dragover', this.handleDragOver.bind(this));
    uploadArea.addEventListener('dragleave', this.handleDragLeave.bind(this));
    uploadArea.addEventListener('drop', this.handleDrop.bind(this));

    // Gestion de la sélection de fichier
    fileInput.addEventListener('change', this.handleFileSelect.bind(this));

    // Gestion du bouton d'analyse
    analyzeBtn.addEventListener('click', this.analyzeFile.bind(this));

    // Gestion du seuil
    thresholdSlider.addEventListener('input', (e) => {
      thresholdValue.textContent = e.target.value + '%';
    });
  }

  handleDragOver(e) {
    e.preventDefault();
    e.currentTarget.classList.add('dragover');
  }

  handleDragLeave(e) {
    e.currentTarget.classList.remove('dragover');
  }

  handleDrop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('dragover');
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      this.selectFile(files[0]);
    }
  }

  handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
      this.selectFile(file);
    }
  }

  selectFile(file) {
    // Vérifier le format
    const allowedExtensions = ['.xlsx', '.xls'];
    const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!allowedExtensions.includes(fileExtension)) {
      alert('Format de fichier non supporté. Utilisez .xlsx ou .xls');
      return;
    }

    // Vérifier la taille (limite à 10MB)
    if (file.size > 10 * 1024 * 1024) {
      alert('Le fichier est trop volumineux (limite: 10MB)');
      return;
    }

    this.selectedFile = file;
    document.getElementById('analyze-btn').disabled = false;
    
    // Mettre à jour l'affichage
    document.querySelector('.upload-area p').textContent = 
      `Fichier sélectionné: ${file.name}`;
  }

  async analyzeFile() {
    if (!this.selectedFile) {
      alert('Veuillez sélectionner un fichier');
      return;
    }

    const threshold = document.getElementById('threshold').value;
    
    // Afficher l'indicateur de progression
    this.showProgress(true);
    document.getElementById('analyze-btn').disabled = true;

    try {
      const formData = new FormData();
      formData.append('file', this.selectedFile);

      const response = await fetch(
        `${this.apiBaseUrl}/upload-analyze?threshold=${threshold}`,
        {
          method: 'POST',
          body: formData
        }
      );

      if (!response.ok) {
        throw new Error(`Erreur HTTP: ${response.status}`);
      }

      const result = await response.json();
      
      if (result.success) {
        this.displayResults(result);
      } else {
        throw new Error(result.error || 'Erreur inconnue');
      }

    } catch (error) {
      console.error('Erreur lors de l\'analyse:', error);
      alert(`Erreur lors de l'analyse: ${error.message}`);
    } finally {
      this.showProgress(false);
      document.getElementById('analyze-btn').disabled = false;
    }
  }

  showProgress(show) {
    const progressIndicator = document.querySelector('.progress-indicator');
    progressIndicator.style.display = show ? 'block' : 'none';
  }

  displayResults(data) {
    // Créer ou mettre à jour le tableau de résultats
    let resultsContainer = document.getElementById('results-container');
    
    if (!resultsContainer) {
      resultsContainer = document.createElement('div');
      resultsContainer.id = 'results-container';
      document.querySelector('.dpgf-analyzer').appendChild(resultsContainer);
    }

    resultsContainer.innerHTML = this.generateResultsHTML(data);
    
    // Ajouter les fonctionnalités interactives
    this.initializeResultsInteractions();
  }

  generateResultsHTML(data) {
    const { elements_count, matches } = data;

    return `
      <div class="results-section">
        <div class="results-header">
          <h3>Résultats de l'analyse</h3>
          <div class="results-stats">
            <span class="stat">
              <strong>${elements_count}</strong> éléments analysés
            </span>
            <span class="stat">
              <strong>${matches.length}</strong> correspondances trouvées
            </span>
          </div>
        </div>

        <div class="search-box">
          <input type="text" id="results-search" placeholder="Rechercher dans les résultats..." />
          <button id="manual-search-btn">Recherche manuelle</button>
        </div>

        <div class="results-table-container">
          <table class="results-table">
            <thead>
              <tr>
                <th>Score</th>
                <th>Libellé</th>
                <th>Prix unitaire</th>
                <th>Quantité</th>
                <th>Unité</th>
                <th>Source DPGF</th>
                <th>Lot</th>
                <th>Section</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${matches.map(match => this.generateMatchRow(match)).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  generateMatchRow(match) {
    return `
      <tr class="match-row" data-element-id="${match.element_id}">
        <td class="score-cell">
          <div class="score-indicator">
            <div class="score-bar" style="width: ${match.score}%"></div>
            <span class="score-text">${match.score.toFixed(1)}%</span>
          </div>
        </td>
        <td class="libelle-cell" title="${match.libelle}">
          ${this.truncateText(match.libelle, 60)}
        </td>
        <td class="price-cell">
          ${this.formatPrice(match.prix_unitaire)} €
        </td>
        <td class="quantity-cell">
          ${this.formatQuantity(match.quantite)}
        </td>
        <td class="unit-cell">${match.unite || '-'}</td>
        <td class="dpgf-cell" title="${match.dpgf_source}">
          ${this.truncateText(match.dpgf_source, 25)}
        </td>
        <td class="lot-cell" title="${match.lot}">
          ${this.truncateText(match.lot, 20)}
        </td>
        <td class="section-cell" title="${match.section}">
          ${this.truncateText(match.section, 30)}
        </td>
        <td class="actions-cell">
          <button class="btn-details" onclick="dpgfAnalyzer.showDetails(${match.element_id})">
            Détails
          </button>
        </td>
      </tr>
    `;
  }

  initializeResultsInteractions() {
    // Recherche dans les résultats
    const searchInput = document.getElementById('results-search');
    if (searchInput) {
      searchInput.addEventListener('input', this.filterResults.bind(this));
    }

    // Recherche manuelle
    const manualSearchBtn = document.getElementById('manual-search-btn');
    if (manualSearchBtn) {
      manualSearchBtn.addEventListener('click', this.performManualSearch.bind(this));
    }
  }

  filterResults(e) {
    const query = e.target.value.toLowerCase();
    const rows = document.querySelectorAll('.match-row');

    rows.forEach(row => {
      const text = row.textContent.toLowerCase();
      row.style.display = text.includes(query) ? '' : 'none';
    });
  }

  async performManualSearch() {
    const query = document.getElementById('results-search').value.trim();
    
    if (!query) {
      alert('Veuillez saisir un terme de recherche');
      return;
    }

    const threshold = document.getElementById('threshold').value;

    try {
      const response = await fetch(
        `${this.apiBaseUrl}/search-elements?query=${encodeURIComponent(query)}&threshold=${threshold}`
      );

      if (!response.ok) {
        throw new Error(`Erreur HTTP: ${response.status}`);
      }

      const results = await response.json();
      
      // Afficher les résultats de la recherche manuelle
      this.displaySearchResults(results, query);

    } catch (error) {
      console.error('Erreur lors de la recherche:', error);
      alert(`Erreur lors de la recherche: ${error.message}`);
    }
  }

  displaySearchResults(results, query) {
    // Créer une section pour les résultats de recherche manuelle
    let searchResultsContainer = document.getElementById('search-results-container');
    
    if (!searchResultsContainer) {
      searchResultsContainer = document.createElement('div');
      searchResultsContainer.id = 'search-results-container';
      document.getElementById('results-container').appendChild(searchResultsContainer);
    }

    searchResultsContainer.innerHTML = `
      <div class="search-results-section">
        <h4>Résultats de recherche pour "${query}"</h4>
        <p>${results.length} correspondance(s) trouvée(s)</p>
        
        <div class="search-results-table-container">
          <table class="results-table">
            <thead>
              <tr>
                <th>Score</th>
                <th>Libellé</th>
                <th>Prix unitaire</th>
                <th>Quantité</th>
                <th>Unité</th>
                <th>Source DPGF</th>
                <th>Lot</th>
                <th>Section</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${results.map(match => this.generateMatchRow(match)).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  showDetails(elementId) {
    // Implémenter l'affichage des détails d'un élément
    // Peut ouvrir une modal avec plus d'informations
    console.log('Affichage des détails pour l\'élément ID:', elementId);
    
    // Exemple d'implémentation modal
    alert(`Fonctionnalité de détails à implémenter pour l'élément ${elementId}`);
  }

  // Méthodes utilitaires
  truncateText(text, maxLength) {
    if (!text) return '-';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  }

  formatPrice(price) {
    return price ? price.toFixed(2) : '0.00';
  }

  formatQuantity(quantity) {
    return quantity ? quantity.toFixed(2) : '0.00';
  }
}

// Initialiser l'analyseur au chargement de la page
document.addEventListener('DOMContentLoaded', () => {
  window.dpgfAnalyzer = new DPGFAnalyzer();
});
```

### 3. CSS pour les résultats

```css
.results-section {
  margin-top: 30px;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  overflow: hidden;
}

.results-header {
  background-color: #f8f9fa;
  padding: 20px;
  border-bottom: 1px solid #dee2e6;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.results-stats {
  display: flex;
  gap: 20px;
}

.stat {
  background-color: white;
  padding: 8px 12px;
  border-radius: 4px;
  border: 1px solid #dee2e6;
}

.search-box {
  padding: 15px;
  border-bottom: 1px solid #dee2e6;
  display: flex;
  gap: 10px;
  align-items: center;
}

.search-box input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #ced4da;
  border-radius: 4px;
}

.results-table-container {
  overflow-x: auto;
}

.results-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.results-table th {
  background-color: #f8f9fa;
  padding: 12px;
  text-align: left;
  border-bottom: 2px solid #dee2e6;
  font-weight: 600;
}

.results-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #dee2e6;
  vertical-align: top;
}

.match-row:hover {
  background-color: #f8f9fa;
}

.score-cell {
  width: 100px;
}

.score-indicator {
  position: relative;
  background-color: #e9ecef;
  height: 20px;
  border-radius: 10px;
  overflow: hidden;
}

.score-bar {
  height: 100%;
  background: linear-gradient(90deg, #dc3545 0%, #ffc107 50%, #28a745 100%);
  transition: width 0.3s ease;
}

.score-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 11px;
  font-weight: bold;
  color: white;
  text-shadow: 0 0 2px rgba(0,0,0,0.5);
}

.price-cell, .quantity-cell {
  text-align: right;
  font-family: monospace;
}

.btn-details {
  background-color: #007bff;
  color: white;
  border: none;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.btn-details:hover {
  background-color: #0056b3;
}

/* Responsive */
@media (max-width: 768px) {
  .results-header {
    flex-direction: column;
    gap: 15px;
    align-items: flex-start;
  }

  .results-stats {
    flex-direction: column;
    gap: 10px;
  }

  .search-box {
    flex-direction: column;
    align-items: stretch;
  }

  .results-table {
    font-size: 12px;
  }

  .results-table th,
  .results-table td {
    padding: 8px;
  }
}
```

## Fonctionnalités avancées

### 1. Export des résultats
```javascript
// Ajouter un bouton d'export dans l'interface
exportResults() {
  const results = this.currentResults;
  const csv = this.convertToCSV(results);
  this.downloadCSV(csv, 'resultats_analyse_dpgf.csv');
}

convertToCSV(data) {
  const headers = ['Score', 'Libellé', 'Prix unitaire', 'Quantité', 'Unité', 'Source DPGF', 'Lot', 'Section'];
  const csvContent = [
    headers.join(','),
    ...data.map(row => [
      row.score,
      `"${row.libelle}"`,
      row.prix_unitaire,
      row.quantite,
      row.unite || '',
      `"${row.dpgf_source}"`,
      `"${row.lot}"`,
      `"${row.section}"`
    ].join(','))
  ].join('\n');
  
  return csvContent;
}
```

### 2. Sauvegarde des analyses
```javascript
// Sauvegarder les résultats d'analyse pour consultation ultérieure
saveAnalysis() {
  const analysisData = {
    timestamp: new Date().toISOString(),
    filename: this.selectedFile.name,
    threshold: document.getElementById('threshold').value,
    results: this.currentResults
  };
  
  localStorage.setItem(`dpgf_analysis_${Date.now()}`, JSON.stringify(analysisData));
}

loadSavedAnalyses() {
  const saved = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key.startsWith('dpgf_analysis_')) {
      saved.push(JSON.parse(localStorage.getItem(key)));
    }
  }
  return saved.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
}
```

### 3. Comparaison d'éléments
```javascript
// Permettre la sélection et comparaison de plusieurs éléments
selectForComparison(elementId) {
  if (!this.selectedForComparison) {
    this.selectedForComparison = [];
  }
  
  const index = this.selectedForComparison.indexOf(elementId);
  if (index > -1) {
    this.selectedForComparison.splice(index, 1);
  } else {
    this.selectedForComparison.push(elementId);
  }
  
  this.updateComparisonUI();
}

showComparison() {
  // Afficher une vue de comparaison des éléments sélectionnés
  const selectedElements = this.currentResults.filter(
    result => this.selectedForComparison.includes(result.element_id)
  );
  
  // Implémenter l'affichage de comparaison
  this.displayComparisonView(selectedElements);
}
```

## Intégration avec frameworks

### Vue.js 3
```vue
<template>
  <div class="dpgf-analyzer">
    <DPGFUpload @file-selected="handleFileSelect" />
    <DPGFResults v-if="results" :results="results" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import DPGFUpload from './components/DPGFUpload.vue'
import DPGFResults from './components/DPGFResults.vue'

const results = ref(null)

const handleFileSelect = async (file, threshold) => {
  // Logique d'analyse du fichier
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await fetch(`/api/v1/dpgf-analysis/upload-analyze?threshold=${threshold}`, {
    method: 'POST',
    body: formData
  })
  
  results.value = await response.json()
}
</script>
```

### React
```jsx
import React, { useState } from 'react';
import DPGFUpload from './components/DPGFUpload';
import DPGFResults from './components/DPGFResults';

function DPGFAnalyzer() {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleFileAnalysis = async (file, threshold) => {
    setLoading(true);
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await fetch(`/api/v1/dpgf-analysis/upload-analyze?threshold=${threshold}`, {
        method: 'POST',
        body: formData
      });
      
      const data = await response.json();
      setResults(data);
    } catch (error) {
      console.error('Erreur:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dpgf-analyzer">
      <DPGFUpload onAnalyze={handleFileAnalysis} loading={loading} />
      {results && <DPGFResults results={results} />}
    </div>
  );
}

export default DPGFAnalyzer;
```

## Gestion des erreurs

### Codes d'erreur communs
- **400** : Fichier invalide ou paramètres incorrects
- **413** : Fichier trop volumineux
- **422** : Format de fichier non supporté
- **500** : Erreur serveur lors de l'analyse

### Gestion des erreurs côté client
```javascript
async function handleApiError(response) {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    
    switch (response.status) {
      case 400:
        throw new Error(errorData.detail || 'Fichier ou paramètres invalides');
      case 413:
        throw new Error('Fichier trop volumineux (limite: 10MB)');
      case 422:
        throw new Error('Format de fichier non supporté');
      case 500:
        throw new Error('Erreur serveur lors de l\'analyse');
      default:
        throw new Error(`Erreur ${response.status}: ${errorData.detail || 'Erreur inconnue'}`);
    }
  }
}
```

## Tests recommandés

### 1. Tests unitaires
- Validation des formats de fichiers
- Calcul des scores de correspondance
- Formatage des données d'affichage

### 2. Tests d'intégration
- Upload et analyse de fichiers DPGF
- Recherche manuelle d'éléments
- Affichage des résultats

### 3. Tests de performance
- Analyse de gros fichiers DPGF (>1000 éléments)
- Recherche dans une base de données importante
- Temps de réponse de l'interface utilisateur

Ce guide fournit une base solide pour implémenter l'interface d'analyse de fichiers DPGF. Adaptez-le selon vos besoins spécifiques et votre stack technologique frontend.
