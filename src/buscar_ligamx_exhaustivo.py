import requests
import json
from datetime import datetime
import time

def buscar_por_pais():
    """Buscar torneos de México específicamente"""
    print("=" * 70)
    print("BÚSQUEDA EXHAUSTIVA DE LIGA MX")
    print("=" * 70)
    
    base_url = "https://api.sofascore.com/api/v1"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Accept': 'application/json',
    }
    
    # Primero intentar obtener todos los países
    print("\n🌍 Obteniendo lista de países...")
    
    try:
        countries_url = f"{base_url}/sport/football/countries"
        response = requests.get(countries_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            countries = data.get('countries', [])
            
            # Buscar México
            mexico = None
            for country in countries:
                name = country.get('name', '')
                if 'mexico' in name.lower() or 'méxico' in name.lower():
                    mexico = country
                    print(f"✅ México encontrado: {name} (ID: {country.get('id')})")
                    break
            
            if mexico:
                country_id = mexico.get('id')
                
                # Obtener torneos de México
                print(f"\n🏆 Obteniendo torneos de México...")
                tournaments_url = f"{base_url}/country/{country_id}/unique-tournaments"
                response = requests.get(tournaments_url, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    tournaments = data.get('uniqueTournaments', [])
                    
                    print(f"✅ {len(tournaments)} torneos encontrados en México")
                    
                    # Buscar Liga MX
                    for tournament in tournaments:
                        name = tournament.get('name', '')
                        tournament_id = tournament.get('id')
                        
                        print(f"   - {name} (ID: {tournament_id})")
                        
                        if 'liga mx' in name.lower() or 'ligamx' in name.lower():
                            print(f"\n🎯 LIGA MX ENCONTRADA!")
                            print(f"   ID: {tournament_id}")
                            print(f"   Nombre: {name}")
                            
                            # Guardar el ID
                            with open('data/ligamx_sofascore_id.txt', 'w') as f:
                                f.write(str(tournament_id))
                            
                            return tournament_id
        
        print("❌ No se pudo obtener por país")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return None

def buscar_exhaustivo():
    """Buscar en rangos masivos de IDs"""
    print("\n🔍 Búsqueda exhaustiva en rangos masivos...")
    
    base_url = "https://api.sofascore.com/api/v1"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Accept': 'application/json',
    }
    
    # Rangos a probar
    rangos = [
        (1, 100),
        (300, 500),
        (500, 700),
        (700, 900),
        (900, 1100),
        (1100, 1300),
        (1300, 1500)
    ]
    
    for inicio, fin in rangos:
        print(f"\n📊 Probando IDs {inicio}-{fin}...")
        
        for tournament_id in range(inicio, fin, 5):  # Saltar de 5 en 5 para ser más rápido
            try:
                url = f"{base_url}/unique-tournament/{tournament_id}"
                response = requests.get(url, headers=headers, timeout=3)
                
                if response.status_code == 200:
                    data = response.json()
                    name = data.get('name', '')
                    category = data.get('category', {})
                    country = category.get('name', '')
                    
                    # Buscar por nombre o país
                    if ('mexico' in name.lower() or 'mexico' in country.lower() or 
                        'liga mx' in name.lower() or 'méxico' in country.lower()):
                        print(f"\n✅ POSIBLE LIGA MX!")
                        print(f"   ID: {tournament_id}")
                        print(f"   Nombre: {name}")
                        print(f"   País: {country}")
                        
                        # Confirmar
                        confirm = input("¿Es Liga MX? (s/n): ")
                        if confirm.lower() == 's':
                            with open('data/ligamx_sofascore_id.txt', 'w') as f:
                                f.write(str(tournament_id))
                            return tournament_id
                
                # Pausa para no saturar la API
                if tournament_id % 50 == 0:
                    time.sleep(0.5)
                
            except:
                continue
    
    return None

def obtener_partidos(tournament_id):
    """Obtener partidos del torneo"""
    print(f"\n📅 Obteniendo partidos del torneo {tournament_id}...")
    
    base_url = "https://api.sofascore.com/api/v1"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Accept': 'application/json',
    }
    
    try:
        # Obtener temporadas
        seasons_url = f"{base_url}/unique-tournament/{tournament_id}/seasons"
        response = requests.get(seasons_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            return None
        
        seasons_data = response.json()
        seasons = seasons_data.get('seasons', [])
        
        if not seasons:
            print("❌ No hay temporadas")
            return None
        
        # Usar la temporada más reciente
        current_season = seasons[0]
        season_id = current_season.get('id')
        print(f"✅ Temporada: {current_season.get('name')}")
        
        # Obtener próximos partidos
        events_url = f"{base_url}/unique-tournament/{tournament_id}/season/{season_id}/events/next/0"
        response = requests.get(events_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            return None
        
        events_data = response.json()
        events = events_data.get('events', [])
        
        if not events:
            print("⚠️ No hay próximos partidos")
            return None
        
        print(f"✅ {len(events)} partidos encontrados\n")
        
        partidos = []
        for event in events[:10]:
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
                    'momio_1': 2.0,
                    'momio_x': 3.5,
                    'momio_2': 3.5
                }
                partidos.append(partido)
                print(f"  ✅ {home_team} vs {away_team}")
        
        return partidos
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def main():
    # Método 1: Buscar por país
    tournament_id = buscar_por_pais()
    
    if not tournament_id:
        # Método 2: Búsqueda exhaustiva
        tournament_id = buscar_exhaustivo()
    
    if tournament_id:
        partidos = obtener_partidos(tournament_id)
        
        if partidos and len(partidos) > 0:
            print(f"\n{'=' * 70}")
            print(f"✅ ÉXITO: {len(partidos)} partidos")
            print(f"{'=' * 70}")
            
            with open('data/jornadas.json', 'w', encoding='utf-8') as f:
                json.dump(partidos, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Guardado en data/jornadas.json")
            return partidos
    
    print(f"\n{'=' * 70}")
    print("❌ No se encontró Liga MX")
    print("💡 Pero seguimos buscando...")
    print(f"{'=' * 70}")
    
    return None

if __name__ == "__main__":
    main()
