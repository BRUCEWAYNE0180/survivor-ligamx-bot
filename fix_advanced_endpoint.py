code = open('src/api.py').read()

# Buscar y eliminar el endpoint problemático
start_marker = '@app.get("/analyze/advanced"'
end_marker = 'if __name__ == "__main__":'

start_idx = code.find(start_marker)
end_idx = code.find(end_marker)

if start_idx != -1 and end_idx != -1:
    # Eliminar el endpoint viejo
    code = code[:start_idx] + code[end_idx:]
    
    # Agregar el endpoint nuevo de forma segura
    new_endpoint = '''
@app.get("/analyze/advanced", summary="Análisis avanzado de mercados", tags=["Analysis"])
@limiter.limit("10/minute")
def analyze_advanced(request: Request, api_key: str = Depends(verify_api_key)):
    """Analiza Handicap Asiático, Goles por Equipo, Marcador Exacto"""
    import subprocess
    import sys
    import json
    try:
        result = subprocess.run(
            [sys.executable, "src/advanced_markets.py"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        
        if result.returncode == 0:
            output_lines = result.stdout.strip().split("\\n")
            json_start = None
            for i, line in enumerate(output_lines):
                if line.strip().startswith("["):
                    json_start = i
                    break
            
            if json_start is not None:
                json_output = "\\n".join(output_lines[json_start:])
                data = json.loads(json_output)
                return {"status": "success", "matches": data}
        
        return {"status": "error", "message": "Error en análisis", "details": result.stderr[:500]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

'''
    
    code = code.replace('if __name__ == "__main__":', new_endpoint + 'if __name__ == "__main__":')
    open('src/api.py', 'w').write(code)
    print('✅ Endpoint corregido')
else:
    print('❌ No se encontró el endpoint')
