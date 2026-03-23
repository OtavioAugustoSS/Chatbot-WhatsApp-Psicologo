import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from core.config import settings

SCOPES = ['https://www.googleapis.com/auth/calendar']
ARQUIVO_CREDENCIAL = "credentials.json"

def _get_calendar_service():
    """Autentica na API do Google Calendar usando a Service Account."""
    if not os.path.exists(ARQUIVO_CREDENCIAL):
        raise FileNotFoundError(f"Arquivo {ARQUIVO_CREDENCIAL} não encontrado na raiz do projeto.")
    
    creds = Credentials.from_service_account_file(ARQUIVO_CREDENCIAL, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    return service

def buscar_horarios_livres(dias_frente=7):
    """
    Busca os próximos 10 horários livres na agenda compartilhada com a Service Account.
    Analisa os intervalos úteis (Seg a Sex | 09:00 - 18:00) cruzando com a agenda lotada (Busy).
    """
    service = _get_calendar_service()
    calendar_id = settings.CALENDAR_ID or settings.EMAIL_REMETENTE
    sp_tz = ZoneInfo("America/Sao_Paulo")
    
    agora = datetime.now(sp_tz)
    # Procuramos vagas a partir de "amanhã" para evitar furos no mesmo dia
    inicio = (agora + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    fim = inicio + timedelta(days=dias_frente)

    body = {
        "timeMin": inicio.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z"),
        "timeMax": fim.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z"),
        "items": [{"id": calendar_id}]
    }

    # Bate na API freebusy do Google
    try:
        resultado = service.freebusy().query(body=body).execute()
        calendarios = resultado.get('calendars', {})
        if calendar_id not in calendarios:
            print(f"[GOOGLE CALENDAR] Calendário de {calendar_id} não acessível. O doutor conferiu os Compartilhamentos?")
            return []
            
        busy_list = calendarios[calendar_id].get('busy', [])
    except Exception as e:
        print(f"[GOOGLE CALENDAR ERROR] {e}")
        return []
    
    # Faz o parser dos horários que o doutor ESTÁ ocupado
    ocupados = []
    for b in busy_list:
        b_start = datetime.fromisoformat(b['start'].replace('Z', '+00:00')).astimezone(sp_tz)
        b_end = datetime.fromisoformat(b['end'].replace('Z', '+00:00')).astimezone(sp_tz)
        ocupados.append((b_start, b_end))

    # Vamos gerar nós mesmos a matriz de slots do Doutor de Seg a Sex
    horarios_candidatos = [9, 10, 11, 14, 15, 16, 17] # Exemplo: 9h até 11h, 14h até 17h.
    slots_livres = []
    
    for d in range(dias_frente):
        dia_atual = inicio + timedelta(days=d)
        if dia_atual.weekday() >= 5: # Pula Sábado(5) e Domingo(6)
            continue
            
        for hora in horarios_candidatos:
            slot_start = dia_atual.replace(hour=hora)
            slot_end = slot_start + timedelta(minutes=50) # Sessões de 50 minutos
            
            # Testa se esse slot mágico colide com os slots Ocupados que o Google devolveu
            conflito = False
            for o_st, o_en in ocupados:
                # Interseção de faixas de horário
                if slot_start < o_en and slot_end > o_st:
                    conflito = True
                    break
            
            if not conflito:
                slots_livres.append({
                    "id": slot_start.isoformat(), 
                    "titulo": f"{dia_atual.strftime('%d/%m')} às {slot_start.strftime('%H:%M')}",
                    "dt_obj": slot_start
                })
                
            # O sistema interativo do WhatsApp permite NO MÁXIMO 10 opções numa "Lista"
            if len(slots_livres) >= 10:
                break
                
        if len(slots_livres) >= 10:
            break

    return slots_livres

def criar_evento(nome_paciente: str, telefone: str, iso_start_time: str):
    """
    Grava o evento oficialmente dentro do Google Calendar do Médico.
    """
    service = _get_calendar_service()
    calendar_id = settings.CALENDAR_ID or settings.EMAIL_REMETENTE
    sp_tz = ZoneInfo("America/Sao_Paulo")
    
    start_time = datetime.fromisoformat(iso_start_time).astimezone(sp_tz)
    end_time = start_time + timedelta(minutes=50)

    evento = {
        'summary': f'Consulta Psicologia: {nome_paciente}',
        'description': f'Telefone do paciente: {telefone}\nAgendado via Bot do WhatsApp Oficial.',
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'America/Sao_Paulo',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'America/Sao_Paulo',
        },
        'reminders': {
            'useDefault': True
        }
    }

    try:
        resultado = service.events().insert(calendarId=calendar_id, body=evento).execute()
        return resultado.get('htmlLink')
    except Exception as e:
        print(f"[GOOGLE CALENDAR ERROR AO CRIAR] {e}")
        return None
