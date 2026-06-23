"""Tests for GitAgent."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from maris.agents.git_agent import GitAgent
from maris.core.models import GitChangeSet


@pytest.fixture
def temp_git_repo():
    """Create a temporary Git repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Create initial commit
        test_file = repo_path / "test.py"
        test_file.write_text("def hello():\n    print('Hello')\n")
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        yield repo_path


@pytest.fixture
def git_agent(temp_git_repo):
    """Create a GitAgent instance for testing."""
    return GitAgent(str(temp_git_repo))


class TestGitAgentInitialization:
    """Test GitAgent initialization."""

    def test_init_with_repo_path(self, temp_git_repo):
        """Test initialization with repository path."""
        agent = GitAgent(str(temp_git_repo))

        assert agent.repo_path == temp_git_repo
        assert agent.maris_dir == temp_git_repo / ".maris"
        assert agent.last_commit_file == temp_git_repo / ".maris" / "last_commit"
        assert agent.graph is not None

    def test_init_with_custom_maris_dir(self, temp_git_repo):
        """Test initialization with custom .maris directory."""
        custom_dir = temp_git_repo / "custom_maris"
        agent = GitAgent(str(temp_git_repo), str(custom_dir))

        assert agent.maris_dir == custom_dir
        assert agent.last_commit_file == custom_dir / "last_commit"


class TestGitAgentNodes:
    """Test individual workflow nodes."""

    def test_check_git_repo_valid(self, git_agent):
        """Test checking a valid Git repository."""
        state = {}
        result = git_agent._check_git_repo(state)

        assert result["is_git_repo"] is True
        assert "error" not in result

    def test_check_git_repo_invalid(self, tmp_path):
        """Test checking an invalid Git repository."""
        agent = GitAgent(str(tmp_path))
        state = {}
        result = agent._check_git_repo(state)

        assert result["is_git_repo"] is False
        assert "error" in result

    def test_get_last_commit_no_file(self, git_agent):
        """Test getting last commit when file doesn't exist."""
        state = {}
        result = git_agent._get_last_commit(state)

        assert result["last_commit"] is None

    def test_get_last_commit_with_file(self, git_agent):
        """Test getting last commit when file exists."""
        # Create .maris directory and last_commit file
        git_agent.maris_dir.mkdir(parents=True, exist_ok=True)
        git_agent.last_commit_file.write_text("abc123def456")

        state = {}
        result = git_agent._get_last_commit(state)

        assert result["last_commit"] == "abc123def456"

    def test_get_current_commit(self, git_agent):
        """Test getting current commit hash."""
        state = {}
        result = git_agent._get_current_commit(state)

        assert "current_commit" in result
        assert len(result["current_commit"]) == 40  # Git SHA-1 hash length
        assert "is_clean" in result

    def test_detect_changes_first_time(self, git_agent):
        """Test detecting changes on first indexing (no last commit)."""
        state = {"last_commit": None, "current_commit": "abc123"}
        result = git_agent._detect_changes(state)

        assert result["raw_changes"] == []

    def test_detect_changes_no_new_commits(self, git_agent):
        """Test detecting changes when no new commits."""
        commit_hash = "abc123"
        state = {"last_commit": commit_hash, "current_commit": commit_hash}
        result = git_agent._detect_changes(state)

        assert result["raw_changes"] == []

    def test_categorize_files_empty(self, git_agent):
        """Test categorizing files with no changes."""
        state = {"raw_changes": []}
        result = git_agent._categorize_files(state)

        assert result["added_files"] == []
        assert result["modified_files"] == []
        assert result["deleted_files"] == []
        assert result["renamed_files"] == []

    def test_categorize_files_added(self, git_agent):
        """Test categorizing added files."""
        state = {"raw_changes": [["A", "new_file.py"]]}
        result = git_agent._categorize_files(state)

        assert result["added_files"] == ["new_file.py"]
        assert result["modified_files"] == []
        assert result["deleted_files"] == []
        assert result["renamed_files"] == []

    def test_categorize_files_modified(self, git_agent):
        """Test categorizing modified files."""
        state = {"raw_changes": [["M", "existing_file.py"]]}
        result = git_agent._categorize_files(state)

        assert result["added_files"] == []
        assert result["modified_files"] == ["existing_file.py"]
        assert result["deleted_files"] == []
        assert result["renamed_files"] == []

    def test_categorize_files_deleted(self, git_agent):
        """Test categorizing deleted files."""
        state = {"raw_changes": [["D", "old_file.py"]]}
        result = git_agent._categorize_files(state)

        assert result["added_files"] == []
        assert result["modified_files"] == []
        assert result["deleted_files"] == ["old_file.py"]
        assert result["renamed_files"] == []

    def test_categorize_files_renamed(self, git_agent):
        """Test categorizing renamed files."""
        state = {"raw_changes": [["R100", "old_name.py", "new_name.py"]]}
        result = git_agent._categorize_files(state)

        assert result["added_files"] == []
        assert result["modified_files"] == []
        assert result["deleted_files"] == []
        assert result["renamed_files"] == [("old_name.py", "new_name.py")]

    def test_categorize_files_mixed(self, git_agent):
        """Test categorizing mixed file changes."""
        state = {
            "raw_changes": [
                ["A", "new.py"],
                ["M", "modified.py"],
                ["D", "deleted.py"],
                ["R100", "old.py", "renamed.py"],
            ]
        }
        result = git_agent._categorize_files(state)

        assert result["added_files"] == ["new.py"]
        assert result["modified_files"] == ["modified.py"]
        assert result["deleted_files"] == ["deleted.py"]
        assert result["renamed_files"] == [("old.py", "renamed.py")]


