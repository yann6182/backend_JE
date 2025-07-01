#!/usr/bin/env python3
"""
Script d'analyse de qualité des imports DPGF
============================================

Ce script analyse les imports DPGF pour détecter et signaler les problèmes :
- DPGF sans lots
- Lots sans sections
- Lots sans éléments d'ouvrage
- Sections sans éléments
- Éléments sans section assignée

Usage:
    python analyze_import_quality.py [options]

Exemples:
    # Analyser tous les DPGF
    python analyze_import_quality.py
    
    # Analyser un client spécifique
    python analyze_import_quality.py --client-id 1
    
    # Analyser un DPGF spécifique
    python analyze_import_quality.py --dpgf-id 5
    
    # Générer un rapport détaillé
    python analyze_import_quality.py --detailed --output-format excel
"""

import sys
import os
import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

# Ajouter le répertoire parent au path pour l'import
sys.path.append(str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.services.element_search import ElementSearchService
from app.db.models.client import Client
from app.db.models.dpgf import DPGF


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure le logging"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f'logs/quality_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        ]
    )
    return logging.getLogger(__name__)


def analyze_quality(
    client_id: int = None,
    dpgf_id: int = None,
    detailed: bool = False,
    logger: logging.Logger = None
) -> dict:
    """
    Analyse la qualité des imports DPGF
    
    Args:
        client_id: ID du client à analyser (optionnel)
        dpgf_id: ID du DPGF à analyser (optionnel)
        detailed: Inclure les détails des problèmes
        logger: Logger pour les messages
        
    Returns:
        Dictionnaire avec l'analyse de qualité
    """
    logger = logger or logging.getLogger(__name__)
    
    logger.info("Démarrage de l'analyse de qualité des imports DPGF")
    
    # Créer une session de base de données
    db = SessionLocal()
    
    try:
        # Créer le service de recherche
        search_service = ElementSearchService(db)
        
        # Effectuer l'analyse
        logger.info("Analyse des DPGF en cours...")
        analysis = search_service.analyze_dpgf_quality(
            client_id=client_id,
            dpgf_id=dpgf_id
        )
        
        # Afficher un résumé
        logger.info(f"Analyse terminée:")
        logger.info(f"   {analysis['total_dpgfs']} DPGF analysés")
        logger.info(f"   {analysis['total_lots']} lots")
        logger.info(f"   {analysis['total_sections']} sections")
        logger.info(f"   {analysis['total_elements']} éléments")
        
        # Afficher les problèmes détectés
        problems = analysis['problems_summary']
        total_problems = sum(problems.values())
        
        if total_problems > 0:
            logger.warning(f"{total_problems} problèmes détectés:")
            if problems['dpgfs_without_lots'] > 0:
                logger.warning(f"   {problems['dpgfs_without_lots']} DPGF sans lots")
            if problems['dpgfs_with_empty_lots'] > 0:
                logger.warning(f"   {problems['dpgfs_with_empty_lots']} DPGF avec lots vides")
            if problems['lots_without_sections'] > 0:
                logger.warning(f"   {problems['lots_without_sections']} lots sans sections")
            if problems['lots_without_elements'] > 0:
                logger.warning(f"   {problems['lots_without_elements']} lots sans éléments")
            if problems['sections_without_elements'] > 0:
                logger.warning(f"   {problems['sections_without_elements']} sections sans éléments")
        else:
            logger.info("Aucun problème détecté ! Tous les imports semblent corrects.")
        
        # Afficher les recommandations
        if 'recommendations' in analysis and analysis['recommendations']:
            logger.info("Recommandations:")
            for rec in analysis['recommendations']:
                priority_indicator = "[HAUTE]" if rec['priority'] == 'high' else "[MOYENNE]" if rec['priority'] == 'medium' else "[BASSE]"
                logger.info(f"   {priority_indicator} {rec['action']} ({rec['affected_count']} affectés)")
        
        # Détails des DPGF problématiques si demandé
        if detailed and analysis['problematic_dpgfs']:
            logger.info("\nDÉTAILS DES DPGF PROBLÉMATIQUES:")
            logger.info("=" * 60)
            
            for dpgf in analysis['problematic_dpgfs']:
                logger.info(f"\nDPGF: {dpgf['nom']} (ID: {dpgf['id']})")
                logger.info(f"   Client: {dpgf['client_nom'] or 'Non spécifié'}")
                logger.info(f"   {dpgf['lots_count']} lots, {dpgf['sections_count']} sections, {dpgf['elements_count']} éléments")
                
                # Problèmes généraux du DPGF
                if dpgf['problems']:
                    logger.warning("   Problèmes généraux:")
                    for problem in dpgf['problems']:
                        severity_indicator = "[CRITIQUE]" if problem['severity'] == 'high' else "[MOYEN]" if problem['severity'] == 'medium' else "[FAIBLE]"
                        logger.warning(f"      {severity_indicator} {problem['description']}")
                
                # Problèmes des lots
                if dpgf['problematic_lots']:
                    logger.warning("   Lots problématiques:")
                    for lot in dpgf['problematic_lots']:
                        logger.warning(f"      Lot {lot['numero']}: {lot['nom']}")
                        logger.warning(f"         {lot['sections_count']} sections, {lot['elements_count']} éléments")
                        for problem in lot['problems']:
                            severity_indicator = "[CRITIQUE]" if problem['severity'] == 'high' else "[MOYEN]" if problem['severity'] == 'medium' else "[FAIBLE]"
                            logger.warning(f"         {severity_indicator} {problem['description']}")
        
        return analysis
        
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse: {e}")
        raise
    finally:
        db.close()


