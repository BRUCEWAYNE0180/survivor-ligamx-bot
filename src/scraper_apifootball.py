#!/usr/bin/env python3
"""Scraper usando API-Football para obtener cuotas de Liga MX"""
import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def obtener_cuotas_ligamx():
    print("=" * 60)
    print("SCRAPER: API-Football - Cuotas Liga MX")
    print("=" * 60)
    
    api_key = os.getenv("APIFOOTBALL_KEY")
    
    if not api_key:
        print("❌ No se encontró APIFOOTBALL_KEY en .env")
        return None
    
    print(f"✅ API Key: {api_key[:10]}...")
    
    headers = {
        "x-apisports-key": api_key
    }
    
    # Obtener próximos partidos de Liga MX (league_id = 128)
    print("\n📡 Obteniendo próximos partidos de Liga MX...")
    fixtures_url = "https://v3.football.api-sports.io/fixtures"
    params = {
        "league": 128,  # Liga MX
        "season": 2026,
        "next": 10
    }
    
    try:
        response = requests.get(fixtures_url, headers=headers, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            print(f"   {response.text[:200]}")
            return None
        
        data = response.json()
        fixtures = data.get("response", [])
        
        if not fixtures:
            print("⚠️ No hay partidos próximos de Liga MX")
            return None
        
        print(f"✅ Se encontraron {len(fixtures)} partidos")
        
        # Ahora obtener cuotas para cada partido
        print("\n🎰 Obteniendo cuotas...")
        odds_url = "https://v3.football.api-sports.io/odds"
        
        jornada_procesada = []
        
        for fixture in fixtures:
            fixture_id = fixture["fixture"]["id"]
            home_team = fixture["teams"]["home"]["name"]
            away_team = fixture["teams"]["away"]["name"]
            fixture_date = fixture["fixture"]["date"]
            
            print(f"\n  📊 {home_team} vs {away_team}")
            
            # Obtener cuotas para este partido
            odds_params = {
                "fixture": fixture_id
            }
            
            try:
                odds_response = requests.get(odds_url, headers=headers, params=odds_params, timeout=30)
                
                if odds_response.status_code == 200:
                    odds_data = odds_response.json()
                    odds_list = odds_data.get("response", [])
                    
                    if odds_list:
                        # Extraer cuotas del primer bookmaker
                        bookmakers = odds_list[0].get("bookmakers", [])
                        if bookmakers:
                            markets = bookmakers[0].get("bets", [])
                            
                            # Buscar mercado 1X2 (Match Winner)
                            match_winner = next((m for m in markets if m["name"] == "Match Winner"), None)
                            
                            if match_winner:
                                outcomes = match_winner.get("value", [])
                                
                                # Buscar cuotas para Local, Empate, Visitante
                                home_odds = next((o["odd"] for o in outcomes if o["value"] == "Home"), None)
                                draw_odds = next((o["odd"] for o in outcomes if o["value"] == "Draw"), None)
                                away_odds = next((o["odd"] for o in outcomes if o["value"] == "Away"), None)
                                
                                partido = {
                                    "home_team": home_team,
                                    "away_team": away_team,
                                    "fixture_date": fixture_date,
                                    "fixture_id": fixture_id,
                                    "bookmakers": {
                                        "markets": {
                                            "outcomes": [
                                                {"name": "Home", "price": home_odds},
                                                {"name": "Draw", "price": draw_odds},
                                                {"name": "Away", "price": away_odds}
                                            ] if home_odds and draw_odds and away_odds else []
                                        }
                                    }
                                }
                                
                                jornada_procesada.append(partido)
                                print(f"     ✅ Cuotas: {home_odds} | {draw_odds} | {away_odds}")
                            else:
                                print(f"     ⚠️ No se encontró mercado Match Winner")
                        else:
                            print(f"     ⚠️ No hay bookmakers disponibles")
                    else:
                        print(f"     ⚠️ No hay cuotas disponibles")
                else:
                    print(f"     ⚠️ Error al obtener cuotas: {odds_response.status_code}")
            
            except Exception as e:
                print(f"     ❌ Error: {e}")
        
        # Guardar en jornadas.json
        if jornada_procesada:
            os.makedirs('data', exist_ok=True)
            with open('data/jornadas.json', 'w', encoding='utf-8') as f:
                json.dump(jornada_procesada, f, indent=4, ensure_ascii=False)
            
            print(f"\n✅ Se guardaron {len(jornada_procesada)} partidos en data/jornadas.json")
            return jornada_procesada
        else:
            print("\n⚠️ No se pudieron obtener cuotas para ningún partido")
            return None
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    obtener_cuotas_ligamx()
