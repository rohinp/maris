"""MARIS CLI - Command-line interface for repository intelligence."""

import os
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from maris.config import MarisConfig, load_config
from maris.core.models import Symbol
from maris.storage.metadata_store import DuckDBMetadataStore
from maris.storage.vector_store import LanceDBVectorStore
from maris.embeddings.ollama_embeddings import OllamaEmbeddingService
from maris.knowledge.repository_knowledge_impl import RepositoryKnowledgeImpl
from maris.agents.orchestrator_agent import OrchestratorAgent, TaskType
from maris.utils.validation import validate_with_helpful_errors

console = Console()


class MarisContext:
    """Shared context for MARIS CLI commands."""

    def __init__(self, config: MarisConfig, skip_validation: bool = False):
        self.config = config
        self.skip_validation = skip_validation

        # Initialize components
        self.metadata_store: Optional[DuckDBMetadataStore] = None
        self.vector_store: Optional[LanceDBVectorStore] = None
        self.embedding_service: Optional[OllamaEmbeddingService] = None
        self.knowledge_service: Optional[RepositoryKnowledgeImpl] = None
        self.orchestrator: Optional[OrchestratorAgent] = None

    def initialize(self, auto_pull: bool = False):
        """
        Initialize all MARIS components using configuration.

        Args:
            auto_pull: If True, automatically pull missing Ollama models
        """
        try:
            # Validate Ollama setup unless skipped
            if not self.skip_validation:
                console.print("\n[cyan]Validating Ollama setup...[/cyan]")
                validation_passed = validate_with_helpful_errors(
                    embedding_model=self.config.embedding_model,
                    qa_model=self.config.qa_model,
                    doc_model=self.config.doc_model,
                    host=(
                        self.config.ollama_host
                        if self.config.ollama_host != "http://localhost:11434"
                        else None
                    ),
                    auto_pull=auto_pull,
                )

                if not validation_passed:
                    console.print(
                        "\n[yellow]Tip: Use --skip-validation to bypass this check[/yellow]"
                    )
                    sys.exit(1)

            # Create data directory if it doesn't exist
            self.config.data_dir.mkdir(parents=True, exist_ok=True)

            # Initialize storage
            db_path = self.config.data_dir / "maris.db"
            vector_path = self.config.data_dir / "vectors"

            self.metadata_store = DuckDBMetadataStore(str(db_path))
            self.metadata_store.initialize()

            self.vector_store = LanceDBVectorStore(str(vector_path))
            self.vector_store.initialize()

            # Initialize embedding service with configured model
            self.embedding_service = OllamaEmbeddingService(
                model=self.config.embedding_model,
                host=(
                    self.config.ollama_host
                    if self.config.ollama_host != "http://localhost:11434"
                    else None
                ),
                batch_size=self.config.embedding_batch_size,
            )

            # Initialize knowledge service
            self.knowledge_service = RepositoryKnowledgeImpl(
                metadata_store=self.metadata_store,
                vector_store=self.vector_store,
                embedding_service=self.embedding_service,
            )

            # Initialize orchestrator agent
            self.orchestrator = OrchestratorAgent(
                knowledge_service=self.knowledge_service,
                metadata_store=self.metadata_store,
                vector_store=self.vector_store,
                repo_path=str(Path.cwd()),  # Use current directory as repo path
                qa_model=self.config.qa_model,
                embedding_model=self.config.embedding_model,
            )

        except Exception as e:
            console.print(f"[red]Error initializing MARIS: {e}[/red]")
            sys.exit(1)

    def close(self):
        """Close all resources."""
        if self.metadata_store:
            self.metadata_store.close()
        if self.vector_store:
            self.vector_store.close()


