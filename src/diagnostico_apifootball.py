#!/usr/bin/env python3
"""Diagnóstico completo de API-Football"""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

def diagnosticar():
    print("=" * 70)
    print("DIAGNÓSTICO COMPLETO: API-Football")
    print("=" * 70)
    
    api_key = os.getenv("APIFOOTBALL_KEY")
    
    if not api_key:
        print("❌ No se encontró APIFOOTBALL_KEY")
        return
    
    print(f"✅ API Key: {api_key[:10]}...")
    
    headers = {"x-apisports-key": api_key}
    
    # 1. Verificar ligas disponibles
    print("\n📊 BUSCANDO LIGA MX...")
    leagues_url = "https://v3.football.api-sports.io/leagues"
    params = {"country": "Mexico"}
    
    try:
        response = requests.get(leagues_url, headers=headers, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Error al obtener ligas: {response.status_code}")
            return
        
        data = response.json()
        leagues = data.get("response", [])
        
        print(f"✅ Se encontraron {len(leagues)} ligas en México")
        
        # Buscar Liga MX
        liga_mx = None
        for league in leagues:
            league_info = league.get("league", {})
            name = league_info.get("name", "")
            league_id = league_info.get("id")
            
            print(f"\n  📌 {name}")
            print(f"     ID: {league_id}")
            print(f"     Tipo: {league_info.get('type', 'N/A')}")
            print(f"     Temporada actual: {league_info.get('current_season', 'N/A')}")
            
            if "liga mx" in name.lower() or "mx" in name.lower():
                liga_mx = league
                print(f"     🇲🇽 <<< ESTA ES LIGA MX >>>")
        
        if not liga_mx:
            print("\n❌ No se encontró Liga MX en las ligas de México")
            print("\n📋 Todas las ligas disponibles:")
            for league in leagues:
                print(f"   - {league.get('league', {}).get('name')} (ID: {league.get('league', {}).get('id')})")
            return
        
        # 2. Verificar temporadas disponibles
        print("\n\n📅 VERIFICANDO TEMPORADAS...")
        seasons_url = "https://v3.football.api-sports.io/seasons"
        params = {"league": liga_mx["league"]["id"]}
        
        response = requests.get(seasons_url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            seasons_data = response.json()
            seasons = seasons_data.get("response", [])
            print(f"✅ Temporadas disponibles: {', '.join(map(str, seasons))}")
            
            # Usar la temporada más reciente
            current_season = max(seasons) if seasons else 2026
            print(f"📌 Usando temporada: {current_season}")
        else:
            print(f"⚠️ No se pudieron obtener temporadas, usando 2026")
            current_season = 2026
        
        # 3. Buscar partidos
        print(f"\n\n🔍 BUSCANDO PARTIDOS (Liga {liga_mx['league']['id']}, Temporada {current_season})...")
        fixtures_url = "https://v3.football.api-sports.io/fixtures"
        
        # Probar diferentes parámetros
        for next_count in [10, 20, 50]:
            params = {
                "league": liga_mx["league"]["id"],
                "season": current_season,
                "next": next_count
            }
            
            print(f"\n  Intentando con next={next_count}...")
            response = requests.get(fixtures_url, headers=headers, params=params, timeout=30)
            
            if response.status_code != 200:
                print(f"  ❌ Error: {response.status_code}")
                continue
            
            data = response.json()
            fixtures = data.get("response", [])
            
            print(f"  📊 Respuesta: {len(fixtures)} partidos")
            
            if fixtures:
                print(f"\n✅ ¡Se encontraron {len(fixtures)} partidos!")
                print("\n📋 Primeros 3 partidos:")
                for i, fixture in enumerate(fixtures[:3], 1):
                    f = fixture["fixture"]
                    teams = fixture["teams"]
                    print(f"\n  {i}. {teams['home']['name']} vs {teams['away']['name']}")
                    print(f"     Fecha: {f['date']}")
                    print(f"     Estado: {f['status']['short']}")
                    print(f"     ID: {f['id']}")
                
                # Guardar información completa
                with open('data/diagnostico_fixtures.json', 'w', encoding='utf-8') as f_out:
                    json.dump(fixtures, f_out, indent=2, ensure_ascii=False)
                print(f"\n💾 Información completa guardada en data/diagnostico_fixtures.json")
                
                return fixtures
            else:
                print(f"  ⚠️ No hay partidos con next={next_count}")
        
        # 4. Intentar con fecha específica
        print("\n\n📅 INTENTANDO CON FECHA ESPECÍFICA...")
        from datetime import datetime, timedelta
        
        for days in [0, 7, 14, 30]:
            date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
            params = {
                "league": liga_mx["league"]["id"],
                "season": current_season,
                "from": date,
                "to": date
            }
            
            print(f"\n  Buscando partidos para {date}...")
            response = requests.get(fixtures_url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                fixtures = data.get("response", [])
                
                if fixtures:
                    print(f"  ✅ ¡Se encontraron {len(fixtures)} partidos para {date}!")
                    return fixtures
                else:
                    print(f"  ⚠️ No hay partidos para {date}")
        
        print("\n\n❌ No se encontraron partidos de Liga MX en ningún rango de fechas")
        print("💡 Posibles razones:")
        print("   - La temporada no ha comenzado")
        print("   - No hay partidos programados")
        print("   - La API no tiene datos actualizados")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 70)

if __name__ == "__main__":
    diagnosticar()
