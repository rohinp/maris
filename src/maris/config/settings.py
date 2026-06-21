"""Configuration settings for MARIS with .env support."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings


class MarisConfig(BaseSettings):
    """
    MARIS configuration with support for .env files and environment variables.

    Configuration priority (highest to lowest):
    1. Environment variables
    2. .env file in current directory
    3. .env file in home directory (~/.maris/.env)
    4. Default values

    Supports different models for different agents:
    - Embedding model for vector generation
    - Q&A model for answering questions
    - Documentation model for generating docs
    """

    # Storage Configuration
    data_dir: Path = Field(
        default_factory=lambda: Path.home() / ".maris",
        description="Directory for MARIS data storage",
    )

    # Ollama Configuration
    ollama_host: str = Field(default="http://localhost:11434", description="Ollama API host URL")

    # Model Configuration - Embeddings
    embedding_model: str = Field(
        default="nomic-embed-text", description="Ollama model for generating embeddings"
    )

    embedding_batch_size: int = Field(default=32, description="Batch size for embedding generation")

    # Model Configuration - Q&A Agent
    qa_model: str = Field(default="qwen2.5:7b", description="Ollama model for Q&A agent")

    qa_temperature: float = Field(default=0.7, description="Temperature for Q&A model (0.0-1.0)")

    qa_max_tokens: int = Field(default=2048, description="Maximum tokens for Q&A responses")

    # Model Configuration - Documentation Agent
    doc_model: str = Field(
        default="qwen2.5:7b", description="Ollama model for documentation generation"
    )

    doc_temperature: float = Field(
        default=0.3, description="Temperature for documentation model (0.0-1.0)"
    )

    doc_max_tokens: int = Field(default=4096, description="Maximum tokens for documentation")

    # Retrieval Configuration
    max_search_results: int = Field(default=20, description="Maximum results for semantic search")

    max_context_symbols: int = Field(
        default=10, description="Maximum symbols to include in context"
    )

    # Performance Configuration
    enable_caching: bool = Field(
        default=True, description="Enable caching for embeddings and results"
    )

    parallel_indexing: bool = Field(
        default=False, description="Enable parallel file indexing (experimental)"
    )

    # Logging Configuration
    log_level: str = Field(
        default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )

    log_file: Optional[Path] = Field(default=None, description="Optional log file path")

    class Config:
        """Pydantic configuration."""

        env_prefix = "MARIS_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def load_config(env_file: Optional[Path] = None) -> MarisConfig:
    """
    Load MARIS configuration from environment and .env files.

    Args:
        env_file: Optional path to .env file. If not provided, searches in:
                  1. Current directory (.env)
                  2. Home directory (~/.maris/.env)

    Returns:
        MarisConfig instance with loaded settings

    Examples:
        # Load with defaults
        config = load_config()

        # Load from specific .env file
        config = load_config(Path(".env.production"))

        # Access configuration
        print(config.qa_model)  # "qwen2.5:7b"
        print(config.doc_model)  # "qwen2.5:7b"
    """
    # Search for .env files in order of priority
    env_files_to_try = []

    if env_file:
        env_files_to_try.append(env_file)

    # Current directory
    env_files_to_try.append(Path(".env"))

    # Home directory
    home_env = Path.home() / ".maris" / ".env"
    env_files_to_try.append(home_env)

    # Load the first .env file that exists
    for env_path in env_files_to_try:
        if env_path.exists():
            load_dotenv(env_path, override=False)
            break

    # Create and return config
    return MarisConfig()


def create_default_env_file(path: Path = Path(".env.example")) -> None:
    """
    Create an example .env file with all available configuration options.

    Args:
        path: Path where to create the example file
    """
    example_content = """# MARIS Configuration
# Copy this file to .env and customize as needed

# Storage Configuration
MARIS_DATA_DIR=~/.maris

# Ollama Configuration
MARIS_OLLAMA_HOST=http://localhost:11434

# Embedding Model Configuration
MARIS_EMBEDDING_MODEL=nomic-embed-text
MARIS_EMBEDDING_BATCH_SIZE=32

# Q&A Agent Model Configuration
MARIS_QA_MODEL=qwen2.5:7b
MARIS_QA_TEMPERATURE=0.7
MARIS_QA_MAX_TOKENS=2048

# Documentation Agent Model Configuration
MARIS_DOC_MODEL=qwen2.5:7b
MARIS_DOC_TEMPERATURE=0.3
MARIS_DOC_MAX_TOKENS=4096

# Retrieval Configuration
MARIS_MAX_SEARCH_RESULTS=20
MARIS_MAX_CONTEXT_SYMBOLS=10

# Performance Configuration
MARIS_ENABLE_CACHING=true
MARIS_PARALLEL_INDEXING=false

# Logging Configuration
MARIS_LOG_LEVEL=INFO
# MARIS_LOG_FILE=/path/to/maris.log

# Example: Use different models for different tasks
# MARIS_EMBEDDING_MODEL=nomic-embed-text
# MARIS_QA_MODEL=qwen2.5:14b          # Larger model for better Q&A
# MARIS_DOC_MODEL=qwen2.5:7b          # Smaller model for docs

# Example: Use faster models for development
# MARIS_QA_MODEL=qwen2.5:3b
# MARIS_DOC_MODEL=qwen2.5:3b

# Example: Use specialized models
# MARIS_QA_MODEL=deepseek-coder:6.7b  # Code-specific model
# MARIS_DOC_MODEL=qwen2.5:7b          # General model for docs
"""

    path.write_text(example_content)
    print(f"Created example configuration file: {path}")
    print("Copy to .env and customize as needed")


if __name__ == "__main__":
    # Create example .env file
    create_default_env_file()

    # Load and display current configuration
    config = load_config()
    print("\nCurrent Configuration:")
    print(f"  Data Directory: {config.data_dir}")
    print(f"  Ollama Host: {config.ollama_host}")
    print(f"  Embedding Model: {config.embedding_model}")
    print(f"  Q&A Model: {config.qa_model}")
    print(f"  Documentation Model: {config.doc_model}")

# Made with Bob
