"""Model comparison orchestrator for multi-provider analysis."""

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger
from tqdm.auto import tqdm

from fyp25_literature_agents.logging_config import setup_logging
from fyp25_literature_agents.prompts import build_simple_prompt
from fyp25_literature_agents.providers import (
    AnthropicProvider,
    DeepSeekProvider,
    GoogleProvider,
    GroqProvider,
    LLMProvider,
    OpenAIProvider,
)
from fyp25_literature_agents.pubmed_search import (
    PubMedArticle,
    PubMedSearchConfig,
    PubMedSearcher,
)
from fyp25_literature_agents.schemas import AnalyzedArticle

# Default model configurations
DEFAULT_MODELS = {
    "openai_gpt5_mini": {
        "provider_class": OpenAIProvider,
        "model_id": "gpt-5-mini",
        "api_key_env": "OPENAI_API_KEY",
        "cost_per_1m_input": 0.25,
        "cost_per_1m_output": 2.00,
        "speed_tokens_per_sec": 150,
        "description": "Best balanced choice",
    },
    "anthropic_haiku_4_5": {
        "provider_class": AnthropicProvider,
        "model_id": "claude-haiku-4-5-20251001",
        "api_key_env": "ANTHROPIC_API_KEY",
        "cost_per_1m_input": 1.00,
        "cost_per_1m_output": 5.00,
        "speed_tokens_per_sec": 120,
        "description": "Budget-friendly accuracy",
    },
    "google_gemini_2_5_flash": {
        "provider_class": GoogleProvider,
        "model_id": "gemini-2.5-flash",
        "api_key_env": "GOOGLE_API_KEY",
        "cost_per_1m_input": 0.075,
        "cost_per_1m_output": 0.30,
        "speed_tokens_per_sec": 200,
        "description": "Fast with higher rate limits",
    },
    "deepseek_v3_1": {
        "provider_class": DeepSeekProvider,
        "model_id": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
        "cost_per_1m_input": 0.23,
        "cost_per_1m_output": 0.90,
        "speed_tokens_per_sec": 80,
        "description": "Cost optimization leader",
    },
    "groq_llama3_1_8b": {
        "provider_class": GroqProvider,
        "model_id": "llama-3.1-8b-instant",
        "api_key_env": "GROQ_API_KEY",
        "cost_per_1m_input": 0.05,
        "cost_per_1m_output": 0.08,
        "speed_tokens_per_sec": 2600,
        "description": "Speed champion",
    },
}


def _sanitize_folder_name(search_term: str) -> str:
    """Convert search term to valid folder name.

    Args:
        search_term: Original search term

    Returns:
        Sanitized folder name
    """
    # Replace spaces and special chars with underscores
    sanitized = re.sub(r"[^\w\s-]", "_", search_term)
    sanitized = re.sub(r"[-\s]+", "_", sanitized)
    return sanitized.strip("_")


def _extract_gene_from_search(search_term: str) -> str:
    """Try to extract gene name from search term.

    Args:
        search_term: PubMed search term

    Returns:
        Extracted gene or first word of search term
    """
    # Simple extraction - take first word/term
    parts = search_term.split()
    if parts:
        # Remove common PubMed operators
        gene = parts[0].strip("()[]").upper()
        return gene
    return "UNKNOWN"


