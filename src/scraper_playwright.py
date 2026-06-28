import asyncio
import json
from datetime import datetime

async def scrape_with_playwright():
    """Usar Playwright para sitios con JavaScript"""
    print("=" * 70)
    print("SCRAPER PLAYWRIGHT: Navegador headless")
    print("=" * 70)
    
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ Playwright no instalado. Instalando...")
        import subprocess
        subprocess.run(["pip", "install", "playwright"], check=True)
        subprocess.run(["playwright", "install", "chromium"], check=True)
        from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Método 1: Caliente.mx (sitio mexicano de apuestas)
        print("\n🔍 Caliente.mx...")
        try:
            await page.goto("https://www.caliente.mx/sportsbook/futbol/liga-mx", timeout=30000)
            await page.wait_for_load_state("networkidle")
            
            # Buscar partidos
            matches = await page.query_selector_all('[data-testid="match-card"], .match-card, .event-card')
            print(f"   ✅ {len(matches)} elementos encontrados")
            
            if matches:
                partidos = []
                for match in matches[:10]:
                    home = await match.query_selector('.home-team, .team-home')
                    away = await match.query_selector('.away-team, .team-away')
                    
                    if home and away:
                        home_text = await home.text_content()
                        away_text = await away.text_content()
                        
                        partido = {
                            'home_team': home_text.strip(),
                            'away_team': away_text.strip(),
                            'date': '',
                            'status': 'scheduled',
                            'venue': '',
                            'momio_1': 2.0,
                            'momio_x': 3.5,
                            'momio_2': 3.5
                        }
                        partidos.append(partido)
                        print(f"      ✅ {partido['home_team']} vs {partido['away_team']}")
                
                await browser.close()
                if partidos:
                    return partidos
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Método 2: Bet365
        print("\n🔍 Bet365...")
        try:
            await page.goto("https://www.bet365.com/#/AC/B13/C20/D1/E40/F4/G40/H1/I1/", timeout=30000)
            await page.wait_for_load_state("networkidle")
            
            matches = await page.query_selector_all('.ovm-Fixture_Container, .fixture')
            print(f"   ✅ {len(matches)} elementos encontrados")
            
            if matches:
                partidos = []
                for match in matches[:10]:
                    home = await match.query_selector('.ovm-Fixture_TwoLineTeamNameHome, .team-home')
                    away = await match.query_selector('.ovm-Fixture_TwoLineTeamNameAway, .team-away')
                    
                    if home and away:
                        home_text = await home.text_content()
                        away_text = await away.text_content()
                        
                        partido = {
                            'home_team': home_text.strip(),
                            'away_team': away_text.strip(),
                            'date': '',
                            'status': 'scheduled',
                            'venue': '',
                            'momio_1': 2.0,
                            'momio_x': 3.5,
                            'momio_2': 3.5
                        }
                        partidos.append(partido)
                        print(f"      ✅ {partido['home_team']} vs {partido['away_team']}")
                
                await browser.close()
                if partidos:
                    return partidos
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        await browser.close()
    
    return None

def scrape_api_alternativas():
    """APIs alternativas menos conocidas"""
    print("\n" + "=" * 70)
    print("APIs ALTERNATIVAS")
    print("=" * 70)
    
    import requests
    
    # API-Football alternativa (RapidAPI)
    print("\n🔍 RapidAPI - API-Football...")
    try:
        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
        
        headers = {
            "X-RapidAPI-Key": "test",  # Necesitarías registrarte
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }
        
        params = {
            "league": "128",  # Liga MX
            "season": "2026",
            "next": "10"
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            fixtures = data.get('response', [])
            
            if fixtures:
                print(f"   ✅ {len(fixtures)} partidos encontrados")
                return fixtures
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return None

def scrape_twitter():
    """Buscar información de partidos en Twitter"""
    print("\n" + "=" * 70)
    print("TWITTER/X")
    print("=" * 70)
    
    # Esto es más complejo, solo mostraré la idea
    print("   ⚠️ Twitter requiere autenticación OAuth")
    print("   💡 Se necesitaría crear una app en developer.twitter.com")
    
    return None

def scrape_reddit():
    """Buscar en Reddit"""
    print("\n" + "=" * 70)
    print("REDDIT")
    print("=" * 70)
    
    import requests
    
    try:
        url = "https://www.reddit.com/r/LigaMX/search.json"
        
        params = {
            "q": "partidos jornada",
            "restrict_sr": "1",
            "sort": "new",
            "limit": "10"
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            posts = data.get('data', {}).get('children', [])
            
            print(f"   ✅ {len(posts)} posts encontrados")
            
            for post in posts[:5]:
                title = post.get('data', {}).get('title', '')
                print(f"      - {title}")
            
            return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return None

async def main():
    print("\n" + "=" * 70)
    print("🚀 SCRAPER AGRESIVO: Playwright + APIs alternativas")
    print("=" * 70)
    
    # Método 1: Playwright
    print("\n[1/4] Playwright (navegador headless)...")
    partidos = await scrape_with_playwright()
    
    if partidos and len(partidos) > 0:
        print(f"\n✅ ÉXITO con Playwright: {len(partidos)} partidos")
        return partidos
    
    # Método 2: APIs alternativas
    print("\n[2/4] APIs alternativas...")
    partidos = scrape_api_alternativas()
    
    if partidos and len(partidos) > 0:
        print(f"\n✅ ÉXITO con API alternativa: {len(partidos)} partidos")
        return partidos
    
    # Método 3: Reddit
    print("\n[3/4] Reddit...")
    result = scrape_reddit()
    
    # Método 4: Twitter
    print("\n[4/4] Twitter...")
    result = scrape_twitter()
    
    print("\n" + "=" * 70)
    print("❌ No se pudo obtener datos automáticamente")
    print("=" * 70)
    
    return None

if __name__ == "__main__":
    partidos = asyncio.run(main())
    
    if partidos and len(partidos) > 0:
        with open('data/jornadas.json', 'w', encoding='utf-8') as f:
            json.dump(partidos, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Guardado en data/jornadas.json")
        print(f"\n📋 Primeros partidos:")
        for i, p in enumerate(partidos[:5], 1):
            print(f"   {i}. {p['home_team']} vs {p['away_team']}")
