"""Validation utilities for checking Ollama setup and model availability."""

import logging
from typing import List, Optional, Tuple

import ollama
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

logger = logging.getLogger(__name__)
console = Console()


class ValidationError(Exception):
    """Raised when validation fails."""

    pass


def check_ollama_running(host: Optional[str] = None) -> bool:
    """
    Check if Ollama is running and accessible.

    Args:
        host: Optional Ollama host URL

    Returns:
        True if Ollama is running, False otherwise
    """
    try:
        client = ollama.Client(host=host) if host else ollama.Client()
        # Try to list models to verify connection
        client.list()
        return True
    except Exception as e:
        logger.debug(f"Ollama connection check failed: {e}")
        return False


def check_model_available(model: str, host: Optional[str] = None) -> bool:
    """
    Check if a specific model is available in Ollama.

    Args:
        model: Model name to check (e.g., "qwen2.5:7b")
        host: Optional Ollama host URL

    Returns:
        True if model is available, False otherwise
    """
    try:
        client = ollama.Client(host=host) if host else ollama.Client()
        models = client.list()

        # Extract model names from the response
        available_models = []
        if hasattr(models, "models"):
            available_models = [m.model if hasattr(m, "model") else str(m) for m in models.models]
        elif isinstance(models, dict) and "models" in models:
            available_models = [m.get("name", m.get("model", str(m))) for m in models["models"]]

        # Check if the model exists (exact match or with tag)
        model_base = model.split(":")[0]
        for available in available_models:
            if available == model or available.startswith(f"{model_base}:"):
                return True

        return False
    except Exception as e:
        logger.debug(f"Model availability check failed for {model}: {e}")
        return False


def get_available_models(host: Optional[str] = None) -> List[str]:
    """
    Get list of available models in Ollama.

    Args:
        host: Optional Ollama host URL

    Returns:
        List of available model names
    """
    try:
        client = ollama.Client(host=host) if host else ollama.Client()
        models = client.list()

        available_models = []
        if hasattr(models, "models"):
            available_models = [m.model if hasattr(m, "model") else str(m) for m in models.models]
        elif isinstance(models, dict) and "models" in models:
            available_models = [m.get("name", m.get("model", str(m))) for m in models["models"]]

        return available_models
    except Exception as e:
        logger.error(f"Failed to get available models: {e}")
        return []


def validate_ollama_setup(
    embedding_model: str,
    qa_model: str,
    doc_model: str,
    host: Optional[str] = None,
    auto_pull: bool = False,
) -> Tuple[bool, List[str]]:
    """
    Validate that Ollama is running and required models are available.

    Args:
        embedding_model: Embedding model name
        qa_model: Q&A model name
        doc_model: Documentation model name
        host: Optional Ollama host URL
        auto_pull: If True, attempt to pull missing models

    Returns:
        Tuple of (success: bool, missing_models: List[str])

    Raises:
        ValidationError: If Ollama is not running
    """
    # Check if Ollama is running
    if not check_ollama_running(host):
        error_msg = "Ollama is not running or not accessible"
        if host:
            error_msg += f" at {host}"
        raise ValidationError(error_msg)

    # Check required models
    required_models = {"Embedding": embedding_model, "Q&A": qa_model, "Documentation": doc_model}

    missing_models = []
    available_models = []

    for purpose, model in required_models.items():
        if check_model_available(model, host):
            available_models.append((purpose, model, True))
        else:
            available_models.append((purpose, model, False))
            missing_models.append(model)

    # Display validation results
    table = Table(title="Ollama Model Validation")
    table.add_column("Purpose", style="cyan")
    table.add_column("Model", style="yellow")
    table.add_column("Status", style="bold")

    for purpose, model, is_available in available_models:
        status = "[green]✓ Available[/green]" if is_available else "[red]✗ Missing[/red]"
        table.add_row(purpose, model, status)

    console.print(table)

    # If models are missing and auto_pull is enabled, attempt to pull them
    if missing_models and auto_pull:
        console.print("\n[yellow]Attempting to pull missing models...[/yellow]")
        for model in missing_models:
            try:
                console.print(f"[cyan]Pulling {model}...[/cyan]")
                client = ollama.Client(host=host) if host else ollama.Client()
                client.pull(model)
                console.print(f"[green]✓ Successfully pulled {model}[/green]")
                missing_models.remove(model)
            except Exception as e:
                console.print(f"[red]✗ Failed to pull {model}: {e}[/red]")

    # Return validation result
    success = len(missing_models) == 0
    return success, missing_models


