import re

code = open('src/api.py').read()

# Buscar y reemplazar el dashboard usando regex
pattern = r'@app\.get\("/dashboard".*?return HTMLResponse\(content=html\)'
replacement = '''@app.get("/dashboard", response_class=HTMLResponse, summary="Dashboard visual", tags=["Dashboard"])
def dashboard():
    stats = get_metrics()
    html = """<!DOCTYPE html>
<html>
<head>
    <title>Survivor LigaMX Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .metric { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .metric h3 { margin: 0; color: #666; font-size: 14px; }
        .metric .value { font-size: 32px; font-weight: bold; color: #333; margin-top: 10px; }
        .chart-container { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Survivor LigaMX Premium</h1>
        <p>Dashboard de Rendimiento en Vivo</p>
    </div>
    <div class="metrics">
        <div class="metric">
            <h3>Total Picks</h3>
            <div class="value">STATS_TOTAL_PICKS</div>
        </div>
        <div class="metric">
            <h3>Wins</h3>
            <div class="value">STATS_WINS</div>
        </div>
        <div class="metric">
            <h3>Win Rate</h3>
            <div class="value">STATS_WIN_RATE%</div>
        </div>
        <div class="metric">
            <h3>Total Profit</h3>
            <div class="value">STATS_TOTAL_PROFIT</div>
        </div>
    </div>
    <div class="chart-container">
        <h3>📈 Rendimiento</h3>
        <canvas id="performanceChart"></canvas>
    </div>
    <script>
        const ctx = document.getElementById('performanceChart').getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Total Picks', 'Wins', 'Losses'],
                datasets: [{
                    label: 'Estadísticas',
                    data: [STATS_TOTAL_PICKS, STATS_WINS, STATS_TOTAL_PICKS - STATS_WINS],
                    backgroundColor: ['#667eea', '#10b981', '#ef4444']
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false }
                }
            }
        });
    </script>
    <p><a href="/docs">📚 Ver documentación API</a></p>
</body>
</html>"""
    html = html.replace('STATS_TOTAL_PICKS', str(stats['total_picks']))
    html = html.replace('STATS_WINS', str(stats['wins']))
    html = html.replace('STATS_WIN_RATE', f"{stats['win_rate']:.1f}")
    html = html.replace('STATS_TOTAL_PROFIT', f"{stats['total_profit']:.2f}")
    return HTMLResponse(content=html)'''

new_code = re.sub(pattern, replacement, code, flags=re.DOTALL)

if new_code != code:
    open('src/api.py', 'w').write(new_code)
    print('✅ Dashboard actualizado')
else:
    print('❌ No se pudo actualizar')
