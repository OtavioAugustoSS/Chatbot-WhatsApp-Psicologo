from fastapi import FastAPI
from core.config import settings
from db.database import engine, Base
from api import webhook

# Criação das tabelas no banco de dados, caso não existam (substitui o alembic no MVP)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Bot Psicológo Meta API",
    description="Webhook e máquina de estados para atendimento de pacientes do Dr Itallo Barcelos",
    version="1.0.0"
)

# Adicionando Rotas
app.include_router(webhook.router)

@app.get("/")
def read_root():
    return {"message": "Bem-vindo ao Webhook do Bot do Psicólogo."}
