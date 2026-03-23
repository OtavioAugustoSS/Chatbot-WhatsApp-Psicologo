import os
from apscheduler.schedulers.background import BackgroundScheduler
from db.database import SessionLocal
from db.models import Appointment
from datetime import datetime
from zoneinfo import ZoneInfo
from services.whatsapp import WhatsAppSender

scheduler = BackgroundScheduler()

def verificar_lembretes():
    db = SessionLocal()
    agora_utc = datetime.utcnow()
    whatsapp = WhatsAppSender()
    sp_tz = ZoneInfo("America/Sao_Paulo")
    
    try:
        # Busca todas as consultas pendentes de aviso
        consultas = db.query(Appointment).filter(
            (Appointment.lembrete_24h_enviado == 0) | (Appointment.lembrete_1h_enviado == 0)
        ).all()
        
        for appt in consultas:
            if not appt.data_hora: 
                continue
                
            diferenca = appt.data_hora - agora_utc
            minutos_faltando = diferenca.total_seconds() / 60
            
            # Converter UTC para SP para exibir na mensagem com precisão
            hora_sp = appt.data_hora.replace(tzinfo=ZoneInfo("UTC")).astimezone(sp_tz)
            str_hora = hora_sp.strftime('%H:%M')
            
            # Lembrete de 24 horas (envia se faltar entre 1435 e 1445 minutos)
            if appt.lembrete_24h_enviado == 0 and 1435 <= minutos_faltando <= 1445:
                nome = appt.user.nome or ""
                msg = f"Olá {nome}! Passando para confirmar nossa consulta amanhã às {str_hora}. Até lá! 😊"
                botoes = [
                    {"id": "menu_voltar", "title": "👍 Confirmar"},
                    {"id": "menu_faq", "title": "🔄 Reagendar/Dúvidas"}
                ]
                whatsapp.enviar_mensagem_botoes(appt.user.telefone, msg, botoes)
                appt.lembrete_24h_enviado = 1
                
            # Lembrete de 1 hora (envia se faltar entre 55 e 65 minutos)
            elif appt.lembrete_1h_enviado == 0 and 55 <= minutos_faltando <= 65:
                msg = f"Oi! Faltam apenas 60 minutinhos para nossa consulta marcada para às {str_hora}! O Dr. Itallo já está se preparando para te atender na clínica."
                whatsapp.enviar_mensagem_texto(appt.user.telefone, msg)
                appt.lembrete_1h_enviado = 1
                
        db.commit()
    except Exception as e:
        print(f"Erro invisivel no motor de lembretes: {e}")
    finally:
        db.close()

def iniciar_scheduler():
    # Roda a verificação pontualmente a cada 5 minutos
    scheduler.add_job(verificar_lembretes, 'interval', minutes=5)
    scheduler.start()
    print("APScheduler ativado: Motor Fantasma de Lembretes rodando a cada 5 min.")
    
def parar_scheduler():
    scheduler.shutdown()
