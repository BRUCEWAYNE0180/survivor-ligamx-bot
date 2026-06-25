import json
import os
import numpy as np
from scipy.stats import poisson

def calcular_pronosticos_avanzados():
    ruta_archivo = 'data/jornadas.json'
    
    if not os.path.exists(ruta_archivo):
        print("❌ Error: No se encuentra data/jornadas.json. Ejecuta primero el scraper.")
        return None

    with open(ruta_archivo, 'r', encoding='utf-8') as f:
        partidos = json.load(f)
    
    ESTRELLAS_LIGA_MX = {
        "Club América": ["Henry Martín (Delantero)", "Diego Valdés (Mediocampista)"],
        "Chivas Guadalajara": ["Cade Cowell (Delantero)", "Roberto Alvarado (Extremo)"],
        "Cruz Azul": ["Giorgos Giakoumakis (Delantero)", "Carlos Rotondi (Carrilero)"],
        "Pumas UNAM": ["César Huerta (Extremo)", "Guillermo Martínez (Delantero)"],
        "Tigres UANL": ["André-Pierre Gignac (Delantero)", "Juan Brunetta (Enganche)"],
        "Monterrey": ["Germán Berterame (Delantero)", "Sergio Canales (Mediocampista)"],
        "Toluca": ["Paulinho (Delantero)", "Alexis Vega (Extremo)"],
        "Tijuana": ["Efraín Álvarez (Mediocampista)", "Carlos González (Delantero)"]
    }

    print("\n📊 --- BOT: GENERANDO PRONÓSTICOS PREDICTIVOS AVANZADOS ---")
    
    for partido in partidos:
        local = partido['home_team']
        visita = partido['away_team']
        temp_estadio = partido.get('clima_temperatura_c', 20.0)
        clima_real = bool(partido.get('clima_real', False))
        clima_label = 'REAL' if clima_real else 'FALLBACK TÉCNICO'
        
        outcomes = partido['bookmakers'][0]['markets'][0]['outcomes']
        cuota_l = next(o['price'] for o in outcomes if o['name'] == local)
        cuota_v = next(o['price'] for o in outcomes if o['name'] == visita)
        cuota_e = next(o['price'] for o in outcomes if o['name'] == 'Draw')
        
        suma_prob = (1/cuota_l) + (1/cuota_v) + (1/cuota_e)
        prob_l = (1/cuota_l) / suma_prob
        prob_v = (1/cuota_v) / suma_prob
        prob_e = (1/cuota_e) / suma_prob
        
        ajuste_clima = 0.95 if temp_estadio > 30.0 else 1.0
        
        lambda_local = (1.6 if prob_l > prob_v else 1.1) * ajuste_clima
        lambda_visita = (1.0 if prob_v > prob_l else 1.2) * ajuste_clima
        
        max_goles = 5
        matriz_marcardores = np.zeros((max_goles, max_goles))
        
        for i in range(max_goles):
            for j in range(max_goles):
                matriz_marcardores[i, j] = poisson.pmf(i, lambda_local) * poisson.pmf(j, lambda_visita)
        
        goles_l_pred, goles_v_pred = np.unravel_index(matriz_marcardores.argmax(), matriz_marcardores.shape)
        confianza_marcador = matriz_marcardores[goles_l_pred, goles_v_pred] * 100
        
        if prob_l > prob_v and prob_l > prob_e: 
            pick = f"Gana {local}"
        elif prob_v > prob_l and prob_v > prob_e: 
            pick = f"Gana {visita}"
        else: 
            pick = "Empate"

        jugadores_l = ESTRELLAS_LIGA_MX.get(local, ["Jugador Destacado Local"])
        jugadores_v = ESTRELLAS_LIGA_MX.get(visita, ["Jugador Destacado Visitante"])

        print("="*65)
        print(f"⚽ PARTIDO: {local} vs {visita} | Clima Estadio: {temp_estadio}°C ({clima_label})")
        print("="*65)
        print(f"📈 PROBABILIDADES: Local: {prob_l*100:.1f}% | Empate: {prob_e*100:.1f}% | Visita: {prob_v*100:.1f}%")
        print(f"🔥 PICK RECOMENDADO: {pick}")
        print(f"🎯 MARCADOR EXACTO: {goles_l_pred} - {goles_v_pred} (Confianza: {confianza_marcador:.1f}%)")
        print(f"⭐ JUGADORES A SEGUIR:")
        print(f"   ↳ En {local}: {', '.join(jugadores_l)}")
        print(f"   ↳ En {visita}: {', '.join(jugadores_v)}")
        print(f"🛡️  AVANCE SURVIVOR (No perder): {local}: {(prob_l+prob_e)*100:.1f}% | {visita}: {(prob_v+prob_e)*100:.1f}%\n")

if __name__ == "__main__":
    calcular_pronosticos_avanzados()
