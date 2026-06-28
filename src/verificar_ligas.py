#!/usr/bin/env python3
"""Verificar qué ligas tiene acceso tu API key"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def verificar():
    print("=" * 70)
    print("VERIFICAR LIGAS DISPONIBLES")
    print("=" * 70)
    
    api_key = os.getenv("APIFOOTBALL_KEY")
    
    if not api_key:
        print("❌ No se encontró APIFOOTBALL_KEY")
        return
    
    print(f"✅ API Key: {api_key[:10]}...")
    
    headers = {"x-apisports-key": api_key}
    
    # Obtener TODAS las ligas (sin filtro)
    print("\n📊 OBTENIENDO TODAS LAS LIGAS DISPONIBLES...")
    leagues_url = "https://v3.football.api-sports.io/leagues"
    
    try:
        response = requests.get(leagues_url, headers=headers, timeout=30)
        
        print(f"📡 Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Error: {response.text[:300]}")
            return
        
        data = response.json()
        leagues = data.get("response", [])
        
        print(f"✅ Total de ligas disponibles: {len(leagues)}")
        
        # Mostrar primeras 20 ligas
        print(f"\n📋 PRIMERAS 20 LIGAS:")
        for i, league in enumerate(leagues[:20], 1):
            league_info = league.get("league", {})
            country = league.get("country", {})
            name = league_info.get("name", "N/A")
            country_name = country.get("name", "N/A")
            league_id = league_info.get("id", "N/A")
            
            print(f"  {i:2d}. {name} ({country_name}) - ID: {league_id}")
        
        # Buscar ligas populares
        print(f"\n\n🔍 BUSCANDO LIGAS POPULARES:")
        popular = ["Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1", "Liga MX"]
        
        for search_term in popular:
            found = [l for l in leagues if search_term.lower() in l.get("league", {}).get("name", "").lower()]
            
            if found:
                print(f"\n  ✅ {search_term}:")
                for league in found:
                    league_info = league.get("league", {})
                    country = league.get("country", {})
                    print(f"     - {league_info.get('name')} ({country.get('name')}) - ID: {league_info.get('id')}")
            else:
                print(f"\n  ❌ {search_term}: NO DISPONIBLE")
        
        # Contar por país
        print(f"\n\n🌍 LIGAS POR PAÍS:")
        countries = {}
        for league in leagues:
            country_name = league.get("country", {}).get("name", "Desconocido")
            countries[country_name] = countries.get(country_name, 0) + 1
        
        # Mostrar top 15 países
        sorted_countries = sorted(countries.items(), key=lambda x: x[1], reverse=True)[:15]
        for country, count in sorted_countries:
            print(f"  {country}: {count} ligas")
        
        # Verificar si México está
        if "Mexico" in countries:
            print(f"\n✅ México tiene {countries['Mexico']} ligas disponibles")
        else:
            print(f"\n❌ México NO está en las ligas disponibles")
            print("💡 Tu plan de API-Football no incluye ligas de México")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 70)

if __name__ == "__main__":
    verificar()
