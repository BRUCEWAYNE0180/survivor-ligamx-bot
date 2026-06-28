import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

def scrape_mediottiempo():
    """Scraping desde Mediotiempo - más accesible"""
    print("🔍 Intentando Mediotiempo...")
    
    url = "https://www.mediottiempo.com/futbol/liga-mx"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'es-MX,es;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    try:
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=30, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        partidos = []
        
        # Buscar partidos en la página
        # Mediotiempo usa diferentes selectores
        match_containers = soup.find_all('div', class_=re.compile(r'match|fixture|game', re.I))
        
        if not match_containers:
            # Intentar con tablas
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows[1:]:  # Skip header
                    cols = row.find_all('td')
                    if len(cols) >= 3:
                        try:
                            home = cols[0].text.strip()
                            away = cols[2].text.strip()
                            if home and away:
                                partidos.append({
                                    'home_team': home,
                                    'away_team': away,
                                    'date': '',
                                    'status': '',
                                    'venue': ''
                                })
                        except:
                            continue
        
        if partidos:
            print(f"✅ {len(partidos)} partidos encontrados en Mediotiempo")
            return partidos
        
    except Exception as e:
        print(f"❌ Error en Mediotiempo: {e}")
    
    return None

def scrape_record():
    """Scraping desde Récord"""
    print("🔍 Intentando Récord...")
    
    url = "https://www.record.com.mx/futbol/liga-mx"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-MX,es;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        partidos = []
        
        # Buscar artículos o contenedores de partidos
        articles = soup.find_all('article')
        
        for article in articles:
            try:
                # Buscar nombres de equipos en el artículo
                teams = article.find_all(['h2', 'h3', 'span'], class_=re.compile(r'team|equipo', re.I))
                if len(teams) >= 2:
                    partidos.append({
                        'home_team': teams[0].text.strip(),
                        'away_team': teams[1].text.strip(),
                        'date': '',
                        'status': '',
                        'venue': ''
                    })
            except:
                continue
        
        if partidos:
            print(f"✅ {len(partidos)} partidos encontrados en Récord")
            return partidos
        
    except Exception as e:
        print(f"❌ Error en Récord: {e}")
    
    return None

def scrape_marca():
    """Scraping desde Marca México"""
    print("🔍 Intentando Marca México...")
    
    url = "https://www.marca.com.mx/futbol/liga-mx.html"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-MX,es;q=0.9',
        'Accept-Encoding': 'gzip, deflate'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        partidos = []
        
        # Buscar contenedores de partidos
        match_divs = soup.find_all('div', class_=re.compile(r'match|juego|partido', re.I))
        
        for div in match_divs:
            try:
                teams = div.find_all(['span', 'a', 'h3'], class_=re.compile(r'team|equipo', re.I))
                if len(teams) >= 2:
                    partidos.append({
                        'home_team': teams[0].text.strip(),
                        'away_team': teams[1].text.strip(),
                        'date': '',
                        'status': '',
                        'venue': ''
                    })
            except:
                continue
        
        if partidos:
            print(f"✅ {len(partidos)} partidos encontrados en Marca")
            return partidos
        
    except Exception as e:
        print(f"❌ Error en Marca: {e}")
    
    return None

def main():
    print("=" * 70)
    print("SCRAPER MULTI-FUENTE: Liga MX")
    print("=" * 70)
    
    # Intentar múltiples fuentes
    fuentes = [
        ("Mediotiempo", scrape_mediottiempo),
        ("Récord", scrape_record),
        ("Marca México", scrape_marca)
    ]
    
    for nombre, scraper in fuentes:
        print(f"\n🔄 Probando {nombre}...")
        partidos = scraper()
        
        if partidos and len(partidos) > 0:
            print(f"\n✅ ÉXITO con {nombre}")
            
            # Guardar en jornadas.json
            with open('data/jornadas.json', 'w', encoding='utf-8') as f:
                json.dump(partidos, f, indent=2, ensure_ascii=False)
            
            print(f"💾 {len(partidos)} partidos guardados en data/jornadas.json")
            print("\n📋 Primeros partidos:")
            for i, p in enumerate(partidos[:5], 1):
                print(f"  {i}. {p['home_team']} vs {p['away_team']}")
            
            return partidos
    
    print("\n❌ No se pudieron obtener partidos de ninguna fuente")
    print("💡 Sugerencia: Las APIs de pago son la única forma confiable")
    print("   - API-Football: $50-100/mes")
    print("   - The Odds API: $79/mes")
    
    return None

if __name__ == "__main__":
    main()