def save_report(analysis: dict, output_format: str, output_file: str = None):
    """
    Sauvegarde le rapport d'analyse
    
    Args:
        analysis: Données d'analyse
        output_format: Format de sortie ('json', 'txt', 'excel')
        output_file: Nom du fichier de sortie (optionnel)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if not output_file:
        output_file = f"quality_report_{timestamp}"
    
    # Créer le répertoire reports s'il n'existe pas
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    
    if output_format == 'json':
        file_path = reports_dir / f"{output_file}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False, default=str)
        print(f"Rapport JSON sauvegardé: {file_path}")
    
    elif output_format == 'txt':
        file_path = reports_dir / f"{output_file}.txt"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("RAPPORT D'ANALYSE DE QUALITÉ DES IMPORTS DPGF\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Date d'analyse: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Résumé
            f.write("RÉSUMÉ:\n")
            f.write(f"- DPGF analysés: {analysis['total_dpgfs']}\n")
            f.write(f"- Lots: {analysis['total_lots']}\n")
            f.write(f"- Sections: {analysis['total_sections']}\n")
            f.write(f"- Éléments: {analysis['total_elements']}\n\n")
            
            # Problèmes
            problems = analysis['problems_summary']
            total_problems = sum(problems.values())
            f.write(f"PROBLÈMES DÉTECTÉS: {total_problems}\n")
            for key, count in problems.items():
                if count > 0:
                    f.write(f"- {key.replace('_', ' ').title()}: {count}\n")
            f.write("\n")
            
            # Recommandations
            if 'recommendations' in analysis:
                f.write("RECOMMANDATIONS:\n")
                for rec in analysis['recommendations']:
                    f.write(f"- [{rec['priority'].upper()}] {rec['action']} ({rec['affected_count']} affectés)\n")
                f.write("\n")
            
            # Détails des DPGF problématiques
            if analysis['problematic_dpgfs']:
                f.write("DPGF PROBLÉMATIQUES:\n")
                for dpgf in analysis['problematic_dpgfs']:
                    f.write(f"\n{dpgf['nom']} (ID: {dpgf['id']}):\n")
                    f.write(f"  Client: {dpgf['client_nom'] or 'Non spécifié'}\n")
                    f.write(f"  Lots: {dpgf['lots_count']}, Sections: {dpgf['sections_count']}, Éléments: {dpgf['elements_count']}\n")
                    
                    if dpgf['problems']:
                        f.write("  Problèmes généraux:\n")
                        for problem in dpgf['problems']:
                            f.write(f"    - [{problem['severity'].upper()}] {problem['description']}\n")
                    
                    if dpgf['problematic_lots']:
                        f.write("  Lots problématiques:\n")
                        for lot in dpgf['problematic_lots']:
                            f.write(f"    Lot {lot['numero']} ({lot['nom']}):\n")
                            for problem in lot['problems']:
                                f.write(f"      - [{problem['severity'].upper()}] {problem['description']}\n")
        
        print(f"Rapport texte sauvegardé: {file_path}")
    
    elif output_format == 'excel':
        try:
            import pandas as pd
            
            file_path = reports_dir / f"{output_file}.xlsx"
            
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Feuille de résumé
                summary_data = {
                    'Métrique': ['DPGF analysés', 'Lots', 'Sections', 'Éléments', 'DPGF problématiques'],
                    'Valeur': [
                        analysis['total_dpgfs'],
                        analysis['total_lots'],
                        analysis['total_sections'],
                        analysis['total_elements'],
                        len(analysis['problematic_dpgfs'])
                    ]
                }
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='Résumé', index=False)
                
                # Feuille des problèmes
                problems_data = []
                for key, count in analysis['problems_summary'].items():
                    problems_data.append({
                        'Type de problème': key.replace('_', ' ').title(),
                        'Nombre': count
                    })
                pd.DataFrame(problems_data).to_excel(writer, sheet_name='Problèmes', index=False)
                
                # Feuille des DPGF problématiques
                if analysis['problematic_dpgfs']:
                    dpgf_data = []
                    for dpgf in analysis['problematic_dpgfs']:
                        dpgf_data.append({
                            'ID': dpgf['id'],
                            'Nom': dpgf['nom'],
                            'Client': dpgf['client_nom'] or 'Non spécifié',
                            'Lots': dpgf['lots_count'],
                            'Sections': dpgf['sections_count'],
                            'Éléments': dpgf['elements_count'],
                            'Problèmes': len(dpgf['problems']) + sum(len(lot['problems']) for lot in dpgf['problematic_lots'])
                        })
                    pd.DataFrame(dpgf_data).to_excel(writer, sheet_name='DPGF problématiques', index=False)
            
            print(f"Rapport Excel sauvegardé: {file_path}")
            
        except ImportError:
            print("pandas non disponible. Utilisation du format JSON à la place.")
            save_report(analysis, 'json', output_file)


def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(
        description="Analyse la qualité des imports DPGF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  %(prog)s                              # Analyser tous les DPGF
  %(prog)s --client-id 1                # Analyser un client spécifique
  %(prog)s --dpgf-id 5                  # Analyser un DPGF spécifique
  %(prog)s --detailed                   # Rapport détaillé
  %(prog)s --output-format excel        # Sortie Excel
        """
    )
    
    parser.add_argument('--client-id', type=int, help='ID du client à analyser')
    parser.add_argument('--dpgf-id', type=int, help='ID du DPGF à analyser')
    parser.add_argument('--detailed', action='store_true', help='Afficher les détails des problèmes')
    parser.add_argument('--output-format', choices=['json', 'txt', 'excel'], default='txt',
                       help='Format du rapport de sortie (défaut: txt)')
    parser.add_argument('--output-file', help='Nom du fichier de sortie (sans extension)')
    parser.add_argument('--verbose', action='store_true', help='Mode verbeux')
    
    args = parser.parse_args()
    
    # Configuration du logging
    logger = setup_logging(args.verbose)
    
    try:
        # Effectuer l'analyse
        analysis = analyze_quality(
            client_id=args.client_id,
            dpgf_id=args.dpgf_id,
            detailed=args.detailed,
            logger=logger
        )
        
        # Sauvegarder le rapport
        save_report(analysis, args.output_format, args.output_file)
        
        # Code de sortie basé sur les problèmes détectés
        total_problems = sum(analysis['problems_summary'].values())
        if total_problems > 0:
            logger.warning(f"{total_problems} problèmes détectés. Consultez le rapport pour plus de détails.")
            sys.exit(1)
        else:
            logger.info("Aucun problème détecté. Tous les imports sont de bonne qualité.")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        sys.exit(2)


if __name__ == '__main__':
    main()
