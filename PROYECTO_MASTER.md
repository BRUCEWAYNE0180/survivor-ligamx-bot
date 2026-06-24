# 📝 DOCUMENTO MAESTRO: RECOLECTOR DE DATOS SURVIVOR Y PRONÓSTICOS LIGA MX

## 📌 Configuración Inicial del Sistema
* **Sistema Operativo:** macOS (Mac nativo).
* **Directorio Base:** `~/Desktop/survivor-ligamx-bot/`
* **Librerías Core instaladas:** `pandas`, `numpy`, `requests`, `scipy`, `requests-html`, `beautifulsoup4`, `groq`.

## ⚙️ Arquitectura del Bot Ultra-Actualizado
1. **src/scraper.py (Fase Actual):** Conexión con los servidores de los casinos vía API para momios 1X2 actualizados al minuto.
2. **src/contexto.py:** Recolector automatizado de Clima, Altitud del Estadio, Minutos de juego y Lesionados.
3. **src/analizador_ia.py:** Conexión con Llama 3.3 en GroqCloud para procesar ruedas de prensa y rotaciones de plantilla.
4. **src/predictor.py:** Modelo de Distribución de Poisson para calcular porcentajes, pick óptimo, marcador exacto y goleadores.
5. **src/optimizer.py:** Algoritmo matemático para ganar el Survivor de Playdoit sin repetir equipos.


## 🔧 Historial de Errores y Soluciones (Mac)
* **Error:** `ModuleNotFoundError: No module named 'requests'` al ejecutar `python3`.
* **Solución:** Se forzó la instalación de dependencias usando el puente directo del sistema: `python3 -m pip install [librerías]`.

## 📦 Actualización de Módulos (Fase 2)
* **Módulo:** `src/contexto.py` integrado con éxito.
* **Funcionalidad:** Mapeo geográfico de estadios de la Liga MX y recolección automatizada de temperatura y estado del tiempo por medio de la API Open-Meteo.

* **Error:** `SyntaxError: invalid syntax` en `src/contexto.py` línea 46 por corchetes de códigos de clima vacíos.
* **Solución:** Se insertaron los códigos numéricos de la Organización Meteorológica Mundial (`[1, 2, 3]` para nublado y rango `[45-99]` para tormentas).

* **Error:** `NewConnectionError` en la API de Clima debido a un formato de URL mal construido (`open-meteo.com19.3029...`).
* **Solución:** Se corrigió el string de la URL inyectando correctamente la ruta del endpoint `/v1/forecast?latitude=`.

## 📊 Integración del Modelo Predictor (Fase 3)
* **Módulo:** `src/predictor.py` desarrollado con éxito.
* **Funcionalidad:** Implementación de la Distribución de Poisson cruzando cuotas limpias del casino y temperatura del estadio. Genera porcentajes de victoria, picks sugeridos, marcadores exactos y lista de goleadores o jugadores clave a seguir.
