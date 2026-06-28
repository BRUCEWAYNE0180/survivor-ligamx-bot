code = open('src/api.py').read()

if 'analyze_additional_markets' not in code:
    # Agregar import
    code = code.replace(
        'from src.telegram_alerts import',
        'from src.market_analyzer import analyze_additional_markets\nfrom src.telegram_alerts import'
    )
    
    # Agregar endpoint antes del if __name__
    endpoint = '''
@app.get("/analyze/markets", summary="Analizar mercados adicionales", tags=["Analysis"])
@limiter.limit("10/minute")
def analyze_markets(request: Request, home: float, draw: float, away: float):
    """Analiza Over/Under, BTTS y Doble Oportunidad"""
    try:
        result = analyze_additional_markets(home, draw, away)
        return {"status": "success", "markets": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

'''
    
    code = code.replace('if __name__ == "__main__":', endpoint + 'if __name__ == "__main__":')
    
    open('src/api.py', 'w').write(code)
    print('✅ Endpoint de mercados agregado')
else:
    print('✅ Ya existe')
