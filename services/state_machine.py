from sqlalchemy.orm import Session
from db.models import User, EstadoUsuario, Lead, Appointment, ModalidadeConsulta
from services.whatsapp import WhatsAppSender
from services.email_service import enviar_resumo_lead_email
import threading

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
        if texto in ["voltar", "cancelar", "menu", "oi", "olá", "ola", "start", "começar", "menu_voltar"]:
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
        elif estado == EstadoUsuario.TRIAGEM_TURNO:
            self._fluxo_triagem_turno(user, texto)
        elif estado == EstadoUsuario.TRIAGEM_DIA:
            self._fluxo_triagem_dia(user, texto)
        elif estado == EstadoUsuario.FAQ_MENU:
            self._fluxo_faq(user, texto)
        elif estado == EstadoUsuario.PACIENTE_MARCAR:
            self._fluxo_paciente_marcar(user, texto)
        elif estado == EstadoUsuario.FINALIZADO:
            self.whatsapp.enviar_mensagem_texto(user.telefone, "Sua solicitação de triagem já foi concluída! O Doutor entrará em contato em breve.")
        else:
            # Fallback para casos não mapeados
            self._enviar_menu_inicial(user.telefone)
            user.estado_atual = EstadoUsuario.MENU_INICIAL
            self.db.commit()

    def _fluxo_nova_interacao(self, user: User):
        msg_boas_vindas = (
            "Olá! Sou o assistente virtual do Dr. Psicólogo.\n\n"
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
            from services.calendar_service import buscar_horarios_livres
            
            # Avisa que vai carregar (pra não dar ilusão de lag)
            self.whatsapp.enviar_mensagem_texto(user.telefone, "Um momento! Estou sincronizando com a nuvem do Google Agenda para puxar as vagas livres desta semana...")
            
            slots = buscar_horarios_livres(dias_frente=7)
            if not slots:
                msg = "Poxa, no momento o Dr. Psicólogo não possui horários livres na agenda nos próximos dias. 😔"
                self.whatsapp.enviar_mensagem_texto(user.telefone, msg)
                botoes = [{"id": "menu_voltar", "title": "Voltar ao Menu"}]
                self.whatsapp.enviar_mensagem_botoes(user.telefone, "Deseja ver outras opções?", botoes)
                return
                
            msg = "Encontrei esses espaços livres na agenda oficial do Doutor! Qual você prefere?"
            rows = [{"id": f"slot_{slot['id']}", "title": slot["titulo"]} for slot in slots]
            
            sessoes = [{"title": "Horários da Semana", "rows": rows}]
            self.whatsapp.enviar_mensagem_lista(user.telefone, msg, "Abrir Horários", sessoes)
            
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

        msg = "Perfeito! Em qual turno você tem preferência para ser atendido?"
        botoes = [
            {"id": "turno_manha", "title": "Manhã"},
            {"id": "turno_tarde", "title": "Tarde"},
            {"id": "turno_noite", "title": "Noite"}
        ]
        self.whatsapp.enviar_mensagem_botoes(user.telefone, msg, botoes)
        user.estado_atual = EstadoUsuario.TRIAGEM_TURNO
        self.db.commit()

    def _fluxo_triagem_turno(self, user: User, texto: str):
        lead = self.db.query(Lead).filter(Lead.user_id == user.id).order_by(Lead.id.desc()).first()
        
        # Mapeando a resposta do botão para texto legível
        turnos_map = {
            "turno_manha": "Manhã",
            "turno_tarde": "Tarde",
            "turno_noite": "Noite",
            "1": "Manhã", "2": "Tarde", "3": "Noite"
        }
        
        turno_escolhido = turnos_map.get(texto)
        if not turno_escolhido:
            self.whatsapp.enviar_mensagem_texto(user.telefone, "Por favor, clique em um dos botões de turno (Manhã, Tarde ou Noite).")
            return
            
        lead.preferencia_horario = f"Turno: {turno_escolhido}"
        self.db.commit()
        
        msg = "Ótimo! Você tem preferência por algum dia da semana específico? (Ex: Segunda, Quinta, ou 'Qualquer dia')"
        self.whatsapp.enviar_mensagem_texto(user.telefone, msg)
        user.estado_atual = EstadoUsuario.TRIAGEM_DIA
        self.db.commit()

    def _fluxo_triagem_dia(self, user: User, texto: str):
        lead = self.db.query(Lead).filter(Lead.user_id == user.id).order_by(Lead.id.desc()).first()
        # Concatenando o dia com o turno que já estava salvo
        if lead.preferencia_horario:
            lead.preferencia_horario += f" | Dia: {texto}"
        else:
            lead.preferencia_horario = f"Dia: {texto}"
            
        self.db.commit()

        msg = (
            "✅ Suas preferências foram anotadas!\n"
            "Vou repassar as informações ao Dr. Psicólogo e ele (ou sua secretaria) "
            "entrará em contato em breve para confirmar seu horário exato.\n\n"
            "Agradecemos o contato!"
        )
        self.whatsapp.enviar_mensagem_texto(user.telefone, msg)
        user.estado_atual = EstadoUsuario.FINALIZADO
        self.db.commit()

        # Resgata formatado do Enum para exibição
        mod_str = lead.modalidade.value if lead.modalidade else "Não informada"
        pref_str = lead.preferencia_horario if lead.preferencia_horario else "Nenhuma"

        # Dispara o envio de E-mail em segundo plano para não dar timeout no Meta
        threading.Thread(
            target=enviar_resumo_lead_email, 
            args=(user.nome, user.telefone, mod_str, pref_str)
        ).start()

    def _fluxo_paciente_marcar(self, user: User, texto: str):
        if not texto.startswith("slot_"):
            self.whatsapp.enviar_mensagem_texto(user.telefone, "⚠️ Por favor, toque no botão 'Abrir Horários' e escolha um dos itens da lista.")
            return
            
        iso_id = texto.replace("slot_", "")
        
        from services.calendar_service import criar_evento
        from services.email_service import enviar_resumo_lead_email
        import threading
        
        # Cria no gcal de forma síncrona
        nome_marcador = user.nome if user.nome else "Paciente (Retorno)"
        link = criar_evento(nome_marcador, user.telefone, iso_id)
        
        if link:
            # Salvar Appointment no banco de dados para os Lembretes do APScheduler funcionarem
            from db.models import Appointment, ModalidadeConsulta
            from datetime import datetime, timezone
            
            # dt_obj em formato UTC puro para gravar no BD MySQL
            dt_obj_utc = datetime.fromisoformat(iso_id).astimezone(timezone.utc).replace(tzinfo=None)
            
            novo_agendamento = Appointment(
                user_id=user.id,
                data_hora=dt_obj_utc,
                modalidade=ModalidadeConsulta.PRESENCIAL
            )
            self.db.add(novo_agendamento)
            
            msg = f"🎉 Feito! Sua sessão para as {iso_id[-14:-9]} foi carimbada lá no Google Calendar oficial do Dr. Psicólogo!"
            self.whatsapp.enviar_mensagem_texto(user.telefone, msg)
            
            # Avisa o doutor no fundo
            threading.Thread(
                target=enviar_resumo_lead_email, 
                args=(nome_marcador, user.telefone, "Já sou paciente (Retorno)", f"Data travada via API: {iso_id}")
            ).start()
        else:
            self.whatsapp.enviar_mensagem_texto(user.telefone, "Um erro bizarro rolou na conexão com o Google. Tente ir no menu e clicar de novo.")
            
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

        msg_voltar = "Deseja voltar para ver outras opções?"
        botoes = [
            {"id": "menu_voltar", "title": "Voltar ao Menu"}
        ]
        self.whatsapp.enviar_mensagem_botoes(user.telefone, msg_voltar, botoes)
