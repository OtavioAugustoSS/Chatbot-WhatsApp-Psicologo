import sys
import os
from dotenv import load_dotenv
load_dotenv()

from services.calendar_service import criar_evento

print("--- Iniciando teste do criar_evento ---")
try:
    res = criar_evento("Paciente Teste", "553899172173", "2026-03-24T14:00:00-03:00")
    print(f"--- Resultado: {res} ---")
except Exception as e:
    print(f"--- ERRO CRÍTICO --- {e}")
