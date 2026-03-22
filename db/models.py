from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
import enum
from datetime import datetime
from db.database import Base

class EstadoUsuario(enum.Enum):
    NOVA_INTERACAO = "nova_interacao"
    MENU_INICIAL = "menu_inicial"
    TRIAGEM_NOME = "triagem_nome"
    TRIAGEM_MODALIDADE = "triagem_modalidade"
    TRIAGEM_TURNO = "triagem_turno"
    TRIAGEM_DIA = "triagem_dia"
    PACIENTE_MARCAR = "paciente_marcar"
    FAQ_MENU = "faq_menu"
    FINALIZADO = "finalizado"
    # adicionaremos mais conforme as árvores cresçam

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telefone = Column(String(20), unique=True, index=True, nullable=False)
    estado_atual = Column(Enum(EstadoUsuario), default=EstadoUsuario.NOVA_INTERACAO, nullable=False)
    nome = Column(String(255), nullable=True) # Nome caso já saibamos (paciente) ou preenchido na triagem
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    leads = relationship("Lead", back_populates="user")
    appointments = relationship("Appointment", back_populates="user")

class ModalidadeConsulta(enum.Enum):
    ONLINE = "online"
    PRESENCIAL = "presencial"

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    modalidade = Column(Enum(ModalidadeConsulta), nullable=True)
    preferencia_horario = Column(String(255), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="leads")

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    data_hora = Column(DateTime, nullable=False)
    modalidade = Column(Enum(ModalidadeConsulta), nullable=False)
    lembrete_24h_enviado = Column(Integer, default=0) # 0 = false, 1 = true (boolean adaptado para MySQL simples)
    lembrete_1h_enviado = Column(Integer, default=0)
    criado_em = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="appointments")
