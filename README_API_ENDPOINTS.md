# Documentation des Endpoints de l’API

## DPGF (`/api/v1/dpgf`)

- **POST `/dpgf/upload`**  
  Upload d’un fichier Excel DPGF (multipart, champ `file`).  
  **Réponse :** `{ "stdout": "...", "stderr": "..." }` (résultat du script d’import)

- **POST `/dpgf/`**  
  Créer un DPGF  
  **Entrée :** JSON (voir schéma `DPGFCreate`)  
  **Sortie :** JSON (voir schéma `DPGFRead`)

- **GET `/dpgf/`**  
  Liste paginée des DPGF  
  **Query :** `skip`, `limit`  
  **Sortie :** `[DPGFRead, ...]`

- **GET `/dpgf/{dpgf_id}`**  
  Détail d’un DPGF  
  **Sortie :** `DPGFRead`

- **DELETE `/dpgf/{dpgf_id}`**  
  Supprimer un DPGF

- **GET `/dpgf/{dpgf_id}/structure`**  
  Structure hiérarchique complète d’un DPGF  
  **Sortie :** `{...}` (lots, sections, éléments)

---

## Clients (`/api/v1/clients`)

- **POST `/clients/`**  
  Créer un client  
  **Entrée :** JSON (schéma `ClientCreate`)  
  **Sortie :** `ClientRead`

- **GET `/clients/`**  
  Liste paginée des clients  
  **Query :** `skip`, `limit`  
  **Sortie :** `[ClientRead, ...]`

- **GET `/clients/{client_id}`**  
  Détail d’un client  
  **Sortie :** `ClientRead`

- **DELETE `/clients/{client_id}`**  
  Supprimer un client

---

## Lots (`/api/v1/lots`)

- **POST `/lots/`**  
  Créer un lot  
  **Entrée :** JSON (schéma `LotCreate`)  
  **Sortie :** `LotRead`

- **GET `/lots/`**  
  Liste paginée des lots  
  **Query :** `skip`, `limit`  
  **Sortie :** `[LotRead, ...]`

- **GET `/lots/{lot_id}`**  
  Détail d’un lot  
  **Sortie :** `LotRead`

- **DELETE `/lots/{lot_id}`**  
  Supprimer un lot

---

## Sections (`/api/v1/sections`)

- **POST `/sections/`**  
  Créer une section  
  **Entrée :** JSON (schéma `SectionCreate`)  
  **Sortie :** `SectionRead`

- **GET `/sections/`**  
  Liste paginée des sections, avec filtres :  
  `skip`, `limit`, `lot_id`, `dpgf_id`, `include_hierarchy`  
  **Sortie :** `[SectionRead, ...]`

- **GET `/sections/with_elements_count`**  
  Sections avec nombre d’éléments d’ouvrage  
  **Query :** `dpgf_id`  
  **Sortie :** `[{"section_id": ..., "count": ...}, ...]`

- **GET `/sections/tree`**  
  Arborescence des sections pour un DPGF  
  **Query :** `dpgf_id`  
  **Sortie :** `[{"section": ..., "children": [...]}, ...]`

- **GET `/sections/{section_id}`**  
  Détail d’une section (option : `include_hierarchy`)  
  **Sortie :** `SectionRead`

- **DELETE `/sections/{section_id}`**  
  Supprimer une section

---

## Éléments d’ouvrage (`/api/v1/element_ouvrages`)

- **POST `/element_ouvrages/`**  
  Créer un élément d’ouvrage  
  **Entrée :** JSON (schéma `ElementOuvrageCreate`)  
  **Sortie :** `ElementOuvrageRead`

- **GET `/element_ouvrages/`**  
  Liste paginée des éléments, option : `include_section`  
  **Sortie :** `[ElementOuvrageRead, ...]`

- **GET `/element_ouvrages/with_sections`**  
  Tous les éléments avec leur section  
  **Query :** `section_id`, `lot_id`, `dpgf_id`, `skip`, `limit`  
  **Sortie :** `[ElementOuvrageWithSection, ...]`

- **GET `/element_ouvrages/complete`**  
  Tous les éléments avec hiérarchie complète  
  **Query :** `dpgf_id`, `skip`, `limit`  
  **Sortie :** `[ElementOuvrageComplete, ...]`

- **GET `/element_ouvrages/{element_id}`**  
  Détail d’un élément (options : `include_section`, `include_hierarchy`)  
  **Sortie :** `ElementOuvrageRead`

- **GET `/element_ouvrages/{element_id}/with_section`**  
  Détail d’un élément avec sa section  
  **Sortie :** `ElementOuvrageWithSection`

- **GET `/element_ouvrages/{element_id}/complete`**  
  Détail d’un élément avec toute la hiérarchie  
  **Sortie :** `ElementOuvrageComplete`

---

Pour chaque endpoint, les schémas (`Read`, `Create`, etc.) sont définis dans le dossier `app/schemas/`.

