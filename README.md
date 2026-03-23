# Chatbot WhatsApp - Psicólogo 

Este é um projeto de chatbot de autoatendimento construído em Python, concebido para automatizar as interações preliminares do consultório de psicologia via WhatsApp.

O foco deste bot é ser **100% determinístico** utilizando uma Máquina de Estados (State Machine) e menus de opções no formato de Botões Interativos (Interactive Buttons), garantindo um fluxo controlado, sem a imprevisibilidade de Inteligências Artificiais ou LLMs.

---

## 🚀 Tecnologias e Arquitetura

- **Linguagem:** Python 3.13+
- **Framework Web:** FastAPI (com Uvicorn)
- **Banco de Dados:** MySQL 8.0+
- **ORM:** SQLAlchemy (usando `pymysql` e `cryptography`)
- **Mensageria:** API Oficial do Meta (WhatsApp Cloud API) via modelo de Webhooks.
- **Nuvem:** Google Cloud Platform (Google Calendar API conectada via Service Account)
- **Background Jobs:** APScheduler (Threads invisíveis para envio de Lembretes)

> **Arquitetura modular:** O código isola a lógica de negócio (State Machine) das rotas HTTP (Webhook), permitindo que a mesma máquina de estados atenda a outras integrações no futuro (como a API do Telegram).

---

## 📋 Escopos e Funcionalidades Implementadas

### 1. Protocolo de Segurança e Acolhimento
A primeira interação do cliente em um chat recém-criado obrigatoriamente gera um retorno humanizado e protetivo contendo as políticas de contenção de crise e recomendação do Centro de Valorização da Vida (CVV).

### 2. Menu Principal (Interativo)
Após a saudação, o bot apresenta três botões de ação na tela do WhatsApp:
- **1ª Consulta:** Direciona para o fluxo de captação de Leads.
- **Já sou paciente:** Prepara terreno para reagendamentos futuros.
- **Dúvidas Frequentes:** Encaminha para o F.A.Q.

### 3. Fluxo de Triagem (Leads)
Coleta, passo a passo, os dados vitais para os novos pacientes (Nome -> Preferência Online/Presencial -> Melhores Dias). Toda interação e progressão de estado é registrada automaticamente nas tabelas do MySQL.

### 4. Tratamento Especial LGPD (Privacidade)
Caso um paciente envie qualquer arquivo de *Mídia* (como Áudio, Imagens, Documentos ou Stickers), o bot ignora o processamento do conteúdo pela rede e retorna uma mensagem protegendo o sigilo, instruindo o usuário a guardar aquele material exclusivo para o encontro presencial/online com o Doutor.

### 5. Agendamento em Tempo Real (Google Calendar)
Através de **Mensagens de Lista (Interactive Lists)** da Meta, o paciente recorrente clica num menu dentro do próprio WhatsApp e escolhe um de 10 horários livres mapeados dinamicamente da agenda oficial do Doutor na Google. O bot insere a consulta oficial lá na nuvem (com 50 minutos de duração) e salva na base local.

### 6. Sistema de Notificação SMTP (E-mail Assíncrono)
Para cada fluxo finalizado ou consulta agendada pelo WhatsApp, o servidor dispara "no escuro" (via `threading`) um e-mail estruturado em HTML para a conta do consultório informando os dados vitais ou turnos coletados, garantindo que a resposta ao paciente no WhatsApp não seja travada pela lentidão na rede SMTP.

### 7. Despertador Fantasma de Lembretes Automáticos
Um Loop baseado em `APScheduler` analisa a agenda silenciosamente a cada 5 minutos procurando as próximas consultas. 
- **Lembrete de 24 Horas:** Envia uma Message interativa nativa alertando o paciente sobre o compromisso com botões de confirmar/reagendar.
- **Lembrete de 1 Hora:** Manda preparo logístico na porta da sessão!

---

## 🛠️ Como Instalar e Configurar o Bot

