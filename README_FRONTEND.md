# 📦 Frontend Guide — Upload & Import DPGF

Ce document explique comment implémenter au niveau frontend l’upload de vos fichiers Excel DPGF vers l’API FastAPI, qui déclenchera automatiquement le script d’import.

---

## 1. Endpoint

**URL**  
POST `http://<HOST>:<PORT>/api/v1/dpgf/upload`

**Content-Type**  
`multipart/form-data`

**Paramètres**

| Nom          | Type     | Obligatoire | Description                                    |
| ------------ | -------- | ----------- | ---------------------------------------------- |
| `file`       | File     | Oui         | Le fichier Excel DPGF (`.xlsx` ou `.xls`).     |

**Réponse**

- 200 – JSON `{ stdout: string, stderr: string }`  
- 500 – Erreur interne si le script échoue  
  `{ detail: "Import script failed: <message>" }`

---

## 2. Exemple React + Axios

```jsx
import React, { useState } from 'react'
import axios from 'axios'

export function DPGFUpload() {
  const [file, setFile]           = useState(null)
  const [loading, setLoading]     = useState(false)
  const [result, setResult]       = useState(null)
  const [error, setError]         = useState(null)

  const handleFileChange = e => {
    setFile(e.target.files[0])
    setError(null)
  }

  const handleUpload = async () => {
    if (!file) {
      setError('Veuillez sélectionner un fichier Excel.')
      return
    }

    const formData = new FormData()
    formData.append('file', file)

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const resp = await axios.post('/api/v1/dpgf/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 5 * 60 * 1000  // 5 min pour gros fichiers
      })
      setResult(resp.data)
    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || 'Erreur lors de l’upload')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="uploader">
      <h2>Importer un fichier DPGF</h2>

      <input
        type="file"
        accept=".xlsx,.xls"
        onChange={handleFileChange}
        disabled={loading}
      />

      {/* La clé Gemini est lue côté serveur depuis .env */}

      <button onClick={handleUpload} disabled={!file || loading}>
        {loading ? 'Import en cours…' : 'Lancer l’import'}
      </button>

      {error && <p className="error">❌ {error}</p>}
      {result && (
        <div className="success">
          <h3>Import terminé</h3>
          <pre>{result.stdout}</pre>
        </div>
      )}
    </div>
  )
}
```

---

## 3. Points d’attention

1. **CORS**  
   Le backend autorise `http://localhost:5173` (Vite/React) par défaut. Adaptez `allow_origins` si besoin dans `app/main.py`.

2. **Timeout**  
   Le script peut prendre plusieurs minutes. Prévoyez un timeout élevé (par ex. 300 000 ms).

3. **Gestion d’erreurs**  
   - 4xx : paramètre manquant ou invalide.  
   - 5xx : échec du script Python (`stderr` dans la réponse).

4. **Sécurité**  
   Ne committez jamais votre `GEMINI_API_KEY` en clair dans le code.  
   Préférez un champ safe (env var + prompt utilisateur).

---

## 4. Test avec curl

```bash
curl -X POST http://localhost:8000/api/v1/dpgf/upload \
  -F "file=@/chemin/vers/mon.xlsx"
```

---

Vous êtes prêt à intégrer l’upload DPGF côté frontend ! 🚀