async def run_model_comparison(
    search_term: str,
    max_results: int = 20,
    num_repeats: int = 5,
    output_dir: str = "model_comparison_results",
    models_config: dict | None = None,
    gene: str | None = None,
    prompt_style: str = "simple",
    ncbi_email: str | None = None,
) -> dict:
    """Run comprehensive model comparison study.

    This function:
    1. Searches PubMed once (shared dataset)
    2. Analyzes abstracts with 5 different LLM providers
    3. Runs each provider 5 times (to measure consistency)
    4. Saves all results to organized folder structure
    5. Generates master CSV with all results

    Args:
        search_term: PubMed search query (e.g., "PPP2R2A AND cancer")
        max_results: Maximum number of articles to retrieve (default: 20)
        num_repeats: Number of times to run each model (default: 5)
        output_dir: Base output directory (default: "model_comparison_results")
        models_config: Custom model configuration (uses DEFAULT_MODELS if None)
        gene: Target gene symbol (auto-extracted from search_term if None)
        prompt_style: Prompt style to use ("simple" or "detailed", default: "simple")
        ncbi_email: NCBI email (reads from env if None)

    Environment Variables:
        LOGURU_LEVEL: Set to DEBUG for detailed logs, INFO for clean output (default: INFO)

    Returns:
        Dictionary with results summary:
        {
            "search_term": str,
            "gene": str,
            "num_articles": int,
            "models_tested": list[dict],
            "num_repeats": int,
            "output_dir": Path,
            "csv_file": Path,
            "json_files": list[Path],
            "metadata_file": Path,
            "summary_stats": dict,
            "failed_analyses": list[dict]
        }

    Raises:
        ValueError: If no API keys found or PubMed search fails
        RuntimeError: If all model analyses fail
    """
    # Setup logging (respects LOGURU_LEVEL environment variable)
    setup_logging()

    start_time = datetime.now(UTC)

    # Use default models if none provided
    if models_config is None:
        models_config = DEFAULT_MODELS

    # Extract gene if not provided
    if gene is None:
        gene = _extract_gene_from_search(search_term)
        print(f"Auto-extracted gene: {gene}")

    # Create output directory
    folder_name = _sanitize_folder_name(search_term)
    output_path = Path(output_dir) / folder_name
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*70}")
    print(f"Model Comparison Study")
    print(f"{'='*70}")
    print(f"Search term: {search_term}")
    print(f"Gene: {gene}")
    print(f"Max results: {max_results}")
    print(f"Models to test: {len(models_config)}")
    print(f"Repeats per model: {num_repeats}")
    print(f"Output directory: {output_path}")
    print(f"{'='*70}\n")

    # Step 1: Search PubMed
    print(f"[1/4] Searching PubMed for '{search_term}'...")

    ncbi_email = ncbi_email or os.getenv("NCBI_EMAIL")
    if not ncbi_email:
        raise ValueError("NCBI email not provided and NCBI_EMAIL not set in environment")

    config = PubMedSearchConfig(email=ncbi_email)
    searcher = PubMedSearcher(config)

    try:
        articles = searcher.search_and_fetch(search_term, max_results=max_results)
        if not articles:
            raise ValueError(f"No articles found for search term: {search_term}")

        print(f"✓ Retrieved {len(articles)} articles from PubMed\n")

    except Exception as e:
        logger.error(f"PubMed search failed: {e}")
        raise ValueError(f"Failed to search PubMed: {e}") from e

    # Save PubMed articles
    pubmed_file = output_path / "pubmed_articles.json"
    with open(pubmed_file, "w") as f:
        json.dump(
            [
                {
                    "pmid": a.pmid,
                    "title": a.title,
                    "abstract": a.abstract,
                    "authors": a.authors,
                    "journal": a.journal,
                    "publication_date": a.publication_date,
                    "doi": a.doi,
                }
                for a in articles
            ],
            f,
            indent=2,
        )

    print(f"[2/4] Initializing {len(models_config)} LLM providers...")

    # Step 2: Initialize providers
    providers = {}
    models_metadata = []

    for model_name, config in models_config.items():
        api_key = os.getenv(config["api_key_env"])
        if not api_key:
            logger.warning(
                f"Skipping {model_name}: {config['api_key_env']} not set in environment"
            )
            print(f"  ⚠ Skipping {model_name} (no API key)")
            continue

        try:
            provider_class = config["provider_class"]
            logger.info(f"Initializing {model_name} with {provider_class.__name__}")
            provider = provider_class(
                model_id=config["model_id"], api_key=api_key, temperature=0.2
            )
            providers[model_name] = provider

            models_metadata.append(
                {
                    "friendly_name": model_name,
                    "model_id": config["model_id"],
                    "provider": provider_class.__name__.replace("Provider", "").lower(),
                    "cost_per_1m_input": config["cost_per_1m_input"],
                    "cost_per_1m_output": config["cost_per_1m_output"],
                    "speed_tokens_per_sec": config["speed_tokens_per_sec"],
                    "description": config["description"],
                }
            )

            print(f"  ✓ {model_name} ({config['model_id']})")

        except Exception as e:
            import traceback
            logger.error(f"Failed to initialize {model_name}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            print(f"  ✗ {model_name} failed: {e}")
            print(f"     Error details: {traceback.format_exc()}")

    if not providers:
        raise ValueError("No providers could be initialized. Check your API keys.")

    print(f"\n[3/4] Running analyses...")
    print(f"  Total analyses to run: {len(articles)} articles × {len(providers)} models × {num_repeats} repeats")
    print(f"  = {len(articles) * len(providers) * num_repeats} total analyses\n")

    # Step 3: Run analysis grid
    json_files = []
    failed_analyses = []
    total_analyses = len(providers) * num_repeats

    with tqdm(
        total=total_analyses,
        desc="Overall Progress",
        unit=" run",
    ) as pbar:
        for model_name, provider in providers.items():
            for repeat_num in range(1, num_repeats + 1):
                pbar.set_description(f"{model_name} (repeat {repeat_num}/{num_repeats})")

                try:
                    # Analyze all articles
                    # Use lower concurrency for Groq to avoid rate limits (6K TPM)
                    max_concurrent = 2 if "groq" in model_name.lower() else 10
                    analyzed_articles = await _analyze_batch(
                        provider=provider,
                        articles=articles,
                        gene=gene,
                        prompt_style=prompt_style,
                        max_concurrent=max_concurrent,
                    )

                    # Check if we got any results
                    if len(analyzed_articles) == 0:
                        logger.warning(
                            f"⚠ {model_name} repeat {repeat_num}: 0 articles analyzed! All failed."
                        )
                        print(f"  ⚠ {model_name} repeat {repeat_num}: 0 articles analyzed")

                    # Save results (even if empty, to track the attempt)
                    json_file = output_path / f"{model_name}_repeat{repeat_num}.json"
                    _save_analysis_results(
                        analyzed_articles=analyzed_articles,
                        output_file=json_file,
                        search_term=search_term,
                        gene=gene,
                        model_name=model_name,
                        model_id=provider.model_id,
                        repeat_num=repeat_num,
                    )

                    json_files.append(json_file)

                    logger.info(
                        f"✓ {model_name} repeat {repeat_num}: {len(analyzed_articles)}/{len(articles)} articles analyzed"
                    )
                    if len(analyzed_articles) > 0:
                        print(f"  ✓ {model_name} repeat {repeat_num}: {len(analyzed_articles)} articles")

                except Exception as e:
                    logger.error(f"✗ {model_name} repeat {repeat_num} failed: {e}")
                    failed_analyses.append(
                        {
                            "model_name": model_name,
                            "repeat_num": repeat_num,
                            "error": str(e),
                        }
                    )

                pbar.update(1)

    # Step 4: Generate CSV
    print("\n[4/4] Generating comparison CSV...")

    from fyp25_literature_agents.export_comparison import export_comparison_to_csv

    csv_file = output_path / "comparison_results.csv"
    try:
        export_comparison_to_csv(
            json_files=json_files, output_csv=csv_file, search_term=search_term, gene=gene
        )
        print(f"✓ CSV saved to: {csv_file}")
    except Exception as e:
        logger.error(f"Failed to generate CSV: {e}")
        csv_file = None

    # Save metadata
    end_time = datetime.now(UTC)
    metadata = {
        "search_term": search_term,
        "gene": gene,
        "num_articles": len(articles),
        "models_tested": models_metadata,
        "num_repeats": num_repeats,
        "total_analyses_attempted": len(providers) * num_repeats,
        "total_analyses_successful": len(json_files),
        "total_analyses_failed": len(failed_analyses),
        "started_at": start_time.isoformat(),
        "completed_at": end_time.isoformat(),
        "duration_seconds": (end_time - start_time).total_seconds(),
        "pubmed_search_config": {
            "max_results": max_results,
            "actual_results": len(articles),
        },
        "failed_analyses": failed_analyses,
    }

    metadata_file = output_path / "metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)

    # Print summary
    print(f"\n{'='*70}")
    print(f"Comparison Study Complete!")
    print(f"{'='*70}")
    print(f"Duration: {metadata['duration_seconds']:.1f} seconds")
    print(f"Successful analyses: {len(json_files)}/{total_analyses}")
    if failed_analyses:
        print(f"Failed analyses: {len(failed_analyses)}")
    print(f"\nResults saved to: {output_path}")
    print(f"  - CSV: {csv_file.name if csv_file else 'Failed to generate'}")
    print(f"  - Metadata: {metadata_file.name}")
    print(f"  - JSON files: {len(json_files)}")
    print(f"{'='*70}\n")

    return {
        "search_term": search_term,
        "gene": gene,
        "num_articles": len(articles),
        "models_tested": models_metadata,
        "num_repeats": num_repeats,
        "output_dir": output_path,
        "csv_file": csv_file,
        "json_files": json_files,
        "metadata_file": metadata_file,
        "summary_stats": metadata,
        "failed_analyses": failed_analyses,
    }


async def _analyze_batch(
    provider: LLMProvider,
    articles: list[PubMedArticle],
    gene: str,
    prompt_style: str = "simple",
    max_concurrent: int = 10,
) -> list[AnalyzedArticle]:
    """Analyze a batch of articles with a single provider in parallel.

    Args:
        provider: LLM provider instance
        articles: List of articles to analyze
        gene: Target gene
        prompt_style: Prompt style
        max_concurrent: Maximum concurrent API calls (default: 10)

    Returns:
        List of analyzed articles
    """

    async def _analyze_single(article: PubMedArticle) -> AnalyzedArticle | None:
        """Analyze a single article with error handling."""
        try:
            # Build prompt
            prompt = build_simple_prompt(gene, article.abstract)

            # Analyze
            analysis = await provider.analyze_abstract(article.abstract, gene, prompt)

            # Extract year from publication_date
            year = ""
            if article.publication_date:
                year = article.publication_date.split("-")[0]

            # Create analyzed article
            return AnalyzedArticle(
                pmid=article.pmid,
                doi=article.doi,
                title=article.title,
                year=year,
                authors=article.authors,
                journal=article.journal,
                abstract=article.abstract,
                search_gene=gene,
                analysis=analysis,
            )

        except Exception as e:
            import traceback
            logger.error(f"Failed to analyze {article.pmid} with {provider}: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None

    # Process articles in batches with concurrency limit
    analyzed = []
    for i in range(0, len(articles), max_concurrent):
        batch = articles[i : i + max_concurrent]
        batch_results = await asyncio.gather(*[_analyze_single(article) for article in batch])
        # Filter out None (failed analyses)
        analyzed.extend([result for result in batch_results if result is not None])

    return analyzed


def _save_analysis_results(
    analyzed_articles: list[AnalyzedArticle],
    output_file: Path,
    search_term: str,
    gene: str,
    model_name: str,
    model_id: str,
    repeat_num: int,
) -> None:
    """Save analysis results to JSON file.

    Args:
        analyzed_articles: List of analyzed articles
        output_file: Path to output JSON file
        search_term: Search term used
        gene: Target gene
        model_name: Friendly model name
        model_id: Actual model ID
        repeat_num: Repeat number
    """
    results = {
        "metadata": {
            "search_term": search_term,
            "gene": gene,
            "model_name": model_name,
            "model_id": model_id,
            "repeat_num": repeat_num,
            "timestamp": datetime.now(UTC).isoformat(),
            "num_articles": len(analyzed_articles),
        },
        "results": [
            {
                "pmid": a.pmid,
                "doi": a.doi,
                "title": a.title,
                "year": a.year,
                "authors": a.authors,
                "journal": a.journal,
                "abstract": a.abstract,
                "search_gene": a.search_gene,
                "analysis": a.analysis.model_dump(),
            }
            for a in analyzed_articles
        ],
    }

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
