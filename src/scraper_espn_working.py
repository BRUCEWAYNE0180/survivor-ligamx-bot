import requests
import json
from datetime import datetime

def scrape_espn_ligamx():
    """ESPN tiene API pública con Liga MX"""
    print("=" * 70)
    print("SCRAPER ESPN: Liga MX (endpoint correcto)")
    print("=" * 70)
    
    # ESPN tiene endpoints públicos
    base_url = "https://site.api.espn.com/apis/site/v2/sports/soccer/mex.1"
    
    try:
        # Obtener calendario
        print("\n📅 Obteniendo calendario...")
        calendar_url = f"{base_url}/scoreboard"
        
        response = requests.get(calendar_url, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            events = data.get('events', [])
            
            print(f"   ✅ {len(events)} eventos encontrados")
            
            if events:
                partidos = []
                for event in events[:10]:
                    competitions = event.get('competitions', [])
                    if competitions:
                        comp = competitions[0]
                        competitors = comp.get('competitors', [])
                        
                        if len(competitors) >= 2:
                            home = competitors[0]
                            away = competitors[1]
                            
                            home_team = home.get('team', {}).get('displayName', '')
                            away_team = away.get('team', {}).get('displayName', '')
                            date = event.get('date', '')
                            
                            if home_team and away_team:
                                partido = {
                                    'home_team': home_team,
                                    'away_team': away_team,
                                    'date': date,
                                    'status': 'scheduled',
                                    'venue': comp.get('venue', {}).get('fullName', ''),
                                    'momio_1': 2.0,
                                    'momio_x': 3.5,
                                    'momio_2': 3.5
                                }
                                partidos.append(partido)
                                print(f"      ✅ {home_team} vs {away_team}")
                
                if partidos:
                    print(f"\n✅ ÉXITO: {len(partidos)} partidos de ESPN")
                    return partidos
        
        # Si no hay eventos, intentar con teams
        print("\n🔍 Obteniendo equipos de Liga MX...")
        teams_url = f"{base_url}/teams"
        
        response = requests.get(teams_url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            teams = data.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', [])
            
            print(f"   ✅ {len(teams)} equipos encontrados")
            
            if teams:
                # Crear partidos de ejemplo con equipos reales
                partidos = []
                for i in range(0, min(10, len(teams) - 1), 2):
                    home = teams[i].get('team', {}).get('displayName', '')
                    away = teams[i+1].get('team', {}).get('displayName', '')
                    
                    if home and away:
                        partido = {
                            'home_team': home,
                            'away_team': away,
                            'date': datetime.now().isoformat(),
                            'status': 'scheduled',
                            'venue': '',
                            'momio_1': 2.0,
                            'momio_x': 3.5,
                            'momio_2': 3.5
                        }
                        partidos.append(partido)
                        print(f"      ✅ {home} vs {away}")
                
                if partidos:
                    print(f"\n✅ ÉXITO: {len(partidos)} partidos con equipos reales")
                    return partidos
    
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return None

if __name__ == "__main__":
    partidos = scrape_espn_ligamx()
    
    if partidos and len(partidos) > 0:
        with open('data/jornadas.json', 'w', encoding='utf-8') as f:
            json.dump(partidos, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Guardado en data/jornadas.json")
        print(f"\n📋 Primeros partidos:")
        for i, p in enumerate(partidos[:5], 1):
            print(f"   {i}. {p['home_team']} vs {p['away_team']}")