@click.group()
@click.option(
    "--config-file",
    type=click.Path(path_type=Path),
    help="Path to .env configuration file",
)
@click.option(
    "--skip-validation",
    is_flag=True,
    help="Skip Ollama and model validation checks",
)
@click.pass_context
def cli(ctx, config_file: Optional[Path], skip_validation: bool):
    """MARIS - Local Multi-Agent Repository Intelligence System.

    A privacy-first repository intelligence platform that helps developers
    understand, navigate, document, and reason about source code.

    Configuration is loaded from (in order of priority):
    1. Environment variables (MARIS_*)
    2. .env file in current directory
    3. ~/.maris/.env
    4. Default values

    Use --config-file to specify a custom .env file.

    By default, MARIS uses project-specific storage (.maris/ in current directory).
    Set MARIS_DATA_DIR environment variable to use a different location.
    """
    # Load configuration
    config = load_config(config_file)

    # Use project-specific storage by default (unless explicitly configured)
    if "MARIS_DATA_DIR" not in os.environ:
        # Use .maris in current working directory
        config.data_dir = Path.cwd() / ".maris"

    ctx.obj = MarisContext(config, skip_validation=skip_validation)


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path), required=False)
@click.option("--recursive", "-r", is_flag=True, help="Index directory recursively")
@click.option(
    "--incremental",
    "-i",
    is_flag=True,
    help="Only index files changed since last indexing (requires Git)",
)
@click.option("--auto-pull", is_flag=True, help="Automatically pull missing Ollama models")
@click.pass_obj
def index(
    ctx: MarisContext, path: Optional[Path], recursive: bool, incremental: bool, auto_pull: bool
):
    """Index a file or directory.

    Examples:
        maris index src/main.py
        maris index src/ --recursive
        maris index src/ -r --auto-pull
        maris index --incremental  # Index only changed files
        maris index -i  # Short form
    """
    ctx.initialize(auto_pull=auto_pull)

    try:
        # Handle incremental indexing
        if incremental:
            if path:
                console.print(
                    "[yellow]Warning: --incremental flag ignores the path argument[/yellow]"
                )

            console.print("[cyan]Detecting changes since last indexing...[/cyan]")

            with console.status("[bold green]Detecting Git changes..."):
                result = ctx.orchestrator.execute(
                    request="Detect Git changes",
                    task_type="git_changes",
                )

            if not result.success:
                console.print(f"[red]✗ Failed to detect changes: {result.error}[/red]")
                console.print("[yellow]Tip: Make sure you're in a Git repository[/yellow]")
                return

            changeset = result.result

            if not changeset.has_changes:
                console.print("[green]✓ No changes detected since last indexing[/green]")
                console.print(f"[dim]Last indexed commit: {changeset.last_commit or 'N/A'}[/dim]")
                console.print(f"[dim]Current commit: {changeset.current_commit}[/dim]")
                return

            # Display changes
            console.print(f"\n[bold]Changes detected:[/bold]")
            if changeset.added_files:
                console.print(f"  [green]Added: {len(changeset.added_files)} files[/green]")
            if changeset.modified_files:
                console.print(f"  [yellow]Modified: {len(changeset.modified_files)} files[/yellow]")
            if changeset.deleted_files:
                console.print(f"  [red]Deleted: {len(changeset.deleted_files)} files[/red]")
            if changeset.renamed_files:
                console.print(f"  [blue]Renamed: {len(changeset.renamed_files)} files[/blue]")

            console.print(
                f"\n[cyan]Performing incremental indexing of {changeset.total_changes} changed files...[/cyan]"
            )

            with console.status("[bold green]Indexing changed files..."):
                result = ctx.orchestrator.execute(
                    request="Incremental index",
                    task_type="incremental_index",
                )

            if result.success:
                indexing_result = result.result
                console.print(f"\n[bold green]✓ Incremental indexing complete![/bold green]")
                console.print(f"  Files processed: {indexing_result.files_processed}")
                console.print(f"  Symbols extracted: {indexing_result.symbols_extracted}")
                console.print(f"  Embeddings generated: {indexing_result.embeddings_generated}")
                console.print(f"  Duration: {indexing_result.duration_seconds:.2f}s")

                if indexing_result.errors:
                    console.print(
                        f"\n[yellow]Errors encountered: {len(indexing_result.errors)}[/yellow]"
                    )
                    for error in indexing_result.errors[:5]:
                        console.print(f"  • {error}")
            else:
                console.print(f"[red]✗ Incremental indexing failed: {result.error}[/red]")

            return

        # Regular indexing (non-incremental)
        if not path:
            console.print(
                "[red]Error: PATH argument is required for non-incremental indexing[/red]"
            )
            console.print(
                "[yellow]Tip: Use --incremental flag to index only changed files[/yellow]"
            )
            return

        # Collect files to index
        files_to_index = []

        if path.is_file():
            files_to_index.append(str(path))
        elif path.is_dir():
            # Use orchestrator to find all supported files
            from maris.indexing import ParserFactory

            supported_extensions = ParserFactory.get_implemented_extensions()

            console.print(
                f"[dim]Scanning for files with extensions: {', '.join(supported_extensions)}[/dim]"
            )
            console.print(f"[dim]Recursive: {recursive}[/dim]")

            if recursive:
                for ext in supported_extensions:
                    found = list(path.rglob(f"*{ext}"))
                    if found:
                        console.print(f"[dim]Found {len(found)} {ext} files[/dim]")
                    files_to_index.extend(str(f) for f in found)
            else:
                for ext in supported_extensions:
                    found = list(path.glob(f"*{ext}"))
                    if found:
                        console.print(f"[dim]Found {len(found)} {ext} files[/dim]")
                    files_to_index.extend(str(f) for f in found)

        if not files_to_index:
            console.print("[yellow]No supported files found to index[/yellow]")
            console.print(f"[dim]Searched in: {path.absolute()}[/dim]")
            console.print(f"[dim]Recursive: {recursive}[/dim]")
            console.print("[yellow]Tip: Use --recursive or -r to search subdirectories[/yellow]")
            return

        console.print(f"[cyan]Indexing {len(files_to_index)} file(s)...[/cyan]")

        # Use orchestrator to index files
        with console.status("[bold green]Indexing files..."):
            result = ctx.orchestrator.execute(
                request="Index files",
                task_type="index",
                file_paths=files_to_index,
            )

        if result.success:
            indexing_result = result.result
            console.print(f"\n[bold green]✓ Indexing complete![/bold green]")
            console.print(f"  Files processed: {indexing_result.files_processed}")
            console.print(f"  Symbols extracted: {indexing_result.symbols_extracted}")
            console.print(f"  Embeddings generated: {indexing_result.embeddings_generated}")

            if indexing_result.errors:
                console.print(
                    f"\n[yellow]Errors encountered: {len(indexing_result.errors)}[/yellow]"
                )
                for error in indexing_result.errors[:5]:  # Show first 5 errors
                    console.print(f"  • {error}")
        else:
            console.print(f"[red]✗ Indexing failed: {result.error}[/red]")

    finally:
        ctx.close()


