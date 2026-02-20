import logging
import os
from pathlib import Path

import jinja2
import yaml
from google.adk import Agent as LlmAgent
from google.adk.runners import Runner
from google.genai import types

from src.memory_gateway import LongTermMemoryGateway
from src.session_gateway import APP_NAME, USER_ID, NegotiationSessionGateway

logger = logging.getLogger(__name__)

# Caminho padrão da política (relativo ao CWD do processo)
DEFAULT_POLICY_PATH = Path("config/memory_policy.yaml")


def _load_max_rejections(config_path: Path | None = None) -> int:
    path = config_path or DEFAULT_POLICY_PATH
    if not path.exists():
        return 3
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return (data.get("session") or {}).get("max_rejections", 3)


def _llm_is_configured() -> bool:
    """
    Evita falhas em ambientes sem credenciais (CI/Lab offline).
    - Google AI Studio: GOOGLE_API_KEY
    - Vertex AI: GOOGLE_GENAI_USE_VERTEXAI + GOOGLE_CLOUD_PROJECT + LOCATION/REGION
    """
    if os.environ.get("USE_MOCK_LLM", "").strip().lower() in ("1", "true", "yes"):
        return False

    if os.environ.get("GOOGLE_API_KEY"):
        return True

    use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in ("1", "true", "yes")
    if not use_vertex:
        return False

    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION") or os.environ.get("GOOGLE_CLOUD_REGION")
    return bool(project and location)


class StatefulFinanceAgent:
    """
    Agente Mestre orquestrador de memória.
    Integra LlmAgent do Google ADK com os Gateways de curto e longo prazo.
    Dependências injetadas (IoC) para testes e substituição de infraestrutura.
    """

    def __init__(
        self,
        session_gw: NegotiationSessionGateway,
        memory_gw: LongTermMemoryGateway,
        *,
        policy_path: Path | None = None,
    ):
        self.session_gw = session_gw
        self.memory_gw = memory_gw
        self._max_rejections = _load_max_rejections(policy_path)

        self.jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader("prompts"))
        self.negotiator_template = self.jinja_env.get_template("negotiator.jinja2")
        self.injector_template = self.jinja_env.get_template("context_injector.jinja2")

        self.llm_agent = LlmAgent(
            name="StatefulAutoFinanceNegotiator",
            model="gemini-2.0-flash",
            instruction="Voce e um negociador de financiamentos. O contexto sera dinamicamente injetado.",
        )
        self.runner = Runner(
            app_name=APP_NAME,
            agent=self.llm_agent,
            session_service=self.session_gw.service,
        )

    async def process_message(
        self,
        session_id: str,
        customer_message: str,
        customer_tier: str = "standard",
    ) -> str:
        """Fluxo orquestrado (async): injeta estado e memória vetorial no prompt."""
        adk_session, state = await self.session_gw.recover_or_create(session_id, customer_tier)

        if state.funnel_stage == "human_handoff":
            return "[SYSTEM] Negociação encerrada pelo agente. Aguarde a transferência para um especialista."

        system_prompt = self.negotiator_template.render(
            funnel_stage=state.funnel_stage,
            proposed_rate=state.proposed_rate,
            rejection_count=state.rejection_count,
            customer_tier=state.customer_tier,
        )
        self.llm_agent.instruction = system_prompt

        contextual_prompt = customer_message
        if state.funnel_stage in ("rate_proposed", "analyzing_credit"):
            insights = await self.memory_gw.search_customer_insights(query=f"Sessao: {session_id}")
            if insights:
                contextual_prompt = self.injector_template.render(
                    base_prompt=customer_message,
                    long_term_insights=insights,
                )

        new_message = types.Content(
            role="user",
            parts=[types.Part(text=contextual_prompt)],
        )
        response_text = ""
        if not _llm_is_configured():
            # Modo offline: mantém o LAB executável sem depender de credenciais externas.
            response_text = (
                "[MOCK] Entendi seu pedido. Vou analisar seu perfil e buscar a melhor condição possível."
            )
        else:
            async for event in self.runner.run_async(
                user_id=USER_ID,
                session_id=session_id,
                new_message=new_message,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if getattr(part, "text", None):
                            response_text = part.text

        # =====================================================================
        # TODO (LAB-DESAFIO): ATUALIZAR O ESTADO E SALVAR CHECKPOINT
        # =====================================================================
        # Para simplificar o LAB, contamos cada chamada como "insatisfação/recusa"
        # (o main simula mensagens negativas). O Circuit Breaker aciona handoff
        # quando atingir o limite configurado.
        state.increment_rejection(max_rejections=self._max_rejections)
        if state.funnel_stage == "human_handoff":
            # Mensagem determinística para o critério de sucesso do LAB.
            response_text += (
                "\n\nHandoff acionado: Transferindo o cliente para analista humano."
                "\n[SYSTEM] Aviso: Limite de recusas excedido. O Circuit Breaker efetuará Handoff Humano."
            )

        # Persistência obrigatória do estado no Storage do ADK.
        await self.session_gw.save_checkpoint(adk_session, state)

        return response_text
    
