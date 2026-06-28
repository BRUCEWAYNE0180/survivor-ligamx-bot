from fastapi import APIRouter, Depends
from src.backtest_engine import run_backtest

router = APIRouter()

@router.post("/cron/backtest")
def cron_backtest():
    result = run_backtest()
    return {"status": "success", "settled": result}
