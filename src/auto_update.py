#!/usr/bin/env python3
import subprocess
import sys
import os
from datetime import datetime

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def run_script(script_name, description):
    log(f"🔄 {description}")
    try:
        result = subprocess.run(
            [sys.executable, f"src/{script_name}"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
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
    except Exception as e:
        log(f"❌ {description} - Exception: {e}")
        return False

def main():
    log("=" * 70)
    log("INICIANDO ACTUALIZACIÓN AUTOMÁTICA (Multi-Source)")
    log("=" * 70)
    
    # Scraper multi-fuente (ESPN + respaldos)
    success1 = run_script("scraper_multi_source.py", "Scraper Multi-Fuente")
    
    # Análisis de confianza
    success2 = run_script("data_confidence.py", "Análisis de confianza")
    
    log("=" * 70)
    if success1 and success2:
        log("✅ ACTUALIZACIÓN COMPLETA")
    else:
        log("⚠️ ACTUALIZACIÓN PARCIAL")
    log("=" * 70)
    
    return success1 and success2

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
