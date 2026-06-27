from fastapi import FastAPI, HTTPException
import pandas as pd
from pathlib import Path
from datetime import datetime
import os

app = FastAPI(
    title="Liga MX Survivor API",
    version="1.0.0",
    description="API gratuita y exclusiva para momios, predicciones y gestión de bankroll de Liga MX."
)

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_KIRO = Path(os.getenv("DATA_KIRO", "data_kiro"))

def load(path):
    if not path.exists(): return pd.DataFrame()
    return pd.read_csv(path)

@app.get("/")
def root(): return {"message": "Liga MX Survivor API activa", "docs": "/docs"}

@app.get("/ligamx/odds")
def get_odds(limit: int = 20):
    df = load(DATA_KIRO / "ligamx_odds_clean.csv")
    if df.empty: raise HTTPException(404, "Sin datos de momios")
    return df.tail(limit).to_dict(orient="records")

@app.get("/ligamx/predict")
def get_prediction():
    df = load(DATA_DIR / "backtest_kelly_v2.csv")
    if df.empty: raise HTTPException(404, "Modelo no calibrado")
    last = df.iloc[-1]
    return {
        "liga": "Liga MX",
        "ev_positive": bool(last.get("mejor_ev", 0) > 0.04),
        "kelly_stake_pct": round(last.get("kelly_pct", 0) * 100, 2),
        "bankroll_simulated": round(last.get("bankroll_final_simulado", 1000), 2),
        "updated_at": datetime.now().isoformat()
    }

@app.get("/ligamx/summary")
def get_summary():
    df = load(DATA_KIRO / "ligamx_odds_clean.csv")
    if df.empty: return {"message": "Esperando datos...", "liga": "Liga MX"}
    return {
        "liga": "Liga MX",
        "total_records": len(df),
        "avg_vig_pct": round(df["vig_pct"].mean(), 2),
        "unique_markets": int(df["id_mercado"].nunique()),
        "last_update": str(df["timestamp"].max())
    }
