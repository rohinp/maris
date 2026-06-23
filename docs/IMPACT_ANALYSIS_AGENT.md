# Impact Analysis Agent Implementation

## Overview

The Impact Analysis Agent is a specialized agent in MARIS that analyzes the impact of code changes, identifies edge cases, suggests test scenarios, and helps developers understand what will be affected by modifications.

## Status

✅ **Implemented** - June 2026

## Architecture

### LangGraph Workflow

The agent uses a LangGraph-based workflow with the following nodes:

```
Entry Point
    ↓
classify_analysis_type
    ↓
retrieve_target_symbol
    ↓
analyze_dependencies
    ↓
analyze_test_coverage
    ↓
detect_edge_cases
    ↓
generate_recommendations
    ↓
format_report
    ↓
END
```

### Core Components

1. **ImpactAnalysisAgent** (`src/maris/agents/impact_analysis_agent.py`)
   - Main agent implementation
   - LangGraph workflow orchestration
   - Analysis logic

2. **Data Models** (`src/maris/core/models.py`)
   - `EdgeCase`: Represents detected edge cases
   - `ImpactAnalysisResult`: Complete analysis result

3. **Integration** (`src/maris/agents/orchestrator_agent.py`)
   - New `IMPACT_ANALYSIS` task type
   - Keyword-based routing
   - Orchestrator integration

## Features

### 1. Dependency Analysis

Finds all symbols that depend on a given symbol:

- **Direct callers**: Symbols that directly call the target
- **Indirect callers**: Symbols that indirectly depend on the target (up to depth 2)
- **Callees**: Symbols called by the target
- **Affected files**: All files that may be impacted

### 2. Test Coverage Analysis

Identifies test coverage for symbols:

- Finds tests that cover the target symbol
- Identifies test gaps
- Suggests missing test scenarios

### 3. Edge Case Detection

Detects potential edge cases using heuristics:

- **Null/None checks**: Missing null parameter validation
- **Error handling**: Missing try/except blocks
- **Boundary conditions**: Potential boundary issues

Each edge case includes:
- Type (null_check, error_handling, boundary, etc.)
- Description
- Location (file:line)
- Whether it's currently handled
- Suggestion for handling
- Severity (high, medium, low)

### 4. Breaking Change Detection

Identifies potential breaking changes:

- Signature changes that would affect callers
- Interface contract changes
- Public API modifications

### 5. Recommendations

Generates actionable recommendations:

- Backward compatibility strategies
- Test coverage improvements
- Edge case handling suggestions
- Deprecation warnings

## Usage

### Programmatic API

```python
from maris.agents.impact_analysis_agent import ImpactAnalysisAgent
from maris.knowledge.service import RepositoryKnowledgeService

# Initialize agent
knowledge_service = RepositoryKnowledgeService(...)
agent = ImpactAnalysisAgent(knowledge_service=knowledge_service)

# Analyze impact by symbol name
result = agent.analyze_impact(symbol_name="MyClass.my_method")

# Analyze impact by file path
result = agent.analyze_impact(file_path="src/my_module.py")

# Format as human-readable report
report = agent.format_report_text(result)
print(report)
```

### Via Orchestrator

```python
from maris.agents.orchestrator_agent import OrchestratorAgent

orchestrator = OrchestratorAgent(...)

# Explicit impact analysis
result = orchestrator.analyze_impact(symbol_name="MyClass.my_method")

# Natural language (auto-routed)
result = orchestrator.execute("What will be affected if I change MyClass?")
```

### Keyword-Based Routing

The orchestrator automatically routes to the Impact Analysis Agent when detecting keywords:

- `impact`, `affect`, `break`, `breaking change`
- `edge case`, `test coverage`
- `caller`, `callee`, `depend`
- `what if`, `should i consider`

## Example Output

```
# Impact Analysis: GitAgent.detect_changes

**Type**: method
**File**: src/maris/agents/git_agent.py:120
**Confidence**: high

## Direct Callers (2)

- OrchestratorAgent._execute_task in src/maris/agents/orchestrator_agent.py:289
- incremental_index in src/maris/cli/main.py:156

## Indirect Impact (5 symbols)

- main in src/maris/cli/main.py
- handle_index_command in src/maris/cli/main.py
- ... and 3 more

## Affected Files (3)

- src/maris/agents/git_agent.py
- src/maris/agents/orchestrator_agent.py
- src/maris/cli/main.py

## Test Coverage (17 tests)

- test_detect_changes_first_time_indexing in tests/test_git_agent.py:45
- test_detect_changes_with_new_commits in tests/test_git_agent.py:78
- ... and 15 more

## Edge Cases (2)

⚠️ **null_check** (MEDIUM)
   No explicit null/None checks detected
   Location: src/maris/agents/git_agent.py:120
   Suggestion: Consider adding null/None parameter validation

⚠️ **error_handling** (LOW)
   No explicit error handling detected
   Location: src/maris/agents/git_agent.py:120
   Suggestion: Consider adding try/except blocks for error handling

## Breaking Changes

⚠️  Changing return type would affect 2 callers
⚠️  Removing parameters would break CLI integration

## Recommendations

1. High impact: 2 direct callers. Consider backward compatibility or deprecation strategy.
2. Good test coverage: 17 tests for 2 callers.
3. Address 2 edge cases before deployment.
```

