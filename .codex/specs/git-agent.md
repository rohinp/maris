# Git Agent Specification

## Purpose
Track repository changes using Git and enable smart incremental indexing by detecting which files have changed since the last indexing operation.

## Status
✅ **Implemented** (June 2026)

## Responsibilities
1. Verify Git repository validity
2. Track last indexed commit hash
3. Detect changes between commits using `git diff`
4. Categorize changed files (added, modified, deleted, renamed)
5. Provide file lists for incremental re-indexing
6. Save current commit after successful indexing

## Architecture

### LangGraph Workflow

```
Entry Point
    ↓
check_git_repo
    ↓
get_last_commit
    ↓
get_current_commit
    ↓
detect_changes
    ↓
categorize_files
    ↓
END
```

### State Schema

```python
{
    "is_git_repo": bool,              # True if .git directory exists
    "last_commit": Optional[str],     # Last indexed commit hash (None on first run)
    "current_commit": str,            # Current HEAD commit hash
    "is_clean": bool,                 # True if no uncommitted changes
    "raw_changes": List[List[str]],   # Raw git diff output
    "added_files": List[str],         # Newly added files
    "modified_files": List[str],      # Modified files
    "deleted_files": List[str],       # Deleted files
    "renamed_files": List[Tuple[str, str]],  # (old_path, new_path) tuples
    "error": Optional[str]            # Error message if any
}
```

## Data Model

### GitChangeSet

```python
@dataclass
class GitChangeSet:
    """Represents changes detected in a Git repository."""

    last_commit: Optional[str]        # None on first indexing
    current_commit: str
    added_files: List[str] = field(default_factory=list)
    modified_files: List[str] = field(default_factory=list)
    deleted_files: List[str] = field(default_factory=list)
    renamed_files: List[Tuple[str, str]] = field(default_factory=list)
    is_clean: bool = True

    @property
    def total_changes(self) -> int:
        """Total number of changed files."""
        return (
            len(self.added_files) +
            len(self.modified_files) +
            len(self.deleted_files) +
            len(self.renamed_files)
        )

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return self.total_changes > 0

    @property
    def files_to_reindex(self) -> List[str]:
        """Files that need to be re-indexed (added + modified + renamed destinations)."""
        files = self.added_files + self.modified_files
        files.extend([new_path for _, new_path in self.renamed_files])
        return files
```

## Workflow Nodes

### 1. check_git_repo
**Purpose**: Verify the repository has a `.git` directory

**Input**: State with repo_path
**Output**: State with `is_git_repo` flag
**Error Handling**: Sets error if not a Git repository

### 2. get_last_commit
**Purpose**: Read last indexed commit from `.maris/last_commit` file

