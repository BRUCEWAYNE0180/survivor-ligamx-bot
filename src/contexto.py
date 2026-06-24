import json
import os
import requests

def obtener_clima_estadios():
    ruta_jornadas = 'data/jornadas.json'
    if not os.path.exists(ruta_jornadas):
        print("❌ Error: No se encuentra data/jornadas.json.")
        return None

    with open(ruta_jornadas, 'r', encoding='utf-8') as f:
        partidos = json.load(f)

    COORDENADAS_CIUDADES = {
        "Club América": {"lat": 19.3029, "lon": -99.1505},      
        "Cruz Azul": {"lat": 19.3835, "lon": -99.1776},         
        "Chivas Guadalajara": {"lat": 20.6811, "lon": -103.4626}, 
        "Tigres UANL": {"lat": 25.7231, "lon": -100.3045},       
        "Monterrey": {"lat": 25.6692, "lon": -100.2443},         
        "Pumas UNAM": {"lat": 19.3321, "lon": -99.1923},         
        "Toluca": {"lat": 19.2871, "lon": -99.6668},             
        "Tijuana": {"lat": 32.5303, "lon": -116.9841}            
    }

    print("\n⛅ Bot: Extrayendo reporte de clima en tiempo real para cada estadio...")

    for partido in partidos:
        local = partido["home_team"]
        coordenadas = COORDENADAS_CIUDADES.get(local, {"lat": 19.4326, "lon": -99.1332})
        
        # URL armada de forma híper-segura usando suma de textos independientes
        url_base = "https://open-meteo.com"
        url_clima = f"{url_base}?latitude={coordenadas['lat']}&longitude={coordenadas['lon']}&current_weather=true"
        
        try:
            respuesta = requests.get(url_clima).json()
            clima_actual = respuesta.get("current_weather", {})
            temperatura = clima_actual.get("temperature", 20.0)
            codigo = clima_actual.get("weathercode", 0)
            
            estado_clima = "Despejado" if codigo == 0 else "Parcialmente Nublado" if codigo < 4 else "Lluvia" if codigo >= 45 else "Nublado"
            partido["clima_temperatura_c"] = temperatura
            partido["clima_estado"] = estado_clima
            
            print(f"🏟️  {partido['estadio_nombre']} ({local}): {temperatura}°C | {estado_clima}")

        except Exception as e:
            print(f"⚠️ No se pudo obtener el clima para {local}: {e}")
            partido["clima_temperatura_c"] = 20.0
            partido["clima_estado"] = "Datos No Disponibles"

    with open(ruta_jornadas, 'w', encoding='utf-8') as f:
        json.dump(partidos, f, indent=4, ensure_ascii=False)
        
    print("✅ Bot: Datos del clima inyectados con éxito en: data/jornadas.json")
    return partidos

if __name__ == "__main__":
    obtener_clima_estadios()