## Analysis Types

The agent supports different analysis types (extensible):

- `impact`: Full impact analysis (default)
- `edge_cases`: Focus on edge case detection
- `tests`: Focus on test coverage
- `breaking_changes`: Focus on breaking change detection

## Implementation Details

### State Schema

```python
{
    "analysis_type": str,           # Type of analysis
    "symbol_name": Optional[str],   # Symbol to analyze
    "file_path": Optional[str],     # File to analyze
    "target_symbol": Symbol,        # Retrieved symbol
    "direct_callers": List[Symbol], # Direct callers
    "indirect_callers": List[Symbol], # Indirect callers
    "callees": List[Symbol],        # Callees
    "affected_files": List[str],    # Affected files
    "affected_tests": List[Symbol], # Tests covering symbol
    "edge_cases": List[EdgeCase],   # Detected edge cases
    "breaking_changes": List[str],  # Breaking changes
    "recommendations": List[str],   # Recommendations
    "result": ImpactAnalysisResult, # Final result
    "error": Optional[str]          # Error if any
}
```

### Confidence Assessment

Confidence is assessed based on available data:

- **High**: Has both direct callers and test coverage
- **Medium**: Has either direct callers or test coverage
- **Low**: No callers or tests found

### Edge Case Detection Heuristics

Current heuristics (can be extended):

1. **Null checks**: Looks for null/None-related callees
2. **Error handling**: Looks for error/exception-related callees
3. **Boundary conditions**: (Future enhancement)
4. **Concurrency issues**: (Future enhancement)

## Testing

Comprehensive test suite in `tests/test_impact_analysis_agent.py`:

- ✅ Agent initialization
- ✅ Impact analysis with symbol name
- ✅ Impact analysis with callers
- ✅ Test coverage identification
- ✅ Edge case detection
- ✅ Recommendation generation
- ✅ Error handling (symbol not found)
- ✅ Report text formatting
- ✅ Impact analysis with file path
- ✅ Confidence assessment

**Test Coverage**: 77% (263 statements, 61 missed)

## Integration Points

### OrchestratorAgent

- New `TaskType.IMPACT_ANALYSIS` enum value
- Keyword-based classification in `_classify_task`
- Agent routing in `_route_to_agent`
- Execution logic in `_execute_task`
- Convenience method `analyze_impact()`

### Repository Knowledge Service

Uses the following methods:

- `find_symbol()`: Find symbols by name
- `find_symbols_in_file()`: Get symbols in a file
- `find_callers()`: Find direct callers
- `find_callees()`: Find callees
- `impacted_files()`: Get affected files

## Future Enhancements

### Phase 1 (Current)
- ✅ Basic dependency analysis
- ✅ Test discovery
- ✅ Edge case detection (heuristics)
- ✅ Recommendation generation

### Phase 2 (Planned)
- [ ] Advanced edge case detection (AST analysis)
- [ ] Breaking change detection (signature comparison)
- [ ] Pattern analysis (similar implementations)
- [ ] CLI commands (`maris impact analyze`)

### Phase 3 (Future)
- [ ] Data flow analysis
- [ ] Taint analysis for security
- [ ] Performance impact prediction
- [ ] Memory usage analysis
- [ ] ML-based failure prediction
- [ ] Dependency graph visualization

## Performance Considerations

### Optimizations

1. **Caller traversal**: Limited to depth 2 to avoid explosion
2. **Indirect callers**: Limited to 5 direct callers for traversal
3. **Result caching**: Can be added for repeated analyses

### Scalability

- Works well for typical codebases (< 100K LOC)
- May need optimization for very large codebases
- Consider incremental analysis for large projects

## Related Documentation

- [Repository Knowledge Layer](./repository-knowledge-layer.md)
- [QA Agent](./qa-agent.md)
- [Indexing Agent](./indexing-agent.md)
- [Git Agent](./GIT_AGENT.md)

## Made with Bob