**Input**: State from previous node
**Output**: State with `last_commit` (None if file doesn't exist)
**Error Handling**: Returns None on read errors (treated as first-time indexing)

### 3. get_current_commit
**Purpose**: Get current HEAD commit hash using `git rev-parse HEAD`

**Input**: State from previous node
**Output**: State with `current_commit` and `is_clean` flag
**Error Handling**: Sets error if git command fails

### 4. detect_changes
**Purpose**: Use `git diff --name-status` to find changed files

**Input**: State with last_commit and current_commit
**Output**: State with `raw_changes` list
**Logic**:
- If no last_commit: return empty changes (first time)
- If last_commit == current_commit: return empty changes (no new commits)
- Otherwise: run `git diff --name-status <last> <current>`

**Error Handling**: Returns empty changes on git command failure

### 5. categorize_files
**Purpose**: Group files by change type

**Input**: State with raw_changes
**Output**: State with categorized file lists
**Categorization**:
- `A` → added_files
- `M` → modified_files
- `D` → deleted_files
- `R*` → renamed_files (e.g., R100, R095)

**Error Handling**: Returns empty lists on errors

## Git Commands Used

### Check Repository
```bash
# Verify .git directory exists
test -d .git
```

### Get Current Commit
```bash
git rev-parse HEAD
```

### Check Working Directory Status
```bash
git status --porcelain
```

### Detect Changes
```bash
git diff --name-status <last_commit> <current_commit>
```

**Output Format**:
```
A       new_file.py
M       modified_file.py
D       deleted_file.py
R100    old_name.py     new_name.py
```

## Commit Tracking

### Storage Location
`.maris/last_commit` file in repository root

### Format
Single line containing the commit hash:
```
abc123def456789...
```

### Update Strategy
- Save after successful full indexing
- Save after successful incremental indexing
- Never save on indexing errors

## Integration with OrchestratorAgent

### New Task Types
```python
class TaskType(Enum):
    GIT_CHANGES = "git_changes"           # Detect changes
    INCREMENTAL_INDEX = "incremental_index"  # Index changed files
```

### Workflow

#### Detect Changes
```python
orchestrator.detect_git_changes() -> GitChangeSet
```

#### Incremental Index
```python
orchestrator.incremental_index() -> IndexingResult
```

**Steps**:
1. Call GitAgent.detect_changes()
2. If has_changes:
   - Get files_to_reindex
   - Call IndexingAgent.index_files(files)
   - If successful: GitAgent.save_current_commit()
3. Return IndexingResult

## CLI Integration

### Command
```bash
maris index --incremental
maris index -i
```

### Behavior
1. Detect changes using GitAgent
2. Display change summary:
   - Added: X files
   - Modified: Y files
   - Deleted: Z files
   - Renamed: W files
3. Perform incremental indexing
4. Display statistics

### Output Example
```
Detecting changes since last indexing...

Changes detected:
  Added: 3 files
  Modified: 5 files
  Deleted: 1 files

Performing incremental indexing of 9 changed files...

✓ Incremental indexing complete!
  Files processed: 8
  Symbols extracted: 127
  Embeddings generated: 127
  Duration: 12.34s
```

## Performance Characteristics

### Time Complexity
- Git operations: O(changed files)
- Change detection: O(changed files)
- Categorization: O(changed files)

### Space Complexity
- State storage: O(changed files)
- Commit tracking: O(1) - single file

### Performance Comparison

**Full Indexing** (1000 files):
- Time: ~5 minutes
- Files processed: 1000
- Symbols: ~15,000

**Incremental Indexing** (10 changed files):
- Time: ~3 seconds
- Files processed: 10
- Symbols: ~150

**Speedup**: ~100x for typical changes

## Error Handling

### Not a Git Repository
**Error**: `.git` directory not found
**Handling**: Return empty changeset with error message
**User Action**: Initialize Git or use full indexing

### Git Command Failure
**Error**: `git` command returns non-zero exit code
**Handling**: Log error, return empty changeset
**User Action**: Check Git installation and repository state

### Uncommitted Changes
**Warning**: Working directory has uncommitted changes
**Handling**: Set `is_clean = False`, continue normally
**User Action**: Commit changes before incremental indexing

### Missing Last Commit
**Behavior**: Treated as first-time indexing
**Handling**: Return empty changeset (no changes to detect)
**User Action**: Perform full indexing first

## Testing Strategy

### Unit Tests
- ✅ Node-level testing (5 nodes)
- ✅ State transitions
- ✅ Error conditions
- ✅ Edge cases (empty repo, no commits, etc.)

### Integration Tests
- ✅ Full workflow execution
- ✅ Multiple commit scenarios
- ✅ File operations (add, modify, delete, rename)
- ✅ Commit tracking

### Test Coverage
- **Target**: >80%
- **Achieved**: 83%
- **Total Tests**: 32 (all passing)

## API Interface

### GitAgent Class

```python
class GitAgent:
    def __init__(self, repo_path: str, maris_dir: Optional[str] = None):
        """Initialize Git agent."""

    def detect_changes(self) -> GitChangeSet:
        """Detect changes since last indexing."""

    def save_current_commit(self) -> bool:
        """Save current commit hash."""

    def get_last_commit(self) -> Optional[str]:
        """Get last indexed commit."""

    def get_current_commit(self) -> Optional[str]:
        """Get current HEAD commit."""
```

## Limitations

### Current
1. **Requires Git Repository**: Only works in Git repositories
2. **Commit-Based**: Changes must be committed to be detected
3. **Branch Switches**: May require full re-index after branch switches
4. **Deleted Files**: Embeddings remain in vector store (LanceDB limitation)

### Future Enhancements
1. **Uncommitted Change Detection**: Detect and index uncommitted changes
2. **Branch-Aware Indexing**: Handle branch switches intelligently
3. **Partial File Updates**: Update only changed symbols within files
4. **Parallel Processing**: Process multiple changed files concurrently
5. **Smart Dependency Updates**: Re-index files that depend on changed files

## Acceptance Criteria

- [x] Detect Git repository validity
- [x] Track last indexed commit
- [x] Detect changes using git diff
- [x] Categorize files by change type
- [x] Provide files for re-indexing
- [x] Save commit after successful indexing
- [x] Handle errors gracefully
- [x] Integrate with OrchestratorAgent
- [x] Support CLI usage
- [x] Pass all tests (32/32)
- [x] Achieve >80% coverage (83%)

**Status**: ✅ All criteria met (June 2026)

## Documentation

### User Documentation
- [Git Agent Guide](../../docs/GIT_AGENT.md) - Complete user guide
- [Implementation Summary](../../docs/GIT_AGENT_IMPLEMENTATION.md) - Technical details

### Code Documentation
- Comprehensive docstrings in `src/maris/agents/git_agent.py`
- Test documentation in `tests/test_git_agent.py`

## Related Specifications
- [Indexing Agent](./indexing-agent.md) - Uses Git Agent for incremental updates
- [Repository Knowledge Layer](./repository-knowledge-layer.md) - Stores indexed data
- [Multi-Language Parser Support](./multi-language-parser-support.md) - Parses changed files

## Made with Bob