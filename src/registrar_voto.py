import json
import os
import sys

def registrar_equipo_usado():
    ruta_historial = 'data/historial_picks.json'
    
    # Comprobar si el usuario ingresó un equipo en la terminal
    if len(sys.argv) < 2:
        print("❌ Error: Debes escribir el nombre del equipo que usaste.")
        print("💡 Ejemplo: python3 src/registrar_voto.py 'Club América'")
        return
        
    nuevo_pick = sys.argv[1]
    
    # Cargar historial existente o crear uno nuevo vacío
    historial = []
    if os.path.exists(ruta_historial):
        with open(ruta_historial, 'r', encoding='utf-8') as f:
            historial = json.load(f)
            
    # Validar si el equipo ya estaba registrado para no duplicarlo
    if nuevo_pick in historial:
        print(f"⚠️ El equipo '{nuevo_pick}' ya se encuentra bloqueado en tu historial.")
        return
        
    # Agregar el nuevo pick y guardar el archivo
    historial.append(nuevo_pick)
    os.makedirs('data', exist_ok=True)
    with open(ruta_historial, 'w', encoding='utf-8') as f:
        json.dump(historial, f, indent=4, ensure_ascii=False)
        
    print(f"🔒 ¡Éxito! El equipo '{nuevo_pick}' ha sido bloqueado de forma permanente para el resto del torneo.")
    print(f"📋 Lista completa de equipos gastados: {', '.join(historial)}")

if __name__ == "__main__":
    registrar_equipo_usado()
