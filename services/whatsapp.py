import requests
from core.config import settings

def extrair_informacoes_mensagem(payload: dict) -> list:
    """
    Recebe o payload monstruoso do webhook do WhatsApp e extrai as partes úteis.
    Retorna uma lista de mensagens processadas, pois o payload pode vir com mais de uma.
    """
    out_messages = []
    
    if not payload.get("object") == "whatsapp_business_account":
        return out_messages
    
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            
            # Verificamos se há mensagens de fato
            if "messages" in value:
                for message in value["messages"]:
                    telefone_origem = message.get("from")
                    msg_id = message.get("id")
                    tipo = message.get("type") # "text", "image", "audio", "document", etc
                    
                    texto = None
                    if tipo == "text":
                        texto = message.get("text", {}).get("body")
                    
                    out_messages.append({
                        "telefone": telefone_origem,
                        "id_mensagem": msg_id,
                        "tipo": tipo,
                        "texto": texto
                    })
                    
    return out_messages

class WhatsAppSender:
    def __init__(self):
        self.token = settings.WHATSAPP_TOKEN
        self.phone_id = settings.WHATSAPP_PHONE_ID
        self.url = f"https://graph.facebook.com/v19.0/{self.phone_id}/messages"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def enviar_mensagem_texto(self, telefone: str, texto: str):
        """
        Envia uma mensagem de texto simples para um número de telefone informado.
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": telefone,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": texto
            }
        }
        
        try:
            resposta = requests.post(self.url, headers=self.headers, json=payload)
            resposta.raise_for_status()
            print(f"Mensagem enviada para {telefone}: {texto[:30]}...")
            return True
        except Exception as e:
            print(f"Erro ao enviar mensagem para {telefone}: {e}")
            if hasattr(e, 'response') and e.response:
                print(e.response.text)
            return False
