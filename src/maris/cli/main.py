"""MARIS CLI - Command-line interface for repository intelligence."""

import os
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from maris import __version__
from maris.agents.orchestrator_agent import OrchestratorAgent
from maris.config import MarisConfig, load_config
from maris.embeddings.ollama_embeddings import OllamaEmbeddingService
from maris.knowledge.repository_knowledge_impl import RepositoryKnowledgeImpl
from maris.storage.metadata_store import DuckDBMetadataStore
from maris.storage.vector_store import LanceDBVectorStore
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
                ollama_host=(
                    self.config.ollama_host
                    if self.config.ollama_host != "http://localhost:11434"
                    else None
                ),
                embedding_service=self.embedding_service,
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
def version():
    """Display MARIS version information."""
    console.print(f"\n[bold cyan]MARIS[/bold cyan] version [bold green]{__version__}[/bold green]")
    console.print("\n[dim]Local Multi-Agent Repository Intelligence System[/dim]")
    console.print("[dim]https://github.com/yourusername/maris[/dim]\n")


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

            console.print("[cyan]Performing incremental indexing...[/cyan]")

            with console.status("[bold green]Indexing changed files..."):
                result = ctx.orchestrator.execute(
                    request="Incremental index",
                    task_type="incremental_index",
                )

            if not result.success:
                console.print(f"[red]✗ Incremental indexing failed: {result.error}[/red]")
                console.print("[yellow]Tip: Make sure you're in a Git repository[/yellow]")
                return

            changeset = result.metadata.get("changeset") if result.metadata else None

            if changeset and not changeset.has_changes:
                console.print("[green]✓ No changes detected since last indexing[/green]")
                console.print(f"[dim]Last indexed commit: {changeset.last_commit or 'N/A'}[/dim]")
                console.print(f"[dim]Current commit: {changeset.current_commit}[/dim]")
                return

            # Display changes
            if changeset:
                console.print("\n[bold]Changes detected:[/bold]")
                if changeset.added_files:
                    console.print(f"  [green]Added: {len(changeset.added_files)} files[/green]")
                if changeset.modified_files:
                    console.print(
                        f"  [yellow]Modified: {len(changeset.modified_files)} files[/yellow]"
                    )
                if changeset.deleted_files:
                    console.print(f"  [red]Deleted: {len(changeset.deleted_files)} files[/red]")
                if changeset.renamed_files:
                    console.print(f"  [blue]Renamed: {len(changeset.renamed_files)} files[/blue]")

            indexing_result = result.result
            console.print("\n[bold green]✓ Incremental indexing complete![/bold green]")
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

        if path.is_file():
            files_to_index = ctx.orchestrator.collect_indexable_files(str(path), recursive=False)
        elif path.is_dir():
            files_to_index = ctx.orchestrator.collect_indexable_files(
                str(path), recursive=recursive
            )
            extension_counts = Counter(Path(file_path).suffix for file_path in files_to_index)
            extensions = sorted(extension_counts)

            console.print(
                f"[dim]Scanning for files with extensions: {', '.join(extensions) or 'none'}[/dim]"
            )
            console.print(f"[dim]Recursive: {recursive}[/dim]")

            for ext, count in sorted(extension_counts.items()):
                console.print(f"[dim]Found {count} {ext} files[/dim]")
        else:
            files_to_index = []

        if not files_to_index:
            console.print("[yellow]No supported files found to index[/yellow]")
            console.print(f"[dim]Searched in: {path.absolute()}[/dim]")
            console.print(f"[dim]Recursive: {recursive}[/dim]")
            console.print("[yellow]Tip: Use --recursive or -r to search subdirectories[/yellow]")
            return

        console.print(f"[cyan]Indexing {len(files_to_index)} file(s)...[/cyan]")

        # Use orchestrator to index files with progress tracking
        from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            # Create tasks for different phases
            parse_task = progress.add_task("[cyan]Parsing files...", total=len(files_to_index))
            embed_task = progress.add_task(
                "[green]Generating embeddings...", total=None, visible=False
            )

            def update_parse_progress(current: int, total: int) -> None:
                progress.update(parse_task, total=total, completed=current)

            def update_embedding_progress(current: int, total: int) -> None:
                progress.update(
                    embed_task,
                    total=total,
                    completed=current,
                    visible=True,
                )

            # Start indexing
            result = ctx.orchestrator.execute(
                request="Index files",
                task_type="index",
                file_paths=files_to_index,
                parse_progress_callback=update_parse_progress,
                embedding_progress_callback=update_embedding_progress,
            )

            # Ensure completed tasks show their final state before the progress exits.
            progress.update(parse_task, total=len(files_to_index), completed=len(files_to_index))

            # Show embedding progress if available
            if result.success and result.result:
                indexing_result = result.result
                if indexing_result.symbols_extracted > 0:
                    progress.update(
                        embed_task,
                        total=indexing_result.symbols_extracted,
                        completed=indexing_result.embeddings_generated,
                        visible=True,
                    )

        if result.success:
            indexing_result = result.result
            console.print("\n[bold green]✓ Indexing complete![/bold green]")
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
        results = ctx.orchestrator.search_symbols(query, max_results)

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
                max_symbols=max_symbols,
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


