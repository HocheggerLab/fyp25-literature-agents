"""Simple API for single-agent literature analysis.

This module provides a high-level interface for analyzing PubMed literature
with minimal code. Perfect for quick analyses and notebooks.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from loguru import logger

from fyp25_literature_agents.llm_agents import LiteratureAgent
from fyp25_literature_agents.logging_config import setup_logging
from fyp25_literature_agents.pubmed_search import PubMedSearchConfig, PubMedSearcher


async def analyze_gene_literature(
    gene: str,
    search_query: str | None = None,
    max_results: int = 10,
    model: str = "gpt-5-nano",
    prompt_style: str = "simple",
    max_concurrent: int = 10,
    date_from: str | None = None,
    date_to: str | None = None,
    save_dir: str = "results",
    ncbi_email: str | None = None,
    openai_api_key: str | None = None,
    verbose: bool = False,
) -> dict:
    """Analyze PubMed literature for a gene with a single function call.

    This is a high-level convenience function that:
    1. Searches PubMed for articles
    2. Analyzes them with an LLM agent
    3. Saves results to JSON
    4. Returns structured data

    Args:
        gene: Target gene symbol (e.g., "PPP2R2A")
        search_query: PubMed query. If None, uses "{gene}[Title/Abstract] AND cancer[Title/Abstract]"
        max_results: Maximum number of articles to analyze (default: 10)
        model: OpenAI model to use (default: "gpt-5-nano")
        prompt_style: "simple" or "detailed" (default: "simple")
        max_concurrent: Maximum concurrent API requests for parallel processing (default: 10)
        date_from: Start date in YYYY/MM/DD format (optional)
        date_to: End date in YYYY/MM/DD format (optional)
        save_dir: Directory to save results (default: "results")
        ncbi_email: NCBI email (if None, reads from NCBI_EMAIL env var)
        openai_api_key: OpenAI API key (if None, reads from OPENAI_API_KEY env var)
        verbose: Show DEBUG level logs (default: False). Use LOG_FILE env var to save logs to file.

    Returns:
        Dictionary with keys:
            - "gene": Gene symbol
            - "search_query": Query used
            - "total_articles": Number of articles found
            - "analyzed_articles": Number successfully analyzed
            - "results": List of AnalyzedArticle dictionaries
            - "summary": Summary statistics
            - "output_file": Path to saved JSON file
            - "timestamp": ISO timestamp

    Example:
        >>> results = await analyze_gene_literature(
        ...     gene="PPP2R2A",
        ...     max_results=5
        ... )
        >>> print(f"Analyzed {results['analyzed_articles']} articles")
        >>> print(f"Results saved to: {results['output_file']}")
    """
    # Setup logging
    setup_logging(verbose=verbose)

    logger.info(f"Starting analysis for gene: {gene}")

    # Get credentials from env if not provided
    ncbi_email = ncbi_email or os.getenv("NCBI_EMAIL")
    if not ncbi_email:
        raise ValueError(
            "NCBI email required. Set NCBI_EMAIL env var or pass ncbi_email parameter"
        )

    # Build search query if not provided
    if search_query is None:
        search_query = f"{gene}[Title/Abstract] AND cancer[Title/Abstract]"
        logger.debug(f"Using default query: {search_query}")

    # Step 1: Search PubMed
    logger.debug(f"Searching PubMed with query: {search_query}")
    config = PubMedSearchConfig(email=ncbi_email, retmax=max_results)
    searcher = PubMedSearcher(config)

    articles = searcher.search_and_fetch(
        query=search_query,
        max_results=max_results,
        date_from=date_from,
        date_to=date_to,
    )

    logger.debug(f"Found {len(articles)} articles from PubMed")

    if len(articles) == 0:
        logger.warning("No articles found. Returning empty results.")
        return {
            "gene": gene,
            "search_query": search_query,
            "total_articles": 0,
            "analyzed_articles": 0,
            "results": [],
            "summary": {},
            "output_file": None,
            "timestamp": datetime.now().isoformat(),
        }

    # Step 2: Analyze with LLM
    logger.debug(f"Initializing LiteratureAgent with model: {model}")
    agent = LiteratureAgent(
        model=model, prompt_style=prompt_style, api_key=openai_api_key
    )

    logger.info(f"Analyzing {len(articles)} articles...")
    analyzed_results = await agent.batch_analyze(articles, gene=gene, max_concurrent=max_concurrent)

    logger.info(f"Analysis complete: {len(analyzed_results)}/{len(articles)} successful")

    # Step 3: Generate summary statistics
    summary = _generate_summary(analyzed_results)

    # Step 4: Save results
    output_file = _save_results(
        gene=gene,
        search_query=search_query,
        results=analyzed_results,
        summary=summary,
        save_dir=save_dir,
    )

    # Step 5: Return structured data
    return {
        "gene": gene,
        "search_query": search_query,
        "total_articles": len(articles),
        "analyzed_articles": len(analyzed_results),
        "results": [r.model_dump() for r in analyzed_results],
        "summary": summary,
        "output_file": str(output_file),
        "timestamp": datetime.now().isoformat(),
    }


def _generate_summary(results: list) -> dict:
    """Generate summary statistics from analysis results.

    Args:
        results: List of AnalyzedArticle objects

    Returns:
        Dictionary with summary statistics
    """
    if not results:
        return {}

    total_cancers = sum(len(r.analysis.cancers) for r in results)
    tumor_suppressor_count = 0
    oncogene_count = 0
    both_count = 0
    unclear_count = 0
    high_confidence_count = 0
    needs_full_text_count = 0

    cancer_types = set()

    for result in results:
        # Count roles
        for cancer in result.analysis.cancers:
            cancer_types.add(cancer.type)
            role = cancer.role.value if hasattr(cancer.role, "value") else cancer.role

            if role == "tumor_suppressor":
                tumor_suppressor_count += 1
            elif role == "oncogene":
                oncogene_count += 1
            elif role == "both":
                both_count += 1
            else:
                unclear_count += 1

        # Count confidence
        if result.analysis.confidence == "high":
            high_confidence_count += 1

        if result.analysis.needs_full_text:
            needs_full_text_count += 1

    return {
        "total_articles_analyzed": len(results),
        "total_cancer_classifications": total_cancers,
        "unique_cancer_types": len(cancer_types),
        "cancer_types_found": sorted(cancer_types),
        "role_distribution": {
            "tumor_suppressor": tumor_suppressor_count,
            "oncogene": oncogene_count,
            "both": both_count,
            "unclear": unclear_count,
        },
        "quality_metrics": {
            "high_confidence_count": high_confidence_count,
            "high_confidence_percentage": round(
                high_confidence_count / len(results) * 100, 1
            ),
            "needs_full_text_count": needs_full_text_count,
            "needs_full_text_percentage": round(
                needs_full_text_count / len(results) * 100, 1
            ),
        },
    }


def _save_results(
    gene: str,
    search_query: str,
    results: list,
    summary: dict,
    save_dir: str = "results",
) -> Path:
    """Save analysis results to JSON file.

    Args:
        gene: Gene symbol
        search_query: Query used
        results: List of AnalyzedArticle objects
        summary: Summary statistics
        save_dir: Directory to save results

    Returns:
        Path to saved file
    """
    # Create save directory if it doesn't exist
    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Use search query for filename (if available), otherwise fall back to gene name
    if search_query and search_query != f"{gene}[Title/Abstract] AND cancer[Title/Abstract]":
        # Extract meaningful part from query and sanitize for filename
        # Remove common PubMed syntax and convert to filename-safe format
        query_base = search_query.replace("[Title/Abstract]", "").replace("[Title]", "").replace("[Abstract]", "")
        query_base = query_base.replace(" AND ", "_").replace(" OR ", "_").replace(" NOT ", "_")
        query_base = query_base.replace("(", "").replace(")", "").replace("[", "").replace("]", "")
        query_base = query_base.replace(" ", "_").replace("/", "_").replace("\\", "_")
        # Remove multiple underscores and trim
        query_base = "_".join(filter(None, query_base.split("_")))
        # Limit length to avoid overly long filenames
        if len(query_base) > 100:
            query_base = query_base[:100]
        filename = f"{query_base}_{timestamp}.json"
    else:
        # Fall back to gene name
        filename = f"{gene}_{timestamp}.json"

    filepath = save_path / filename

    # Prepare output data
    output_data = {
        "gene": gene,
        "search_query": search_query,
        "timestamp": datetime.now().isoformat(),
        "summary": summary,
        "results": [r.model_dump() for r in results],
    }

    # Save to JSON
    with open(filepath, "w") as f:
        json.dump(output_data, f, indent=2)

    logger.debug(f"Results saved to: {filepath}")
    return filepath


# Synchronous wrapper for convenience
def analyze_gene_literature_sync(*args, **kwargs) -> dict:
    """Synchronous wrapper for analyze_gene_literature.

    Use this if you're not in an async context.

    Example:
        >>> results = analyze_gene_literature_sync(
        ...     gene="PPP2R2A",
        ...     max_results=5
        ... )
    """
    import asyncio

    return asyncio.run(analyze_gene_literature(*args, **kwargs))
