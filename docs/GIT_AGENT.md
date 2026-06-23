# Git Agent - Incremental Indexing

The Git Agent enables smart incremental indexing by tracking repository changes using Git. Instead of re-indexing the entire repository, MARIS can detect which files have changed since the last indexing and only process those files.

## Overview

The Git Agent is a LangGraph-based agent that:
- Detects changes in a Git repository since the last indexing
- Categorizes changes (added, modified, deleted, renamed files)
- Enables efficient incremental re-indexing
- Tracks the last indexed commit hash

## Architecture

### LangGraph Workflow

The Git Agent uses a 5-node workflow:

1. **check_git_repo**: Verify the repository has a `.git` directory
2. **get_last_commit**: Read the last indexed commit from `.maris/last_commit`
3. **get_current_commit**: Get the current HEAD commit hash
4. **detect_changes**: Use `git diff` to find changed files between commits
5. **categorize_files**: Group files by change type (added/modified/deleted/renamed)

### State Management

The workflow uses explicit state management with dictionaries:

```python
state = {
    "is_git_repo": bool,
    "last_commit": Optional[str],
    "current_commit": str,
    "is_clean": bool,
    "raw_changes": List[List[str]],
    "added_files": List[str],
    "modified_files": List[str],
    "deleted_files": List[str],
    "renamed_files": List[Tuple[str, str]],
    "error": Optional[str]
}
```

### GitChangeSet Model

The `GitChangeSet` dataclass represents detected changes:

```python
@dataclass
class GitChangeSet:
    last_commit: Optional[str]  # None on first indexing
    current_commit: str
    added_files: List[str]
    modified_files: List[str]
    deleted_files: List[str]
    renamed_files: List[Tuple[str, str]]
    is_clean: bool

    @property
    def total_changes(self) -> int

    @property
    def has_changes(self) -> bool

    @property
    def files_to_reindex(self) -> List[str]
```

## Usage

### CLI Usage

#### Incremental Indexing

Index only files that have changed since the last indexing:

```bash
# Full form
maris index --incremental

# Short form
maris index -i
```

The CLI will:
1. Detect changes using Git
2. Display a summary of changes
3. Index only the changed files
4. Save the current commit hash

Example output:

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

#### First-Time Indexing

On the first indexing, no previous commit exists:

```bash
maris index --incremental

# Output:
✓ No changes detected since last indexing
Last indexed commit: N/A
Current commit: abc123def456
```

You should do a full index first:

```bash
maris index src/ --recursive
```

### Programmatic Usage

#### Using OrchestratorAgent

```python
from maris.agents.orchestrator_agent import OrchestratorAgent

# Initialize orchestrator
orchestrator = OrchestratorAgent(
    knowledge_service=knowledge_service,
    metadata_store=metadata_store,
    vector_store=vector_store,
    repo_path="/path/to/repo"
)

# Detect changes
changeset = orchestrator.detect_git_changes()

if changeset.has_changes:
    print(f"Changes detected: {changeset.total_changes} files")
    print(f"Added: {len(changeset.added_files)}")
    print(f"Modified: {len(changeset.modified_files)}")
    print(f"Deleted: {len(changeset.deleted_files)}")

    # Perform incremental indexing
    result = orchestrator.incremental_index()
    print(f"Indexed {result.files_processed} files")
else:
    print("No changes detected")
```

#### Using GitAgent Directly

```python
from maris.agents.git_agent import GitAgent

# Initialize Git agent
git_agent = GitAgent(repo_path="/path/to/repo")

# Detect changes
changeset = git_agent.detect_changes()

# Check for changes
if changeset.has_changes:
    # Get files to reindex
    files = changeset.files_to_reindex
    print(f"Files to reindex: {files}")

    # Index the files (using IndexingAgent)
    # ...

    # Save current commit after successful indexing
    git_agent.save_current_commit()
```

## How It Works

### Change Detection

The Git Agent uses `git diff --name-status` to detect changes:

```bash
git diff --name-status <last_commit> <current_commit>
```

This returns lines like:
- `A\tfile.py` - Added file
- `M\tfile.py` - Modified file
- `D\tfile.py` - Deleted file
- `R100\told.py\tnew.py` - Renamed file

### Commit Tracking

The last indexed commit is stored in `.maris/last_commit`:

```
abc123def456789...
```

