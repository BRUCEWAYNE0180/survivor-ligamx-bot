import requests
import json
from datetime import datetime
import xml.etree.ElementTree as ET

def probar_sportsdata():
    """Sportsdata.io tiene free tier"""
    print("🔍 Sportsdata.io...")
    
    # API gratuita con Liga MX
    url = "https://api.sportsdata.io/v3/soccer/scores/json/Competitions"
    
    params = {
        'key': 'test'  # Key de prueba
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            for comp in data:
                if 'mexico' in comp.get('Name', '').lower():
                    print(f"   ✅ {comp.get('Name')}")
                    return comp.get('CompetitionID')
    
    except Exception as e:
        print(f"   ❌ {e}")
    
    return None

def probar_futbol24():
    """Futbol24.com tiene datos"""
    print("🔍 Futbol24.com...")
    
    url = "https://www.futbol24.com/Live/Mexico/Liga-MX/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar partidos
            matches = soup.find_all('div', class_='match')
            print(f"   ✅ {len(matches)} elementos encontrados")
            
            if matches:
                return True
    
    except Exception as e:
        print(f"   ❌ {e}")
    
    return None

def probar_rss_espn():
    """RSS feed de ESPN México"""
    print("🔍 ESPN RSS Feed...")
    
    url = "https://www.espn.com.mx/rss/futbol/mexico/news"
    
    try:
        response = requests.get(url, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            items = root.findall('.//item')
            print(f"   ✅ {len(items)} noticias encontradas")
            
            # Buscar noticias sobre partidos
            for item in items[:5]:
                title = item.find('title').text
                print(f"      - {title}")
            
            return True
    
    except Exception as e:
        print(f"   ❌ {e}")
    
    return None

def probar_google_sheets():
    """Buscar Google Sheets públicos con datos de Liga MX"""
    print("🔍 Google Sheets públicos...")
    
    # Este es un sheet público de ejemplo con datos de Liga MX
    sheet_id = "1X2Y3Z4A5B6C7D8E9F0G"  # ID de ejemplo
    
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/Sheet1"
    
    params = {
        'key': 'AIzaSyDummyKey'  # Key de ejemplo
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Datos encontrados")
            return True
    
    except Exception as e:
        print(f"   ❌ {e}")
    
    return None

def probar_sofascore_busqueda():
    """Buscar en SofaScore por nombre de equipo"""
    print("🔍 SofaScore (búsqueda por equipo)...")
    
    base_url = "https://api.sofascore.com/api/v1"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Accept': 'application/json',
    }
    
    # Buscar equipos conocidos de Liga MX
    equipos = ["Club America", "Chivas", "Cruz Azul", "Pumas", "Tigres"]
    
    for equipo in equipos:
        try:
            url = f"{base_url}/search/teams/{equipo}"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                teams = data.get('teams', [])
                
                for team in teams:
                    team_name = team.get('name', '')
                    tournament = team.get('tournament', {})
                    tournament_name = tournament.get('name', '')
                    tournament_id = tournament.get('uniqueTournament', {}).get('id')
                    
                    if 'america' in team_name.lower() or 'chivas' in team_name.lower():
                        print(f"   ✅ {team_name} en {tournament_name} (ID: {tournament_id})")
                        
                        if tournament_id:
                            return tournament_id
        
        except Exception as e:
            continue
    
    return None

def probar_api_deportes_mexico():
    """APIs específicas de México"""
    print("🔍 APIs deportivas de México...")
    
    # Probar diferentes endpoints
    urls = [
        "https://api.ligamx.mx/v1/partidos",
        "https://datos.ligamx.mx/api/partidos",
        "https://api.fmf.mx/partidos"
    ]
    
    for url in urls:
        try:
            response = requests.get(url, timeout=10)
            print(f"   {url}: {response.status_code}")
            
            if response.status_code == 200:
                return True
        
        except:
            continue
    
    return None

def probar_flashscore_mejorado():
    """Flashscore con mejor scraping"""
    print("🔍 Flashscore (mejorado)...")
    
    # Flashscore tiene una API interna
    url = "https://d.flashscore.com/x/feed/f_1_xxxxx_1_es_1"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'x-fsign': 'SW9D1eZo',
        'Accept': 'application/json',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ Datos obtenidos")
            return True
    
    except Exception as e:
        print(f"   ❌ {e}")
    
    return None

def main():
    print("=" * 70)
    print("BÚSQUEDA TOTAL: Todas las fuentes posibles")
    print("=" * 70)
    
    fuentes = [
        ("Sportsdata.io", probar_sportsdata),
        ("Futbol24.com", probar_futbol24),
        ("ESPN RSS", probar_rss_espn),
        ("Google Sheets", probar_google_sheets),
        ("SofaScore (equipos)", probar_sofascore_busqueda),
        ("APIs México", probar_api_deportes_mexico),
        ("Flashscore", probar_flashscore_mejorado)
    ]
    
    resultados = {}
    
    for nombre, funcion in fuentes:
        print(f"\n[{nombre}]")
        resultado = funcion()
        resultados[nombre] = resultado
        
        if resultado:
            print(f"   🎯 POSIBLE SOLUCIÓN")
    
    print(f"\n{'=' * 70}")
    print("RESUMEN:")
    print(f"{'=' * 70}")
    
    for nombre, resultado in resultados.items():
        status = "✅" if resultado else "❌"
        print(f"{status} {nombre}")
    
    # Si encontramos algo en SofaScore por equipo
    if resultados.get("SofaScore (equipos)"):
        print(f"\n💡 Usar el ID encontrado en SofaScore")
        return resultados["SofaScore (equipos)"]
    
    return None

if __name__ == "__main__":
    main()
