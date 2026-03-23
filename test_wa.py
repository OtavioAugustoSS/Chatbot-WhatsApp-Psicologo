import os
from dotenv import load_dotenv
load_dotenv()

from services.whatsapp import WhatsAppSender
from services.calendar_service import buscar_horarios_livres

w = WhatsAppSender()
slots = buscar_horarios_livres(7)
rows = [{"id": f"slot_{s['id']}", "title": s['titulo']} for s in slots]
sessoes = [{"title": "Horários Livres", "rows": rows}]

print('Enviando lista para Meta...')
res = w.enviar_mensagem_lista('553899172173', 'Escolha o melhor horário:', 'Ver Horários', sessoes)
print('Sucesso:', res)
