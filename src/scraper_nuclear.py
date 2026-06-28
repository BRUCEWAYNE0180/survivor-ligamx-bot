import requests
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup
import time

def scrape_sofascore_ligamx_directo():
    """Buscar Liga MX directamente en SofaScore"""
    print("=" * 70)
    print("MÉTODO 1: SofaScore - Búsqueda directa de Liga MX")
    print("=" * 70)
    
    base_url = "https://api.sofascore.com/api/v1"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
    }
    
    # Buscar directamente "Liga MX"
    search_terms = ["Liga MX", "LigaMX", "Mexico Liga", "Primera Division Mexico"]
    
    for term in search_terms:
        print(f"\n🔍 Buscando: {term}")
        
        try:
            url = f"{base_url}/search/tournaments/{term}"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                tournaments = data.get('tournaments', [])
                
                for tournament in tournaments:
                    name = tournament.get('name', '')
                    tournament_id = tournament.get('uniqueTournament', {}).get('id')
                    country = tournament.get('category', {}).get('name', '')
                    
                    print(f"   ✅ {name} ({country}) - ID: {tournament_id}")
                    
                    if 'mexico' in country.lower() or 'mx' in name.lower():
                        print(f"   🎯 LIGA MX ENCONTRADA!")
                        return get_sofascore_partidos(tournament_id, headers)
        
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    return None

