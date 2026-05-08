"""Générateur de table calendrier pour analyses temporelles."""

import pandas as pd
from datetime import datetime, timedelta
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CALENDAR_PATH = os.path.join(BASE_DIR, "calendar.csv")


def generate_calendar(start_date="2023-01-01", end_date="2026-12-31"):
    """
    Génère une table calendrier complète pour analyses temporelles.

    Args:
        start_date (str): Date de début (YYYY-MM-DD)
        end_date (str): Date de fin (YYYY-MM-DD)

    Returns:
        pd.DataFrame: Table calendrier avec colonnes temporelles
    """
    # Génère la plage de dates
    dates = pd.date_range(start=start_date, end=end_date, freq='D')

    # Création du DataFrame de base
    calendar = pd.DataFrame({
        'Date': dates,
        'Année': dates.year,
        'Mois': dates.month,
        'Nom_Mois': dates.strftime('%B'),
        'Jour': dates.day,
        'Jour_Semaine': dates.dayofweek + 1,  # 1=Lundi, 7=Dimanche
        'Nom_Jour_Semaine': dates.strftime('%A'),
        'Semaine_Année': dates.isocalendar().week,
        'Trimestre': ((dates.month - 1) // 3) + 1,
        'Semestre': ((dates.month - 1) // 6) + 1,
        'Est_Weekend': dates.dayofweek >= 5,  # Samedi=5, Dimanche=6
        'Est_Jour_Férié': False,  # À compléter selon les jours fériés locaux
        'Fin_De_Mois': dates.is_month_end,
        'Fin_De_Trimestre': dates.is_quarter_end,
        'Fin_De_Semestre': (dates.month % 6 == 0) & dates.is_month_end,
        'Fin_De_Année': dates.is_year_end,
    })

    # Ajout de colonnes calculées supplémentaires
    calendar['Mois_Année'] = calendar['Date'].dt.strftime('%Y-%m')
    calendar['Trimestre_Année'] = calendar['Date'].dt.year.astype(str) + '-Q' + calendar['Trimestre'].astype(str)
    calendar['Semestre_Année'] = calendar['Date'].dt.year.astype(str) + '-S' + calendar['Semestre'].astype(str)

    # Numéro de semaine dans le mois
    calendar['Semaine_Mois'] = ((calendar['Jour'] - 1) // 7) + 1

    # Jours ouvrés (hors weekend et jours fériés)
    calendar['Est_Jour_Ouvré'] = (~calendar['Est_Weekend']) & (~calendar['Est_Jour_Férié'])

    # Colonnes pour analyses saisonnières
    calendar['Saison'] = pd.cut(
        calendar['Mois'],
        bins=[0, 3, 6, 9, 12],
        labels=['Hiver', 'Printemps', 'Été', 'Automne']
    )

    # Colonnes pour périodes fiscales (si applicable)
    # À adapter selon les besoins fiscaux locaux
    calendar['Période_Fiscale'] = calendar['Trimestre']

    return calendar


def save_calendar(calendar_df, output_path=CALENDAR_PATH):
    """
    Sauvegarde la table calendrier au format CSV.

    Args:
        calendar_df (pd.DataFrame): Table calendrier
        output_path (str): Chemin de sauvegarde
    """
    calendar_df.to_csv(output_path, index=False, encoding='utf-8')
    print(f"[OK] Table calendrier sauvegardee : {output_path}")
    print(f"   Periode : {calendar_df['Date'].min()} -> {calendar_df['Date'].max()}")
    print(f"   Nombre de jours : {len(calendar_df)}")


def get_calendar_sample():
    """Retourne un échantillon de la table calendrier pour vérification."""
    calendar = generate_calendar("2023-01-01", "2023-12-31")
    return calendar.head(10)


if __name__ == "__main__":
    # Génération de la table calendrier complète
    calendar_df = generate_calendar()

    # Sauvegarde
    save_calendar(calendar_df)

    # Affichage d'un échantillon
    print("\n[CALENDAR] Echantillon de la table calendrier :")
    print(get_calendar_sample().to_string(index=False))