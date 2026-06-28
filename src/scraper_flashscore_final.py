import requests
import json
import re
from datetime import datetime

def scrape_flashscore_ligamx():
    """Flashscore API interna para Liga MX"""
    print("=" * 70)
    print("SCRAPER FLASHSCORE: Liga MX")
    print("=" * 70)
    
    # Flashscore usa IDs específicos para cada liga
    # Liga MX tiene ID: tr_1 (Turkey) o mx_1 (Mexico)
    # Vamos a probar diferentes IDs
    
    base_url = "https://d.flashscore.com/x/feed"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'x-fsign': 'SW9D1eZo',
        'Accept': 'application/json',
        'Accept-Language': 'es-MX,es;q=0.9',
    }
    
    # IDs posibles para Liga MX
    liga_ids = [
        'mx_1',      # Liga MX
        'mexico_1',  # Alternativa
        'liga_mx',   # Alternativa
    ]
    
    for liga_id in liga_ids:
        print(f"\n🔍 Probando ID: {liga_id}")
        
        # Endpoint para partidos próximos
        url = f"{base_url}/f_1_{liga_id}_1_es_1"
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                content = response.text
                print(f"   ✅ Respuesta recibida ({len(content)} bytes)")
                
                # Flashscore devuelve datos en formato especial
                # Vamos a parsearlo
                partidos = parse_flashscore_data(content)
                
                if partidos and len(partidos) > 0:
                    print(f"\n✅ {len(partidos)} partidos encontrados")
                    return partidos
                else:
                    print("   ⚠️ No se pudieron extraer partidos")
        
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Si no funciona con IDs específicos, probar con el feed general
    print("\n🔍 Probando feed general...")
    return scrape_flashscore_general(headers)

def parse_flashscore_data(content):
    """Parsear datos de Flashscore"""
    partidos = []
    
    try:
        # Flashscore usa un formato especial con ~ como separador
        lines = content.split('\n')
        
        for line in lines:
            if '~' in line:
                parts = line.split('~')
                
                # Buscar líneas con información de partidos
                if len(parts) >= 10:
                    # Extraer equipos y datos
                    home_team = parts[2] if len(parts) > 2 else ''
                    away_team = parts[3] if len(parts) > 3 else ''
                    date_str = parts[4] if len(parts) > 4 else ''
                    
                    if home_team and away_team and 'vs' not in home_team.lower():
                        partido = {
                            'home_team': clean_team_name(home_team),
                            'away_team': clean_team_name(away_team),
                            'date': date_str,
                            'status': 'scheduled',
                            'venue': '',
                            'momio_1': 2.0,
                            'momio_x': 3.5,
                            'momio_2': 3.5
                        }
                        partidos.append(partido)
                        print(f"   ✅ {partido['home_team']} vs {partido['away_team']}")
    
    except Exception as e:
        print(f"   ❌ Error parseando: {e}")
    
    return partidos

def clean_team_name(name):
    """Limpiar nombre de equipo"""
    # Remover caracteres especiales
    name = re.sub(r'[^\w\sáéíóúñÁÉÍÓÚÑ]', '', name)
    return name.strip()

def scrape_flashscore_general(headers):
    """Scraping general de Flashscore"""
    print("\n🔍 Flashscore (método general)...")
    
    # URL de Liga MX en Flashscore
    url = "https://www.flashscore.com.mx/futbol/mexico/liga-mx/"
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar scripts con datos
            scripts = soup.find_all('script')
            
            for script in scripts:
                if script.string and ('tournamentCalendar' in script.string or 'events' in script.string):
                    print("   ✅ Script con datos encontrado")
                    
                    # Extraer JSON del script
                    json_match = re.search(r'({.*})', script.string, re.DOTALL)
                    if json_match:
                        try:
                            data = json.loads(json_match.group(1))
                            return extract_partidos_from_json(data)
                        except:
                            continue
            
            # Si no hay scripts, buscar en HTML
            return extract_partidos_from_html(soup)
    
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return None

def extract_partidos_from_json(data):
    """Extraer partidos de JSON"""
    partidos = []
    
    try:
        events = data.get('events', [])
        
        for event in events[:10]:
            home = event.get('homeTeam', {}).get('name', '')
            away = event.get('awayTeam', {}).get('name', '')
            
            if home and away:
                partido = {
                    'home_team': home,
                    'away_team': away,
                    'date': event.get('date', ''),
                    'status': 'scheduled',
                    'venue': '',
                    'momio_1': 2.0,
                    'momio_x': 3.5,
                    'momio_2': 3.5
                }
                partidos.append(partido)
                print(f"   ✅ {home} vs {away}")
    
    except Exception as e:
        print(f"   ❌ Error extrayendo JSON: {e}")
    
    return partidos

def extract_partidos_from_html(soup):
    """Extraer partidos de HTML"""
    partidos = []
    
    try:
        # Buscar contenedores de partidos
        match_divs = soup.find_all('div', class_=re.compile(r'match|fixture|game', re.I))
        
        for div in match_divs[:10]:
            teams = div.find_all(['span', 'a'], class_=re.compile(r'team|name', re.I))
            
            if len(teams) >= 2:
                home = teams[0].text.strip()
                away = teams[1].text.strip()
                
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
                    print(f"   ✅ {home} vs {away}")
    
    except Exception as e:
        print(f"   ❌ Error extrayendo HTML: {e}")
    
    return partidos

def main():
    partidos = scrape_flashscore_ligamx()
    
    if partidos and len(partidos) > 0:
        print(f"\n{'=' * 70}")
        print(f"✅ ÉXITO: {len(partidos)} partidos de Liga MX")
        print(f"{'=' * 70}")
        
        with open('data/jornadas.json', 'w', encoding='utf-8') as f:
            json.dump(partidos, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Guardado en data/jornadas.json")
        print(f"\n📋 Primeros partidos:")
        for i, p in enumerate(partidos[:5], 1):
            print(f"   {i}. {p['home_team']} vs {p['away_team']}")
        
        return partidos
    
    print(f"\n{'=' * 70}")
    print("❌ No se pudieron obtener partidos de Flashscore")
    print(f"{'=' * 70}")
    
    return None

if __name__ == "__main__":
    main()