def get_sofascore_partidos(tournament_id, headers):
    """Obtener partidos de SofaScore"""
    base_url = "https://api.sofascore.com/api/v1"
    
    try:
        # Obtener temporadas
        seasons_url = f"{base_url}/unique-tournament/{tournament_id}/seasons"
        response = requests.get(seasons_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return None
        
        seasons_data = response.json()
        seasons = seasons_data.get('seasons', [])
        
        if not seasons:
            return None
        
        # Usar la temporada más reciente
        current_season = seasons[0]
        season_id = current_season.get('id')
        print(f"   Temporada: {current_season.get('name')}")
        
        # Obtener próximos partidos
        events_url = f"{base_url}/unique-tournament/{tournament_id}/season/{season_id}/events/next/0"
        response = requests.get(events_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return None
        
        events_data = response.json()
        events = events_data.get('events', [])
        
        if not events:
            return None
        
        print(f"   ✅ {len(events)} partidos encontrados")
        
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
                    'venue': '',
                    'momio_1': 2.0,
                    'momio_x': 3.5,
                    'momio_2': 3.5
                }
                partidos.append(partido)
                print(f"      ✅ {home_team} vs {away_team}")
        
        return partidos
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def scrape_oddsportal():
    """OddsPortal tiene Liga MX"""
    print("\n" + "=" * 70)
    print("MÉTODO 2: OddsPortal")
    print("=" * 70)
    
    url = "https://www.oddsportal.com/football/mexico/liga-mx/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar partidos
            matches = soup.find_all('div', class_='event__match')
            
            if not matches:
                # Intentar con otros selectores
                matches = soup.find_all('tr', class_='stage-finished')
            
            print(f"   ✅ {len(matches)} elementos encontrados")
            
            partidos = []
            for match in matches[:10]:
                home = match.find('span', class_='event__participant--home')
                away = match.find('span', class_='event__participant--away')
                
                if home and away:
                    partido = {
                        'home_team': home.text.strip(),
                        'away_team': away.text.strip(),
                        'date': '',
                        'status': 'scheduled',
                        'venue': '',
                        'momio_1': 2.0,
                        'momio_x': 3.5,
                        'momio_2': 3.5
                    }
                    partidos.append(partido)
                    print(f"      ✅ {partido['home_team']} vs {partido['away_team']}")
            
            if partidos:
                return partidos
    
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return None

def scrape_flashscore_mejorado():
    """Flashscore con parsing mejorado"""
    print("\n" + "=" * 70)
    print("MÉTODO 3: Flashscore (parsing mejorado)")
    print("=" * 70)
    
    url = "https://www.flashscore.com.mx/futbol/mexico/liga-mx/calendario/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar en scripts
            scripts = soup.find_all('script')
            
            for script in scripts:
                if script.string:
                    # Buscar patrones de partidos
                    content = script.string
                    
                    # Buscar JSON embebido
                    json_matches = re.findall(r'\{[^{}]*"homeTeam"[^{}]*\}', content)
                    
                    if json_matches:
                        print(f"   ✅ {len(json_matches)} partidos en script")
                        
                        partidos = []
                        for match_str in json_matches[:10]:
                            try:
                                match_data = json.loads(match_str)
                                home = match_data.get('homeTeam', {}).get('name', '')
                                away = match_data.get('awayTeam', {}).get('name', '')
                                
                                if home and away:
                                    partido = {
                                        'home_team': home,
                                        'away_team': away,
                                        'date': '',
                                        'status': 'scheduled',
                                        'venue': '',
                                        'momio_1': 2.0,
                                        'momio_x': 3.5,
                                        'momio_2': 3.5
                                    }
                                    partidos.append(partido)
                                    print(f"      ✅ {home} vs {away}")
                            except:
                                continue
                        
                        if partidos:
                            return partidos
    
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return None

def scrape_betexplorer():
    """BetExplorer tiene Liga MX"""
    print("\n" + "=" * 70)
    print("MÉTODO 4: BetExplorer")
    print("=" * 70)
    
    url = "https://www.betexplorer.com/next/soccer/mexico/liga-mx/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar partidos
            matches = soup.find_all('tr', class_='table-main')
            
            print(f"   ✅ {len(matches)} elementos encontrados")
            
            partidos = []
            for match in matches[:10]:
                home = match.find('td', class_='h-m')
                away = match.find('td', class_='a-m')
                
                if home and away:
                    partido = {
                        'home_team': home.text.strip(),
                        'away_team': away.text.strip(),
                        'date': '',
                        'status': 'scheduled',
                        'venue': '',
                        'momio_1': 2.0,
                        'momio_x': 3.5,
                        'momio_2': 3.5
                    }
                    partidos.append(partido)
                    print(f"      ✅ {partido['home_team']} vs {partido['away_team']}")
            
            if partidos:
                return partidos
    
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return None

def main():
    print("\n" + "=" * 70)
    print("🚀 SCRAPER NUCLEAR: Múltiples métodos agresivos")
    print("=" * 70)
    
    # Método 1: SofaScore directo
    print("\n[1/4] Intentando SofaScore...")
    partidos = scrape_sofascore_ligamx_directo()
    
    if partidos and len(partidos) > 0:
        print(f"\n✅ ÉXITO con SofaScore: {len(partidos)} partidos")
        return partidos
    
    # Método 2: OddsPortal
    print("\n[2/4] Intentando OddsPortal...")
    partidos = scrape_oddsportal()
    
    if partidos and len(partidos) > 0:
        print(f"\n✅ ÉXITO con OddsPortal: {len(partidos)} partidos")
        return partidos
    
    # Método 3: Flashscore mejorado
    print("\n[3/4] Intentando Flashscore...")
    partidos = scrape_flashscore_mejorado()
    
    if partidos and len(partidos) > 0:
        print(f"\n✅ ÉXITO con Flashscore: {len(partidos)} partidos")
        return partidos
    
    # Método 4: BetExplorer
    print("\n[4/4] Intentando BetExplorer...")
    partidos = scrape_betexplorer()
    
    if partidos and len(partidos) > 0:
        print(f"\n✅ ÉXITO con BetExplorer: {len(partidos)} partidos")
        return partidos
    
    print("\n" + "=" * 70)
    print("❌ No se pudo obtener datos de ninguna fuente")
    print("=" * 70)
    
    return None

if __name__ == "__main__":
    partidos = main()
    
    if partidos and len(partidos) > 0:
        with open('data/jornadas.json', 'w', encoding='utf-8') as f:
            json.dump(partidos, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Guardado en data/jornadas.json")
        print(f"\n📋 Primeros partidos:")
        for i, p in enumerate(partidos[:5], 1):
            print(f"   {i}. {p['home_team']} vs {p['away_team']}")
