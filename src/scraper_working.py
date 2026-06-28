import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timedelta

def scrape_flashscore():
    """Flashscore tiene Liga MX y es accesible"""
    print("🔍 Intentando Flashscore...")
    
    url = "https://www.flashscore.com.mx/futbol/mexico/liga-mx/calendario/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-MX,es;q=0.9',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Flashscore carga datos dinámicamente, buscar en scripts
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'tournamentCalendar' in str(script.string):
                    print("✅ Datos encontrados en script")
                    return True
            
            # Buscar partidos en la estructura HTML
            matches = soup.find_all('div', class_='sportName')
            print(f"Encontrados {len(matches)} elementos")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return None

def scrape_sofascore():
    """Sofascore API es pública"""
    print("🔍 Intentando SofaScore API...")
    
    # SofaScore tiene API pública
    url = "https://api.sofascore.com/api/v1/unique-tournament/131/season/52186/events/last/0"
    
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            events = data.get('events', [])
            print(f"✅ {len(events)} eventos encontrados")
            
            partidos = []
            for event in events[:10]:
                home = event.get('homeTeam', {}).get('name', '')
                away = event.get('awayTeam', {}).get('name', '')
                start = event.get('startTimestamp', 0)
                
                if home and away:
                    partidos.append({
                        'home_team': home,
                        'away_team': away,
                        'date': datetime.fromtimestamp(start).isoformat() if start else '',
                        'status': 'scheduled',
                        'venue': '',
                        'momio_1': 2.0,
                        'momio_x': 3.5,
                        'momio_2': 3.5
                    })
                    print(f"  ✅ {home} vs {away}")
            
            if partidos:
                return partidos
    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return None

def scrape_goal():
    """Goal.com tiene Liga MX"""
    print("🔍 Intentando Goal.com...")
    
    url = "https://www.goal.com/es-mx/lista/liga-mx-calendario-partidos-resultados/1k5x8x8x8x8x8x8x8x8x8"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar artículos de partidos
            articles = soup.find_all('article')
            print(f"Encontrados {len(articles)} artículos")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return None

def main():
    print("=" * 70)
    print("SCRAPER MEJORADO: Probando múltiples fuentes")
    print("=" * 70)
    
    # Probar SofaScore API (la más prometedora)
    partidos = scrape_sofascore()
    
    if partidos and len(partidos) > 0:
        print(f"\n✅ ÉXITO: {len(partidos)} partidos de SofaScore")
        
        with open('data/jornadas.json', 'w', encoding='utf-8') as f:
            json.dump(partidos, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Guardado en data/jornadas.json")
        return partidos
    
    # Probar Flashscore
    result = scrape_flashscore()
    
    # Probar Goal
    result = scrape_goal()
    
    print("\n❌ No se pudo obtener datos automáticamente")
    print("\n💡 SOLUCIÓN INMEDIATA:")
    print("Usa los datos de prueba que ya creé:")
    print("  cat data/jornadas.json")
    print("\nO ingresa datos manualmente editando el archivo.")
    
    return None

if __name__ == "__main__":
    main()
