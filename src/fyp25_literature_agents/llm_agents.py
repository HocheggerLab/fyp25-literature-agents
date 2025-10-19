"""LLM agent implementations for literature analysis."""

import json
import os
from datetime import UTC, datetime

from loguru import logger
from openai import AsyncOpenAI
from pydantic import ValidationError

from fyp25_literature_agents.prompts import build_analysis_prompt, build_simple_prompt
from fyp25_literature_agents.pubmed_search import PubMedArticle
from fyp25_literature_agents.schemas import (
    AgentAnalysis,
    AgentResult,
    AnalyzedArticle,
)


class LiteratureAgent:
    """Agent for analyzing scientific literature using LLM."""

    def __init__(
        self,
        model: str = "gpt-5-nano",
        prompt_style: str = "simple",
        api_key: str | None = None,
    ):
        """Initialize the literature analysis agent.

        Args:
            model: OpenAI model name (e.g., "gpt-4o-mini", "gpt-5-nano")
            prompt_style: Style of prompt to use ("simple" or "detailed", default: "simple")
            api_key: OpenAI API key (if None, reads from OPENAI_API_KEY env var)
        """
        self.model = model
        self.prompt_style = prompt_style

        # Initialize OpenAI client
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not provided and OPENAI_API_KEY not set")

        self.client = AsyncOpenAI(api_key=api_key)
        logger.debug(f"Initialized LiteratureAgent with model: {model}")

    async def analyze_article(
        self,
        article: PubMedArticle,
        gene: str,
    ) -> AnalyzedArticle:
        """Analyze a PubMed article for gene-cancer relationships.

        Args:
            article: PubMedArticle object to analyze
            gene: Target gene to focus analysis on (e.g., 'PPP2R2A')

        Returns:
            AnalyzedArticle with complete analysis results

        Raises:
            ValueError: If analysis fails or returns invalid data
            RuntimeError: If LLM request fails
        """
        logger.debug(f"Analyzing article {article.pmid} for gene {gene}")

        # Build appropriate prompt based on style
        if self.prompt_style == "simple":
            prompt = build_simple_prompt(gene, article.abstract)
        else:
            prompt = build_analysis_prompt(gene, article.abstract)

        try:
            # Query OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a scientific literature analyst specializing in cancer genetics. You extract structured information from abstracts and respond only with valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},  # Ensures JSON response
                reasoning_effort="minimal",
            )

            response_text = response.choices[0].message.content

            # Log response for debugging
            logger.debug(f"LLM response for {article.pmid}: {response_text[:200]}...")

            # Parse JSON response
            analysis_data = self._parse_json_response(response_text)

            # Validate with Pydantic
            try:
                analysis = AgentAnalysis(**analysis_data)
            except ValidationError as ve:
                # Log the full response and parsed data for debugging
                logger.debug(f"Validation failed for {article.pmid}")
                logger.debug(f"Full LLM response: {response_text}")
                logger.debug(f"Parsed data keys: {list(analysis_data.keys())}")
                logger.debug(f"Validation error: {ve}")

                # Try to fix incomplete/invalid response
                logger.debug(f"Attempting to fix incomplete response for {article.pmid}")

                # Fix confidence (invalid values like "moderate", "low_to_medium")
                if "confidence" not in analysis_data or analysis_data["confidence"] not in ["high", "medium", "low"]:
                    old_val = analysis_data.get("confidence", "missing")
                    analysis_data["confidence"] = "low"
                    logger.debug(f"Fixed confidence: {old_val} -> low")

                # Fix reasoning (might be nested in "conclusion" object)
                if "reasoning" not in analysis_data:
                    # Check if reasoning is in a "conclusion" object
                    if "conclusion" in analysis_data and isinstance(analysis_data["conclusion"], dict):
                        if "reasoning" in analysis_data["conclusion"]:
                            analysis_data["reasoning"] = analysis_data["conclusion"]["reasoning"]
                            logger.debug("Extracted reasoning from conclusion object")
                        else:
                            analysis_data["reasoning"] = "Incomplete analysis from LLM"
                    else:
                        analysis_data["reasoning"] = "Incomplete analysis from LLM"
                        logger.debug("Added default reasoning")

                # Fix needs_full_text
                if "needs_full_text" not in analysis_data:
                    analysis_data["needs_full_text"] = True
                    logger.debug("Added default needs_full_text: true")

                # Fix study_types (empty dict or missing required fields)
                if "study_types" not in analysis_data or not isinstance(analysis_data["study_types"], dict):
                    analysis_data["study_types"] = {}

                st = analysis_data["study_types"]
                if "clinical" not in st:
                    st["clinical"] = False
                    logger.debug("Added default study_types.clinical: false")
                if "basic" not in st:
                    st["basic"] = False
                    logger.debug("Added default study_types.basic: false")
                if "clinical_description" not in st:
                    st["clinical_description"] = st.get("clinical_description", None)
                if "basic_description" not in st:
                    st["basic_description"] = st.get("basic_description", None)

                # Fix mechanisms
                if "mechanisms" not in analysis_data:
                    analysis_data["mechanisms"] = {
                        "tumor_suppressor_mechanisms": [],
                        "oncogenic_mechanisms": [],
                        "mutations_described": False,
                        "mutation_details": None,
                    }
                    logger.debug("Added default mechanisms")
                else:
                    # Fix mutation_details if it's a list or dict (should be string or null)
                    mech = analysis_data["mechanisms"]
                    if "mutation_details" in mech and isinstance(mech["mutation_details"], (list, dict)):
                        # Convert to string
                        mech["mutation_details"] = str(mech["mutation_details"])
                        logger.debug("Converted mutation_details from list/dict to string")

                # Fix cancers (empty if missing, and fix invalid role values)
                if "cancers" not in analysis_data:
                    analysis_data["cancers"] = []
                    logger.debug("Added default cancers: empty list")
                else:
                    # Fix invalid role values ("unknown" -> "unclear")
                    for cancer in analysis_data["cancers"]:
                        if "role" in cancer and cancer["role"] not in ["tumor_suppressor", "oncogene", "both", "unclear"]:
                            old_role = cancer["role"]
                            cancer["role"] = "unclear"
                            logger.debug(f"Fixed cancer role: {old_role} -> unclear")

                        # Fix invalid confidence values in cancers
                        if "confidence" in cancer and cancer["confidence"] not in ["high", "medium", "low"]:
                            old_conf = cancer["confidence"]
                            cancer["confidence"] = "low"
                            logger.debug(f"Fixed cancer confidence: {old_conf} -> low")

                        # Remove extra fields not in schema (gene, notes, etc.)
                        valid_cancer_fields = {"type", "role", "evidence_mentioned", "confidence", "quote_from_abstract"}
                        extra_fields = set(cancer.keys()) - valid_cancer_fields
                        if extra_fields:
                            for field in extra_fields:
                                del cancer[field]
                            logger.debug(f"Removed extra cancer fields: {extra_fields}")

                # Remove top-level extra fields not in schema
                valid_top_fields = {"cancers", "study_types", "mechanisms", "confidence", "reasoning", "ambiguities", "needs_full_text"}
                extra_top_fields = set(analysis_data.keys()) - valid_top_fields
                if extra_top_fields:
                    for field in extra_top_fields:
                        del analysis_data[field]
                    logger.debug(f"Removed extra top-level fields: {extra_top_fields}")

                # Try validation again
                try:
                    analysis = AgentAnalysis(**analysis_data)
                    logger.debug(f"Successfully recovered incomplete response for {article.pmid}")
                except ValidationError as ve2:
                    logger.error(f"Could not recover response for {article.pmid}: {ve2}")
                    raise ValueError(f"Invalid analysis format even after adding defaults: {ve2}") from ve2

            # Extract year from publication_date if available
            year = ""
            if article.publication_date:
                year = article.publication_date.split("-")[0]

            # Create complete analyzed article
            analyzed = AnalyzedArticle(
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

            logger.debug(
                f"Successfully analyzed {article.pmid}: "
                f"Found {len(analysis.cancers)} cancer(s), "
                f"confidence={analysis.confidence}"
            )

            return analyzed

        except ValidationError as e:
            logger.error(f"Validation error for {article.pmid}: {e}")
            raise ValueError(f"Invalid analysis format: {e}") from e

        except Exception as e:
            logger.error(f"Analysis failed for {article.pmid}: {e}")
            raise RuntimeError(f"Failed to analyze article: {e}") from e

    def _parse_json_response(self, response_text: str) -> dict:
        """Parse JSON from LLM response, handling markdown code blocks.

        Args:
            response_text: Raw text response from LLM

        Returns:
            Parsed dictionary

        Raises:
            ValueError: If JSON parsing fails
        """
        # Remove markdown code blocks if present
        text = response_text.strip()

        if text.startswith("```json"):
            text = text[7:]  # Remove ```json
        elif text.startswith("```"):
            text = text[3:]  # Remove ```

        if text.endswith("```"):
            text = text[:-3]  # Remove trailing ```

        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {text[:200]}...")
            raise ValueError(f"Invalid JSON response: {e}") from e

    async def create_agent_result(
        self,
        article: PubMedArticle,
        gene: str,
    ) -> AgentResult:
        """Create a complete AgentResult with metadata.

        This is useful for dual-agent scenarios where we need to track
        which model produced which result.

        Args:
            article: PubMedArticle object to analyze
            gene: Target gene to focus analysis on

        Returns:
            AgentResult with model metadata and analysis
        """
        analyzed = await self.analyze_article(article, gene)

        return AgentResult(
            model=self.model,
            timestamp=datetime.now(UTC).isoformat(),
            analysis=analyzed.analysis,
        )

    async def batch_analyze(
        self,
        articles: list[PubMedArticle],
        gene: str,
        max_concurrent: int = 10,
        show_progress: bool = True,
    ) -> list[AnalyzedArticle]:
        """Analyze multiple articles in parallel.

        Args:
            articles: List of PubMedArticle objects to analyze
            gene: Target gene for all analyses
            max_concurrent: Maximum number of concurrent API calls (default: 10)
            show_progress: Show progress bar (default: True)

        Returns:
            List of AnalyzedArticle objects (in same order as input)
        """
        import asyncio

        from tqdm.auto import tqdm

        logger.debug(f"Analyzing {len(articles)} articles for {gene} (max {max_concurrent} concurrent)")

        # Create progress bar if requested (tqdm for better Jupyter support)
        if show_progress:
            progress = tqdm(
                total=len(articles),
                desc=f"Analyzing {gene}",
                unit=" articles",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
            )
        else:
            progress = None

        # Create tasks for all articles
        async def analyze_with_error_handling(
            article: PubMedArticle, index: int
        ) -> tuple[int, AnalyzedArticle | None]:
            """Analyze single article with error handling."""
            try:
                logger.debug(f"Processing article {index + 1}/{len(articles)}: {article.pmid}")
                analyzed = await self.analyze_article(article, gene)
                logger.debug(f"✓ Completed {index + 1}/{len(articles)}: {article.pmid}")
                if progress:
                    progress.update(1)
                return (index, analyzed)
            except Exception as e:
                logger.error(f"✗ Failed to analyze {article.pmid}: {e}")
                if progress:
                    progress.update(1)
                return (index, None)

        try:
            # Process in batches to respect rate limits
            results_with_indices = []
            for i in range(0, len(articles), max_concurrent):
                batch = articles[i : i + max_concurrent]
                batch_start = i

                logger.debug(
                    f"Processing batch {i // max_concurrent + 1} "
                    f"({len(batch)} articles, positions {i + 1}-{i + len(batch)})"
                )

                # Run batch in parallel
                batch_tasks = [
                    analyze_with_error_handling(article, batch_start + j)
                    for j, article in enumerate(batch)
                ]
                batch_results = await asyncio.gather(*batch_tasks)
                results_with_indices.extend(batch_results)

            # Sort by original index and filter out failures
            results_with_indices.sort(key=lambda x: x[0])
            results = [r for _, r in results_with_indices if r is not None]

            logger.debug(
                f"Batch analysis complete: {len(results)}/{len(articles)} successful"
            )
            return results

        finally:
            # Close progress bar
            if progress:
                progress.close()
