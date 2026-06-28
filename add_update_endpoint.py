code = open('src/api.py').read()

if '/update/data' not in code:
    endpoint = '''
@app.post("/update/data", summary="Forzar actualización de datos", tags=["Admin"])
@limiter.limit("2/minute")
def update_data(request: Request, api_key: str = Depends(verify_api_key)):
    """Fuerza la actualización manual de datos"""
    import subprocess
    import sys
    try:
        result = subprocess.run(
            [sys.executable, "src/auto_update.py"],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        return {
            "status": "success" if result.returncode == 0 else "error",
            "message": "Datos actualizados" if result.returncode == 0 else "Error en actualización",
            "output": result.stdout[-500:] if result.stdout else "",
            "errors": result.stderr[-500:] if result.stderr else ""
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

'''
    
    code = code.replace('if __name__ == "__main__":', endpoint + 'if __name__ == "__main__":')
    open('src/api.py', 'w').write(code)
    print('✅ Endpoint de actualización agregado')
else:
    print('✅ Ya existe')
