"""Git Agent - LangGraph-based implementation for tracking repository changes."""

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph, END

from maris.core.models import GitChangeSet

logger = logging.getLogger(__name__)


class GitAgent:
    """
    LangGraph-based Git Agent for tracking repository changes.

    Uses a workflow with explicit state management:
    1. check_git_repo: Verify repository has .git directory
    2. get_last_commit: Read last indexed commit from .maris/last_commit
    3. get_current_commit: Get current HEAD commit hash
    4. detect_changes: Use git diff to find changed files
    5. categorize_files: Group files by change type (added/modified/deleted/renamed)

    Responsible for:
    - Detecting which files have changed since last indexing
    - Identifying added, modified, deleted, and renamed files
    - Providing file lists for incremental re-indexing
    """

    def __init__(self, repo_path: str, maris_dir: Optional[str] = None):
        """
        Initialize the Git agent.

        Args:
            repo_path: Path to the Git repository root
            maris_dir: Path to .maris directory (defaults to repo_path/.maris)
        """
        self.repo_path = Path(repo_path)
        self.maris_dir = Path(maris_dir) if maris_dir else self.repo_path / ".maris"
        self.last_commit_file = self.maris_dir / "last_commit"

        # Build the LangGraph workflow
        self.graph = self._build_graph()

        logger.info(f"Initialized GitAgent for repo: {repo_path}")

    def _build_graph(self) -> Any:
        """Build the LangGraph workflow for Git operations."""
        # Use dict directly as state schema (LangGraph supports this)
        workflow = StateGraph(dict)  # type: ignore

        # Add nodes
        workflow.add_node("check_git_repo", self._check_git_repo)
        workflow.add_node("get_last_commit", self._get_last_commit)
        workflow.add_node("get_current_commit", self._get_current_commit)
        workflow.add_node("detect_changes", self._detect_changes)
        workflow.add_node("categorize_files", self._categorize_files)

        # Define edges
        workflow.set_entry_point("check_git_repo")
        workflow.add_edge("check_git_repo", "get_last_commit")
        workflow.add_edge("get_last_commit", "get_current_commit")
        workflow.add_edge("get_current_commit", "detect_changes")
        workflow.add_edge("detect_changes", "categorize_files")
        workflow.add_edge("categorize_files", END)

        return workflow.compile()

    def _check_git_repo(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Check if the repository is a valid Git repository.

        Args:
            state: Current workflow state

        Returns:
            Updated state with is_git_repo flag
        """
        try:
            git_dir = self.repo_path / ".git"
            state["is_git_repo"] = git_dir.exists() and git_dir.is_dir()

            if not state["is_git_repo"]:
                state["error"] = f"Not a Git repository: {self.repo_path}"
                logger.warning(f"Not a Git repository: {self.repo_path}")
            else:
                logger.debug(f"Verified Git repository: {self.repo_path}")

        except Exception as e:
            logger.error(f"Error checking Git repository: {e}")
            state["error"] = f"Failed to check Git repository: {str(e)}"
            state["is_git_repo"] = False

        return state

    def _get_last_commit(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Get the last indexed commit hash from .maris/last_commit file.

        Args:
            state: Current workflow state

        Returns:
            Updated state with last_commit hash (None if first time)
        """
        if state.get("error"):
            return state

        try:
            if self.last_commit_file.exists():
                last_commit = self.last_commit_file.read_text().strip()
                state["last_commit"] = last_commit if last_commit else None
                logger.info(f"Last indexed commit: {last_commit}")
            else:
                state["last_commit"] = None
                logger.info("No previous commit found - first time indexing")

        except Exception as e:
            logger.error(f"Error reading last commit: {e}")
            state["last_commit"] = None

        return state

    def _get_current_commit(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Get the current HEAD commit hash.

        Args:
            state: Current workflow state

        Returns:
            Updated state with current_commit hash
        """
        if state.get("error"):
            return state

        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            current_commit = result.stdout.strip()
            state["current_commit"] = current_commit
            logger.info(f"Current commit: {current_commit}")

            # Check if working directory is clean
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            state["is_clean"] = len(status_result.stdout.strip()) == 0

            if not state["is_clean"]:
                logger.warning("Working directory has uncommitted changes")

        except subprocess.CalledProcessError as e:
            logger.error(f"Error getting current commit: {e}")
            state["error"] = f"Failed to get current commit: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error getting current commit: {e}")
            state["error"] = f"Failed to get current commit: {str(e)}"

        return state

    def _detect_changes(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Detect changed files using git diff.

        Args:
            state: Current workflow state

        Returns:
            Updated state with raw_changes list
        """
        if state.get("error"):
            return state

        try:
            last_commit = state.get("last_commit")
            current_commit = state.get("current_commit")

            if not last_commit:
                # First time indexing - no changes to detect
                state["raw_changes"] = []
                logger.info("First time indexing - no previous changes to detect")
                return state

            if last_commit == current_commit:
                # No new commits
                state["raw_changes"] = []
                logger.info("No new commits since last indexing")
                return state

            # Get diff between last and current commit
            # Ensure commit hashes are strings
            last_commit_str = str(last_commit) if last_commit else ""
            current_commit_str = str(current_commit) if current_commit else ""

            result = subprocess.run(
                ["git", "diff", "--name-status", last_commit_str, current_commit_str],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )

            # Parse output: each line is "STATUS\tFILE" or "STATUS\tOLD\tNEW" for renames
            raw_changes = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        raw_changes.append(parts)

            state["raw_changes"] = raw_changes
            logger.info(f"Detected {len(raw_changes)} file changes")

        except subprocess.CalledProcessError as e:
            logger.error(f"Error detecting changes: {e}")
            state["error"] = f"Failed to detect changes: {str(e)}"
            state["raw_changes"] = []
        except Exception as e:
            logger.error(f"Unexpected error detecting changes: {e}")
            state["error"] = f"Failed to detect changes: {str(e)}"
            state["raw_changes"] = []

        return state

    def _categorize_files(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Categorize changed files by type (added/modified/deleted/renamed).

        Args:
            state: Current workflow state

        Returns:
            Updated state with categorized file lists
        """
        if state.get("error"):
            return state

        try:
            raw_changes = state.get("raw_changes", [])

            added_files = []
            modified_files = []
            deleted_files = []
            renamed_files = []

            for change in raw_changes:
                status = change[0]

                if status == "A":
                    # Added file
                    added_files.append(change[1])
                elif status == "M":
                    # Modified file
                    modified_files.append(change[1])
                elif status == "D":
                    # Deleted file
                    deleted_files.append(change[1])
                elif status.startswith("R"):
                    # Renamed file (R100, R095, etc.)
                    if len(change) >= 3:
                        old_path = change[1]
                        new_path = change[2]
                        renamed_files.append((old_path, new_path))
                # Ignore other statuses (C for copied, T for type change, etc.)

            state["added_files"] = added_files
            state["modified_files"] = modified_files
            state["deleted_files"] = deleted_files
            state["renamed_files"] = renamed_files

            total = len(added_files) + len(modified_files) + len(deleted_files) + len(renamed_files)
            logger.info(
                f"Categorized changes: {len(added_files)} added, "
                f"{len(modified_files)} modified, {len(deleted_files)} deleted, "
                f"{len(renamed_files)} renamed (total: {total})"
            )

        except Exception as e:
            logger.error(f"Error categorizing files: {e}")
            state["error"] = f"Failed to categorize files: {str(e)}"
            state["added_files"] = []
            state["modified_files"] = []
            state["deleted_files"] = []
            state["renamed_files"] = []

        return state

    def detect_changes(self) -> GitChangeSet:
        """
        Detect changes in the repository since last indexing.

        Returns:
            GitChangeSet with all detected changes
        """
        logger.info("Detecting repository changes")

        # Initialize state
        initial_state: Dict[str, Any] = {}

        # Run the workflow
        final_state = self.graph.invoke(initial_state)

        # Build GitChangeSet from final state
        if final_state.get("error"):
            logger.error(f"Error detecting changes: {final_state['error']}")
            # Return empty changeset on error
            return GitChangeSet(
                last_commit=final_state.get("last_commit"),
                current_commit=final_state.get("current_commit", "unknown"),
                is_clean=final_state.get("is_clean", False),
            )

        changeset = GitChangeSet(
            last_commit=final_state.get("last_commit"),
            current_commit=final_state.get("current_commit", "unknown"),
            added_files=final_state.get("added_files", []),
            modified_files=final_state.get("modified_files", []),
            deleted_files=final_state.get("deleted_files", []),
            renamed_files=final_state.get("renamed_files", []),
            is_clean=final_state.get("is_clean", False),
        )

        logger.info(f"Change detection complete: {changeset.total_changes} files changed")
        return changeset

    def save_current_commit(self) -> bool:
        """
        Save the current commit hash to .maris/last_commit file.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current commit
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            current_commit = result.stdout.strip()

            # Ensure .maris directory exists
            self.maris_dir.mkdir(parents=True, exist_ok=True)

            # Write commit hash
            self.last_commit_file.write_text(current_commit)
            logger.info(f"Saved current commit: {current_commit}")
            return True

        except Exception as e:
            logger.error(f"Error saving current commit: {e}")
            return False

    def get_last_commit(self) -> Optional[str]:
        """
        Get the last indexed commit hash.

        Returns:
            Commit hash or None if not found
        """
        try:
            if self.last_commit_file.exists():
                return self.last_commit_file.read_text().strip()
            return None
        except Exception as e:
            logger.error(f"Error reading last commit: {e}")
            return None

    def get_current_commit(self) -> Optional[str]:
        """
        Get the current HEAD commit hash.

        Returns:
            Commit hash or None if error
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except Exception as e:
            logger.error(f"Error getting current commit: {e}")
            return None


# Made with Bob
