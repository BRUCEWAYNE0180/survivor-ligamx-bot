import requests
import json
from datetime import datetime

def scrape_thesportsdb():
    """TheSportsDB - API gratuita con datos deportivos"""
    print("=" * 70)
    print("MÉTODO 1: TheSportsDB")
    print("=" * 70)
    
    # TheSportsDB tiene API gratuita
    base_url = "https://www.thesportsdb.com/api/v1/json/3"
    
    # Buscar Liga MX
    print("\n🔍 Buscando Liga MX...")
    
    try:
        # Buscar liga por nombre
        url = f"{base_url}/search_all_leagues.php"
        params = {"s": "Soccer", "c": "Mexico"}
        
        response = requests.get(url, params=params, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            leagues = data.get('countrys', [])
            
            print(f"   ✅ {len(leagues)} ligas encontradas en México")
            
            for league in leagues:
                name = league.get('strLeague', '')
                league_id = league.get('idLeague', '')
                print(f"      - {name} (ID: {league_id})")
                
                if 'liga mx' in name.lower() or 'primera' in name.lower():
                    print(f"\n   🎯 LIGA MX ENCONTRADA!")
                    
                    # Obtener próximos eventos
                    events_url = f"{base_url}/eventsnextleague.php"
                    events_params = {"id": league_id}
                    
                    events_response = requests.get(events_url, params=events_params, timeout=30)
                    
                    if events_response.status_code == 200:
                        events_data = events_response.json()
                        events = events_data.get('events', [])
                        
                        if events:
                            print(f"   ✅ {len(events)} próximos partidos")
                            
                            partidos = []
                            for event in events[:10]:
                                home = event.get('strHomeTeam', '')
                                away = event.get('strAwayTeam', '')
                                date = event.get('dateEvent', '')
                                
                                if home and away:
                                    partido = {
                                        'home_team': home,
                                        'away_team': away,
                                        'date': date,
                                        'status': 'scheduled',
                                        'venue': event.get('strVenue', ''),
                                        'momio_1': 2.0,
                                        'momio_x': 3.5,
                                        'momio_2': 3.5
                                    }
                                    partidos.append(partido)
                                    print(f"      ✅ {home} vs {away}")
                            
                            return partidos
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return None

def scrape_wikidata():
    """Wikidata - Datos estructurados de Wikipedia"""
    print("\n" + "=" * 70)
    print("MÉTODO 2: Wikidata")
    print("=" * 70)
    
    # Wikidata tiene datos estructurados de ligas deportivas
    endpoint = "https://query.wikidata.org/sparql"
    
    # Query SPARQL para buscar Liga MX
    query = """
    SELECT ?league ?leagueLabel ?team ?teamLabel ?event ?eventLabel ?date
    WHERE {
      ?league wdt:P31 wd:Q13419648 .  # Instancia de liga de fútbol
      ?league wdt:P17 wd:Q96 .         # País: México
      ?league rdfs:label ?leagueLabel .
      FILTER(LANG(?leagueLabel) = "es")
      FILTER(CONTAINS(LCASE(?leagueLabel), "liga mx") || 
             CONTAINS(LCASE(?leagueLabel), "primera división"))
      
      OPTIONAL {
        ?team wdt:P118 ?league .         # Equipo pertenece a la liga
        ?team rdfs:label ?teamLabel .
        FILTER(LANG(?teamLabel) = "es")
      }
      
      OPTIONAL {
        ?event wdt:P3450 ?league .       # Evento/competición de la liga
        ?event wdt:P580 ?date .          # Fecha de inicio
        ?event rdfs:label ?eventLabel .
        FILTER(LANG(?eventLabel) = "es")
      }
    }
    LIMIT 50
    """
    
    try:
        response = requests.get(
            endpoint,
            params={"query": query, "format": "json"},
            timeout=30
        )
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', {}).get('bindings', [])
            
            print(f"   ✅ {len(results)} resultados encontrados")
            
            for result in results[:10]:
                league = result.get('leagueLabel', {}).get('value', '')
                team = result.get('teamLabel', {}).get('value', '')
                event = result.get('eventLabel', {}).get('value', '')
                
                print(f"      - Liga: {league}")
                if team:
                    print(f"        Equipo: {team}")
                if event:
                    print(f"        Evento: {event}")
            
            return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return None

def scrape_football_data_co_uk():
    """Football-Data.co.uk - Datos históricos gratuitos"""
    print("\n" + "=" * 70)
    print("MÉTODO 3: Football-Data.co.uk")
    print("=" * 70)
    
    # Este sitio tiene datos históricos gratuitos
    base_url = "https://www.football-data.co.uk"
    
    try:
        # Buscar datos de México
        url = f"{base_url}/mxmm.php"  # México
        
        response = requests.get(url, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            print("   ✅ Página encontrada")
            
            # Buscar enlaces a archivos CSV
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            links = soup.find_all('a', href=True)
            csv_links = [link for link in links if link['href'].endswith('.csv')]
            
            print(f"   ✅ {len(csv_links)} archivos CSV encontrados")
            
            if csv_links:
                # Descargar el primer CSV
                csv_url = f"{base_url}/{csv_links[0]['href']}"
                print(f"   📥 Descargando: {csv_url}")
                
                csv_response = requests.get(csv_url, timeout=30)
                
                if csv_response.status_code == 200:
                    import csv
                    from io import StringIO
                    
                    csv_data = csv.reader(StringIO(csv_response.text))
                    rows = list(csv_data)
                    
                    print(f"   ✅ {len(rows)} filas en el CSV")
                    
                    if len(rows) > 1:
                        headers = rows[0]
                        print(f"   📊 Columnas: {', '.join(headers[:5])}")
                        
                        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return None

def scrape_github_datasets():
    """Buscar datasets de Liga MX en GitHub"""
    print("\n" + "=" * 70)
    print("MÉTODO 4: GitHub Datasets")
    print("=" * 70)
    
    # Buscar repositorios con datos de Liga MX
    api_url = "https://api.github.com/search/repositories"
    
    params = {
        "q": "liga mx dataset OR partidos OR fixtures",
        "sort": "stars",
        "order": "desc",
        "per_page": "10"
    }
    
    try:
        response = requests.get(api_url, params=params, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            repos = data.get('items', [])
            
            print(f"   ✅ {len(repos)} repositorios encontrados")
            
            for repo in repos[:5]:
                name = repo.get('name', '')
                description = repo.get('description', '')
                stars = repo.get('stargazers_count', 0)
                url = repo.get('html_url', '')
                
                print(f"\n   📦 {name} ⭐ {stars}")
                if description:
                    print(f"      {description}")
                print(f"      {url}")
                
                # Buscar archivos JSON/CSV en el repo
                contents_url = f"https://api.github.com/repos/{repo['full_name']}/contents"
                contents_response = requests.get(contents_url, timeout=10)
                
                if contents_response.status_code == 200:
                    files = contents_response.json()
                    data_files = [f for f in files if f['name'].endswith(('.json', '.csv'))]
                    
                    if data_files:
                        print(f"      📁 Archivos de datos: {len(data_files)}")
                        for f in data_files[:3]:
                            print(f"         - {f['name']}")
            
            return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return None

def scrape_kaggle():
    """Kaggle - Datasets públicos"""
    print("\n" + "=" * 70)
    print("MÉTODO 5: Kaggle Datasets")
    print("=" * 70)
    
    # Kaggle tiene datasets públicos
    # No tiene API pública sin autenticación, pero podemos buscar
    
    print("   💡 Kaggle requiere autenticación")
    print("   🔗 Busca manualmente en: https://www.kaggle.com/datasets")
    print("   🔍 Términos: 'liga mx', 'mexican football', 'soccer mexico'")
    
    return None

def main():
    print("\n" + "=" * 70)
    print("🚀 SCRAPER ULTIMATE: APIs no convencionales")
    print("=" * 70)
    
    # Método 1: TheSportsDB
    print("\n[1/5] TheSportsDB...")
    partidos = scrape_thesportsdb()
    
    if partidos and len(partidos) > 0:
        print(f"\n✅ ÉXITO con TheSportsDB: {len(partidos)} partidos")
        return partidos
    
    # Método 2: Wikidata
    print("\n[2/5] Wikidata...")
    result = scrape_wikidata()
    
    # Método 3: Football-Data.co.uk
    print("\n[3/5] Football-Data.co.uk...")
    result = scrape_football_data_co_uk()
    
    # Método 4: GitHub
    print("\n[4/5] GitHub Datasets...")
    result = scrape_github_datasets()
    
    # Método 5: Kaggle
    print("\n[5/5] Kaggle...")
    result = scrape_kaggle()
    
    print("\n" + "=" * 70)
    print("❌ No se pudo obtener datos de APIs no convencionales")
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
