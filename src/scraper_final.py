import requests
import json
from datetime import datetime, timedelta

def scrape_sofascore_correct():
    """SofaScore API con estructura correcta"""
    print("🔍 SofaScore API (estructura correcta)...")
    
    # ID de Liga MX en SofaScore es 131
    # Necesitamos obtener la temporada actual primero
    base_url = "https://api.sofascore.com/api/v1"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Accept': 'application/json',
    }
    
    try:
        # Obtener temporadas del torneo
        print("  Buscando temporadas...")
        seasons_url = f"{base_url}/unique-tournament/131/seasons"
        response = requests.get(seasons_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"  ❌ Error obteniendo temporadas: {response.status_code}")
            return None
        
        seasons_data = response.json()
        seasons = seasons_data.get('seasons', [])
        
        if not seasons:
            print("  ❌ No se encontraron temporadas")
            return None
        
        # Usar la temporada más reciente
        current_season = seasons[0]
        season_id = current_season.get('id')
        print(f"  ✅ Temporada actual: {current_season.get('name')} (ID: {season_id})")
        
        # Obtener eventos de la temporada
        print("  Obteniendo partidos...")
        events_url = f"{base_url}/unique-tournament/131/season/{season_id}/events/next/0"
        response = requests.get(events_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"  ❌ Error obteniendo eventos: {response.status_code}")
            return None
        
        events_data = response.json()
        events = events_data.get('events', [])
        
        if not events:
            print("  ⚠️ No hay próximos partidos")
            return None
        
        print(f"  ✅ {len(events)} partidos encontrados")
        
        partidos = []
        for event in events[:10]:  # Primeros 10 partidos
            home_team = event.get('homeTeam', {}).get('name', '')
            away_team = event.get('awayTeam', {}).get('name', '')
            start_timestamp = event.get('startTimestamp', 0)
            
            if home_team and away_team:
                partido = {
                    'home_team': home_team,
                    'away_team': away_team,
                    'date': datetime.fromtimestamp(start_timestamp).isoformat() if start_timestamp else '',
                    'status': 'scheduled',
                    'venue': event.get('venue', {}).get('name', ''),
                    'momio_1': 2.0,  # Momios por defecto
                    'momio_x': 3.5,
                    'momio_2': 3.5
                }
                partidos.append(partido)
                print(f"    ✅ {home_team} vs {away_team}")
        
        return partidos
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

def scrape_api_football_free():
    """API-Football free tier"""
    print("🔍 API-Football (free tier)...")
    
    # Esta es una API gratuita que tiene Liga MX
    url = "https://v3.football.api-sports.io/fixtures"
    
    headers = {
        'x-apisports-key': 'tu_api_key_aqui',  # Necesitarás registrarte
        'Accept': 'application/json'
    }
    
    params = {
        'league': 128,  # Liga MX
        'season': 2026,
        'next': 10
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            fixtures = data.get('response', [])
            
            if fixtures:
                print(f"  ✅ {len(fixtures)} partidos encontrados")
                return fixtures
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    return None

def scrape_the_odds_api():
    """The Odds API - verificar si tiene Liga MX"""
    print("🔍 The Odds API (verificando Liga MX)...")
    
    url = "https://api.the-odds-api.com/v4/sports"
    
    params = {
        'apiKey': 'tu_key_aqui',  # Necesitarás registrarte
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            sports = response.json()
            
            # Buscar Liga MX
            liga_mx = [s for s in sports if 'mexico' in s.get('key', '').lower()]
            
            if liga_mx:
                print(f"  ✅ Liga MX encontrada: {liga_mx[0]}")
                return liga_mx[0]
            else:
                print("  ❌ Liga MX no disponible en The Odds API")
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    return None

def main():
    print("=" * 70)
    print("SCRAPER FINAL: Múltiples métodos automáticos")
    print("=" * 70)
    
    # Método 1: SofaScore (el más prometedor)
    print("\n[MÉTODO 1] SofaScore API")
    partidos = scrape_sofascore_correct()
    
    if partidos and len(partidos) > 0:
        print(f"\n✅ ÉXITO con SofaScore: {len(partidos)} partidos")
        
        # Guardar en jornadas.json
        with open('data/jornadas.json', 'w', encoding='utf-8') as f:
            json.dump(partidos, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Guardado en data/jornadas.json")
        print("\n📋 Partidos:")
        for i, p in enumerate(partidos[:5], 1):
            print(f"  {i}. {p['home_team']} vs {p['away_team']}")
        
        return partidos
    
    print("\n❌ No se pudo obtener datos automáticamente")
    print("\n💡 Siguiente paso: Crear sistema de actualización manual rápida")
    
    return None

if __name__ == "__main__":
    main()
