# Impact Analysis Agent Specification

Last updated: 2026-06-24

## Status
✅ **Implemented** (June 2026)

## Purpose
Analyze the impact of code changes, identify edge cases, suggest test scenarios, and help developers understand what will be affected by modifications.

## Motivation
When implementing new features or modifying existing code, developers need to understand:
- What other code depends on this?
- What tests cover this functionality?
- What edge cases should be handled?
- What might break if this changes?
- What similar patterns exist in the codebase?

The QA Agent can answer some of these questions, but the specialized Impact Analysis Agent provides more structured, actionable insights through explicit CLI commands and orchestrator routing.

## Responsibilities

### 1. Dependency Analysis
- Find all symbols that depend on a given symbol
- Traverse call graphs (callers and callees)
- Identify import relationships
- Map inheritance hierarchies

### 2. Test Discovery
- Find tests that cover a symbol
- Identify test gaps (untested code paths)
- Suggest test scenarios based on code structure

### 3. Edge Case Detection
- Analyze code paths and branches
- Identify error handling paths
- Detect boundary conditions
- Find null/undefined checks
- Identify exception handling

### 4. Breaking Change Detection
- Identify public API changes
- Find symbols that would be affected by signature changes
- Detect interface contract changes

### 5. Pattern Analysis
- Find similar implementations in the codebase
- Identify common patterns and anti-patterns
- Suggest refactoring opportunities

## Architecture

### LangGraph Workflow

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

### State Schema

```python
{
    "analysis_type": str,           # "impact", "edge_cases", "tests", "breaking_changes"
    "target_symbol": Symbol,        # Symbol to analyze
    "target_file": Optional[str],   # File to analyze (if no specific symbol)
    "callers": List[Symbol],        # Symbols that call the target
    "callees": List[Symbol],        # Symbols called by the target
    "dependencies": List[Symbol],   # All dependencies
    "tests": List[Symbol],          # Tests covering the target
    "edge_cases": List[EdgeCase],   # Detected edge cases
    "recommendations": List[str],   # Actionable recommendations
    "error": Optional[str]
}
```

## Data Models

### EdgeCase

```python
@dataclass
class EdgeCase:
    """Represents a detected edge case."""

    type: str                       # "null_check", "boundary", "error_path", etc.
    description: str                # Human-readable description
    location: str                   # File:line where detected
    is_handled: bool                # Whether it's currently handled
    suggestion: Optional[str]       # How to handle it
    severity: str                   # "high", "medium", "low"
```

### ImpactAnalysisResult

```python
@dataclass
class ImpactAnalysisResult:
    """Result of impact analysis."""

    target_symbol: Symbol
    direct_callers: List[Symbol]
    indirect_callers: List[Symbol]
    affected_files: List[str]
    affected_tests: List[Symbol]
    edge_cases: List[EdgeCase]
    breaking_changes: List[str]
    recommendations: List[str]
    confidence: str                 # "high", "medium", "low"
```

## Analysis Types

### 1. Impact Analysis
**Question**: "What will be affected if I change X?"

**Analysis**:
- Find all direct callers
- Find all indirect callers (transitive)
- Identify affected files
- Find related tests
- Detect potential breaking changes

**Output**:
```
Impact Analysis: GitAgent.detect_changes

Direct Callers (2):
  - OrchestratorAgent._execute_task (line 289)
  - GitAgent.detect_changes (public API)

Indirect Impact (5 files):
  - src/maris/cli/main.py
  - tests/test_git_agent.py (17 tests)
  - tests/test_orchestrator_agent.py (3 tests)

Breaking Changes:
  ⚠ Changing return type would break 2 callers
  ⚠ Removing parameters would break CLI integration

Recommendations:
  - Add deprecation warning before breaking changes
  - Update tests in test_git_agent.py
  - Consider backward compatibility wrapper
```

### 2. Edge Case Detection
**Question**: "What edge cases should I handle?"

**Analysis**:
- Analyze code paths and branches
- Identify error conditions
- Find boundary conditions
- Detect missing null checks
- Identify exception handling gaps

**Output**:
```
Edge Case Analysis: GitAgent.detect_changes

Handled Edge Cases (3):
  ✓ Non-Git repository (line 91)
  ✓ Missing last commit (line 120)
  ✓ Git command failure (line 226)

Unhandled Edge Cases (3):
  ⚠ Detached HEAD state (HIGH)
    Location: line 164
    Suggestion: Check for detached HEAD before diff

  ⚠ Merge conflicts (MEDIUM)
    Location: line 203
    Suggestion: Detect merge conflicts in working tree

  ⚠ Submodule changes (LOW)
    Location: line 203
    Suggestion: Handle submodule updates separately

Recommendations:
  - Add test for detached HEAD scenario
  - Document merge conflict behavior
  - Consider submodule support in future
```

### 3. Test Coverage Analysis
**Question**: "What tests cover this code?"

**Analysis**:
- Find tests that call the symbol
- Identify test gaps
- Suggest missing test scenarios

