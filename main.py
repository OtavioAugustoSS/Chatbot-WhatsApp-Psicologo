from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.config import settings
from db.database import engine, Base
from api import webhook

# Criação das tabelas no banco de dados, caso não existam (substitui o alembic no MVP)
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    from jobs.lembretes import iniciar_scheduler, parar_scheduler
    iniciar_scheduler()
    yield
    parar_scheduler()

app = FastAPI(
    title="Bot Psicológo Meta API",
    description="Webhook e máquina de estados para atendimento de pacientes do Dr Itallo Barcelos",
    version="1.0.0",
    lifespan=lifespan
)

# Adicionando Rotas
app.include_router(webhook.router)

@app.get("/")
def read_root():
    return {"message": "Bem-vindo ao Webhook do Bot do Psicólogo."}
