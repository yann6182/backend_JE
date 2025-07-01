"""
Service de recherche avancée pour les éléments d'ouvrage.
Permet de rechercher des éléments avec filtrage multicritères, 
tri personnalisé et suggestions contextuelles.
"""

import re
from typing import List, Dict, Any, Optional, Tuple, Union, Set
from sqlalchemy import or_, and_, func, desc, asc, case, Float, cast
from sqlalchemy.orm import Session
from sqlalchemy.sql import text
from pathlib import Path
import logging
from difflib import SequenceMatcher

from app.db.models.element_ouvrage import ElementOuvrage
from app.db.models.section import Section
from app.db.models.lot import Lot
from app.db.models.dpgf import DPGF
from app.db.models.client import Client
from app.schemas.element_ouvrage import ElementOuvrageRead


class ElementSearchService:
    """
    Service de recherche avancée pour les éléments d'ouvrage avec
    filtrage, scoring et tri intelligents.
    """
    
    def __init__(self, db: Session):
        """
        Initialise le service de recherche
        
        Args:
            db: Session de base de données
        """
        self.db = db
        
        # Configuration du logger
        self.logger = logging.getLogger(__name__)
        
        # Liste des mots vides (stop words) en français
        self.stop_words = {
            'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'à', 'au', 'aux',
            'et', 'ou', 'pour', 'par', 'en', 'sur', 'sous', 'dans', 'avec', 'sans',
            'ce', 'ces', 'cet', 'cette', 'mon', 'ton', 'son', 'nos', 'vos', 'leurs'
        }
    
    def search_elements(
        self,
        query: Optional[str] = None,
        client_id: Optional[int] = None,
        dpgf_id: Optional[int] = None,
        lot_id: Optional[int] = None, 
        section_id: Optional[int] = None,
        lot_numero: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        sort_by: str = "relevance",
        descending: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Recherche des éléments d'ouvrage selon des critères multiples
        
        Args:
            query: Texte de recherche (désignation ou description)
            client_id: Filtrer par client
            dpgf_id: Filtrer par DPGF
            lot_id: Filtrer par lot
            section_id: Filtrer par section
            lot_numero: Filtrer par numéro de lot
            min_price: Prix unitaire minimum
            max_price: Prix unitaire maximum
            sort_by: Critère de tri ('relevance', 'price', 'date', 'designation')
            descending: Ordre décroissant si True, croissant sinon
            limit: Nombre maximum de résultats
            offset: Décalage pour la pagination
            
        Returns:
            Tuple (résultats, nombre total de résultats)
        """
        # Commencer la requête
        query_elements = self.db.query(
            ElementOuvrage, 
            Section.numero.label("section_numero"),
            Section.titre.label("section_titre"),
            Lot.numero.label("lot_numero"),
            Lot.nom.label("lot_nom"),
            DPGF.nom.label("dpgf_nom"),
            Client.nom.label("client_nom")
        ).join(
            Lot, ElementOuvrage.lot_id == Lot.id
        ).outerjoin(
            Section, ElementOuvrage.section_id == Section.id
        ).join(
            DPGF, Lot.dpgf_id == DPGF.id
        ).join(
            Client, DPGF.client_id == Client.id
        )
        
        # Appliquer les filtres
        query_elements = self._apply_filters(
            query_elements,
            query=query,
            client_id=client_id,
            dpgf_id=dpgf_id,
            lot_id=lot_id,
            section_id=section_id,
            lot_numero=lot_numero,
            min_price=min_price,
            max_price=max_price
        )
        
        # Compter le total avant d'appliquer limit/offset
        total_count = query_elements.count()
        
        # Appliquer le tri
        query_elements = self._apply_sorting(
            query_elements,
            sort_by=sort_by,
            descending=descending,
            search_query=query
        )
        
        # Appliquer limit et offset
        query_elements = query_elements.offset(offset).limit(limit)
        
        # Exécuter la requête
        results = query_elements.all()
        
        # Formater les résultats
        formatted_results = self._format_results(results)
        
        return formatted_results, total_count
    
    def _apply_filters(
        self, 
        query_elements,
        query: Optional[str] = None,
        client_id: Optional[int] = None,
        dpgf_id: Optional[int] = None,
        lot_id: Optional[int] = None,
        section_id: Optional[int] = None,
        lot_numero: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None
    ):
        """
        Applique les filtres à la requête
        
        Args:
            query_elements: La requête de base
            autres paramètres: identiques à search_elements
            
        Returns:
            La requête avec les filtres appliqués
        """
        # Filtre de texte (recherche dans la désignation et la description)
        if query:
            # Normaliser la requête et diviser en tokens
            search_terms = self._tokenize_query(query)
            
            if search_terms:
                # Utiliser la nouvelle méthode de scoring par pertinence
                query_elements = self._apply_text_search_with_scoring(query_elements, search_terms, query)
        
        # Filtrer par client
        if client_id:
            query_elements = query_elements.filter(Client.id == client_id)
        
        # Filtrer par DPGF
        if dpgf_id:
            query_elements = query_elements.filter(DPGF.id == dpgf_id)
        
        # Filtrer par lot (par ID)
        if lot_id:
            query_elements = query_elements.filter(Lot.id == lot_id)
        
        # Filtrer par lot (par numéro)
        if lot_numero:
            query_elements = query_elements.filter(Lot.numero == lot_numero)
        
        # Filtrer par section
        if section_id:
            query_elements = query_elements.filter(ElementOuvrage.section_id == section_id)
        
        # Filtrer par fourchette de prix
        if min_price is not None:
            query_elements = query_elements.filter(ElementOuvrage.prix_unitaire >= min_price)
        
        if max_price is not None:
            query_elements = query_elements.filter(ElementOuvrage.prix_unitaire <= max_price)
        
        return query_elements
    
    def _tokenize_query(self, query: str) -> List[str]:
        """
        Tokenise et nettoie une requête de recherche
        
        Args:
            query: Texte de recherche
            
        Returns:
            Liste de tokens significatifs
        """
        if not query:
            return []
        
        # Convertir en minuscules et supprimer les caractères spéciaux
        cleaned_query = re.sub(r'[^\w\s]', ' ', query.lower())
        
        # Diviser en tokens
        tokens = cleaned_query.split()
        
        # Filtrer les mots vides et les tokens trop courts
        significant_tokens = [
            token for token in tokens 
            if token not in self.stop_words and len(token) > 1
        ]
        
        return significant_tokens
        
    def _apply_text_search_with_scoring(self, query_elements, search_terms: List[str], original_query: str):
        """
        Applique une recherche textuelle avancée avec système de scoring
        
        Args:
            query_elements: La requête de base
            search_terms: Liste de termes de recherche tokenisés
            original_query: Requête originale complète
            
        Returns:
            La requête avec les filtres de recherche textuelle appliqués
        """
        if not search_terms:
            return query_elements
            
        # Pour chaque terme, créer une condition de recherche
        conditions = []
        scoring_elements = []
        
        for term in search_terms:
            # Si le terme est suffisamment long, autoriser une recherche partielle
            if len(term) >= 3:
                term_pattern = f"%{term}%"
                
                # Condition de correspondance pour ce terme
                term_condition = or_(
                    func.lower(ElementOuvrage.designation).like(term_pattern),
                    func.lower(ElementOuvrage.description).like(term_pattern),
                    func.lower(Section.titre).like(term_pattern) if Section else False
                )
                conditions.append(term_condition)
                
                # Facteurs de scoring pour ce terme
                # Score plus élevé pour les correspondances dans la désignation
                designation_score = case(
                    [(func.lower(ElementOuvrage.designation).like(term_pattern), 10)],
                    else_=0
                )
                
                # Score moyen pour les correspondances dans la description
                description_score = case(
                    [(func.lower(ElementOuvrage.description).like(term_pattern), 5)],
                    else_=0
                )
                
                # Score pour les correspondances dans le titre de section
                section_score = case(
                    [(func.lower(Section.titre).like(term_pattern), 3)],
                    else_=0
                )
                
                # Ajouter les scores aux éléments de scoring
                scoring_elements.append(designation_score + description_score + section_score)
            else:
                # Pour les termes très courts, exiger une correspondance exacte (mot entier)
                term_pattern = f"% {term} %"
                
                term_condition = or_(
                    func.lower(ElementOuvrage.designation).like(term_pattern),
                    func.lower(ElementOuvrage.description).like(term_pattern)
                )
                conditions.append(term_condition)
        
        # Combiner tous les termes avec AND (tous les termes doivent correspondre)
        if conditions:
            query_elements = query_elements.filter(and_(*conditions))
            
        # Ajouter la colonne de score total si des éléments de scoring sont présents
        if scoring_elements:
            total_score = sum(scoring_elements).label("relevance_score")
            query_elements = query_elements.add_columns(total_score)
            
        return query_elements
    
    def _apply_sorting(
        self,
        query_elements,
        sort_by: str = "relevance",
        descending: bool = True,
        search_query: Optional[str] = None
    ):
        """
        Applique le tri à la requête
        
        Args:
            query_elements: La requête filtrée
            sort_by: Critère de tri
            descending: Ordre décroissant si True, croissant sinon
            search_query: Requête de recherche (pour le tri par pertinence)
            
        Returns:
            La requête avec le tri appliqué
        """
        # Direction du tri
        direction = desc if descending else asc
        
        # Appliquer le tri selon le critère choisi
        if sort_by == "price":
            # Tri par prix unitaire
            query_elements = query_elements.order_by(direction(ElementOuvrage.prix_unitaire))
        
        elif sort_by == "date":
            # Tri par date de création
            query_elements = query_elements.order_by(direction(ElementOuvrage.created_at))
        
        elif sort_by == "designation":
            # Tri alphabétique par désignation
            query_elements = query_elements.order_by(direction(ElementOuvrage.designation))
        
        elif sort_by == "dpgf":
            # Tri par nom de DPGF
            query_elements = query_elements.order_by(direction(DPGF.nom))
        
        elif sort_by == "lot":
            # Tri par numéro de lot puis nom
            query_elements = query_elements.order_by(direction(Lot.numero), direction(Lot.nom))
            
        elif sort_by == "section":
            # Tri par numéro de section puis titre
            query_elements = query_elements.order_by(direction(Section.numero), direction(Section.titre))
            
        elif sort_by == "relevance" and search_query:
            # Vérifier si le score de pertinence a été calculé
            if hasattr(query_elements, '_entities') and any('relevance_score' in str(entity) for entity in query_elements._entities):
                # Utiliser le score de pertinence pour trier
                query_elements = query_elements.order_by(desc("relevance_score"))
            else:
                # Si aucun score de pertinence n'est disponible, appliquer un tri par défaut
                # basé sur la présence de termes dans la désignation
                search_terms = self._tokenize_query(search_query)
                if search_terms:
                    # Créer une expression de tri dynamique basée sur la présence des termes
                    relevance_expr = None
                    for term in search_terms:
                        term_pattern = f"%{term}%"
                        term_expr = case(
                            [(func.lower(ElementOuvrage.designation).like(term_pattern), 1)], 
                            else_=0
                        )
                        
                        if relevance_expr is None:
                            relevance_expr = term_expr
                        else:
                            relevance_expr += term_expr
                    
                    # Utiliser cette expression pour le tri
                    if relevance_expr is not None:
                        query_elements = query_elements.order_by(desc(relevance_expr))
        
        # Tri secondaire pour assurer un ordre cohérent
        if sort_by != "designation":
            query_elements = query_elements.order_by(asc(ElementOuvrage.designation))
        
        return query_elements
    
    def _format_results(self, results) -> List[Dict[str, Any]]:
        """
        Formate les résultats de la requête
        
        Args:
            results: Résultats de la requête
            
        Returns:
            Liste de dictionnaires formatés
        """
        formatted_results = []
        
        for row in results:
            element = row[0]  # ElementOuvrage
            
            # Vérifier si un score de pertinence est présent dans le résultat
            relevance_score = None
            if len(row) > 7:  # 7 est le nombre de colonnes standard attendues sans le score
                # Le dernier élément est le score de pertinence
                relevance_score = row[-1]
            
            # Créer un dictionnaire avec toutes les propriétés
            element_dict = {
                "id": element.id,
                "designation": element.designation,
                "description": element.description,
                "unite": element.unite,
                "quantite": element.quantite,
                "prix_unitaire": element.prix_unitaire,
                "prix_total": element.prix_total,
                "lot": {
                    "id": element.lot_id,
                    "numero": row.lot_numero,
                    "nom": row.lot_nom
                },
                "section": None,
                "dpgf": {
                    "id": row.DPGF.id if hasattr(row, 'DPGF') and row.DPGF else None,
                    "nom": row.dpgf_nom
                },
                "client": {
                    "id": row.Client.id if hasattr(row, 'Client') and row.Client else None,
                    "nom": row.client_nom
                },
                "created_at": element.created_at.isoformat() if element.created_at else None,
                "updated_at": element.updated_at.isoformat() if element.updated_at else None,
            }
            
            # Ajouter le score de pertinence si disponible
            if relevance_score is not None:
                element_dict["relevance_score"] = relevance_score
            
            # Ajouter les informations de section si disponibles
            if element.section_id:
                element_dict["section"] = {
                    "id": element.section_id,
                    "numero": row.section_numero,
                    "titre": row.section_titre
                }
            
            formatted_results.append(element_dict)
        
        return formatted_results
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Calcule la similarité entre deux textes
        
        Args:
            text1: Premier texte
            text2: Deuxième texte
            
        Returns:
            Score de similarité entre 0 et 1
        """
        if not text1 or not text2:
            return 0.0
        
        # Normaliser les textes
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()
        
        # Utiliser SequenceMatcher de difflib pour calculer la similarité
        matcher = SequenceMatcher(None, text1, text2)
        similarity = matcher.ratio()
        
        return similarity
    
    def find_similar_elements(self, element_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Trouve des éléments similaires à un élément donné
        
        Args:
            element_id: ID de l'élément de référence
            limit: Nombre maximum de résultats
            
        Returns:
            Liste d'éléments similaires
        """
        # Récupérer l'élément de référence
        reference_element = self.db.query(ElementOuvrage).filter(ElementOuvrage.id == element_id).first()
        if not reference_element:
            return []
        
        # Récupérer le lot et la section de l'élément de référence
        lot_id = reference_element.lot_id
        section_id = reference_element.section_id
        
        # Construire une requête pour trouver des éléments similaires
        query = self.db.query(
            ElementOuvrage, 
            Section.numero.label("section_numero"),
            Section.titre.label("section_titre"),
            Lot.numero.label("lot_numero"),
            Lot.nom.label("lot_nom"),
            DPGF.nom.label("dpgf_nom"),
            Client.nom.label("client_nom")
        ).join(
            Lot, ElementOuvrage.lot_id == Lot.id
        ).outerjoin(
            Section, ElementOuvrage.section_id == Section.id
        ).join(
            DPGF, Lot.dpgf_id == DPGF.id
        ).join(
            Client, DPGF.client_id == Client.id
        ).filter(
            # Exclure l'élément de référence
            ElementOuvrage.id != element_id
        )
        
        # Extraire les termes significatifs de la désignation et de la description de référence
        designation_terms = self._tokenize_query(reference_element.designation) if reference_element.designation else []
        description_terms = self._tokenize_query(reference_element.description) if reference_element.description else []
        
        # Combiner tous les termes
        all_terms = designation_terms + description_terms
        
        # Si nous avons des termes, chercher des correspondances
        if all_terms:
            # Créer des conditions pour chaque terme
            conditions = []
            for term in all_terms:
                if len(term) >= 3:  # Utiliser uniquement les termes significatifs
                    term_pattern = f"%{term}%"
                    term_condition = or_(
                        func.lower(ElementOuvrage.designation).like(term_pattern),
                        func.lower(ElementOuvrage.description).like(term_pattern)
                    )
                    conditions.append(term_condition)
            
            # Si nous avons des conditions, filtrer la requête
            if conditions:
                # Exiger qu'au moins un terme corresponde
                query = query.filter(or_(*conditions))
        
        # Donner la priorité aux éléments du même lot et/ou de la même section
        if lot_id or section_id:
            lot_section_case = None
            
            # Score plus élevé pour les éléments du même lot et de la même section
            if lot_id and section_id:
                lot_section_case = case(
                    [(and_(ElementOuvrage.lot_id == lot_id, ElementOuvrage.section_id == section_id), 30)],
                    [(ElementOuvrage.lot_id == lot_id, 20)],
                    [(ElementOuvrage.section_id == section_id, 10)],
                    else_=0
                )
            # Score plus élevé pour les éléments du même lot
            elif lot_id:
                lot_section_case = case(
                    [(ElementOuvrage.lot_id == lot_id, 20)],
                    else_=0
                )
            # Score plus élevé pour les éléments de la même section
            elif section_id:
                lot_section_case = case(
                    [(ElementOuvrage.section_id == section_id, 10)],
                    else_=0
                )
            
            if lot_section_case is not None:
                query = query.add_columns(lot_section_case.label("similarity_score"))
                query = query.order_by(desc("similarity_score"))
        
        # Limiter le nombre de résultats
        query = query.limit(limit)
        
        # Exécuter la requête
        results = query.all()
        
        # Formater les résultats
        formatted_results = self._format_results(results)
        
        # Calculer manuellement la similarité textuelle pour le tri final
        if reference_element.designation:
            for result in formatted_results:
                similarity = self._calculate_text_similarity(
                    reference_element.designation, 
                    result["designation"]
                )
                result["text_similarity"] = round(similarity * 100)  # Score en pourcentage
        
        return formatted_results
    
    def get_search_suggestions(
        self, 
        query: str, 
        client_id: Optional[int] = None,
        dpgf_id: Optional[int] = None,
        lot_id: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Génère des suggestions de recherche avancées basées sur une requête partielle
        et filtres contextuels
        
        Args:
            query: Texte de recherche partiel
            client_id: Filtrer par client
            dpgf_id: Filtrer par DPGF
            lot_id: Filtrer par lot
            limit: Nombre maximum de suggestions
            
        Returns:
            Liste de suggestions de complétion avec métadonnées
        """
        # Si la requête est vide ou trop courte
        if not query or len(query) < 2:
            return []
        
        # Normaliser la requête
        query = query.lower().strip()
        
        # Base de la requête pour les suggestions
        base_query = self.db.query(
            ElementOuvrage.designation,
            ElementOuvrage.id,
            ElementOuvrage.unite,
            ElementOuvrage.prix_unitaire,
            ElementOuvrage.section_id,
            Lot.numero.label("lot_numero"),
            Section.numero.label("section_numero"),
            Section.titre.label("section_titre")
        ).join(
            Lot, ElementOuvrage.lot_id == Lot.id
        ).outerjoin(
            Section, ElementOuvrage.section_id == Section.id
        )
        
        # Appliquer des filtres contextuels si disponibles
        if client_id or dpgf_id:
            base_query = base_query.join(DPGF, Lot.dpgf_id == DPGF.id)
            
            if client_id:
                base_query = base_query.filter(DPGF.client_id == client_id)
            
            if dpgf_id:
                base_query = base_query.filter(DPGF.id == dpgf_id)
        
        if lot_id:
            base_query = base_query.filter(ElementOuvrage.lot_id == lot_id)
        
        # Recherche dans les désignations (principale)
        designations_query = base_query.filter(
            func.lower(ElementOuvrage.designation).contains(query)
        ).order_by(func.length(ElementOuvrage.designation)).distinct(ElementOuvrage.designation)
        
        # Exécuter la requête
        results = designations_query.limit(limit).all()
        
        # Convertir en liste de dictionnaires
        suggestions = []
        seen_designations = set()
        
        for item in results:
            if item.designation not in seen_designations:
                suggestion = {
                    "text": item.designation,
                    "id": item.id,
                    "type": "designation",
                    "metadata": {
                        "unite": item.unite,
                        "prix": item.prix_unitaire,
                        "lot": item.lot_numero
                    }
                }
                
                # Ajouter la section si disponible
                if item.section_id:
                    suggestion["metadata"]["section"] = {
                        "numero": item.section_numero,
                        "titre": item.section_titre
                    }
                
                suggestions.append(suggestion)
                seen_designations.add(item.designation)
        
        # Si on n'a pas assez de suggestions, chercher aussi dans les descriptions
        if len(suggestions) < limit:
            remaining = limit - len(suggestions)
            
            # Requête pour les descriptions
            descriptions_query = base_query.filter(
                func.lower(ElementOuvrage.description).contains(query)
            ).filter(
                ~ElementOuvrage.designation.in_([s["text"] for s in suggestions])
            ).order_by(func.length(ElementOuvrage.description)).distinct(ElementOuvrage.description)
            
            # Exécuter la requête
            desc_results = descriptions_query.limit(remaining).all()
            
            # Ajouter aux suggestions
            for item in desc_results:
                if item.designation not in seen_designations:
                    suggestion = {
                        "text": item.designation,
                        "id": item.id,
                        "type": "description",
                        "metadata": {
                            "unite": item.unite,
                            "prix": item.prix_unitaire,
                            "lot": item.lot_numero
                        }
                    }
                    
                    # Ajouter la section si disponible
                    if item.section_id:
                        suggestion["metadata"]["section"] = {
                            "numero": item.section_numero,
                            "titre": item.section_titre
                        }
                    
                    suggestions.append(suggestion)
                    seen_designations.add(item.designation)
        
        # Si on n'a pas encore assez de suggestions, chercher dans les titres de sections
        if len(suggestions) < limit and not lot_id:
            remaining = limit - len(suggestions)
            
            # Requête pour les titres de sections
            sections_query = self.db.query(
                Section.titre,
                Section.id,
                Section.numero,
                Lot.numero.label("lot_numero")
            ).join(
                Lot, Section.lot_id == Lot.id
            ).filter(
                func.lower(Section.titre).contains(query)
            )
            
            # Appliquer des filtres contextuels si disponibles
            if client_id or dpgf_id:
                sections_query = sections_query.join(DPGF, Lot.dpgf_id == DPGF.id)
                
                if client_id:
                    sections_query = sections_query.filter(DPGF.client_id == client_id)
                
                if dpgf_id:
                    sections_query = sections_query.filter(DPGF.id == dpgf_id)
            
            # Exécuter la requête
            section_results = sections_query.limit(remaining).all()
            
            # Ajouter aux suggestions
            for item in section_results:
                suggestion = {
                    "text": f"Section {item.numero}: {item.titre}",
                    "id": item.id,
                    "type": "section",
                    "metadata": {
                        "section": {
                            "id": item.id,
                            "numero": item.numero,
                            "titre": item.titre
                        },
                        "lot": item.lot_numero
                    }
                }
                
                suggestions.append(suggestion)
        
        return suggestions
    
    def analyze_text_for_matches(
        self, 
        text: str, 
        client_id: Optional[int] = None,
        dpgf_id: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Analyse un texte pour trouver des éléments correspondants
        
        Args:
            text: Texte à analyser
            client_id: Filtrer par client
            dpgf_id: Filtrer par DPGF
            limit: Nombre maximum de résultats
            
        Returns:
            Liste d'éléments correspondants avec score de confiance
        """
        # Si le texte est vide
        if not text:
            return []
        
        # Normaliser et tokeniser le texte
        tokens = self._tokenize_query(text)
        
        # Si aucun token significatif
        if not tokens:
            return []
        
        # Base de la requête
        query = self.db.query(
            ElementOuvrage, 
            Section.numero.label("section_numero"),
            Section.titre.label("section_titre"),
            Lot.numero.label("lot_numero"),
            Lot.nom.label("lot_nom"),
            DPGF.nom.label("dpgf_nom"),
            Client.nom.label("client_nom")
        ).join(
            Lot, ElementOuvrage.lot_id == Lot.id
        ).outerjoin(
            Section, ElementOuvrage.section_id == Section.id
        ).join(
            DPGF, Lot.dpgf_id == DPGF.id
        ).join(
            Client, DPGF.client_id == Client.id
        )
        
        # Appliquer des filtres contextuels
        if client_id:
            query = query.filter(Client.id == client_id)
        
        if dpgf_id:
            query = query.filter(DPGF.id == dpgf_id)
        
        # Pour chaque token, générer un score de correspondance
        scoring_elements = []
        
        # Conditions pour filtrer les résultats
        conditions = []
        
        for token in tokens:
            if len(token) >= 3:
                token_pattern = f"%{token}%"
                
                # Ajouter à la condition de filtrage
                token_condition = or_(
                    func.lower(ElementOuvrage.designation).like(token_pattern),
                    func.lower(ElementOuvrage.description).like(token_pattern),
                    func.lower(Section.titre).like(token_pattern) if Section else False
                )
                conditions.append(token_condition)
                
                # Ajouter au score
                designation_score = case(
                    [(func.lower(ElementOuvrage.designation).like(token_pattern), 10)],
                    else_=0
                )
                
                description_score = case(
                    [(func.lower(ElementOuvrage.description).like(token_pattern), 5)],
                    else_=0
                )
                
                section_score = case(
                    [(func.lower(Section.titre).like(token_pattern), 3)],
                    else_=0
                )
                
                scoring_elements.append(designation_score + description_score + section_score)
        
        # Exiger qu'au moins un token corresponde
        if conditions:
            # Utiliser OR pour les conditions (au moins une correspondance)
            query = query.filter(or_(*conditions))
        
        # Calculer le score total et ajouter à la requête
        if scoring_elements:
            token_count = float(len(tokens))
            # Normaliser le score sur 100
            total_score = (cast(sum(scoring_elements), Float) / (token_count * 10) * 100).label("match_score")
            query = query.add_columns(total_score)
            
            # Ordonner par score décroissant
            query = query.order_by(desc("match_score"))
        
        # Limiter le nombre de résultats
        query = query.limit(limit)
        
        # Exécuter la requête
        results = query.all()
        
        # Formater et retourner les résultats
        formatted_results = self._format_results(results)
        
        # Ajouter des méta-informations
        for result in formatted_results:
            # S'assurer que le score est affiché comme un pourcentage arrondi
            if "relevance_score" in result:
                match_score = result.pop("relevance_score")
                # Normaliser et arrondir le score
                result["match_confidence"] = min(100, max(0, round(match_score)))
                
                # Ajouter une classification du niveau de confiance
                if result["match_confidence"] >= 80:
                    result["confidence_level"] = "élevée"
                elif result["match_confidence"] >= 50:
                    result["confidence_level"] = "moyenne"
                else:
                    result["confidence_level"] = "faible"
            
        return formatted_results
    
    def extract_keywords(
        self,
        client_id: Optional[int] = None,
        dpgf_id: Optional[int] = None,
        lot_id: Optional[int] = None,
        section_id: Optional[int] = None,
        limit_per_category: int = 20
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extrait les mots-clés les plus fréquents des éléments d'ouvrage
        
        Args:
            client_id: Filtrer par client
            dpgf_id: Filtrer par DPGF
            lot_id: Filtrer par lot
            section_id: Filtrer par section
            limit_per_category: Nombre maximum de mots-clés par catégorie
            
        Returns:
            Dictionnaire de mots-clés par catégorie
        """
        # Base de la requête
        query = self.db.query(ElementOuvrage)
        
        # Appliquer des filtres si nécessaire
        if any([client_id, dpgf_id, lot_id, section_id]):
            query = query.join(Lot, ElementOuvrage.lot_id == Lot.id)
            
            if dpgf_id or client_id:
                query = query.join(DPGF, Lot.dpgf_id == DPGF.id)
                
                if client_id:
                    query = query.filter(DPGF.client_id == client_id)
                
                if dpgf_id:
                    query = query.filter(DPGF.id == dpgf_id)
            
            if lot_id:
                query = query.filter(Lot.id == lot_id)
            
            if section_id:
                query = query.filter(ElementOuvrage.section_id == section_id)
        
        # Récupérer les données pertinentes
        elements = query.with_entities(
            ElementOuvrage.designation,
            ElementOuvrage.description,
            ElementOuvrage.unite
        ).all()
        
        # Initialiser les structures pour stocker les mots-clés
        keywords = {
            "materiaux": {},
            "techniques": {},
            "unites": {},
            "dimensions": {}
        }
        
        # Expression régulière pour extraire les dimensions
        dimension_pattern = re.compile(r'(\d+(?:[,.]\d+)?)[xX*](\d+(?:[,.]\d+)?)', re.IGNORECASE)
        
        # Liste des termes techniques courants (à compléter selon le domaine)
        technique_terms = {
            "pose", "installation", "montage", "démontage", "assemblage", 
            "fixation", "scellement", "soudure", "vissage", "chevillage",
            "étanchéité", "isolation", "revêtement", "finition", "peinture",
            "découpe", "perçage", "forage", "sciage", "traitement"
        }
        
        # Liste des matériaux courants (à compléter)
        material_terms = {
            "bois", "acier", "inox", "aluminium", "pvc", "béton", "pierre", 
            "carrelage", "ciment", "plâtre", "brique", "verre", "métal",
            "plastique", "cuivre", "zinc", "plomb", "caoutchouc", "composite"
        }
        
        # Parcourir tous les éléments
        for element in elements:
            designation = element.designation.lower() if element.designation else ""
            description = element.description.lower() if element.description else ""
            unite = element.unite if element.unite else ""
            
            # Compter les unités
            if unite:
                keywords["unites"][unite] = keywords["unites"].get(unite, 0) + 1
            
            # Rechercher des dimensions dans la désignation et la description
            for text in [designation, description]:
                dim_matches = dimension_pattern.findall(text)
                for dim in dim_matches:
                    dim_str = f"{dim[0]}x{dim[1]}"
                    keywords["dimensions"][dim_str] = keywords["dimensions"].get(dim_str, 0) + 1
            
            # Tokeniser et analyser le texte
            tokens = set(self._tokenize_query(designation + " " + description))
            
            # Rechercher des techniques
            for token in tokens:
                if token in technique_terms:
                    keywords["techniques"][token] = keywords["techniques"].get(token, 0) + 1
                
                # Rechercher des matériaux
                if token in material_terms:
                    keywords["materiaux"][token] = keywords["materiaux"].get(token, 0) + 1
        
        # Convertir en liste triée par fréquence
        result = {}
        for category, kw_dict in keywords.items():
            # Trier par fréquence décroissante et limiter
            sorted_kws = sorted(kw_dict.items(), key=lambda x: x[1], reverse=True)[:limit_per_category]
            
            # Convertir en liste de dictionnaires
            result[category] = [
                {"keyword": kw, "count": count, "percentage": round(count * 100 / max(1, len(elements)))}
                for kw, count in sorted_kws
            ]
        
        return result
    
    def group_elements_by_category(
        self,
        client_id: Optional[int] = None,
        dpgf_id: Optional[int] = None,
        lot_id: Optional[int] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Regroupe les éléments d'ouvrage par catégories
        
        Args:
            client_id: Filtrer par client
            dpgf_id: Filtrer par DPGF
            lot_id: Filtrer par lot
            
        Returns:
            Dictionnaire de catégories d'éléments
        """
        # Base de la requête pour récupérer les lots et sections
        lot_query = self.db.query(Lot)
        
        # Appliquer des filtres si nécessaire
        if client_id or dpgf_id:
            lot_query = lot_query.join(DPGF, Lot.dpgf_id == DPGF.id)
            
            if client_id:
                lot_query = lot_query.filter(DPGF.client_id == client_id)
            
            if dpgf_id:
                lot_query = lot_query.filter(DPGF.id == dpgf_id)
        
        if lot_id:
            lot_query = lot_query.filter(Lot.id == lot_id)
        
        # Récupérer les lots
        lots = lot_query.all()
        
        # Initialiser le résultat
        result = {
            "by_lot": {},
            "by_unite": {},
            "by_price_range": {
                "très_bas": {"count": 0, "min": 0, "max": 0, "elements": []},
                "bas": {"count": 0, "min": 0, "max": 0, "elements": []},
                "moyen": {"count": 0, "min": 0, "max": 0, "elements": []},
                "élevé": {"count": 0, "min": 0, "max": 0, "elements": []},
                "très_élevé": {"count": 0, "min": 0, "max": 0, "elements": []}
            }
        }
        
        # Pour chaque lot, récupérer les sections et éléments
        for lot in lots:
            lot_info = {
                "id": lot.id,
                "numero": lot.numero,
                "nom": lot.nom,
                "elements_count": 0,
                "sections": {},
                "price_stats": {"min": None, "max": None, "avg": 0, "total": 0}
            }
            
            # Récupérer les sections de ce lot
            sections = self.db.query(Section).filter(Section.lot_id == lot.id).all()
            
            # Récupérer les éléments de ce lot
            elements_query = self.db.query(ElementOuvrage).filter(ElementOuvrage.lot_id == lot.id)
            elements = elements_query.all()
            
            # Compter les éléments
            lot_info["elements_count"] = len(elements)
            
            # Calculer les statistiques de prix
            if elements:
                prices = [e.prix_unitaire for e in elements if e.prix_unitaire is not None]
                if prices:
                    lot_info["price_stats"]["min"] = min(prices)
                    lot_info["price_stats"]["max"] = max(prices)
                    lot_info["price_stats"]["avg"] = sum(prices) / len(prices)
                    lot_info["price_stats"]["total"] = sum([e.prix_total for e in elements if e.prix_total is not None])
            
            # Pour chaque section, regrouper les éléments
            for section in sections:
                section_elements = [e for e in elements if e.section_id == section.id]
                if section_elements:
                    section_info = {
                        "id": section.id,
                        "numero": section.numero,
                        "titre": section.titre,
                        "elements_count": len(section_elements),
                        "elements": [
                            {
                                "id": e.id,
                                "designation": e.designation,
                                "unite": e.unite,
                                "prix_unitaire": e.prix_unitaire,
                                "prix_total": e.prix_total
                            } for e in section_elements[:10]  # Limiter à 10 éléments pour éviter une surcharge
                        ]
                    }
                    lot_info["sections"][section.numero] = section_info
            
            # Ajouter les éléments sans section
            no_section_elements = [e for e in elements if e.section_id is None]
            if no_section_elements:
                lot_info["sans_section"] = {
                    "elements_count": len(no_section_elements),
                    "elements": [
                        {
                            "id": e.id,
                            "designation": e.designation,
                            "unite": e.unite,
                            "prix_unitaire": e.prix_unitaire,
                            "prix_total": e.prix_total
                        } for e in no_section_elements[:10]  # Limiter à 10 éléments
                    ]
                }
            
            # Ajouter au résultat
            result["by_lot"][lot.numero] = lot_info
        
        # Regrouper par unité
        unite_query = self.db.query(
            ElementOuvrage.unite,
            func.count(ElementOuvrage.id).label("count"),
            func.min(ElementOuvrage.prix_unitaire).label("min_price"),
            func.max(ElementOuvrage.prix_unitaire).label("max_price"),
            func.avg(ElementOuvrage.prix_unitaire).label("avg_price")
        ).filter(ElementOuvrage.unite != None).group_by(ElementOuvrage.unite)
        
        # Appliquer les filtres
        if lot_id:
            unite_query = unite_query.filter(ElementOuvrage.lot_id == lot_id)
        elif dpgf_id or client_id:
            unite_query = unite_query.join(Lot, ElementOuvrage.lot_id == Lot.id)
            unite_query = unite_query.join(DPGF, Lot.dpgf_id == DPGF.id)
            
            if dpgf_id:
                unite_query = unite_query.filter(DPGF.id == dpgf_id)
            if client_id:
                unite_query = unite_query.filter(DPGF.client_id == client_id)
        
        # Exécuter la requête
        unites = unite_query.all()
        
        # Ajouter au résultat
        for unite_info in unites:
            result["by_unite"][unite_info.unite] = {
                "unite": unite_info.unite,
                "count": unite_info.count,
                "min_price": unite_info.min_price,
                "max_price": unite_info.max_price,
                "avg_price": unite_info.avg_price
            }
        
        # Calculer les gammes de prix pour la catégorisation
        price_query = self.db.query(
            func.min(ElementOuvrage.prix_unitaire).label("min_price"),
            func.max(ElementOuvrage.prix_unitaire).label("max_price"),
            func.avg(ElementOuvrage.prix_unitaire).label("avg_price"),
            func.stddev(ElementOuvrage.prix_unitaire).label("stddev_price")
        ).filter(ElementOuvrage.prix_unitaire != None)
        
        # Appliquer les filtres
        if lot_id:
            price_query = price_query.filter(ElementOuvrage.lot_id == lot_id)
        elif dpgf_id or client_id:
            price_query = price_query.join(Lot, ElementOuvrage.lot_id == Lot.id)
            price_query = price_query.join(DPGF, Lot.dpgf_id == DPGF.id)
            
            if dpgf_id:
                price_query = price_query.filter(DPGF.id == dpgf_id)
            if client_id:
                price_query = price_query.filter(DPGF.client_id == client_id)
        
        # Exécuter la requête
        price_stats = price_query.first()
        
        # Si on a des statistiques de prix, définir les plages
        if price_stats and price_stats.stddev_price:
            avg = price_stats.avg_price
            stddev = price_stats.stddev_price
            
            # Définir les seuils pour chaque catégorie de prix
            price_ranges = {
                "très_bas": (price_stats.min_price, avg - 1.5 * stddev),
                "bas": (avg - 1.5 * stddev, avg - 0.5 * stddev),
                "moyen": (avg - 0.5 * stddev, avg + 0.5 * stddev),
                "élevé": (avg + 0.5 * stddev, avg + 1.5 * stddev),
                "très_élevé": (avg + 1.5 * stddev, price_stats.max_price)
            }
            
            # Pour chaque plage, récupérer les éléments correspondants
            for category, (min_price, max_price) in price_ranges.items():
                # Requête pour cette plage de prix
                range_query = self.db.query(
                    ElementOuvrage.id,
                    ElementOuvrage.designation,
                    ElementOuvrage.unite,
                    ElementOuvrage.prix_unitaire,
                    ElementOuvrage.prix_total,
                    Lot.numero.label("lot_numero")
                ).join(
                    Lot, ElementOuvrage.lot_id == Lot.id
                ).filter(
                    ElementOuvrage.prix_unitaire.between(min_price, max_price)
                )
                
                # Appliquer les filtres
                if lot_id:
                    range_query = range_query.filter(ElementOuvrage.lot_id == lot_id)
                elif dpgf_id or client_id:
                    range_query = range_query.join(DPGF, Lot.dpgf_id == DPGF.id, isouter=True)
                    
                    if dpgf_id:
                        range_query = range_query.filter(DPGF.id == dpgf_id)
                    if client_id:
                        range_query = range_query.filter(DPGF.client_id == client_id)
                
                # Limiter à 20 éléments pour éviter une surcharge
                range_elements = range_query.limit(20).all()
                
                # Compter le total d'éléments dans cette plage
                count_query = range_query.with_entities(func.count().label("count"))
                count = count_query.scalar() or 0
                
                # Mettre à jour les résultats
                result["by_price_range"][category] = {
                    "count": count,
                    "min": min_price,
                    "max": max_price,
                    "elements": [
                        {
                            "id": e.id,
                            "designation": e.designation,
                            "unite": e.unite,
                            "prix_unitaire": e.prix_unitaire,
                            "prix_total": e.prix_total,
                            "lot": e.lot_numero
                        } for e in range_elements
                    ]
                }
        
        return result
        
    def get_statistics(
        self,
        client_id: Optional[int] = None,
        dpgf_id: Optional[int] = None,
        lot_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Récupère des statistiques sur les éléments d'ouvrage
        
        Args:
            client_id: Filtrer par client
            dpgf_id: Filtrer par DPGF
            lot_id: Filtrer par lot
            
        Returns:
            Dictionnaire de statistiques
        """
        # Commencer la requête
        query = self.db.query(ElementOuvrage)
        
        # Appliquer les filtres si nécessaire
        if client_id or dpgf_id or lot_id:
            query = query.join(Lot, ElementOuvrage.lot_id == Lot.id)
            
            if dpgf_id or client_id:
                query = query.join(DPGF, Lot.dpgf_id == DPGF.id)
                
                if client_id:
                    query = query.filter(DPGF.client_id == client_id)
                
                if dpgf_id:
                    query = query.filter(DPGF.id == dpgf_id)
            
            if lot_id:
                query = query.filter(Lot.id == lot_id)
        
        # Statistiques de base
        total_count = query.count()
        
        # Statistiques de prix
        price_stats = self.db.query(
            func.min(ElementOuvrage.prix_unitaire).label("min_price"),
            func.max(ElementOuvrage.prix_unitaire).label("max_price"),
            func.avg(ElementOuvrage.prix_unitaire).label("avg_price"),
            func.sum(ElementOuvrage.prix_total).label("total_price")
        ).filter(ElementOuvrage.id.in_([e.id for e in query])).first()
        
        # Regroupement par unité
        unit_counts = {}
        units = self.db.query(
            ElementOuvrage.unite,
            func.count(ElementOuvrage.id).label("count")
        ).filter(ElementOuvrage.id.in_([e.id for e in query])).group_by(
            ElementOuvrage.unite
        ).all()
        
        for unit, count in units:
            if unit:  # Ignorer les unités NULL
                unit_counts[unit] = count
        
        # Compter les éléments avec et sans section
        with_section_count = query.filter(ElementOuvrage.section_id != None).count()
        without_section_count = total_count - with_section_count
        
        # Assembler les statistiques
        statistics = {
            "total_count": total_count,
            "price_statistics": {
                "min_price": price_stats.min_price if price_stats.min_price else 0,
                "max_price": price_stats.max_price if price_stats.max_price else 0,
                "avg_price": price_stats.avg_price if price_stats.avg_price else 0,
                "total_price": price_stats.total_price if price_stats.total_price else 0
            },
            "units": unit_counts,
            "section_statistics": {
                "with_section": with_section_count,
                "without_section": without_section_count,
                "section_coverage_percent": round((with_section_count / total_count) * 100) if total_count > 0 else 0
            }
        }
        
        return statistics
    
    def analyze_dpgf_quality(
        self,
        client_id: Optional[int] = None,
        dpgf_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Analyse la qualité des imports DPGF pour détecter les problèmes
        comme le manque de lots, sections ou éléments
        
        Args:
            client_id: Filtrer par client
            dpgf_id: Filtrer par DPGF spécifique
            
        Returns:
            Rapport d'analyse avec problèmes détectés
        """
        # Résultat d'analyse
        analysis = {
            "total_dpgfs": 0,
            "total_lots": 0,
            "total_sections": 0,
            "total_elements": 0,
            "problematic_dpgfs": [],
            "problems_summary": {
                "dpgfs_without_lots": 0,
                "dpgfs_with_empty_lots": 0,
                "lots_without_sections": 0,
                "lots_without_elements": 0,
                "sections_without_elements": 0
            }
        }
        
        # Base de la requête pour les DPGF
        dpgf_query = self.db.query(DPGF)
        if client_id:
            dpgf_query = dpgf_query.filter(DPGF.id_client == client_id)
        if dpgf_id:
            dpgf_query = dpgf_query.filter(DPGF.id_dpgf == dpgf_id)
            
        # Récupérer les DPGF
        dpgfs = dpgf_query.all()
        analysis["total_dpgfs"] = len(dpgfs)
        
        # Analyser chaque DPGF
        for dpgf in dpgfs:
            dpgf_analysis = {
                "id": dpgf.id_dpgf,
                "nom": dpgf.nom_projet,
                "client_id": dpgf.id_client,
                "client_nom": self.db.query(Client.nom_client).filter(Client.id_client == dpgf.id_client).scalar() if dpgf.id_client else None,
                "lots_count": 0,
                "sections_count": 0,
                "elements_count": 0,
                "problems": [],
                "problematic_lots": []
            }
            
            # Récupérer les lots
            lots = self.db.query(Lot).filter(Lot.id_dpgf == dpgf.id_dpgf).all()
            dpgf_analysis["lots_count"] = len(lots)
            analysis["total_lots"] += len(lots)
            
            # Vérifier s'il y a des lots
            if not lots:
                dpgf_analysis["problems"].append({
                    "type": "dpgf_sans_lots",
                    "severity": "high",
                    "description": f"DPGF sans aucun lot"
                })
                analysis["problems_summary"]["dpgfs_without_lots"] += 1
            
            # Analyser chaque lot
            for lot in lots:
                lot_analysis = {
                    "id": lot.id_lot,
                    "numero": lot.numero_lot,
                    "nom": lot.nom_lot,
                    "sections_count": 0,
                    "elements_count": 0,
                    "problems": []
                }
                
                # Récupérer les sections
                sections = self.db.query(Section).filter(Section.id_lot == lot.id_lot).all()
                lot_analysis["sections_count"] = len(sections)
                analysis["total_sections"] += len(sections)
                
                # Récupérer les éléments
                elements = self.db.query(ElementOuvrage).filter(ElementOuvrage.id_section.in_([s.id_section for s in sections])).all() if sections else []
                lot_analysis["elements_count"] = len(elements)
                analysis["total_elements"] += len(elements)
                dpgf_analysis["elements_count"] += len(elements)
                
                # Vérifier si le lot n'a pas de sections
                if not sections:
                    lot_analysis["problems"].append({
                        "type": "lot_sans_sections",
                        "severity": "medium",
                        "description": f"Lot sans aucune section"
                    })
                    analysis["problems_summary"]["lots_without_sections"] += 1
                
                # Vérifier si le lot n'a pas d'éléments
                if not elements:
                    lot_analysis["problems"].append({
                        "type": "lot_sans_elements",
                        "severity": "high",
                        "description": f"Lot sans aucun élément d'ouvrage"
                    })
                    analysis["problems_summary"]["lots_without_elements"] += 1
                
                # Analyser chaque section
                section_elements_count = 0
                for section in sections:
                    section_elements = [e for e in elements if e.id_section == section.id_section]
                    section_elements_count += len(section_elements)
                    
                    # Vérifier si la section n'a pas d'éléments
                    if not section_elements:
                        lot_analysis["problems"].append({
                            "type": "section_sans_elements",
                            "severity": "medium",
                            "description": f"Section '{section.titre_section}' sans aucun élément d'ouvrage"
                        })
                        analysis["problems_summary"]["sections_without_elements"] += 1
                
                # Vérifier les éléments sans section
                elements_without_section = len(elements) - section_elements_count
                if elements_without_section > 0:
                    lot_analysis["problems"].append({
                        "type": "elements_sans_section",
                        "severity": "low",
                        "description": f"{elements_without_section} éléments sans section assignée"
                    })
                
                # Ajouter le lot au rapport s'il a des problèmes
                if lot_analysis["problems"]:
                    dpgf_analysis["problematic_lots"].append(lot_analysis)
            
            # Vérifier si le DPGF a des lots vides (sans éléments)
            if dpgf_analysis["lots_count"] > 0 and dpgf_analysis["elements_count"] == 0:
                dpgf_analysis["problems"].append({
                    "type": "dpgf_avec_lots_vides",
                    "severity": "high",
                    "description": f"DPGF avec {dpgf_analysis['lots_count']} lots mais aucun élément d'ouvrage"
                })
                analysis["problems_summary"]["dpgfs_with_empty_lots"] += 1
            
            # Ajouter le DPGF au rapport final s'il a des problèmes
            if dpgf_analysis["problems"] or dpgf_analysis["problematic_lots"]:
                analysis["problematic_dpgfs"].append(dpgf_analysis)
        
        # Ajouter des statistiques générales
        if analysis["total_dpgfs"] > 0:
            analysis["statistics"] = {
                "avg_lots_per_dpgf": analysis["total_lots"] / analysis["total_dpgfs"],
                "avg_sections_per_lot": analysis["total_sections"] / analysis["total_lots"] if analysis["total_lots"] > 0 else 0,
                "avg_elements_per_lot": analysis["total_elements"] / analysis["total_lots"] if analysis["total_lots"] > 0 else 0,
                "dpgfs_with_problems_percentage": len(analysis["problematic_dpgfs"]) * 100 / analysis["total_dpgfs"]
            }
            
            # Classification des DPGF selon la qualité
            problem_counts = [
                len(dpgf["problems"]) + sum(len(lot["problems"]) for lot in dpgf["problematic_lots"])
                for dpgf in analysis["problematic_dpgfs"]
            ]
            
            analysis["quality_classification"] = {
                "excellent": analysis["total_dpgfs"] - len(analysis["problematic_dpgfs"]),
                "bon": len([c for c in problem_counts if c <= 2]),
                "moyen": len([c for c in problem_counts if 2 < c <= 5]),
                "mauvais": len([c for c in problem_counts if c > 5])
            }
        
        return analysis
