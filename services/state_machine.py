from sqlalchemy.orm import Session
from db.models import User, EstadoUsuario, Lead, Appointment, ModalidadeConsulta
from services.whatsapp import WhatsAppSender

class StateMachine:
    def __init__(self, db: Session, whatsapp: WhatsAppSender):
        self.db = db
        self.whatsapp = whatsapp

    def obter_ou_criar_usuario(self, telefone: str) -> User:
        user = self.db.query(User).filter(User.telefone == telefone).first()
        if not user:
            user = User(telefone=telefone, estado_atual=EstadoUsuario.NOVA_INTERACAO)
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        return user

    def processar_mensagem(self, telefone: str, texto: str):
        user = self.obter_ou_criar_usuario(telefone)
        estado = user.estado_atual
        texto = texto.strip().lower()

        # Independente de onde estiver, se digitar algo como voltar/cancelar/oi, volta pro menu inicial
        if texto in ["voltar", "cancelar", "menu", "oi", "olá", "ola", "start", "começar"]:
            user.estado_atual = EstadoUsuario.MENU_INICIAL
            self.db.commit()
            self._enviar_menu_inicial(telefone)
            return

        print(f"[{telefone}] Processando estado: {estado.name}")

        if estado == EstadoUsuario.NOVA_INTERACAO:
            self._fluxo_nova_interacao(user)
        elif estado == EstadoUsuario.MENU_INICIAL:
            self._fluxo_menu_inicial(user, texto)
        elif estado == EstadoUsuario.TRIAGEM_NOME:
            self._fluxo_triagem_nome(user, texto)
        elif estado == EstadoUsuario.TRIAGEM_MODALIDADE:
            self._fluxo_triagem_modalidade(user, texto)
        elif estado == EstadoUsuario.TRIAGEM_HORARIO:
            self._fluxo_triagem_horario(user, texto)
        elif estado == EstadoUsuario.FAQ_MENU:
            self._fluxo_faq(user, texto)
        else:
            # Fallback para casos não mapeados
            self._enviar_menu_inicial(user.telefone)
            user.estado_atual = EstadoUsuario.MENU_INICIAL
            self.db.commit()

    def _fluxo_nova_interacao(self, user: User):
        msg_boas_vindas = (
            "Olá! Sou o assistente virtual do Dr. Itallo Barcelos de Lima.\n\n"
            "⚠️ *Importante:* este chat é apenas para agendamentos e dúvidas. "
            "Se você estiver em crise ou precisando de ajuda imediata, por favor, ligue para o CVV (188) ou vá ao pronto-socorro mais próximo."
        )
        self.whatsapp.enviar_mensagem_texto(user.telefone, msg_boas_vindas)
        self._enviar_menu_inicial(user.telefone)
        
        user.estado_atual = EstadoUsuario.MENU_INICIAL
        self.db.commit()

    def _enviar_menu_inicial(self, telefone: str):
        menu = "Como posso te ajudar hoje? Escolha uma das opções abaixo:"
        botoes = [
            {"id": "menu_agendar", "title": "1ª Consulta"},
            {"id": "menu_paciente", "title": "Já sou paciente"},
            {"id": "menu_faq", "title": "Dúvidas Frequentes"}
        ]
        self.whatsapp.enviar_mensagem_botoes(telefone, menu, botoes)

    def _fluxo_menu_inicial(self, user: User, texto: str):
        if texto == "menu_agendar" or texto == "1":
            msg = "Que ótimo! Para começarmos, *qual é o seu nome completo?*"
            self.whatsapp.enviar_mensagem_texto(user.telefone, msg)
            user.estado_atual = EstadoUsuario.TRIAGEM_NOME
            self.db.commit()
        elif texto == "menu_paciente" or texto == "2":
            # Aqui entrará a lógica de mostrar horários livres para pacientes recorrentes
            msg = "Bem-vindo de volta! (Em breve: Mostrar horários livres). Digite 'menu' para voltar."
            self.whatsapp.enviar_mensagem_texto(user.telefone, msg)
            user.estado_atual = EstadoUsuario.PACIENTE_MARCAR
            self.db.commit()
        elif texto == "menu_faq" or texto == "3":
            msg = "Aqui estão as dúvidas mais frequentes. Clique em uma das opções abaixo:"
            botoes = [
                {"id": "faq_valor", "title": "Valor e Pagamento"},
                {"id": "faq_convenio", "title": "Convênios/Recibos"},
                {"id": "faq_sessao", "title": "Sobre a Sessão"}
            ]
            self.whatsapp.enviar_mensagem_botoes(user.telefone, msg, botoes)
            user.estado_atual = EstadoUsuario.FAQ_MENU
            self.db.commit()
        else:
            self.whatsapp.enviar_mensagem_texto(user.telefone, "Desculpe, não entendi. Por favor, clique em um dos botões do menu.")

    def _fluxo_triagem_nome(self, user: User, texto: str):
        # O usuário acabou de digitar o nome dele
        user.nome = texto
        
        # Cria um lead no banco temporariamente
        novo_lead = Lead(user_id=user.id)
        self.db.add(novo_lead)
        self.db.commit()

        msg = f"Prazer em conhecer, {user.nome}! Você prefere atendimentos na modalidade:"
        botoes = [
            {"id": "mod_online", "title": "Online"},
            {"id": "mod_presencial", "title": "Presencial"}
        ]
        self.whatsapp.enviar_mensagem_botoes(user.telefone, msg, botoes)
        user.estado_atual = EstadoUsuario.TRIAGEM_MODALIDADE
        self.db.commit()

    def _fluxo_triagem_modalidade(self, user: User, texto: str):
        lead = self.db.query(Lead).filter(Lead.user_id == user.id).order_by(Lead.id.desc()).first()
        
        if texto == "mod_online" or texto == "1":
            lead.modalidade = ModalidadeConsulta.ONLINE
        elif texto == "mod_presencial" or texto == "2":
            lead.modalidade = ModalidadeConsulta.PRESENCIAL
        else:
            self.whatsapp.enviar_mensagem_texto(user.telefone, "Por favor, clique apenas em 'Online' ou 'Presencial'.")
            return

        self.db.commit()

        msg = "Perfeito. Quais são os melhores dias e turnos para você? (Ex: Terça de manhã, Quarta à tarde...)"
        self.whatsapp.enviar_mensagem_texto(user.telefone, msg)
        user.estado_atual = EstadoUsuario.TRIAGEM_HORARIO
        self.db.commit()

    def _fluxo_triagem_horario(self, user: User, texto: str):
        lead = self.db.query(Lead).filter(Lead.user_id == user.id).order_by(Lead.id.desc()).first()
        lead.preferencia_horario = texto
        self.db.commit()

        msg = (
            "✅ Suas preferências foram anotadas!\n"
            "Vou repassar as informações ao Dr. Itallo e ele (ou sua secretaria) "
            "entrará em contato em breve para confirmar seu horário exato.\n\n"
            "Agradecemos o contato!"
        )
        self.whatsapp.enviar_mensagem_texto(user.telefone, msg)
        user.estado_atual = EstadoUsuario.FINALIZADO
        self.db.commit()

    def _fluxo_faq(self, user: User, texto: str):
        if texto == "faq_valor" or texto == "1":
            msg = "As sessões particulares têm o valor de R$ XXX. O pagamento pode ser feito via PIX, transferência ou cartão de crédito ao final de cada mês ou sessão independente."
            self.whatsapp.enviar_mensagem_texto(user.telefone, msg)
        elif texto == "faq_convenio" or texto == "2":
            msg = "Não atendo planos de saúde diretamente, mas emito recibos e notas fiscais que você pode usar para solicitar o reembolso no seu convênio."
            self.whatsapp.enviar_mensagem_texto(user.telefone, msg)
        elif texto == "faq_sessao" or texto == "3":
            msg = "As sessões duram cerca de 50 minutos. Nelas, você tem um espaço seguro e sigiloso para falar sobre o que quiser..."
            self.whatsapp.enviar_mensagem_texto(user.telefone, msg)
        elif texto == "0":
            self._enviar_menu_inicial(user.telefone)
            user.estado_atual = EstadoUsuario.MENU_INICIAL
            self.db.commit()
            return
        else:
            self.whatsapp.enviar_mensagem_texto(user.telefone, "Opção inválida. Por favor, clique em um dos botões.")
            return

        self.whatsapp.enviar_mensagem_texto(user.telefone, "\nDigite 'menu' ou 'voltar' quando quiser retornar ao menu inicial.")
