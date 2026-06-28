import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

def scrape_espn_ligamx():
    print("🔍 Obteniendo datos de Liga MX desde ESPN...")
    
    url = "https://www.espn.com.mx/futbol/liga/_nombre/mex.mx.1"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        partidos = []
        
        # Buscar partidos en la página
        # ESPN usa diferentes estructuras, vamos a buscar patrones
        scripts = soup.find_all('script')
        
        for script in scripts:
            if script.string and 'window.__espnfitt__scoreboard' in script.string:
                # Extraer JSON del script
                match = re.search(r'window\.__espnfitt__scoreboard\s*=\s*({.*?});', script.string, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        
                        # Navegar por la estructura de ESPN
                        events = data.get('page', {}).get('content', {}).get('scoreboard', {}).get('evts', [])
                        
                        for event in events:
                            competition = event.get('cp', {})
                            if 'mx.1' in competition.get('id', '') or 'Liga MX' in competition.get('name', ''):
                                
                                competitors = event.get('competitors', [])
                                if len(competitors) >= 2:
                                    home = competitors[0]
                                    away = competitors[1]
                                    
                                    partido = {
                                        'home_team': home.get('team', {}).get('displayName', ''),
                                        'away_team': away.get('team', {}).get('displayName', ''),
                                        'date': event.get('date', ''),
                                        'status': event.get('status', {}).get('type', {}).get('description', ''),
                                        'venue': event.get('venue', {}).get('fullName', '')
                                    }
                                    
                                    partidos.append(partido)
                                    print(f"✅ {partido['home_team']} vs {partido['away_team']}")
                    except json.JSONDecodeError:
                        continue
        
        if not partidos:
            print("⚠️ No se encontraron partidos en ESPN, intentando método alternativo...")
            return scrape_espn_alternative()
        
        print(f"\n✅ Total: {len(partidos)} partidos encontrados")
        
        # Guardar en jornadas.json
        with open('data/jornadas.json', 'w', encoding='utf-8') as f:
            json.dump(partidos, f, indent=2, ensure_ascii=False)
        
        print("💾 Guardado en data/jornadas.json")
        return partidos
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def scrape_espn_alternative():
    """Método alternativo buscando en la página de partidos"""
    print("🔄 Intentando método alternativo...")
    
    url = "https://www.espn.com.mx/futbol/liga/partidos/_nombre/mex.mx.1"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        partidos = []
        
        # Buscar tablas de partidos
        tables = soup.find_all('table', class_='Table')
        
        for table in tables:
            rows = table.find_all('tr', class_='Table__tr')
            
            for row in rows:
                try:
                    # Buscar nombres de equipos
                    teams = row.find_all('span', class_='team-name')
                    if len(teams) >= 2:
                        partido = {
                            'home_team': teams[0].text.strip(),
                            'away_team': teams[1].text.strip(),
                            'date': '',
                            'status': '',
                            'venue': ''
                        }
                        partidos.append(partido)
                        print(f"✅ {partido['home_team']} vs {partido['away_team']}")
                except:
                    continue
        
        if partidos:
            print(f"\n✅ Total: {len(partidos)} partidos encontrados")
            
            with open('data/jornadas.json', 'w', encoding='utf-8') as f:
                json.dump(partidos, f, indent=2, ensure_ascii=False)
            
            print("💾 Guardado en data/jornadas.json")
            return partidos
        
        return None
        
    except Exception as e:
        print(f"❌ Error en método alternativo: {e}")
        return None

if __name__ == "__main__":
    scrape_espn_ligamx()
