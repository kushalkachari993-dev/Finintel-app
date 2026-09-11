import logging
import time
from dataclasses import dataclass
from typing import Callable
from typing import Literal

from backend.config import settings
from backend.llm.model_selector import select_groq_model
from backend.storage import ConversationRepositoryError
from backend.utils.async_execution import run_blocking
from backend.utils.financial_guardrails import apply_financial_guardrails


logger = logging.getLogger(__name__)


ResearchMode = Literal["chat", "report"]
ProgressCallback = Callable[[str, dict], None]
CHAT_ROUTES = {
    "FUNDAMENTAL",
    "PRICE_QUERY",
    "COMPARISON",
    "EDUCATIONAL",
    "NEWS",
    "DISCOVERY",
}


@dataclass(frozen=True)
class ResearchOutcome:
    payload: dict
    status_code: int = 200
    route: str | None = None


class ConversationNotFoundError(Exception):
    pass


class ResearchService:
    """Coordinates one research request independently of the HTTP transport."""

    SUCCESS_PROGRESS_TOTAL = 10

    def __init__(
        self,
        *,
        router_agent,
        fundamental_agent,
        comparison_agent,
        price_agent,
        educational_agent,
        discovery_agent,
        news_agent,
        report_agent,
        query_intelligence,
        conversation_repository,
        conversation_context_for_request: Callable,
        contextual_query: Callable,
        build_generation_context: Callable,
        is_follow_up_query: Callable,
        response_context_text: Callable,
    ):
        self.router_agent = router_agent
        self.fundamental_agent = fundamental_agent
        self.comparison_agent = comparison_agent
        self.price_agent = price_agent
        self.educational_agent = educational_agent
        self.discovery_agent = discovery_agent
        self.news_agent = news_agent
        self.report_agent = report_agent
        self.query_intelligence = query_intelligence
        self.conversation_repository = conversation_repository
        self.conversation_context_for_request = (
            conversation_context_for_request
        )
        self.contextual_query = contextual_query
        self.build_generation_context = build_generation_context
        self.is_follow_up_query = is_follow_up_query
        self.response_context_text = response_context_text

    async def execute_chat(
        self,
        *,
        query: str,
        answer_detail: str = "brief",
        conversation_id: str | None = None,
        client_context: list | None = None,
        principal_id: str = "unknown",
        request_id: str = "",
        api_client_id: str | None = None,
        on_route_selected: Callable[[str], None] | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> ResearchOutcome:
        return await self._execute(
            mode="chat",
            query=query,
            answer_detail=answer_detail,
            conversation_id=conversation_id,
            client_context=client_context or [],
            principal_id=principal_id,
            request_id=request_id,
            api_client_id=api_client_id,
            on_route_selected=on_route_selected,
            on_progress=on_progress,
        )

    async def execute_report(
        self,
        *,
        query: str,
        conversation_id: str | None = None,
        client_context: list | None = None,
        principal_id: str = "unknown",
        request_id: str = "",
        api_client_id: str | None = None,
        on_route_selected: Callable[[str], None] | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> ResearchOutcome:
        return await self._execute(
            mode="report",
            query=query,
            answer_detail="detailed",
            conversation_id=conversation_id,
            client_context=client_context or [],
            principal_id=principal_id,
            request_id=request_id,
            api_client_id=api_client_id,
            on_route_selected=on_route_selected,
            on_progress=on_progress,
        )

    async def _execute(
        self,
        *,
        mode: ResearchMode,
        query: str,
        answer_detail: str,
        conversation_id: str | None,
        client_context: list,
        principal_id: str,
        request_id: str,
        api_client_id: str | None,
        on_route_selected: Callable[[str], None] | None,
        on_progress: ProgressCallback | None,
    ) -> ResearchOutcome:
        started_at = time.perf_counter()
        user_query = query.strip()
        route = "REPORT" if mode == "report" else "FUNDAMENTAL"
        routing_result = (
            {
                "route": "REPORT",
                "confidence": 1.0,
                "reasoning": "Report mode selected by user.",
            }
            if mode == "report"
            else {}
        )
        intelligence = {}
        selected_model = None

        self._emit_progress(
            on_progress,
            "request_started",
            message="Research request accepted.",
            mode=mode,
        )

        if not user_query:
            self._emit_progress(
                on_progress,
                "failed",
                message="Query cannot be empty.",
                status_code=400,
            )
            return ResearchOutcome(
                payload={
                    "success": False,
                    "error": "Query cannot be empty.",
                },
                status_code=400,
                route=route,
            )

        try:
            conversation_id = await self._resolve_conversation(
                principal_id=principal_id,
                conversation_id=conversation_id,
                title=user_query,
            )
            self._emit_progress(
                on_progress,
                "conversation_ready",
                message="Conversation is ready.",
                conversation_id=conversation_id,
            )
            conversation_context = (
                await self.conversation_context_for_request(
                    principal_id=principal_id,
                    conversation_id=conversation_id,
                    client_context=client_context,
                )
            )
            self._emit_progress(
                on_progress,
                "context_loaded",
                message="Conversation context loaded.",
                message_count=len(conversation_context),
            )
            await self.conversation_repository.add_message(
                conversation_id=conversation_id,
                principal_id=principal_id,
                role="user",
                content=user_query,
            )

            analysis_query = self.contextual_query(
                user_query,
                conversation_context,
            )
            generation_context = (
                self.build_generation_context(
                    conversation_context
                )
                if self.is_follow_up_query(user_query)
                else ""
            )

            intelligence = await run_blocking(
                self.query_intelligence.extract,
                analysis_query,
                timeout_seconds=(
                    settings.EXTERNAL_CALL_TIMEOUT_SECONDS
                ),
            )

            logger.info(
                "query_intelligence query=%r intelligence=%s",
                user_query,
                intelligence,
            )
            self._emit_progress(
                on_progress,
                "query_classified",
                message="Question classified.",
                intent=(
                    intelligence.get("intent")
                    if isinstance(intelligence, dict)
                    else None
                ),
            )

            if mode == "chat":
                routing_result = await run_blocking(
                    self.router_agent.route,
                    analysis_query,
                    intelligence=intelligence,
                    timeout_seconds=(
                        settings.EXTERNAL_CALL_TIMEOUT_SECONDS
                    ),
                )
                route = routing_result.get(
                    "route",
                    "FUNDAMENTAL",
                )

                if route not in CHAT_ROUTES:
                    route = "FUNDAMENTAL"
                    routing_result = {
                        "route": route,
                        "confidence": 0.30,
                        "reasoning": "Fallback route triggered.",
                    }

            selected_model = select_groq_model(
                route,
                answer_detail,
            )

            if on_route_selected:
                on_route_selected(route)

            self._emit_progress(
                on_progress,
                "route_selected",
                message=(
                    "Using the "
                    f"{route.replace('_', ' ').lower()} research workflow."
                ),
                route=route,
                model=selected_model,
            )

            logger.info(
                "route_selected query=%r route=%s model=%s routing=%s",
                user_query,
                route,
                selected_model,
                routing_result,
            )

            self._emit_progress(
                on_progress,
                "agent_started",
                message="Research agent started.",
                route=route,
            )

            if mode == "report":
                response = await run_blocking(
                    self.report_agent.generate,
                    query=analysis_query,
                    intelligence=intelligence,
                    model=selected_model,
                    conversation_context=generation_context,
                    timeout_seconds=(
                        settings.CHAT_EXECUTION_TIMEOUT_SECONDS
                    ),
                )
            else:
                (
                    route,
                    routing_result,
                    selected_model,
                    response,
                ) = await self._execute_chat_route(
                    route=route,
                    routing_result=routing_result,
                    query=analysis_query,
                    intelligence=intelligence,
                    model=selected_model,
                    answer_detail=answer_detail,
                    conversation_context=generation_context,
                )

                if on_route_selected:
                    on_route_selected(route)

            self._emit_progress(
                on_progress,
                "response_generated",
                message="Research response generated.",
                route=route,
            )

            response = apply_financial_guardrails(
                response,
                route,
            )
            self._emit_progress(
                on_progress,
                "guardrails_applied",
                message="Financial guardrails applied.",
                route=route,
            )
            final_response = {
                "success": True,
                "query": user_query,
                "conversation_id": conversation_id,
                "answer_detail": answer_detail,
                "route": route,
                "routing": routing_result,
                "query_intelligence": intelligence,
                "model": selected_model,
                "response": response,
            }

            await self._persist_success(
                final_response=final_response,
                response=response,
                mode=mode,
                principal_id=principal_id,
                request_id=request_id,
                api_client_id=api_client_id,
                conversation_id=conversation_id,
                started_at=started_at,
            )
            self._emit_progress(
                on_progress,
                "persisted",
                message="Research result saved.",
                conversation_id=conversation_id,
            )
            self._emit_progress(
                on_progress,
                "completed",
                message="Research completed.",
                route=route,
            )

            return ResearchOutcome(
                payload=final_response,
                route=route,
            )

        except ConversationNotFoundError:
            self._emit_progress(
                on_progress,
                "failed",
                message="Conversation not found.",
                status_code=404,
            )
            return ResearchOutcome(
                payload={
                    "success": False,
                    "error": "Conversation not found.",
                },
                status_code=404,
                route=route,
            )

        except ConversationRepositoryError:
            message = "Research storage is temporarily unavailable."
            logger.exception(
                "research_persistence_failed mode=%s query=%r route=%s",
                mode,
                user_query,
                route,
            )
            self._emit_progress(
                on_progress,
                "failed",
                message=message,
                status_code=503,
                route=route,
            )
            return ResearchOutcome(
                payload=self._error_payload(
                    message=message,
                    user_query=user_query,
                    answer_detail=answer_detail,
                    route=route,
                    routing_result=routing_result,
                    intelligence=intelligence,
                ),
                status_code=503,
                route=route,
            )

        except TimeoutError:
            message = (
                "Request timed out while waiting for external providers."
            )
            logger.warning(
                "research_timed_out mode=%s query=%r route=%s",
                mode,
                user_query,
                route,
            )
            await self._persist_failure(
                message=message,
                user_query=user_query,
                answer_detail=answer_detail,
                route=route,
                routing_result=routing_result,
                intelligence=intelligence,
                selected_model=selected_model,
                conversation_id=conversation_id,
                principal_id=principal_id,
                request_id=request_id,
                api_client_id=api_client_id,
                started_at=started_at,
            )
            self._emit_progress(
                on_progress,
                "failed",
                message=message,
                status_code=504,
                route=route,
            )
            return ResearchOutcome(
                payload=self._error_payload(
                    message=message,
                    user_query=user_query,
                    answer_detail=answer_detail,
                    route=route,
                    routing_result=routing_result,
                    intelligence=intelligence,
                ),
                status_code=504,
                route=route,
            )

        except Exception as error:
            logger.exception(
                "research_failed mode=%s query=%r route=%s",
                mode,
                user_query,
                route,
            )
            message = str(error)
            await self._persist_failure(
                message=message,
                user_query=user_query,
                answer_detail=answer_detail,
                route=route,
                routing_result=routing_result,
                intelligence=intelligence,
                selected_model=selected_model,
                conversation_id=conversation_id,
                principal_id=principal_id,
                request_id=request_id,
                api_client_id=api_client_id,
                started_at=started_at,
            )
            self._emit_progress(
                on_progress,
                "failed",
                message=message,
                status_code=500,
                route=route,
            )
            return ResearchOutcome(
                payload=self._error_payload(
                    message=message,
                    user_query=user_query,
                    answer_detail=answer_detail,
                    route=route,
                    routing_result=routing_result,
                    intelligence=intelligence,
                ),
                status_code=500,
                route=route,
            )

    @staticmethod
    def _emit_progress(
        callback: ProgressCallback | None,
        stage: str,
        *,
        message: str,
        **details,
    ):
        if not callback:
            return

        try:
            callback(
                stage,
                {
                    "message": message,
                    **details,
                },
            )
        except Exception:
            logger.exception(
                "research_progress_callback_failed stage=%s",
                stage,
            )

    async def _resolve_conversation(
        self,
        *,
        principal_id: str,
        conversation_id: str | None,
        title: str,
    ) -> str:
        if conversation_id:
            if not await self.conversation_repository.conversation_exists(
                principal_id=principal_id,
                conversation_id=conversation_id,
            ):
                raise ConversationNotFoundError

            return conversation_id

        return await self.conversation_repository.create_conversation(
            principal_id=principal_id,
            title=title,
        )

    async def _execute_chat_route(
        self,
        *,
        route: str,
        routing_result: dict,
        query: str,
        intelligence: dict,
        model: str,
        answer_detail: str,
        conversation_context: str,
    ) -> tuple[str, dict, str, dict]:
        common = {
            "timeout_seconds": (
                settings.CHAT_EXECUTION_TIMEOUT_SECONDS
            ),
        }

        if route == "FUNDAMENTAL":
            response = await run_blocking(
                self.fundamental_agent.analyze,
                query=query,
                intelligence=intelligence,
                model=model,
                answer_detail=answer_detail,
                conversation_context=conversation_context,
                **common,
            )
        elif route == "PRICE_QUERY":
            response = await run_blocking(
                self.price_agent.get_price,
                query,
                answer_detail=answer_detail,
                **common,
            )
        elif route == "COMPARISON":
            response = await run_blocking(
                self.comparison_agent.compare,
                query,
                intelligence=intelligence,
                model=model,
                answer_detail=answer_detail,
                conversation_context=conversation_context,
                **common,
            )
        elif route == "EDUCATIONAL":
            response = await run_blocking(
                self.educational_agent.explain,
                query,
                model=model,
                answer_detail=answer_detail,
                conversation_context=conversation_context,
                **common,
            )
        elif route == "NEWS":
            response = await run_blocking(
                self.news_agent.analyze,
                query,
                intelligence=intelligence,
                model=model,
                answer_detail=answer_detail,
                conversation_context=conversation_context,
                **common,
            )
        elif route == "DISCOVERY":
            response = await run_blocking(
                self.discovery_agent.discover,
                query,
                intelligence=intelligence,
                model=model,
                answer_detail=answer_detail,
                conversation_context=conversation_context,
                **common,
            )
        else:
            route = "FUNDAMENTAL"
            model = select_groq_model(
                route,
                answer_detail,
            )
            routing_result = {
                "route": route,
                "confidence": 0.30,
                "reasoning": "Fallback route triggered.",
            }
            response = await run_blocking(
                self.fundamental_agent.analyze,
                query,
                intelligence=intelligence,
                model=model,
                answer_detail=answer_detail,
                conversation_context=conversation_context,
                **common,
            )

        return route, routing_result, model, response

    async def _persist_success(
        self,
        *,
        final_response: dict,
        response: dict,
        mode: ResearchMode,
        principal_id: str,
        request_id: str,
        api_client_id: str | None,
        conversation_id: str,
        started_at: float,
    ):
        await self.conversation_repository.persist_assistant_and_audit(
            conversation_id=conversation_id,
            principal_id=principal_id,
            content=(
                self.response_context_text(response)
                or (
                    "Report generated."
                    if mode == "report"
                    else "Analysis completed."
                )
            ),
            payload=final_response,
            query=final_response["query"],
            route=final_response["route"],
            routing=final_response["routing"],
            query_intelligence=final_response["query_intelligence"],
            response=response,
            answer_detail=final_response["answer_detail"],
            model=final_response["model"],
            request_id=request_id,
            user_id=None,
            api_client_id=api_client_id,
            latency_ms=round(
                (time.perf_counter() - started_at) * 1000,
                2,
            ),
        )

    async def _persist_failure(
        self,
        *,
        message: str,
        user_query: str,
        answer_detail: str,
        route: str,
        routing_result: dict,
        intelligence: dict,
        selected_model: str | None,
        conversation_id: str | None,
        principal_id: str,
        request_id: str,
        api_client_id: str | None,
        started_at: float,
    ):
        if not conversation_id:
            return

        response = {
            "success": False,
            "error": message,
        }
        final_response = {
            "success": False,
            "query": user_query,
            "conversation_id": conversation_id,
            "answer_detail": answer_detail,
            "route": route,
            "routing": routing_result,
            "query_intelligence": intelligence,
            "model": selected_model,
            "response": response,
        }

        try:
            await self.conversation_repository.persist_assistant_and_audit(
                conversation_id=conversation_id,
                principal_id=principal_id,
                content=message,
                payload=final_response,
                query=final_response["query"],
                route=final_response["route"],
                routing=final_response["routing"],
                query_intelligence=final_response["query_intelligence"],
                response=response,
                answer_detail=final_response["answer_detail"],
                model=final_response["model"],
                request_id=request_id,
                user_id=None,
                api_client_id=api_client_id,
                latency_ms=round(
                    (time.perf_counter() - started_at) * 1000,
                    2,
                ),
            )
        except Exception:
            logger.exception(
                "research_failure_persistence_failed request_id=%s",
                request_id,
            )

    @staticmethod
    def _error_payload(
        *,
        message: str,
        user_query: str,
        answer_detail: str,
        route: str,
        routing_result: dict,
        intelligence: dict,
    ) -> dict:
        return {
            "success": False,
            "query": user_query,
            "answer_detail": answer_detail,
            "route": route,
            "routing": routing_result,
            "query_intelligence": intelligence,
            "error": message,
        }