This file is automatically created/updated after successful indexing.

### Integration with Indexing

The incremental indexing workflow:

1. **Detect Changes**: GitAgent detects changed files
2. **Filter Files**: Only files that need re-indexing (added + modified + renamed destinations)
3. **Index Files**: IndexingAgent processes only those files
4. **Update Commit**: Save current commit hash on success

### Error Handling

The Git Agent handles various error scenarios:

- **Not a Git repository**: Returns empty changeset with error
- **No previous commit**: Treats as first-time indexing (no changes)
- **Git command fails**: Logs error and returns empty changeset
- **Uncommitted changes**: Detects via `git status --porcelain`

## Benefits

### Performance

Incremental indexing is significantly faster than full re-indexing:

- **Full indexing**: Process all files (can take minutes for large repos)
- **Incremental indexing**: Process only changed files (typically seconds)

Example for a 1000-file repository:
- Full index: ~5 minutes
- Incremental (10 changed files): ~3 seconds

### Efficiency

Only processes what's necessary:
- Skips unchanged files
- Removes deleted files from index
- Updates modified files
- Adds new files

### Workflow Integration

Fits naturally into development workflow:

```bash
# Make changes
git add .
git commit -m "Add new feature"

# Update index
maris index --incremental

# Query updated codebase
maris ask "How does the new feature work?"
```

## Best Practices

### 1. Commit Before Indexing

Always commit your changes before incremental indexing:

```bash
git add .
git commit -m "Your changes"
maris index --incremental
```

### 2. Full Index After Major Changes

After major refactoring or branch switches, do a full index:

```bash
git checkout main
maris index src/ --recursive
```

### 3. Regular Incremental Updates

Update the index regularly during development:

```bash
# After each commit
git commit -m "..."
maris index -i
```

### 4. Check for Uncommitted Changes

The Git Agent warns about uncommitted changes:

```python
changeset = git_agent.detect_changes()
if not changeset.is_clean:
    print("Warning: Working directory has uncommitted changes")
```

## Limitations

### 1. Requires Git Repository

Incremental indexing only works in Git repositories. For non-Git projects, use regular indexing.

### 2. Commit-Based Tracking

Changes are tracked at the commit level. Uncommitted changes are not automatically detected.

### 3. Branch Switches

Switching branches may require a full re-index if the branches have diverged significantly.

### 4. Deleted Files

Deleted files are removed from the metadata store but their embeddings remain in the vector store (this is a known limitation of LanceDB).

## Testing

The Git Agent has comprehensive test coverage (83%):

```bash
# Run Git Agent tests
pytest tests/test_git_agent.py -v

# Run with coverage
pytest tests/test_git_agent.py --cov=src/maris/agents/git_agent
```

Test categories:
- Initialization tests
- Individual node tests
- Full workflow tests
- Commit management tests
- Error handling tests
- Integration tests

## Troubleshooting

### "Not a Git repository" Error

**Problem**: Git Agent can't find `.git` directory

**Solution**:
- Ensure you're in a Git repository
- Run `git init` if needed
- Check that `.git` directory exists

### "No changes detected" on First Run

**Problem**: First-time indexing shows no changes

**Solution**: This is expected. Do a full index first:

```bash
maris index src/ --recursive
```

### Incremental Index Misses Changes

**Problem**: Some changes not detected

**Solution**:
- Ensure changes are committed
- Check `git status` for uncommitted files
- Try a full re-index if needed

### Performance Issues

**Problem**: Incremental indexing still slow

**Solution**:
- Check number of changed files
- Consider indexing specific directories
- Ensure Git repository is not too large

## Future Enhancements

Potential improvements for the Git Agent:

1. **Uncommitted Change Detection**: Detect and index uncommitted changes
2. **Branch-Aware Indexing**: Handle branch switches intelligently
3. **Partial File Updates**: Update only changed symbols within files
4. **Parallel Processing**: Process multiple changed files concurrently
5. **Smart Dependency Updates**: Re-index files that depend on changed files

## Related Documentation

- [Architecture](ARCHITECTURE.md) - Overall system architecture
- [CLI Guide](CLI_GUIDE.md) - Complete CLI reference
- [Getting Started](GETTING_STARTED.md) - Quick start guide
- [Multi-Language Support](MULTI_LANGUAGE_SUPPORT.md) - Supported languages

## Made with Bob