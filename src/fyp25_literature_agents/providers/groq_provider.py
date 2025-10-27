"""Groq provider implementation."""

import asyncio
import json

from loguru import logger
from openai import AsyncOpenAI, RateLimitError
from pydantic import ValidationError

from fyp25_literature_agents.providers.base import LLMProvider
from fyp25_literature_agents.schemas import AgentAnalysis


class GroqProvider(LLMProvider):
    """Groq API provider for literature analysis.

    Uses Llama 3.3 70B via Groq's ultra-fast LPU infrastructure.
    Best for speed - processes at 2600+ tokens/second.
    """

    def __init__(
        self,
        model_id: str = "llama-3.3-70b-versatile",
        api_key: str | None = None,
        temperature: float = 0.2,
        **kwargs,
    ):
        """Initialize Groq provider.

        Args:
            model_id: Groq model identifier (default: "llama-3.3-70b-versatile")
            api_key: Groq API key
            temperature: Temperature for generation (default: 0.2)
            **kwargs: Additional parameters
        """
        super().__init__(
            model_id=model_id,
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            temperature=temperature,
            **kwargs,
        )
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        logger.debug(f"Initialized Groq provider with model: {model_id}")

    async def analyze_abstract(
        self, abstract: str, gene: str, prompt: str
    ) -> AgentAnalysis:
        """Analyze abstract using Groq API with automatic retry on rate limits.

        Args:
            abstract: Abstract text
            gene: Target gene
            prompt: Full prompt to send

        Returns:
            AgentAnalysis object

        Raises:
            ValueError: If response is invalid
            RuntimeError: If API request fails after retries
        """
        max_retries = 3
        base_delay = 2.0  # seconds

        for attempt in range(max_retries):
            try:
                logger.debug(f"Calling Groq {self.model_id} for gene {gene} (attempt {attempt + 1}/{max_retries})")

                response = await self.client.chat.completions.create(
                    model=self.model_id,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a scientific literature analyst specializing in cancer genetics. Extract gene-cancer data as valid JSON.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=self.temperature,
                )

                response_text = response.choices[0].message.content
                logger.debug(f"Groq response received: {response_text[:200]}...")

                # Parse JSON
                data = self._parse_json_response(response_text)

                # Validate with Pydantic
                analysis = self._validate_and_fix(data)

                logger.debug(
                    f"Groq analysis complete: {len(analysis.cancers)} cancer(s), "
                    f"confidence={analysis.confidence}"
                )

                return analysis

            except RateLimitError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Groq rate limit hit, retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Groq rate limit exceeded after {max_retries} attempts")
                    raise RuntimeError(f"Groq API request failed after retries: {e}") from e

            except Exception as e:
                logger.error(f"Groq API error for {self.model_id}: {e}")
                raise RuntimeError(f"Groq API request failed: {e}") from e

    def _parse_json_response(self, response_text: str) -> dict:
        """Parse JSON from response."""
        text = response_text.strip()

        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {text[:200]}...")
            raise ValueError(f"Invalid JSON response: {e}") from e

    def _validate_and_fix(self, analysis_data: dict) -> AgentAnalysis:
        """Validate response and fix common issues."""
        try:
            return AgentAnalysis(**analysis_data)
        except ValidationError:
            logger.debug("Validation failed, attempting to fix response")

            # Apply same fixes as OpenAI provider
            if "confidence" not in analysis_data or analysis_data["confidence"] not in [
                "high",
                "medium",
                "low",
            ]:
                analysis_data["confidence"] = "low"

            if "reasoning" not in analysis_data:
                analysis_data["reasoning"] = "Incomplete analysis from LLM"

            if "needs_full_text" not in analysis_data:
                analysis_data["needs_full_text"] = True

            if "study_types" not in analysis_data:
                analysis_data["study_types"] = {}

            st = analysis_data["study_types"]
            st.setdefault("clinical", False)
            st.setdefault("basic", False)
            st.setdefault("clinical_description", None)
            st.setdefault("basic_description", None)

            if "mechanisms" not in analysis_data:
                analysis_data["mechanisms"] = {
                    "tumor_suppressor_mechanisms": [],
                    "oncogenic_mechanisms": [],
                    "mutations_described": False,
                    "mutation_details": None,
                }

            if "cancers" not in analysis_data:
                analysis_data["cancers"] = []
            else:
                for cancer in analysis_data["cancers"]:
                    if "role" in cancer and cancer["role"] not in [
                        "tumor_suppressor",
                        "oncogene",
                        "both",
                        "unclear",
                    ]:
                        cancer["role"] = "unclear"
                    if "confidence" in cancer and cancer["confidence"] not in [
                        "high",
                        "medium",
                        "low",
                    ]:
                        cancer["confidence"] = "low"

            try:
                return AgentAnalysis(**analysis_data)
            except ValidationError as ve2:
                logger.error(f"Could not recover response: {ve2}")
                raise ValueError(f"Invalid analysis format: {ve2}") from ve2
