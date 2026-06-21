"""MARIS CLI - Command-line interface for repository intelligence."""

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
from maris.indexing.python_parser import PythonParser
from maris.storage.metadata_store import DuckDBMetadataStore
from maris.storage.vector_store import LanceDBVectorStore
from maris.embeddings.ollama_embeddings import OllamaEmbeddingService
from maris.knowledge.repository_knowledge_impl import RepositoryKnowledgeImpl
from maris.agents.indexing_agent import IndexingAgent
from maris.agents.documentation_agent import DocumentationAgent
from maris.agents.qa_agent import QAAgent
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
        self.parser: Optional[PythonParser] = None

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

            # Initialize parser
            self.parser = PythonParser()

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
    """
    # Load configuration
    config = load_config(config_file)
    ctx.obj = MarisContext(config, skip_validation=skip_validation)


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--recursive", "-r", is_flag=True, help="Index directory recursively")
@click.option("--auto-pull", is_flag=True, help="Automatically pull missing Ollama models")
@click.pass_obj
def index(ctx: MarisContext, path: Path, recursive: bool, auto_pull: bool):
    """Index a file or directory.

    Examples:
        maris index src/main.py
        maris index src/ --recursive
        maris index src/ -r --auto-pull
    """
    ctx.initialize(auto_pull=auto_pull)

    try:
        # Collect files to index
        files_to_index = []

        if path.is_file():
            if path.suffix == ".py":
                files_to_index.append(path)
            else:
                console.print(f"[yellow]Skipping non-Python file: {path}[/yellow]")
        elif path.is_dir():
            if recursive:
                files_to_index.extend(path.rglob("*.py"))
            else:
                files_to_index.extend(path.glob("*.py"))

        if not files_to_index:
            console.print("[yellow]No Python files found to index[/yellow]")
            return

        console.print(f"[cyan]Indexing {len(files_to_index)} file(s)...[/cyan]")

        # Index each file
        with console.status("[bold green]Indexing files...") as status:
            for i, file_path in enumerate(files_to_index, 1):
                status.update(
                    f"[bold green]Indexing {file_path.name} ({i}/{len(files_to_index)})..."
                )
                try:
                    # Read file content
                    content = file_path.read_text()

                    # Parse file
                    tree = ctx.parser.parse_file(str(file_path), content)
                    if not tree:
                        console.print(f"[red]✗[/red] {file_path}: Failed to parse")
                        continue

                    # Extract symbols
                    symbols = ctx.parser.extract_symbols(tree, str(file_path), content)

                    # Extract dependencies
                    dependencies = ctx.parser.extract_dependencies(
                        tree, symbols, str(file_path), content
                    )

                    # Store symbols
                    ctx.metadata_store.insert_symbols(symbols)

                    # Store dependencies
                    for dep in dependencies:
                        ctx.metadata_store.insert_dependency(dep)

                    # Generate and store embeddings
                    for symbol in symbols:
                        embedding = ctx.embedding_service.embed_symbol(symbol)
                        metadata = {
                            "symbol_name": symbol.name,
                            "type": symbol.type.value,
                            "file": symbol.file_path,
                            "language": symbol.language,
                        }
                        ctx.vector_store.insert_embedding(
                            symbol.id,
                            embedding,
                            f"{symbol.name} {symbol.signature or ''}",
                            metadata,
                        )

                    console.print(f"[green]✓[/green] {file_path} ({len(symbols)} symbols)")
                except Exception as e:
                    console.print(f"[red]✗[/red] {file_path}: {e}")

        console.print(f"\n[bold green]✓ Indexed {len(files_to_index)} file(s)[/bold green]")

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
        qa_agent = QAAgent(
            knowledge_service=ctx.knowledge_service,
            model=ctx.config.qa_model,
            host=(
                ctx.config.ollama_host
                if ctx.config.ollama_host != "http://localhost:11434"
                else None
            ),
        )

        with console.status(f"[bold green]Analyzing {symbol_name}..."):
            answer = qa_agent.explain_symbol(symbol_name)

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
        console.print(f"\n[{confidence_color}]Confidence: {answer.confidence}[/{confidence_color}]")

        # Display sources
        if answer.relevant_symbols:
            console.print("\n[bold]Relevant Symbols:[/bold]")
            for symbol in answer.relevant_symbols[:5]:
                console.print(f"  • {symbol.name} ({symbol.type.value}) in {symbol.file_path}")

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
        qa_agent = QAAgent(
            knowledge_service=ctx.knowledge_service,
            model=ctx.config.qa_model,
            host=(
                ctx.config.ollama_host
                if ctx.config.ollama_host != "http://localhost:11434"
                else None
            ),
        )

        with console.status("[bold green]Thinking..."):
            answer = qa_agent.answer_question(question, max_symbols=max_symbols)

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
        console.print(f"\n[{confidence_color}]Confidence: {answer.confidence}[/{confidence_color}]")

        # Display sources
        if answer.relevant_symbols:
            console.print("\n[bold]Relevant Symbols:[/bold]")
            for symbol in answer.relevant_symbols[:5]:
                console.print(f"  • {symbol.name} ({symbol.type.value}) in {symbol.file_path}")

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
        doc_agent = DocumentationAgent(knowledge_service=ctx.knowledge_service)

        with console.status(f"[bold green]Generating documentation for {file_path.name}..."):
            markdown = doc_agent.generate_markdown_documentation(str(file_path))

        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(markdown)
            console.print(f"[green]✓ Documentation written to {output}[/green]")
        else:
            console.print(Markdown(markdown))

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
        qa_agent = QAAgent(
            knowledge_service=ctx.knowledge_service,
            model=ctx.config.qa_model,
            host=(
                ctx.config.ollama_host
                if ctx.config.ollama_host != "http://localhost:11434"
                else None
            ),
        )

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
                    answer = qa_agent.answer_question(question)

                console.print(f"\n[bold green]Answer:[/bold green]\n{answer.answer}")

                confidence_color = (
                    "green"
                    if answer.confidence == "high"
                    else "yellow" if answer.confidence == "medium" else "red"
                )
                console.print(
                    f"\n[{confidence_color}]Confidence: {answer.confidence}[/{confidence_color}]"
                )

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