@cli.group()
@click.pass_obj
def impact(ctx: MarisContext):
    """Analyze code impact, edge cases, and test coverage.

    Examples:
        maris impact analyze --symbol "GitAgent.detect_changes"
        maris impact analyze --file "src/maris/agents/git_agent.py"
        maris impact edge-cases --symbol "IndexingAgent.index_files"
        maris impact tests --symbol "QAAgent.answer_question"
    """
    ctx.initialize()


@impact.command()
@click.option("--symbol", "-s", help="Symbol name to analyze")
@click.option(
    "--file", "-f", "file_path", type=click.Path(exists=True), help="File path to analyze"
)
@click.option(
    "--format", "-fmt", type=click.Choice(["text", "json"]), default="text", help="Output format"
)
@click.pass_obj
def analyze(ctx: MarisContext, symbol: Optional[str], file_path: Optional[str], format: str):
    """Analyze the impact of changes to a symbol or file.

    Performs comprehensive impact analysis including:
    - Direct and indirect callers
    - Affected files and tests
    - Edge cases and recommendations
    - Breaking change detection

    Examples:
        maris impact analyze --symbol "GitAgent.detect_changes"
        maris impact analyze --file "src/maris/agents/git_agent.py"
        maris impact analyze -s "MyClass.method" --format json
    """
    if not symbol and not file_path:
        console.print("[red]Error: Either --symbol or --file must be provided[/red]")
        sys.exit(1)

    try:
        with console.status("[bold green]Analyzing impact..."):
            result = ctx.orchestrator.analyze_impact(
                symbol_name=symbol, file_path=file_path, analysis_type="impact"
            )

        if format == "json":
            import json

            console.print_json(json.dumps(result.to_dict(), indent=2))
        else:
            report = ctx.orchestrator.format_impact_report(result)
            console.print(Markdown(report))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        ctx.close()


