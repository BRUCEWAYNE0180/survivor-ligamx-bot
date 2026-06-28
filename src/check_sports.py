#!/usr/bin/env python3
"""Verificar qué deportes están disponibles en The Odds API"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def check_sports():
    print("=" * 60)
    print("VERIFICAR SPORTS DISPONIBLES EN THE ODDS API")
    print("=" * 60)
    
    api_key = os.getenv("ODDS_API_KEY_PRIMARY") or os.getenv("ODDS_API_KEY")
    
    if not api_key:
        print("❌ No se encontró API key")
        return
    
    print(f"✅ API Key: {api_key[:10]}...")
    
    # Endpoint para listar todos los sports
    endpoint = "https://api.the-odds-api.com/v4/sports/"
    
    try:
        response = requests.get(
            endpoint,
            params={"apiKey": api_key},
            timeout=30
        )
        
        print(f"\n📡 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            sports = response.json()
            print(f"\n✅ Total de sports disponibles: {len(sports)}")
            
            # Buscar soccer/fútbol
            soccer_sports = [s for s in sports if 'soccer' in s.get('key', '').lower() or 'football' in s.get('title', '').lower()]
            
            print(f"\n⚽ Sports de fútbol/soccer encontrados: {len(soccer_sports)}")
            
            for sport in soccer_sports:
                key = sport.get('key', '')
                title = sport.get('title', '')
                active = sport.get('active', False)
                has_ou = sport.get('has_outrights', False)
                
                print(f"\n  📊 Key: {key}")
                print(f"     Title: {title}")
                print(f"     Active: {active}")
                
                # Marcar si es Liga MX
                if 'mexico' in key.lower() or 'ligamx' in key.lower() or 'mx' in key.lower():
                    print(f"     🇲🇽 <<< ESTE PARECE SER LIGA MX >>>")
            
            # Buscar específicamente soccer_mexico_ligamx
            mex_key = "soccer_mexico_ligamx"
            found = next((s for s in sports if s.get('key') == mex_key), None)
            
            if found:
                print(f"\n✅ '{mex_key}' SÍ existe en la API")
                print(f"   Title: {found.get('title')}")
                print(f"   Active: {found.get('active')}")
            else:
                print(f"\n❌ '{mex_key}' NO existe en la API")
                print(f"   Sports similares:")
                for s in sports:
                    if 'mex' in s.get('key', '').lower() or 'liga' in s.get('key', '').lower():
                        print(f"   - {s.get('key')}: {s.get('title')}")
        
        else:
            print(f"\n❌ Error: {response.text[:500]}")
    
    except Exception as e:
        print(f"\n❌ Excepción: {type(e).__name__}: {e}")
    
    print("=" * 60)

if __name__ == "__main__":
    check_sports()
