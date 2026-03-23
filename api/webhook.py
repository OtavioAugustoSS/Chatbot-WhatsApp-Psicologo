from fastapi import APIRouter, Request, HTTPException, Depends
from core.config import settings
from services.whatsapp import extrair_informacoes_mensagem, WhatsAppSender
from services.state_machine import StateMachine
from db.database import get_db
from sqlalchemy.orm import Session

router = APIRouter()

# Armazena os IDs das mensagens já processadas para evitar duplicatas (retries da Meta)
mensagens_processadas = set()

@router.get("/webhook")
async def verify_webhook(request: Request):
    """
    Endpoint obrigatório para o Meta Cloud API validar nossa URL.
    Ele envia um hub.mode, hub.challenge e hub.verify_token.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == settings.WEBHOOK_VERIFY_TOKEN:
            print("Webhook Verified!")
            return int(challenge)
        else:
            raise HTTPException(status_code=403, detail="Forbidden - Token Mismatch")
    
    raise HTTPException(status_code=400, detail="Bad Request - Missing query parameters")

@router.post("/webhook")
async def receive_message(request: Request, db: Session = Depends(get_db)):
    """
    Receptor primário de todas as notificações e mensagens do WhatsApp.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    mensagens = extrair_informacoes_mensagem(body)
    
    whatsapp = WhatsAppSender()
    state_machine = StateMachine(db, whatsapp)
    
    for msg in mensagens:
        tipo = msg.get("tipo")
        telefone = msg.get("telefone")
        texto = msg.get("texto")
        id_msg = msg.get("id_mensagem")
        
        # Sistema Anti-Duplicação do Webhook
        if id_msg in mensagens_processadas:
            print(f"[{telefone}] Ignorando mensagem ID {id_msg} (já processada).")
            continue
            
        mensagens_processadas.add(id_msg)
        if len(mensagens_processadas) > 2000:
            mensagens_processadas.clear()
        
        print(f"[{telefone}] Nova mensagem tipo '{tipo}': {texto if texto else '<Mídia>'}")
        
        # Filtro de LGPD - Tratar Áudio e Documentos aqui
        if tipo in ["image", "audio", "document", "video", "sticker"]:
            print(f"[{telefone}] BLOQUEADO TIPO MÍDIA - Retornar msg de LGPD.")
            msg_lgpd = (
                "Recebi seu arquivo/áudio! 🤖\nComo sou apenas o assistente virtual, "
                "peço que guarde esses detalhes em texto ou compartilhe diretamente "
                "com o Dr. Psicólogo no momento da sua sessão.\n\n"
                "Para continuarmos nosso agendamento, por favor, me envie apenas mensagens de *texto*."
            )
            whatsapp.enviar_mensagem_texto(telefone, msg_lgpd)
            continue
        
        if tipo in ["text", "interactive"] and texto:
            print(f"[{telefone}] MENSAGEM RECEBIDA (text/interactive). Prosseguir para máquina de estados.")
            state_machine.processar_mensagem(telefone, texto)
        
    return {"status": "ok"}