@impact.command()
@click.option("--symbol", "-s", help="Symbol name to analyze")
@click.option(
    "--file", "-f", "file_path", type=click.Path(exists=True), help="File path to analyze"
)
@click.pass_obj
def edge_cases(ctx: MarisContext, symbol: Optional[str], file_path: Optional[str]):
    """Detect potential edge cases in code.

    Identifies:
    - Missing null/None checks
    - Missing error handling
    - Boundary conditions
    - Unhandled exceptions

    Examples:
        maris impact edge-cases --symbol "GitAgent.detect_changes"
        maris impact edge-cases --file "src/maris/agents/git_agent.py"
    """
    if not symbol and not file_path:
        console.print("[red]Error: Either --symbol or --file must be provided[/red]")
        sys.exit(1)

    try:
        with console.status("[bold green]Detecting edge cases..."):
            result = ctx.orchestrator.analyze_impact(
                symbol_name=symbol, file_path=file_path, analysis_type="edge_cases"
            )

        # Display edge cases
        if result.edge_cases:
            console.print(f"\n[bold]Edge Cases for {result.target_symbol.name}:[/bold]\n")

            for edge_case in result.edge_cases:
                severity_color = {"high": "red", "medium": "yellow", "low": "blue"}.get(
                    edge_case.severity, "white"
                )

                status = "✓" if edge_case.is_handled else "⚠️"
                console.print(
                    f"{status} [{severity_color}]{edge_case.type.upper()}[/{severity_color}] ({edge_case.severity})"
                )
                console.print(f"   {edge_case.description}")
                console.print(f"   Location: {edge_case.location}")
                if edge_case.suggestion:
                    console.print(f"   [dim]Suggestion: {edge_case.suggestion}[/dim]")
                console.print()
        else:
            console.print(f"[green]No edge cases detected for {result.target_symbol.name}[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        ctx.close()


@impact.command()
@click.option("--symbol", "-s", help="Symbol name to analyze")
@click.option(
    "--file", "-f", "file_path", type=click.Path(exists=True), help="File path to analyze"
)
@click.pass_obj
def tests(ctx: MarisContext, symbol: Optional[str], file_path: Optional[str]):
    """Analyze test coverage for a symbol or file.

    Shows:
    - Tests that cover the symbol
    - Test gaps and missing scenarios
    - Recommendations for additional tests

    Examples:
        maris impact tests --symbol "GitAgent.detect_changes"
        maris impact tests --file "src/maris/agents/git_agent.py"
    """
    if not symbol and not file_path:
        console.print("[red]Error: Either --symbol or --file must be provided[/red]")
        sys.exit(1)

    try:
        with console.status("[bold green]Analyzing test coverage..."):
            result = ctx.orchestrator.analyze_impact(
                symbol_name=symbol, file_path=file_path, analysis_type="tests"
            )

        # Display test coverage
        console.print(f"\n[bold]Test Coverage for {result.target_symbol.name}:[/bold]\n")

        if result.affected_tests:
            console.print(f"[green]Found {len(result.affected_tests)} test(s):[/green]\n")
            for test in result.affected_tests:
                console.print(f"  ✓ {test.name}")
                console.print(f"    {test.file_path}:{test.start_line}")
                console.print()
        else:
            console.print("[yellow]⚠️  No tests found covering this symbol[/yellow]\n")

        # Show recommendations
        if result.recommendations:
            console.print("[bold]Recommendations:[/bold]\n")
            for i, rec in enumerate(result.recommendations, 1):
                console.print(f"  {i}. {rec}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        ctx.close()


@impact.command()
@click.option("--symbol", "-s", help="Symbol name to analyze")
@click.option(
    "--file", "-f", "file_path", type=click.Path(exists=True), help="File path to analyze"
)
@click.pass_obj
def breaking_changes(ctx: MarisContext, symbol: Optional[str], file_path: Optional[str]):
    """Detect potential breaking changes.

    Identifies:
    - Callers that would be affected
    - Interface contract changes
    - Public API modifications

    Examples:
        maris impact breaking-changes --symbol "GitAgent.detect_changes"
        maris impact breaking-changes --file "src/maris/agents/git_agent.py"
    """
    if not symbol and not file_path:
        console.print("[red]Error: Either --symbol or --file must be provided[/red]")
        sys.exit(1)

    try:
        with console.status("[bold green]Detecting breaking changes..."):
            result = ctx.orchestrator.analyze_impact(
                symbol_name=symbol, file_path=file_path, analysis_type="breaking_changes"
            )

        # Display breaking changes
        console.print(f"\n[bold]Breaking Change Analysis for {result.target_symbol.name}:[/bold]\n")

        if result.breaking_changes:
            console.print("[yellow]Potential Breaking Changes:[/yellow]\n")
            for change in result.breaking_changes:
                console.print(f"  ⚠️  {change}")
            console.print()
        else:
            console.print("[green]No breaking changes detected[/green]\n")

        # Show affected callers
        if result.direct_callers:
            console.print(f"[bold]Affected Callers ({len(result.direct_callers)}):[/bold]\n")
            for caller in result.direct_callers[:10]:
                console.print(f"  • {caller.name}")
                console.print(f"    {caller.file_path}:{caller.start_line}")
            if len(result.direct_callers) > 10:
                console.print(f"\n  ... and {len(result.direct_callers) - 10} more")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
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
        status = ctx.orchestrator.get_status()

        # Display statistics
        table = Table(title="Repository Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Repository", status["repository_path"])
        table.add_row("Indexed Files", str(status["total_files"]))
        table.add_row("Total Symbols", str(status["total_symbols"]))
        table.add_row("Dependencies", str(status["total_dependencies"]))
        table.add_row("Embeddings", str(status["total_embeddings"]))
        table.add_row("Languages", ", ".join(status["languages"]) or "N/A")
        table.add_row("Last Indexed", str(status["last_indexed"] or "N/A"))

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
        ctx.orchestrator.clear_index()

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
