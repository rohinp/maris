"""Orchestrator Agent - LangGraph-based multi-agent coordinator for MARIS."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from langgraph.graph import StateGraph, END

from maris.agents.qa_agent import QAAgent, Answer
from maris.agents.indexing_agent import IndexingAgent
from maris.agents.documentation_agent import (
    DocumentationAgent,
    ModuleDocumentation,
    ArchitectureOverview,
)
from maris.core.models import IndexingResult
from maris.knowledge.service import RepositoryKnowledgeService
from maris.storage.metadata_store import MetadataStore
from maris.storage.vector_store import VectorStore
from maris.embeddings.ollama_embeddings import OllamaEmbeddingService

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of tasks the orchestrator can handle."""

    QUESTION = "question"  # Answer questions about code
    INDEX = "index"  # Index repository or files
    DOCUMENT = "document"  # Generate documentation
    STATUS = "status"  # Get repository status
    UNKNOWN = "unknown"


@dataclass
class OrchestratorResult:
    """Result from orchestrator execution."""

    task_type: TaskType
    success: bool
    result: Any
    agent_used: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Initialize metadata if None."""
        if self.metadata is None:
            self.metadata = {}


class OrchestratorAgent:
    """
    LangGraph-based Orchestrator Agent for multi-agent coordination.

    Uses a supervisor pattern with explicit workflow:
    1. classify_task: Determine which agent should handle the request
    2. route_to_agent: Route to the appropriate specialized agent
    3. execute_task: Execute the task with the selected agent
    4. format_response: Format the response for the user

    Coordinates between:
    - QA Agent: Answering questions about code
    - Indexing Agent: Indexing repositories and files
    - Documentation Agent: Generating documentation
    """

    def __init__(
        self,
        knowledge_service: RepositoryKnowledgeService,
        metadata_store: MetadataStore,
        vector_store: VectorStore,
        repo_path: str,
        qa_model: str = "qwen2.5:7b",
        embedding_model: str = "nomic-embed-text",
    ):
        """
        Initialize the orchestrator agent.

        Args:
            knowledge_service: Repository knowledge service
            metadata_store: Metadata store for indexing
            vector_store: Vector store for embeddings
            repo_path: Path to the repository
            qa_model: Model to use for Q&A
            embedding_model: Model to use for embeddings
        """
        self.knowledge_service = knowledge_service
        self.metadata_store = metadata_store
        self.vector_store = vector_store
        self.repo_path = repo_path

        # Initialize specialized agents
        self.qa_agent = QAAgent(
            knowledge_service=knowledge_service,
            model=qa_model,
        )

        embedding_service = OllamaEmbeddingService(model=embedding_model)
        self.indexing_agent = IndexingAgent(
            metadata_store=metadata_store,
            vector_store=vector_store,
            repo_path=repo_path,
            embedding_service=embedding_service,
        )

        self.documentation_agent = DocumentationAgent(
            knowledge_service=knowledge_service,
        )

        # Build the LangGraph workflow
        self.graph = self._build_graph()

        logger.info("Initialized OrchestratorAgent with multi-agent coordination")

    def _build_graph(self) -> Any:
        """Build the LangGraph workflow for orchestration."""
        # Use dict directly as state schema (LangGraph supports this)
        workflow = StateGraph(dict)

        # Add nodes
        workflow.add_node("classify_task", self._classify_task)
        workflow.add_node("route_to_agent", self._route_to_agent)
        workflow.add_node("execute_task", self._execute_task)
        workflow.add_node("format_response", self._format_response)

        # Define edges
        workflow.set_entry_point("classify_task")
        workflow.add_edge("classify_task", "route_to_agent")
        workflow.add_edge("route_to_agent", "execute_task")
        workflow.add_edge("execute_task", "format_response")
        workflow.add_edge("format_response", END)

        return workflow.compile()

    def _classify_task(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Classify the task type based on the request.

        Args:
            state: Current workflow state

        Returns:
            Updated state with task classification
        """
        try:
            logger.info("Classifying task")

            request = state.get("request", "")
            task_type = state.get("task_type")

            # If task_type is explicitly provided, use it
            if task_type:
                state["classified_task"] = TaskType(task_type)
                logger.info(f"Using explicit task type: {task_type}")
                return state

            # Otherwise, infer from request
            request_lower = request.lower()

            # Check for status keywords first (more specific than "index")
            if any(keyword in request_lower for keyword in ["status", "stats", "statistics"]):
                state["classified_task"] = TaskType.STATUS
            # Check for indexing keywords
            elif any(keyword in request_lower for keyword in ["index", "scan", "parse", "extract"]):
                state["classified_task"] = TaskType.INDEX
            # Check for documentation keywords
            elif any(
                keyword in request_lower
                for keyword in ["document", "generate doc", "architecture", "overview"]
            ):
                state["classified_task"] = TaskType.DOCUMENT
            # Check for question keywords (default for most queries)
            elif any(
                keyword in request_lower
                for keyword in ["what", "how", "why", "where", "when", "explain", "describe", "?"]
            ):
                state["classified_task"] = TaskType.QUESTION
            else:
                # Default to question for ambiguous requests
                state["classified_task"] = TaskType.QUESTION

            logger.info(f"Classified task as: {state['classified_task'].value}")

        except Exception as e:
            logger.error(f"Error classifying task: {e}")
            state["error"] = f"Failed to classify task: {str(e)}"
            state["classified_task"] = TaskType.UNKNOWN

        return state

    def _route_to_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Route to the appropriate agent based on task classification.

        Args:
            state: Current workflow state

        Returns:
            Updated state with selected agent
        """
        if state.get("error"):
            return state

        try:
            logger.info("Routing to appropriate agent")

            task_type = state.get("classified_task", TaskType.UNKNOWN)

            # Map task types to agents
            agent_mapping = {
                TaskType.QUESTION: "qa_agent",
                TaskType.INDEX: "indexing_agent",
                TaskType.DOCUMENT: "documentation_agent",
                TaskType.STATUS: "indexing_agent",  # Status comes from indexing agent
                TaskType.UNKNOWN: None,
            }

            selected_agent = agent_mapping.get(task_type)

            if not selected_agent:
                state["error"] = f"No agent available for task type: {task_type.value}"
                return state

            state["selected_agent"] = selected_agent
            logger.info(f"Routed to: {selected_agent}")

        except Exception as e:
            logger.error(f"Error routing to agent: {e}")
            state["error"] = f"Failed to route to agent: {str(e)}"

        return state

    def _execute_task(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Execute the task with the selected agent.

        Args:
            state: Current workflow state

        Returns:
            Updated state with execution result
        """
        if state.get("error"):
            return state

        try:
            logger.info("Executing task with selected agent")

            selected_agent = state.get("selected_agent")
            task_type = state.get("classified_task")

            result = None

            # Execute based on agent and task type
            if selected_agent == "qa_agent":
                question = state.get("request", "")
                result = self.qa_agent.answer_question(question)

            elif selected_agent == "indexing_agent":
                if task_type == TaskType.STATUS:
                    result = self.indexing_agent.get_indexing_status()
                elif task_type == TaskType.INDEX:
                    # Check if specific files or full repository
                    file_paths = state.get("file_paths")
                    if file_paths:
                        result = self.indexing_agent.index_files(file_paths)
                    else:
                        result = self.indexing_agent.index_repository()

            elif selected_agent == "documentation_agent":
                # Check what type of documentation is requested
                file_path = state.get("file_path")
                if file_path:
                    # Module documentation
                    format_type = state.get("format", "object")
                    if format_type == "markdown":
                        result = self.documentation_agent.generate_markdown_documentation(file_path)
                    else:
                        result = self.documentation_agent.generate_module_documentation(file_path)
                else:
                    # Architecture overview
                    format_type = state.get("format", "object")
                    if format_type == "markdown":
                        result = self.documentation_agent.generate_architecture_markdown()
                    else:
                        result = self.documentation_agent.generate_architecture_overview()

            state["execution_result"] = result
            state["success"] = True
            logger.info("Task executed successfully")

        except Exception as e:
            logger.error(f"Error executing task: {e}")
            state["error"] = f"Failed to execute task: {str(e)}"
            state["success"] = False

        return state

    def _format_response(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Format the response for the user.

        Args:
            state: Current workflow state

        Returns:
            Updated state with formatted response
        """
        try:
            logger.info("Formatting response")

            task_type = state.get("classified_task", TaskType.UNKNOWN)
            selected_agent = state.get("selected_agent", "unknown")
            success = state.get("success", False)
            result = state.get("execution_result")
            error = state.get("error")

            # Create orchestrator result
            orchestrator_result = OrchestratorResult(
                task_type=task_type,
                success=success,
                result=result,
                agent_used=selected_agent,
                error=error,
                metadata={
                    "request": state.get("request", ""),
                    "file_paths": state.get("file_paths"),
                    "file_path": state.get("file_path"),
                },
            )

            state["orchestrator_result"] = orchestrator_result
            logger.info("Response formatted")

        except Exception as e:
            logger.error(f"Error formatting response: {e}")
            state["orchestrator_result"] = OrchestratorResult(
                task_type=TaskType.UNKNOWN,
                success=False,
                result=None,
                agent_used="unknown",
                error=f"Failed to format response: {str(e)}",
            )

        return state

    def execute(
        self,
        request: str,
        task_type: Optional[str] = None,
        file_paths: Optional[List[str]] = None,
        file_path: Optional[str] = None,
        format: str = "object",
    ) -> OrchestratorResult:
        """
        Execute a request by routing to the appropriate agent.

        Args:
            request: Natural language request or command
            task_type: Optional explicit task type (question, index, document, status)
            file_paths: Optional list of files for indexing
            file_path: Optional file path for documentation
            format: Output format (object or markdown)

        Returns:
            OrchestratorResult with execution details
        """
        logger.info(f"Executing request: {request}")

        # Initialize state
        initial_state: Dict[str, Any] = {
            "request": request,
            "task_type": task_type,
            "file_paths": file_paths,
            "file_path": file_path,
            "format": format,
            "classified_task": None,
            "selected_agent": None,
            "execution_result": None,
            "success": False,
            "error": None,
            "orchestrator_result": None,
        }

        # Run the workflow
        final_state = self.graph.invoke(initial_state)

        # Handle None return from graph
        if final_state is None:
            final_state = initial_state
            final_state["orchestrator_result"] = OrchestratorResult(
                task_type=TaskType.UNKNOWN,
                success=False,
                result=None,
                agent_used="unknown",
                error="Workflow returned None",
            )

        result = final_state.get("orchestrator_result")
        if result is None:
            # Fallback if orchestrator_result wasn't set
            return OrchestratorResult(
                task_type=TaskType.UNKNOWN,
                success=False,
                result=None,
                agent_used="unknown",
                error="No orchestrator result in final state",
            )
        return result

    # Convenience methods for common operations

    def ask_question(self, question: str) -> Answer:
        """
        Ask a question about the repository.

        Args:
            question: Natural language question

        Returns:
            Answer from QA agent
        """
        result = self.execute(question, task_type="question")
        if result.success:
            return result.result
        else:
            raise Exception(f"Failed to answer question: {result.error}")

    def index_repository(self) -> IndexingResult:
        """
        Index the entire repository.

        Returns:
            IndexingResult with statistics
        """
        result = self.execute("Index repository", task_type="index")
        if result.success:
            return result.result
        else:
            raise Exception(f"Failed to index repository: {result.error}")

    def index_files(self, file_paths: List[str]) -> IndexingResult:
        """
        Index specific files.

        Args:
            file_paths: List of file paths to index

        Returns:
            IndexingResult with statistics
        """
        result = self.execute("Index files", task_type="index", file_paths=file_paths)
        if result.success:
            return result.result
        else:
            raise Exception(f"Failed to index files: {result.error}")

    def generate_documentation(self, file_path: str, format: str = "object") -> Any:
        """
        Generate documentation for a file.

        Args:
            file_path: Path to the file
            format: Output format (object or markdown)

        Returns:
            ModuleDocumentation object or markdown string
        """
        result = self.execute(
            f"Generate documentation for {file_path}",
            task_type="document",
            file_path=file_path,
            format=format,
        )
        if result.success:
            return result.result
        else:
            raise Exception(f"Failed to generate documentation: {result.error}")

    def get_status(self) -> dict:
        """
        Get repository indexing status.

        Returns:
            Status dictionary
        """
        result = self.execute("Get status", task_type="status")
        if result.success:
            return result.result
        else:
            raise Exception(f"Failed to get status: {result.error}")


# Made with Bob
