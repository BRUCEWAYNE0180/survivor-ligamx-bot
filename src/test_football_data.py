#!/usr/bin/env python3
import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("FOOTBALL_DATA_KEY")
print(f"API Key: {api_key[:10]}...")

headers = {"X-Auth-Token": api_key}

# Obtener competiciones disponibles
url = "https://api.football-data.org/v4/competitions"
response = requests.get(url, headers=headers)

print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    competitions = data.get("competitions", [])
    
    print(f"\nTotal competiciones: {len(competitions)}")
    
    # Buscar Liga MX
    liga_mx = None
    for comp in competitions:
        name = comp.get("name", "")
        code = comp.get("code", "")
        comp_id = comp.get("id")
        
        if "liga mx" in name.lower() or "mexico" in name.lower() or code == "LMX":
            liga_mx = comp
            print(f"\n✅ LIGA MX ENCONTRADA:")
            print(f"   Nombre: {name}")
            print(f"   Código: {code}")
            print(f"   ID: {comp_id}")
    
    if not liga_mx:
        print("\n❌ Liga MX no encontrada")
        print("\nCompeticiones disponibles:")
        for comp in competitions[:20]:
            print(f"   - {comp.get('name')} ({comp.get('code')})")
else:
    print(f"Error: {response.text}")
