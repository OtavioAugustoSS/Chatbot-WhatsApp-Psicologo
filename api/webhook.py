from fastapi import APIRouter, Request, HTTPException, Depends
from core.config import settings
from services.whatsapp import extrair_informacoes_mensagem
from db.database import get_db
from sqlalchemy.orm import Session
# from db.models import User, EstadoUsuario # Importaremos quando fizermos a máquina de estados completa

router = APIRouter()

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
    
    for msg in mensagens:
        tipo = msg.get("tipo")
        telefone = msg.get("telefone")
        texto = msg.get("texto")
        
        print(f"[{telefone}] Nova mensagem tipo '{tipo}': {texto if texto else '<Mídia>'}")
        
        # Filtro de LGPD - Tratar Áudio e Documentos aqui
        if tipo in ["image", "audio", "document", "video", "sticker"]:
            # TODO: Enviar resposta padrão sobre LGPD e salvar o estado atual se necessário
            # Ex: whatsapp_sender.enviar_mensagem(telefone, "Recebi seu áudio/arquivo! Como sou apenas o assistente virtual...")
            print(f"[{telefone}] BLOQUEADO TIPO MÍDIA - Retornar msg de LGPD.")
            continue
        
        if tipo == "text":
            # TODO: Processar a máquina de estado do usuário
            # Buscar user db
            # Jogar na state_machine.processar(user, texto)
            print(f"[{telefone}] TEXTO RECEBIDO. Prosseguir para máquina de estados.")
        
    return {"status": "ok"}
