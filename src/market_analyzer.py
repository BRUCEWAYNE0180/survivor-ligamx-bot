import pandas as pd
from scipy.stats import poisson
import numpy as np

def calculate_over_under_prob(home_expected, away_expected, line=2.5):
    """Calcula probabilidades Over/Under"""
    total_goals = home_expected + away_expected
    
    # Probabilidad de cada cantidad de goles
    goal_probs = [poisson.pmf(i, total_goals) for i in range(10)]
    
    under_prob = sum(goal_probs[:int(line)])
    over_prob = 1 - under_prob
    
    return {
        "over": round(over_prob, 4),
        "under": round(under_prob, 4),
        "expected_goals": round(total_goals, 2)
    }

def calculate_btts_prob(home_expected, away_expected):
    """Calcula probabilidad de Ambos Equipos Marcan"""
    home_no_goal = poisson.pmf(0, home_expected)
    away_no_goal = poisson.pmf(0, away_expected)
    
    btts_no = home_no_goal + away_no_goal - (home_no_goal * away_no_goal)
    btts_yes = 1 - btts_no
    
    return {
        "yes": round(btts_yes, 4),
        "no": round(btts_no, 4)
    }

def calculate_double_chance(home_win, draw, away_win):
    """Calcula doble oportunidad"""
    return {
        "1X": round(home_win + draw, 4),
        "X2": round(draw + away_win, 4),
        "12": round(home_win + away_win, 4)
    }

def analyze_additional_markets(home_odds, draw_odds, away_odds):
    """Analiza todos los mercados adicionales"""
    # Calcular probabilidades implícitas
    total_margin = 1/home_odds + 1/draw_odds + 1/away_odds
    
    home_prob = (1/home_odds) / total_margin
    draw_prob = (1/draw_odds) / total_margin
    away_prob = (1/away_odds) / total_margin
    
    # Calcular goles esperados (aproximación simple)
    home_expected = home_prob * 2.5
    away_expected = away_prob * 2.5
    
    # Analizar mercados
    over_under = calculate_over_under_prob(home_expected, away_expected)
    btts = calculate_btts_prob(home_expected, away_expected)
    double_chance = calculate_double_chance(home_prob, draw_prob, away_prob)
    
    return {
        "over_under_2.5": over_under,
        "btts": btts,
        "double_chance": double_chance,
        "expected_goals": {
            "home": round(home_expected, 2),
            "away": round(away_expected, 2),
            "total": round(home_expected + away_expected, 2)
        }
    }
