#!/usr/bin/env python3
"""
Auto-Update System - Mantener datos frescos automáticamente
"""
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def run_script(script_name, description):
    log(f"🔄 {description}")
    try:
        result = subprocess.run(
            [sys.executable, f"src/{script_name}"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            log(f"✅ {description} - OK")
            return True
        else:
            log(f"❌ {description} - Error: {result.stderr[:200]}")
            return False
    except subprocess.TimeoutExpired:
        log(f"⏱️ {description} - Timeout")
        return False
    except Exception as e:
        log(f"❌ {description} - Exception: {e}")
        return False

def main():
    log("=" * 60)
    log("INICIANDO ACTUALIZACIÓN AUTOMÁTICA DE DATOS")
    log("=" * 60)
    
    results = {}
    
    # 1. Sincronizar fixtures desde API-Football
    results['fixtures'] = run_script(
        "api_football_fixtures_sync.py",
        "Sincronizando fixtures API-Football"
    )
    
    # 2. Sincronizar cuotas desde The Odds API
    results['odds'] = run_script(
        "sync_odds_api.py",
        "Sincronizando cuotas The Odds API"
    )
    
    # 3. Procesar datos de confianza
    results['confidence'] = run_script(
        "data_confidence.py",
        "Procesando análisis de confianza"
    )
    
    log("=" * 60)
    success_count = sum(results.values())
    total_count = len(results)
    
    if success_count == total_count:
        log(f"✅ ACTUALIZACIÓN COMPLETA ({success_count}/{total_count})")
    else:
        log(f"⚠️ ACTUALIZACIÓN PARCIAL ({success_count}/{total_count})")
    
    log("=" * 60)
    return success_count == total_count

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
