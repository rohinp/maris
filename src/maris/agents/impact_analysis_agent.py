"""Impact Analysis Agent - LangGraph-based implementation for analyzing code impact."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from langgraph.graph import StateGraph, END

from maris.core.models import EdgeCase, ImpactAnalysisResult, Symbol
from maris.knowledge.service import RepositoryKnowledgeService

logger = logging.getLogger(__name__)


class AnalysisType:
    """Types of impact analysis."""

    IMPACT = "impact"
    EDGE_CASES = "edge_cases"
    TESTS = "tests"
    BREAKING_CHANGES = "breaking_changes"


class ImpactAnalysisAgent:
    """
    LangGraph-based Impact Analysis Agent for analyzing code changes.

    Uses explicit workflow:
    1. classify_analysis_type: Determine what type of analysis to perform
    2. retrieve_target_symbol: Find the symbol to analyze
    3. analyze_dependencies: Find callers and callees
    4. analyze_test_coverage: Find tests covering the symbol
    5. detect_edge_cases: Identify potential edge cases
    6. generate_recommendations: Create actionable recommendations
    7. format_report: Format the final report

    Capabilities:
    - Dependency analysis (who calls this? who does this call?)
    - Test coverage analysis (what tests cover this?)
    - Edge case detection (what edge cases should be handled?)
    - Breaking change detection (will this change break anything?)
    """

    def __init__(
        self,
        knowledge_service: RepositoryKnowledgeService,
    ):
        """
        Initialize the impact analysis agent.

        Args:
            knowledge_service: Repository knowledge service for retrieval
        """
        self.knowledge_service = knowledge_service

        # Build the LangGraph workflow
        self.graph = self._build_graph()

        logger.info("Initialized ImpactAnalysisAgent with LangGraph")

    def _build_graph(self) -> Any:
        """Build the LangGraph workflow for impact analysis."""
        workflow = StateGraph(dict)

        # Add nodes
        workflow.add_node("classify_analysis_type", self._classify_analysis_type)
        workflow.add_node("retrieve_target_symbol", self._retrieve_target_symbol)
        workflow.add_node("analyze_dependencies", self._analyze_dependencies)
        workflow.add_node("analyze_test_coverage", self._analyze_test_coverage)
        workflow.add_node("detect_edge_cases", self._detect_edge_cases)
        workflow.add_node("generate_recommendations", self._generate_recommendations)
        workflow.add_node("format_report", self._format_report)

        # Define edges
        workflow.set_entry_point("classify_analysis_type")
        workflow.add_edge("classify_analysis_type", "retrieve_target_symbol")
        workflow.add_edge("retrieve_target_symbol", "analyze_dependencies")
        workflow.add_edge("analyze_dependencies", "analyze_test_coverage")
        workflow.add_edge("analyze_test_coverage", "detect_edge_cases")
        workflow.add_edge("detect_edge_cases", "generate_recommendations")
        workflow.add_edge("generate_recommendations", "format_report")
        workflow.add_edge("format_report", END)

        return workflow.compile()

    def _classify_analysis_type(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Classify the type of analysis to perform.

        Args:
            state: Current workflow state

        Returns:
            Updated state with analysis type
        """
        try:
            logger.info("Classifying analysis type")

            # Use explicit type if provided
            analysis_type = state.get("analysis_type")
            if not analysis_type:
                # Default to impact analysis
                analysis_type = AnalysisType.IMPACT

            state["analysis_type"] = analysis_type
            logger.info(f"Analysis type: {analysis_type}")

        except Exception as e:
            logger.error(f"Error classifying analysis type: {e}")
            state["error"] = f"Failed to classify analysis type: {str(e)}"

        return state

    def _retrieve_target_symbol(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Retrieve the target symbol to analyze.

        Args:
            state: Current workflow state

        Returns:
            Updated state with target symbol
        """
        if state.get("error"):
            return state

        try:
            logger.info("Retrieving target symbol")

            symbol_name = state.get("symbol_name")
            file_path = state.get("file_path")

            if not symbol_name and not file_path:
                state["error"] = "Either symbol_name or file_path must be provided"
                return state

            # Find the symbol
            if symbol_name:
                symbols = self.knowledge_service.find_symbol(symbol_name)
                if not symbols:
                    state["error"] = f"Symbol '{symbol_name}' not found"
                    return state
                state["target_symbol"] = symbols[0]
            elif file_path:
                # Analyze all symbols in the file
                symbols = self.knowledge_service.find_symbols_in_file(file_path)
                if not symbols:
                    state["error"] = f"No symbols found in '{file_path}'"
                    return state
                # For now, use the first symbol (could be enhanced to analyze all)
                state["target_symbol"] = symbols[0]
                state["file_symbols"] = symbols

            logger.info(f"Target symbol: {state['target_symbol'].name}")

        except Exception as e:
            logger.error(f"Error retrieving target symbol: {e}")
            state["error"] = f"Failed to retrieve target symbol: {str(e)}"

        return state

    def _analyze_dependencies(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Analyze dependencies (callers and callees).

        Args:
            state: Current workflow state

        Returns:
            Updated state with dependency analysis
        """
        if state.get("error"):
            return state

        try:
            logger.info("Analyzing dependencies")

            target_symbol = state.get("target_symbol")
            if not target_symbol:
                return state

            # Find direct callers
            direct_callers = self.knowledge_service.find_callers(target_symbol)
            state["direct_callers"] = direct_callers

            # Find indirect callers (up to depth 2)
            indirect_callers_list: List[Symbol] = []
            direct_caller_ids = {c.id for c in direct_callers}

            for caller in direct_callers[:5]:  # Limit to avoid explosion
                indirect = self.knowledge_service.find_callers(caller)
                for ind_caller in indirect:
                    # Only add if not already a direct caller and not already in list
                    if ind_caller.id not in direct_caller_ids:
                        if not any(ic.id == ind_caller.id for ic in indirect_callers_list):
                            indirect_callers_list.append(ind_caller)

            state["indirect_callers"] = indirect_callers_list

            # Find callees
            callees = self.knowledge_service.find_callees(target_symbol)
            state["callees"] = callees

            # Find affected files
            affected_files = self.knowledge_service.impacted_files(target_symbol)
            state["affected_files"] = list(affected_files)

            logger.info(
                f"Found {len(direct_callers)} direct callers, "
                f"{len(indirect_callers_list)} indirect callers, "
                f"{len(callees)} callees"
            )

        except Exception as e:
            logger.error(f"Error analyzing dependencies: {e}")
            state["error"] = f"Failed to analyze dependencies: {str(e)}"

        return state

    def _analyze_test_coverage(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Analyze test coverage for the target symbol.

        Args:
            state: Current workflow state

        Returns:
            Updated state with test coverage analysis
        """
        if state.get("error"):
            return state

        try:
            logger.info("Analyzing test coverage")

            target_symbol = state.get("target_symbol")
            if not target_symbol:
                return state

            # Find tests that call this symbol
            direct_callers = state.get("direct_callers", [])
            tests = [
                caller
                for caller in direct_callers
                if "test" in caller.file_path.lower() or "test" in caller.name.lower()
            ]

            state["affected_tests"] = tests
            logger.info(f"Found {len(tests)} tests covering the symbol")

        except Exception as e:
            logger.error(f"Error analyzing test coverage: {e}")
            state["error"] = f"Failed to analyze test coverage: {str(e)}"

        return state

    def _detect_edge_cases(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Detect potential edge cases.

        Args:
            state: Current workflow state

        Returns:
            Updated state with detected edge cases
        """
        if state.get("error"):
            return state

        try:
            logger.info("Detecting edge cases")

            target_symbol = state.get("target_symbol")
            if not target_symbol:
                return state

            edge_cases: List[EdgeCase] = []

            # Heuristic: Check if symbol has error handling
            # This is a simplified implementation - could be enhanced with AST analysis
            callees = state.get("callees", [])

            # Check for null/None handling
            has_null_check = any(
                "none" in callee.name.lower() or "null" in callee.name.lower() for callee in callees
            )

            if not has_null_check and target_symbol.signature:
                edge_cases.append(
                    EdgeCase(
                        type="null_check",
                        description="No explicit null/None checks detected",
                        location=f"{target_symbol.file_path}:{target_symbol.start_line}",
                        is_handled=False,
                        suggestion="Consider adding null/None parameter validation",
                        severity="medium",
                    )
                )

            # Check for error handling
            has_error_handling = any(
                "error" in callee.name.lower()
                or "exception" in callee.name.lower()
                or "raise" in callee.name.lower()
                for callee in callees
            )

            if not has_error_handling:
                edge_cases.append(
                    EdgeCase(
                        type="error_handling",
                        description="No explicit error handling detected",
                        location=f"{target_symbol.file_path}:{target_symbol.start_line}",
                        is_handled=False,
                        suggestion="Consider adding try/except blocks for error handling",
                        severity="low",
                    )
                )

            state["edge_cases"] = edge_cases
            logger.info(f"Detected {len(edge_cases)} potential edge cases")

        except Exception as e:
            logger.error(f"Error detecting edge cases: {e}")
            state["error"] = f"Failed to detect edge cases: {str(e)}"

        return state

    def _generate_recommendations(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Generate actionable recommendations.

        Args:
            state: Current workflow state

        Returns:
            Updated state with recommendations
        """
        if state.get("error"):
            return state

        try:
            logger.info("Generating recommendations")

            recommendations: List[str] = []
            target_symbol = state.get("target_symbol")
            direct_callers = state.get("direct_callers", [])
            affected_tests = state.get("affected_tests", [])
            edge_cases = state.get("edge_cases", [])

            # Recommendation based on callers
            if len(direct_callers) > 10:
                recommendations.append(
                    f"High impact: {len(direct_callers)} direct callers. "
                    "Consider backward compatibility or deprecation strategy."
                )
            elif len(direct_callers) == 0:
                recommendations.append(
                    "No direct callers found. This symbol may be unused or only called externally."
                )

            # Recommendation based on tests
            if len(affected_tests) == 0:
                recommendations.append(
                    "No tests found covering this symbol. Consider adding unit tests."
                )
            elif len(affected_tests) < len(direct_callers) * 0.5:
                recommendations.append(
                    f"Low test coverage: {len(affected_tests)} tests for {len(direct_callers)} callers. "
                    "Consider adding more test scenarios."
                )

            # Recommendations based on edge cases
            high_severity_cases = [ec for ec in edge_cases if ec.severity == "high"]
            if high_severity_cases:
                recommendations.append(
                    f"Address {len(high_severity_cases)} high-severity edge cases before deployment."
                )

            # Breaking change detection
            breaking_changes: List[str] = []
            if len(direct_callers) > 0:
                breaking_changes.append(
                    f"Changing signature would affect {len(direct_callers)} callers"
                )

            state["recommendations"] = recommendations
            state["breaking_changes"] = breaking_changes
            logger.info(f"Generated {len(recommendations)} recommendations")

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            state["error"] = f"Failed to generate recommendations: {str(e)}"

        return state

    def _format_report(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Format the final impact analysis report.

        Args:
            state: Current workflow state

        Returns:
            Updated state with formatted report
        """
        try:
            logger.info("Formatting report")

            target_symbol = state.get("target_symbol")
            if not target_symbol:
                state["result"] = None
                return state

            # Assess confidence
            direct_callers = state.get("direct_callers", [])
            affected_tests = state.get("affected_tests", [])

            if len(direct_callers) > 0 and len(affected_tests) > 0:
                confidence = "high"
            elif len(direct_callers) > 0 or len(affected_tests) > 0:
                confidence = "medium"
            else:
                confidence = "low"

            # Create result
            result = ImpactAnalysisResult(
                target_symbol=target_symbol,
                direct_callers=state.get("direct_callers", []),
                indirect_callers=state.get("indirect_callers", []),
                affected_files=state.get("affected_files", []),
                affected_tests=state.get("affected_tests", []),
                edge_cases=state.get("edge_cases", []),
                breaking_changes=state.get("breaking_changes", []),
                recommendations=state.get("recommendations", []),
                confidence=confidence,
            )

            state["result"] = result
            logger.info("Report formatted successfully")

        except Exception as e:
            logger.error(f"Error formatting report: {e}")
            state["error"] = f"Failed to format report: {str(e)}"

        return state

    def analyze_impact(
        self,
        symbol_name: Optional[str] = None,
        file_path: Optional[str] = None,
        analysis_type: str = AnalysisType.IMPACT,
    ) -> ImpactAnalysisResult:
        """
        Analyze the impact of changes to a symbol or file.

        Args:
            symbol_name: Name of the symbol to analyze
            file_path: Path to the file to analyze
            analysis_type: Type of analysis to perform

        Returns:
            ImpactAnalysisResult with analysis details
        """
        logger.info(f"Analyzing impact for: {symbol_name or file_path}")

        # Initialize state
        initial_state: Dict[str, Any] = {
            "symbol_name": symbol_name,
            "file_path": file_path,
            "analysis_type": analysis_type,
            "target_symbol": None,
            "direct_callers": [],
            "indirect_callers": [],
            "callees": [],
            "affected_files": [],
            "affected_tests": [],
            "edge_cases": [],
            "breaking_changes": [],
            "recommendations": [],
            "result": None,
            "error": None,
        }

        # Run the workflow
        final_state = self.graph.invoke(initial_state)

        # Handle errors
        if final_state.get("error"):
            raise Exception(final_state["error"])

        result = final_state.get("result")
        if not result:
            raise Exception("No result generated")

        return result

    def format_report_text(self, result: ImpactAnalysisResult) -> str:
        """
        Format impact analysis result as human-readable text.

        Args:
            result: Impact analysis result

        Returns:
            Formatted text report
        """
        lines = [
            f"# Impact Analysis: {result.target_symbol.name}",
            "",
            f"**Type**: {result.target_symbol.type.value}",
            f"**File**: {result.target_symbol.file_path}:{result.target_symbol.start_line}",
            f"**Confidence**: {result.confidence}",
            "",
        ]

        # Direct callers
        if result.direct_callers:
            lines.append(f"## Direct Callers ({len(result.direct_callers)})")
            lines.append("")
            for caller in result.direct_callers[:10]:
                lines.append(f"- {caller.name} in {caller.file_path}:{caller.start_line}")
            if len(result.direct_callers) > 10:
                lines.append(f"- ... and {len(result.direct_callers) - 10} more")
            lines.append("")

        # Indirect impact
        if result.indirect_callers:
            lines.append(f"## Indirect Impact ({len(result.indirect_callers)} symbols)")
            lines.append("")
            for caller in result.indirect_callers[:5]:
                lines.append(f"- {caller.name} in {caller.file_path}")
            if len(result.indirect_callers) > 5:
                lines.append(f"- ... and {len(result.indirect_callers) - 5} more")
            lines.append("")

        # Affected files
        if result.affected_files:
            lines.append(f"## Affected Files ({len(result.affected_files)})")
            lines.append("")
            for file_path in result.affected_files[:10]:
                lines.append(f"- {file_path}")
            if len(result.affected_files) > 10:
                lines.append(f"- ... and {len(result.affected_files) - 10} more")
            lines.append("")

        # Test coverage
        if result.affected_tests:
            lines.append(f"## Test Coverage ({len(result.affected_tests)} tests)")
            lines.append("")
            for test in result.affected_tests:
                lines.append(f"- {test.name} in {test.file_path}:{test.start_line}")
            lines.append("")
        else:
            lines.append("## Test Coverage")
            lines.append("")
            lines.append("⚠️  No tests found covering this symbol")
            lines.append("")

        # Edge cases
        if result.edge_cases:
            lines.append(f"## Edge Cases ({len(result.edge_cases)})")
            lines.append("")
            for edge_case in result.edge_cases:
                status = "✓" if edge_case.is_handled else "⚠️"
                lines.append(f"{status} **{edge_case.type}** ({edge_case.severity.upper()})")
                lines.append(f"   {edge_case.description}")
                lines.append(f"   Location: {edge_case.location}")
                if edge_case.suggestion:
                    lines.append(f"   Suggestion: {edge_case.suggestion}")
                lines.append("")

        # Breaking changes
        if result.breaking_changes:
            lines.append("## Breaking Changes")
            lines.append("")
            for change in result.breaking_changes:
                lines.append(f"⚠️  {change}")
            lines.append("")

        # Recommendations
        if result.recommendations:
            lines.append("## Recommendations")
            lines.append("")
            for i, rec in enumerate(result.recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        return "\n".join(lines)


# Made with Bob