def display_validation_error(missing_models: List[str], host: Optional[str] = None):
    """
    Display a helpful error message for missing models.

    Args:
        missing_models: List of missing model names
        host: Optional Ollama host URL
    """
    host_info = f" at {host}" if host else ""

    error_panel = Panel(
        f"[bold red]Missing Required Models[/bold red]\n\n"
        f"The following models are not available in Ollama{host_info}:\n\n"
        + "\n".join(f"  • {model}" for model in missing_models)
        + "\n\n[bold]To install missing models, run:[/bold]\n\n"
        + "\n".join(f"  ollama pull {model}" for model in missing_models)
        + "\n\n[bold]Or let MARIS pull them automatically:[/bold]\n\n"
        "  maris index --auto-pull src/",
        border_style="red",
        title="[bold red]Validation Failed[/bold red]",
    )

    console.print(error_panel)


def display_ollama_not_running_error(host: Optional[str] = None):
    """
    Display error message when Ollama is not running.

    Args:
        host: Optional Ollama host URL
    """
    host_info = f" at {host}" if host else ""

    error_panel = Panel(
        f"[bold red]Ollama Not Running[/bold red]\n\n"
        f"Cannot connect to Ollama{host_info}.\n\n"
        "[bold]To start Ollama:[/bold]\n\n"
        "  1. Install Ollama from https://ollama.ai\n"
        "  2. Start the Ollama service:\n"
        "     • macOS/Linux: ollama serve\n"
        "     • Windows: Ollama runs as a service\n\n"
        "[bold]Or specify a different host:[/bold]\n\n"
        "  maris --config-file .env index src/\n"
        "  # Set MARIS_OLLAMA_HOST in .env",
        border_style="red",
        title="[bold red]Connection Failed[/bold red]",
    )

    console.print(error_panel)


def validate_with_helpful_errors(
    embedding_model: str,
    qa_model: str,
    doc_model: str,
    host: Optional[str] = None,
    auto_pull: bool = False,
) -> bool:
    """
    Validate Ollama setup with helpful error messages.

    Args:
        embedding_model: Embedding model name
        qa_model: Q&A model name
        doc_model: Documentation model name
        host: Optional Ollama host URL
        auto_pull: If True, attempt to pull missing models

    Returns:
        True if validation passed, False otherwise
    """
    try:
        success, missing_models = validate_ollama_setup(
            embedding_model, qa_model, doc_model, host, auto_pull
        )

        if not success:
            display_validation_error(missing_models, host)
            return False

        console.print("\n[bold green]✓ All required models are available![/bold green]\n")
        return True

    except ValidationError as e:
        display_ollama_not_running_error(host)
        return False
    except Exception as e:
        console.print(f"[red]Validation error: {e}[/red]")
        return False


if __name__ == "__main__":
    # Test validation
    print("Testing Ollama validation...")

    try:
        success, missing = validate_ollama_setup(
            embedding_model="nomic-embed-text", qa_model="qwen2.5:7b", doc_model="qwen2.5:7b"
        )

        if success:
            print("✓ Validation passed!")
        else:
            print(f"✗ Validation failed. Missing models: {missing}")

    except ValidationError as e:
        print(f"✗ Validation error: {e}")

# Made with Bob