**Output**:
```
Test Coverage: GitAgent.detect_changes

Covered Scenarios (8):
  ✓ First time indexing (test_detect_changes_first_time_indexing)
  ✓ New commits (test_detect_changes_with_new_commits)
  ✓ Modifications (test_detect_changes_with_modifications)
  ✓ Deletions (test_detect_changes_with_deletions)
  ✓ Renames (test_detect_changes_with_renames)
  ✓ No changes (test_detect_changes_no_new_commits)
  ✓ Non-Git repo (test_detect_changes_non_git_repo)
  ✓ Multiple commits (test_full_workflow_multiple_commits)

Missing Scenarios (3):
  ⚠ Detached HEAD state
  ⚠ Merge conflicts
  ⚠ Large number of changes (>1000 files)

Recommendations:
  - Add test for detached HEAD
  - Add test for merge conflicts
  - Add performance test for large changesets
```

### 4. Breaking Change Detection
**Question**: "Will this change break anything?"

**Analysis**:
- Compare old and new signatures
- Find callers that would break
- Identify interface contract changes

**Output**:
```
Breaking Change Analysis: GitAgent.detect_changes

Proposed Change:
  - Old: detect_changes() -> GitChangeSet
  + New: detect_changes(include_untracked: bool = False) -> GitChangeSet

Impact:
  ✓ Backward compatible (new parameter has default)
  ✓ Return type unchanged
  ✓ No breaking changes detected

Affected Callers (2):
  - OrchestratorAgent._execute_task (compatible)
  - CLI integration (compatible)

Recommendations:
  - Safe to implement
  - Update documentation
  - Add tests for new parameter
```

## Integration with OrchestratorAgent

### New Task Type

```python
class TaskType(Enum):
    IMPACT_ANALYSIS = "impact_analysis"
```

### Classification Logic

The orchestrator should route to Impact Analysis Agent when detecting keywords:

```python
# Impact analysis keywords
impact_keywords = [
    "impact", "affect", "break", "change",
    "edge case", "test", "coverage",
    "depend", "caller", "callee",
    "what if", "should i consider"
]

# Example questions that should route to Impact Analysis Agent:
# - "What will be affected if I change GitAgent?"
# - "What edge cases should I handle for incremental indexing?"
# - "What tests cover the detect_changes method?"
# - "Will changing this function break anything?"
# - "What should I consider when implementing TypeScript support?"
```

### CLI Integration

```bash
# Explicit impact analysis
maris impact analyze --symbol "GitAgent.detect_changes"
maris impact edge-cases --file "src/maris/agents/git_agent.py"
maris impact tests --symbol "IndexingAgent.index_files"
maris impact breaking-changes --symbol "QAAgent.answer_question"

# Implicit via ask (orchestrator decides)
maris ask "What will be affected if I change GitAgent.detect_changes?"
maris ask "What edge cases should I handle for incremental indexing?"
maris ask "What tests cover the detect_changes method?"
```

## Implementation Phases

### Phase 1: Basic Dependency Analysis
- [x] Implement call graph traversal
- [x] Find direct callers and callees
- [x] Identify affected files

### Phase 2: Test Discovery
- [x] Find tests that cover symbols
- [x] Identify test gaps
- [x] Suggest test scenarios

### Phase 3: Edge Case Detection
- [x] Analyze code paths
- [x] Detect error conditions
- [x] Identify boundary conditions

### Phase 4: Breaking Change Detection
- [x] Compare signatures
- [x] Detect interface changes
- [x] Identify breaking changes

### Phase 5: Pattern Analysis
- [ ] Find similar implementations
- [ ] Identify common patterns
- [ ] Suggest refactoring opportunities

## Technical Approach

### Static Analysis
- Use AST traversal for code path analysis
- Leverage existing symbol and dependency data
- Build call graphs from stored relationships

### Heuristics
- Pattern matching for common edge cases
- Naming conventions for test discovery
- Signature comparison for breaking changes

### LLM Reasoning
- Use LLM to generate recommendations
- Explain detected issues
- Suggest solutions

## Performance Considerations

### Caching
- Cache call graphs
- Cache test coverage maps
- Invalidate on file changes

### Incremental Analysis
- Only analyze changed symbols
- Reuse previous analysis results
- Update incrementally with Git changes

## Testing Strategy

### Unit Tests
- Test each analysis type independently
- Test edge case detection algorithms
- Test call graph traversal

### Integration Tests
- Test full analysis workflows
- Test orchestrator routing
- Test CLI integration

### Test Data
- Use MARIS codebase as test data
- Create synthetic examples for edge cases
- Test with various code patterns

## Acceptance Criteria

- [x] Implement basic dependency analysis
- [x] Implement test discovery
- [x] Implement edge case detection
- [x] Implement breaking-change analysis
- [x] Integrate with OrchestratorAgent
- [x] Add CLI commands
- [x] Create tests for core behavior
- [x] Document usage and examples
- [ ] Achieve and publish >80% test coverage for this agent
- [ ] Implement advanced pattern analysis

## Future Enhancements

### Advanced Analysis
- Data flow analysis
- Taint analysis for security
- Performance impact prediction
- Memory usage analysis

### Machine Learning
- Learn from historical bugs
- Predict likely failure points
- Suggest test priorities

### Visualization
- Generate dependency graphs
- Visualize call hierarchies
- Show test coverage maps

## Related Specifications
- [QA Agent](./qa-agent.md) - Complementary question answering
- [Repository Knowledge Layer](./repository-knowledge-layer.md) - Data source
- [Indexing Agent](./indexing-agent.md) - Symbol and dependency data

## Remaining Work

- Advanced pattern analysis
- More real-repository regression scenarios
- Published coverage measurement for the agent-specific test suite
- Optional dependency graph visualization

## Made with Bob
