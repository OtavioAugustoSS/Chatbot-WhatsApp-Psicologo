import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from core.config import settings

def enviar_resumo_lead_email(nome: str, telefone: str, modalidade: str, preferencia_horario: str):
    """ Envia um e-mail formatado em HTML informando ao Doutor que a Triagem foi finalizada. """
    
    if not settings.EMAIL_REMETENTE or not settings.EMAIL_SENHA:
        print("[EMAIL] Credenciais não configuradas no .env. Ignorando envio.")
        return

    destinatario = settings.EMAIL_REMETENTE # Envia para o próprio e-mail configurado do consultório

    assunto = f"Aviso de Nova Triagem (Chatbot): {nome}"
    
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #2F80ED;">Novo Paciente Agendando Consulta</h2>
        <p>Um lead completou a triagem com o Assistente Virtual pelo WhatsApp!</p>
        
        <table border="1" cellpadding="10" cellspacing="0" style="border-collapse: collapse; width: 100%; max-width: 600px;">
            <tr>
                <td style="background-color: #f7f7f7;"><strong>Nome do Paciente:</strong></td>
                <td>{nome}</td>
            </tr>
            <tr>
                <td style="background-color: #f7f7f7;"><strong>Telefone:</strong></td>
                <td>{telefone}</td>
            </tr>
            <tr>
                <td style="background-color: #f7f7f7;"><strong>Modalidade:</strong></td>
                <td>{modalidade}</td>
            </tr>
            <tr>
                <td style="background-color: #f7f7f7;"><strong>Preferência de Horário:</strong></td>
                <td>{preferencia_horario}</td>
            </tr>
        </table>
        <br>
        <a href="https://wa.me/{telefone.replace('+', '')}" 
           style="background-color: #25D366; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">
           Responder no WhatsApp
        </a>
      </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['From'] = settings.EMAIL_REMETENTE
    msg['To'] = destinatario
    msg['Subject'] = assunto

    msg.attach(MIMEText(html, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(settings.EMAIL_REMETENTE, settings.EMAIL_SENHA)
        server.send_message(msg)
        server.quit()
        print(f"[EMAIL] E-mail de triagem processado com sucesso para {destinatario}!")
    except Exception as e:
        print(f"[EMAIL ERROR] Falha ao enviar o E-mail: {e}")