### 1. Requisitos Prévios
- Ter o **Python 3.13** (ou superior) instalado.
- Ter o **MySQL Server** (junto com o MySQL Workbench) em execução local.
- No MySQL Workbench, execute a query: `CREATE DATABASE psicologo_bot_db;` para criar o banco vazio.

### 2. Instalação das Dependências
Clone ou abra a pasta do projeto e rode no terminal:
```bash
pip install -r requirements.txt
```

### 3. Configuração de Variáveis (Ambiente)
Na raiz do projeto existe o modelo `.env.example`.
1. Crie um novo arquivo chamado literalmente apenas: `.env`
2. Copie o conteúdo do modelo para ele.
3. Preencha a senha do seu banco de dados (`DB_PASSWORD`).
4. Preencha seus tokens fornecidos pelo painel Meta for Developers (Token permanente e ID do Telefone).
5. Defina uma senha em `WEBHOOK_VERIFY_TOKEN` (ex: `token_123`).
6. Requisite suas credenciais JSON de acesso Cloud na plataforma do **Google Cloud (Service Accounts)** e jogue o arquivo raiz com o nome obrigatório de `credentials.json`.
7. Configure o `EMAIL_REMETENTE`, a sua `EMAIL_SENHA` de Aplicativo Google (16 Letras), e o ID Master do dono do calendário em `CALENDAR_ID`.

---

## ▶️ Como Rodar o Servidor Localmente

Como a infraestrutura utiliza `uvicorn` rodando pelo módulo do Python, abra um terminal e simplesmente insira:

```bash
python -m uvicorn main:app --reload
```

*Se tudo der certo, aparecerá a mensagem verde `Application startup complete` indicando que a porta `8000` está aguardando conexões.*

---

## 🛜 Conectando ao Meta (Webhook Externo)

Para que a API Cloud do WhatsApp da sua conta corporativa consiga enviar mensagens para o seu computador (localhost), você deve expor a sua porta 8000. Você pode usar uma ferramenta gratuita como o `localtunnel`:

1. Em um SEGUNDO terminal rodando ao mesmo tempo, digite:
```bash
npx localtunnel --port 8000 --subdomain testepsicologo
```
2. Pegue o link gerado (ex: `https://testepsicologo.loca.lt`) e coloque no painel do Meta adicionando `/webhook` no final.
3. Insira lá no painel também o mesmo `WEBHOOK_VERIFY_TOKEN` que você salvou no `.env`.
4. Valide o Webhook e clique em **Gerenciar campos**, assinando o canal **`messages`**.

⚠️ **ATENÇÃO AOS BLOQUEIOS FREQUENTES:**
  - **Senha do Localtunnel:** Após rodar o comando 1, o site loca.lt agora bloqueia conexões via webhooks por razões de segurança, apresentando uma tela que exige uma *"Tunnel Password"*. A senha solicitada é o seu **IP Local** atual. Você deve acessar essa URL [https://loca.lt/mytunnelpassword](https://loca.lt/mytunnelpassword), copiar a sequência, acessar o seu link e destrancar a porta, caso contrário o Meta não conseguirá entregar mensagens ao sistema.
  - **Tokens Expiram em 24h:** O `WHATSAPP_TOKEN` temporário gerado no painel da Meta expira rotineiramente a cada 24 horas. Se você começar a observar *Erro 400 (Bad Request)* ou *Erro 10 (OAuthException)* nos logs do console, substitua o Token no arquivo `.env`. Logo após salvar, lembre-se de **reiniciar o servidor Uvicorn** (CTRL+C e rode novamente), pois as variáveis do `.env` só são injetadas no momento do boot.
  - **Telefones de Teste:** Enquanto o aplicativo não for oficial/produção, você só pode enviar e receber mensagens de números cadastrados manualmente na seção de Desenvolvedores da Meta.

Pronto! Seu Chatbot determinístico e voltado para privacidade na área da saúde estará conversando ativamente de acordo com os dados no MySQL.