@cli.command()
@click.argument("query")
@click.option("--max-results", "-n", default=10, help="Maximum number of results")
@click.pass_obj
def search(ctx: MarisContext, query: str, max_results: int):
    """Search for symbols in the indexed repository.

    Examples:
        maris search "GraphRunner"
        maris search "retry" --max-results 5
    """
    ctx.initialize()

    try:
        results = ctx.knowledge_service.semantic_search(query, max_results)

        if not results:
            console.print("[yellow]No results found[/yellow]")
            return

        table = Table(title=f"Search Results for '{query}'")
        table.add_column("Symbol", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("File", style="green")
        table.add_column("Score", style="yellow")

        for symbol, score in results:
            table.add_row(symbol.name, symbol.type.value, symbol.file_path, f"{score:.3f}")

        console.print(table)

    finally:
        ctx.close()


@cli.command()
@click.argument("symbol_name")
@click.pass_obj
def explain(ctx: MarisContext, symbol_name: str):
    """Explain a symbol in detail.

    Examples:
        maris explain GraphRunner
        maris explain retryExecuteNode
    """
    ctx.initialize()

    try:
        with console.status(f"[bold green]Analyzing {symbol_name}..."):
            result = ctx.orchestrator.execute(
                request=f"Explain the symbol {symbol_name}",
                task_type="question",
            )

        if result.success:
            answer = result.result
            # Display answer
            panel = Panel(
                Markdown(answer.answer),
                title=f"[bold cyan]Explanation: {symbol_name}[/bold cyan]",
                border_style="cyan",
            )
            console.print(panel)

            # Display confidence
            confidence_color = (
                "green"
                if answer.confidence == "high"
                else "yellow" if answer.confidence == "medium" else "red"
            )
            console.print(
                f"\n[{confidence_color}]Confidence: {answer.confidence}[/{confidence_color}]"
            )

            # Display sources
            if answer.relevant_symbols:
                console.print("\n[bold]Relevant Symbols:[/bold]")
                for symbol in answer.relevant_symbols[:5]:
                    console.print(f"  • {symbol.name} ({symbol.type.value}) in {symbol.file_path}")
        else:
            console.print(f"[red]✗ Failed to explain symbol: {result.error}[/red]")

    finally:
        ctx.close()


@cli.command()
@click.argument("question")
@click.option("--max-symbols", "-n", default=10, help="Maximum symbols to retrieve")
@click.pass_obj
def ask(ctx: MarisContext, question: str, max_symbols: int):
    """Ask a question about the codebase.

    Examples:
        maris ask "How does the parser work?"
        maris ask "What is the purpose of the indexing agent?"
    """
    ctx.initialize()

    try:
        with console.status("[bold green]Thinking..."):
            result = ctx.orchestrator.execute(
                request=question,
                task_type="question",
            )

        if result.success:
            answer = result.result
            # Display answer
            panel = Panel(
                Markdown(answer.answer), title="[bold cyan]Answer[/bold cyan]", border_style="cyan"
            )
            console.print(panel)

            # Display confidence
            confidence_color = (
                "green"
                if answer.confidence == "high"
                else "yellow" if answer.confidence == "medium" else "red"
            )
            console.print(
                f"\n[{confidence_color}]Confidence: {answer.confidence}[/{confidence_color}]"
            )

            # Display sources
            if answer.relevant_symbols:
                console.print("\n[bold]Relevant Symbols:[/bold]")
                for symbol in answer.relevant_symbols[:5]:
                    console.print(f"  • {symbol.name} ({symbol.type.value}) in {symbol.file_path}")
        else:
            console.print(f"[red]✗ Failed to answer question: {result.error}[/red]")

    finally:
        ctx.close()


@cli.command()
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file path")
@click.pass_obj
def document(ctx: MarisContext, file_path: Path, output: Optional[Path]):
    """Generate documentation for a file.

    Examples:
        maris document src/main.py
        maris document src/main.py --output docs/main.md
    """
    ctx.initialize()

    try:
        with console.status(f"[bold green]Generating documentation for {file_path.name}..."):
            result = ctx.orchestrator.execute(
                request=f"Generate documentation for {file_path}",
                task_type="document",
                file_path=str(file_path),
                format="markdown",
            )

        if result.success:
            markdown = result.result
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(markdown)
                console.print(f"[green]✓ Documentation written to {output}[/green]")
            else:
                console.print(Markdown(markdown))
        else:
            console.print(f"[red]✗ Failed to generate documentation: {result.error}[/red]")

    finally:
        ctx.close()


@cli.command()
@click.pass_obj
def stats(ctx: MarisContext):
    """Show repository statistics.

    Examples:
        maris stats
    """
    ctx.initialize()

    try:
        # Query all symbols
        conn = ctx.metadata_store.conn
        result = conn.execute(
            "SELECT type, COUNT(*) as count FROM symbols GROUP BY type"
        ).fetchall()

        total_symbols = sum(row[1] for row in result)

        # Get file count
        file_result = conn.execute("SELECT COUNT(DISTINCT file_path) FROM symbols").fetchone()
        file_count = file_result[0] if file_result else 0

        # Display statistics
        table = Table(title="Repository Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="green", justify="right")

        table.add_row("Total Symbols", str(total_symbols))
        table.add_row("Indexed Files", str(file_count))

        for symbol_type, count in result:
            table.add_row(f"  {symbol_type.capitalize()}s", str(count))

        console.print(table)

    finally:
        ctx.close()


@cli.command()
@click.confirmation_option(prompt="Are you sure you want to clear all indexed data?")
@click.pass_obj
def clear(ctx: MarisContext):
    """Clear all indexed data.

    Examples:
        maris clear
    """
    ctx.initialize()

    try:
        # Clear metadata store
        ctx.metadata_store.conn.execute("DELETE FROM symbols")
        ctx.metadata_store.conn.execute("DELETE FROM dependencies")
        ctx.metadata_store.conn.execute("DELETE FROM commits")

        # Clear vector store
        try:
            ctx.vector_store.db.drop_table("symbols")
        except Exception:
            pass  # Table might not exist

        console.print("[green]✓ All indexed data cleared[/green]")

    finally:
        ctx.close()


@cli.command()
@click.pass_obj
def interactive(ctx: MarisContext):
    """Start interactive Q&A session.

    Examples:
        maris interactive
    """
    ctx.initialize()

    try:
        console.print(
            Panel(
                "[bold cyan]MARIS Interactive Q&A[/bold cyan]\n\n"
                "Ask questions about your codebase.\n"
                "Type 'exit' or 'quit' to end the session.",
                border_style="cyan",
            )
        )

        while True:
            try:
                question = console.input("\n[bold cyan]Question:[/bold cyan] ")

                if question.lower() in ["exit", "quit", "q"]:
                    console.print("[yellow]Goodbye![/yellow]")
                    break

                if not question.strip():
                    continue

                with console.status("[bold green]Thinking..."):
                    result = ctx.orchestrator.execute(
                        request=question,
                        task_type="question",
                    )

                if result.success:
                    answer = result.result
                    console.print(f"\n[bold green]Answer:[/bold green]\n{answer.answer}")

                    confidence_color = (
                        "green"
                        if answer.confidence == "high"
                        else "yellow" if answer.confidence == "medium" else "red"
                    )
                    console.print(
                        f"\n[{confidence_color}]Confidence: {answer.confidence}[/{confidence_color}]"
                    )
                else:
                    console.print(f"[red]Error: {result.error}[/red]")

            except KeyboardInterrupt:
                console.print("\n[yellow]Goodbye![/yellow]")
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

    finally:
        ctx.close()


if __name__ == "__main__":
    cli()

# Made with Bob
