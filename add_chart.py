code = open('src/api.py').read()

# Agregar el script de Chart.js antes de </head>
code = code.replace(
    '</head>',
    '''    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>'''
)

# Agregar el canvas y el script antes de </body>
chart_code = '''
    <div style="background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px;">
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
</body>'''

code = code.replace('</body>', chart_code)

# Reemplazar los placeholders con los valores reales
code = code.replace(
    'html_content = """',
    '''html_content = f"""'''
)

# Agregar los reemplazos antes del return
code = code.replace(
    'return HTMLResponse(content=html_content)',
    '''html_content = html_content.replace('STATS_TOTAL_PICKS', str(stats['total_picks']))
    html_content = html_content.replace('STATS_WINS', str(stats['wins']))
    html_content = html_content.replace('STATS_TOTAL_PICKS - STATS_WINS', str(stats['total_picks'] - stats['wins']))
    return HTMLResponse(content=html_content)'''
)

open('src/api.py', 'w').write(code)
print('✅ Gráfico agregado')
