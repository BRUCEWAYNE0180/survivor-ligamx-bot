import requests
import json
from datetime import datetime

def find_ligamx_id():
    """Buscar el ID correcto de Liga MX en SofaScore"""
    print("=" * 70)
    print("BUSCANDO LIGA MX EN SOFASCORE")
    print("=" * 70)
    
    base_url = "https://api.sofascore.com/api/v1"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Accept': 'application/json',
    }
    
    # Probar diferentes IDs de torneos populares
    # Liga MX suele estar en el rango 100-200
    print("\n🔍 Probando IDs de torneos...")
    
    for tournament_id in range(100, 300):
        try:
            url = f"{base_url}/unique-tournament/{tournament_id}"
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                name = data.get('name', '')
                category = data.get('category', {})
                country = category.get('name', '')
                
                # Buscar Liga MX
                if 'mexico' in name.lower() or 'liga mx' in name.lower() or 'mex' in name.lower():
                    print(f"\n✅ ENCONTRADO!")
                    print(f"   ID: {tournament_id}")
                    print(f"   Nombre: {name}")
                    print(f"   País: {country}")
                    
                    # Guardar el ID
                    with open('data/ligamx_sofascore_id.txt', 'w') as f:
                        f.write(str(tournament_id))
                    
                    print(f"\n💾 ID guardado en data/ligamx_sofascore_id.txt")
                    
                    # Obtener partidos
                    return get_partidos(tournament_id, headers)
                
                # Mostrar algunos para referencia
                if tournament_id % 20 == 0:
                    print(f"   ID {tournament_id}: {name} ({country})")
        
        except Exception as e:
            continue
    
    print("\n❌ No se encontró Liga MX en el rango 100-300")
    print("Intentando rangos adicionales...")
    
    # Probar rangos adicionales
    for tournament_id in list(range(1, 100)) + list(range(300, 500)):
        try:
            url = f"{base_url}/unique-tournament/{tournament_id}"
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                name = data.get('name', '')
                category = data.get('category', {})
                country = category.get('name', '')
                
                if 'mexico' in name.lower() or 'liga mx' in name.lower():
                    print(f"\n✅ ENCONTRADO!")
                    print(f"   ID: {tournament_id}")
                    print(f"   Nombre: {name}")
                    print(f"   País: {country}")
                    
                    with open('data/ligamx_sofascore_id.txt', 'w') as f:
                        f.write(str(tournament_id))
                    
                    return get_partidos(tournament_id, headers)
        
        except:
            continue
    
    return None

def get_partidos(tournament_id, headers):
    """Obtener partidos del torneo encontrado"""
    print(f"\n📅 Obteniendo partidos del torneo {tournament_id}...")
    
    base_url = "https://api.sofascore.com/api/v1"
    
    try:
        # Obtener temporadas
        seasons_url = f"{base_url}/unique-tournament/{tournament_id}/seasons"
        response = requests.get(seasons_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Error obteniendo temporadas: {response.status_code}")
            return None
        
        seasons_data = response.json()
        seasons = seasons_data.get('seasons', [])
        
        if not seasons:
            print("❌ No se encontraron temporadas")
            return None
        
        # Usar la temporada más reciente
        current_season = seasons[0]
        season_id = current_season.get('id')
        print(f"✅ Temporada: {current_season.get('name')} (ID: {season_id})")
        
        # Obtener próximos partidos
        events_url = f"{base_url}/unique-tournament/{tournament_id}/season/{season_id}/events/next/0"
        response = requests.get(events_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Error obteniendo eventos: {response.status_code}")
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
    partidos = find_ligamx_id()
    
    if partidos and len(partidos) > 0:
        print(f"\n{'=' * 70}")
        print(f"✅ ÉXITO: {len(partidos)} partidos de Liga MX")
        print(f"{'=' * 70}")
        
        with open('data/jornadas.json', 'w', encoding='utf-8') as f:
            json.dump(partidos, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Guardado en data/jornadas.json")
        return partidos
    
    print(f"\n{'=' * 70}")
    print("❌ No se encontró Liga MX")
    print("💡 Continuaremos buscando...")
    print(f"{'=' * 70}")
    
    return None

if __name__ == "__main__":
    main()