class TestGitAgentWorkflow:
    """Test full workflow execution."""

    def test_detect_changes_first_time_indexing(self, git_agent):
        """Test detecting changes on first indexing."""
        changeset = git_agent.detect_changes()

        assert changeset.last_commit is None
        assert changeset.current_commit is not None
        assert len(changeset.current_commit) == 40
        assert changeset.total_changes == 0
        assert not changeset.has_changes

    def test_detect_changes_with_new_commits(self, git_agent, temp_git_repo):
        """Test detecting changes with new commits."""
        # Save current commit as last indexed
        git_agent.save_current_commit()

        # Make changes
        new_file = temp_git_repo / "new_file.py"
        new_file.write_text("def new_function():\n    pass\n")
        subprocess.run(["git", "add", "."], cwd=temp_git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add new file"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Detect changes
        changeset = git_agent.detect_changes()

        assert changeset.last_commit is not None
        assert changeset.current_commit is not None
        assert changeset.last_commit != changeset.current_commit
        assert changeset.has_changes
        assert "new_file.py" in changeset.added_files

    def test_detect_changes_with_modifications(self, git_agent, temp_git_repo):
        """Test detecting file modifications."""
        # Save current commit
        git_agent.save_current_commit()

        # Modify existing file
        test_file = temp_git_repo / "test.py"
        test_file.write_text("def hello():\n    print('Hello, World!')\n")
        subprocess.run(["git", "add", "."], cwd=temp_git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Modify test.py"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Detect changes
        changeset = git_agent.detect_changes()

        assert changeset.has_changes
        assert "test.py" in changeset.modified_files

    def test_detect_changes_with_deletions(self, git_agent, temp_git_repo):
        """Test detecting file deletions."""
        # Save current commit
        git_agent.save_current_commit()

        # Delete file
        test_file = temp_git_repo / "test.py"
        test_file.unlink()
        subprocess.run(["git", "add", "."], cwd=temp_git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Delete test.py"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Detect changes
        changeset = git_agent.detect_changes()

        assert changeset.has_changes
        assert "test.py" in changeset.deleted_files

    def test_detect_changes_with_renames(self, git_agent, temp_git_repo):
        """Test detecting file renames."""
        # Save current commit
        git_agent.save_current_commit()

        # Rename file
        subprocess.run(
            ["git", "mv", "test.py", "renamed_test.py"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Rename test.py"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Detect changes
        changeset = git_agent.detect_changes()

        assert changeset.has_changes
        assert ("test.py", "renamed_test.py") in changeset.renamed_files


class TestGitAgentCommitManagement:
    """Test commit hash management."""

    def test_save_current_commit(self, git_agent):
        """Test saving current commit hash."""
        success = git_agent.save_current_commit()

        assert success
        assert git_agent.last_commit_file.exists()

        saved_commit = git_agent.last_commit_file.read_text().strip()
        assert len(saved_commit) == 40

    def test_get_last_commit_none(self, git_agent):
        """Test getting last commit when none saved."""
        last_commit = git_agent.get_last_commit()
        assert last_commit is None

    def test_get_last_commit_exists(self, git_agent):
        """Test getting last commit when saved."""
        git_agent.save_current_commit()
        last_commit = git_agent.get_last_commit()

        assert last_commit is not None
        assert len(last_commit) == 40

    def test_get_current_commit(self, git_agent):
        """Test getting current commit hash."""
        current_commit = git_agent.get_current_commit()

        assert current_commit is not None
        assert len(current_commit) == 40


class TestGitChangeSet:
    """Test GitChangeSet model."""

    def test_changeset_no_changes(self):
        """Test changeset with no changes."""
        changeset = GitChangeSet(
            last_commit="abc123",
            current_commit="abc123",
        )

        assert not changeset.has_changes
        assert changeset.total_changes == 0
        assert changeset.files_to_reindex == []

    def test_changeset_with_changes(self):
        """Test changeset with changes."""
        changeset = GitChangeSet(
            last_commit="abc123",
            current_commit="def456",
            added_files=["new.py"],
            modified_files=["modified.py"],
            deleted_files=["deleted.py"],
        )

        assert changeset.has_changes
        assert changeset.total_changes == 3
        assert set(changeset.files_to_reindex) == {"new.py", "modified.py"}

    def test_changeset_with_renames(self):
        """Test changeset with renamed files."""
        changeset = GitChangeSet(
            last_commit="abc123",
            current_commit="def456",
            renamed_files=[("old.py", "new.py")],
        )

        assert changeset.has_changes
        assert changeset.total_changes == 1
        assert "new.py" in changeset.files_to_reindex

    def test_changeset_first_time(self):
        """Test changeset for first time indexing."""
        changeset = GitChangeSet(
            last_commit=None,
            current_commit="abc123",
        )

        assert not changeset.has_changes
        assert changeset.total_changes == 0


class TestGitAgentErrorHandling:
    """Test error handling in GitAgent."""

    def test_detect_changes_non_git_repo(self, tmp_path):
        """Test detecting changes in non-Git repository."""
        agent = GitAgent(str(tmp_path))
        changeset = agent.detect_changes()

        # Should return empty changeset without crashing
        assert changeset.current_commit == "unknown"
        assert not changeset.has_changes

    def test_save_commit_non_git_repo(self, tmp_path):
        """Test saving commit in non-Git repository."""
        agent = GitAgent(str(tmp_path))
        success = agent.save_current_commit()

        assert not success

    def test_get_current_commit_non_git_repo(self, tmp_path):
        """Test getting current commit in non-Git repository."""
        agent = GitAgent(str(tmp_path))
        commit = agent.get_current_commit()

        assert commit is None


class TestGitAgentIntegration:
    """Integration tests for GitAgent."""

    def test_full_workflow_multiple_commits(self, git_agent, temp_git_repo):
        """Test full workflow with multiple commits."""
        # Initial indexing
        changeset1 = git_agent.detect_changes()
        assert not changeset1.has_changes
        git_agent.save_current_commit()

        # Add file
        new_file = temp_git_repo / "file1.py"
        new_file.write_text("# File 1\n")
        subprocess.run(["git", "add", "."], cwd=temp_git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add file1"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Detect changes
        changeset2 = git_agent.detect_changes()
        assert changeset2.has_changes
        assert "file1.py" in changeset2.added_files
        git_agent.save_current_commit()

        # Modify file
        new_file.write_text("# File 1 modified\n")
        subprocess.run(["git", "add", "."], cwd=temp_git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Modify file1"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Detect changes
        changeset3 = git_agent.detect_changes()
        assert changeset3.has_changes
        assert "file1.py" in changeset3.modified_files
        git_agent.save_current_commit()

        # Delete file
        new_file.unlink()
        subprocess.run(["git", "add", "."], cwd=temp_git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Delete file1"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Detect changes
        changeset4 = git_agent.detect_changes()
        assert changeset4.has_changes
        assert "file1.py" in changeset4.deleted_files


# Made with Bob
