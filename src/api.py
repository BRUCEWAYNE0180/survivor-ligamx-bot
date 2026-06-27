from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
from datetime import datetime, timedelta

app = FastAPI(title="Survivor LigaMX API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

PICKS_CACHE = {"status": "inactive", "picks": [], "last_update": None}

def refresh_cache():
    global PICKS_CACHE
    try:
        df = pd.read_parquet("data_kiro/ligamx_odds_clean.parquet")
        # Usa el nombre real de la columna
        valid = df[df["vig_pct"] < 15].copy()
        
        # Calcula EV y Kelly fraccionario (25%, tope 8%) para el mercado 1
        valid["expected_value"] = valid["true_prob_1"] * valid["momio_1"] - 1
        b = valid["momio_1"] - 1
        valid["kelly_stake"] = (b * valid["true_prob_1"] - (1 - valid["true_prob_1"])) / b
        valid["kelly_stake"] = (valid["kelly_stake"] * 0.25).clip(0, 8)  # 25% Kelly, máx 8%
        
        # Filtra picks con EV positivo > 4%
        valid = valid[(valid["expected_value"] > 0.04) & (valid["momio_1"] > 1)].copy()
        valid = valid.sort_values("timestamp", ascending=False).head(10)
        
        # Mapea a formato esperado por el frontend
        picks_out = []
        for _, row in valid.iterrows():
            picks_out.append({
                "match": f"Liga {row.get('id_liga','')} | M {row.get('id_mercado','')}",
                "true_prob": float(row["true_prob_1"]),
                "expected_value": float(row["expected_value"]),
                "kelly_stake": float(row["kelly_stake"]),
                "market": "1 (Local)",
                "timestamp": str(row["timestamp"])
            })
            
        PICKS_CACHE = {
            "status": "active",
            "last_update": datetime.utcnow().isoformat() + "Z",
            "picks": picks_out
        }
    except Exception as e:
        PICKS_CACHE = {"status": "error", "message": str(e), "last_update": None}

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/picks/latest")
def get_latest_picks():
    if not PICKS_CACHE["last_update"] or \
       datetime.fromisoformat(PICKS_CACHE["last_update"].replace("Z","")) < datetime.utcnow() - timedelta(minutes=15):
        refresh_cache()
    return PICKS_CACHE

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api:app", host="0.0.0.0", port=8000, reload=True)
