"""OpenAI provider implementation."""

import json

from loguru import logger
from openai import AsyncOpenAI
from pydantic import ValidationError

from fyp25_literature_agents.providers.base import LLMProvider
from fyp25_literature_agents.schemas import AgentAnalysis


class OpenAIProvider(LLMProvider):
    """OpenAI API provider for literature analysis.

    Supports OpenAI models like gpt-5-mini, gpt-4o, etc.
    Uses minimal reasoning effort and low temperature for consistent extraction.
    """

    def __init__(
        self,
        model_id: str = "gpt-5-mini",
        api_key: str | None = None,
        temperature: float = 0.2,
        **kwargs,
    ):
        """Initialize OpenAI provider.

        Args:
            model_id: OpenAI model identifier (default: "gpt-5-mini")
            api_key: OpenAI API key
            temperature: Temperature for generation (default: 0.2)
            **kwargs: Additional parameters
        """
        super().__init__(
            model_id=model_id,
            api_key=api_key,
            base_url=None,  # Use default OpenAI endpoint
            temperature=temperature,
            **kwargs,
        )
        self.client = AsyncOpenAI(api_key=self.api_key)
        logger.debug(f"Initialized OpenAI provider with model: {model_id}")

    async def analyze_abstract(
        self, abstract: str, gene: str, prompt: str
    ) -> AgentAnalysis:
        """Analyze abstract using OpenAI API.

        Args:
            abstract: Abstract text
            gene: Target gene
            prompt: Full prompt to send

        Returns:
            AgentAnalysis object

        Raises:
            ValueError: If response is invalid
            RuntimeError: If API request fails
        """
        try:
            logger.debug(f"Calling OpenAI {self.model_id} for gene {gene}")

            # Build request parameters - newer models may not support all parameters
            request_params = {
                "model": self.model_id,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a scientific literature analyst specializing in cancer genetics. You extract structured information from abstracts and respond only with valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
            }

            # Try to add optional parameters, but catch errors if not supported
            try:
                response = await self.client.chat.completions.create(**request_params)
            except Exception as e:
                # If it fails, it might be due to unsupported parameters
                logger.debug(f"Request failed, trying without optional params: {e}")
                response = await self.client.chat.completions.create(**request_params)

            response_text = response.choices[0].message.content
            logger.debug(f"OpenAI response received: {response_text[:200]}...")

            # Parse JSON
            data = self._parse_json_response(response_text)

            # Validate with Pydantic
            analysis = self._validate_and_fix(data)

            logger.debug(
                f"OpenAI analysis complete: {len(analysis.cancers)} cancer(s), "
                f"confidence={analysis.confidence}"
            )

            return analysis

        except Exception as e:
            logger.error(f"OpenAI API error for {self.model_id}: {e}")
            raise RuntimeError(f"OpenAI API request failed: {e}") from e

    def _parse_json_response(self, response_text: str) -> dict:
        """Parse JSON from response, handling markdown code blocks.

        Args:
            response_text: Raw text response

        Returns:
            Parsed dictionary

        Raises:
            ValueError: If JSON parsing fails
        """
        text = response_text.strip()

        # Remove markdown code blocks if present
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
        """Validate response and fix common issues.

        Args:
            analysis_data: Raw analysis dictionary

        Returns:
            Validated AgentAnalysis object

        Raises:
            ValueError: If validation fails even after fixes
        """
        try:
            return AgentAnalysis(**analysis_data)
        except ValidationError as ve:
            logger.debug("Validation failed, attempting to fix response")

            # Fix confidence
            if "confidence" not in analysis_data or analysis_data["confidence"] not in [
                "high",
                "medium",
                "low",
            ]:
                analysis_data["confidence"] = "low"
                logger.debug("Fixed confidence -> low")

            # Fix reasoning
            if "reasoning" not in analysis_data:
                if "conclusion" in analysis_data and isinstance(
                    analysis_data["conclusion"], dict
                ):
                    analysis_data["reasoning"] = analysis_data["conclusion"].get(
                        "reasoning", "Incomplete analysis"
                    )
                else:
                    analysis_data["reasoning"] = "Incomplete analysis from LLM"
                logger.debug("Added default reasoning")

            # Fix needs_full_text
            if "needs_full_text" not in analysis_data:
                analysis_data["needs_full_text"] = True

            # Fix study_types
            if "study_types" not in analysis_data or not isinstance(
                analysis_data["study_types"], dict
            ):
                analysis_data["study_types"] = {}

            st = analysis_data["study_types"]
            st.setdefault("clinical", False)
            st.setdefault("basic", False)
            st.setdefault("clinical_description", None)
            st.setdefault("basic_description", None)

            # Fix mechanisms
            if "mechanisms" not in analysis_data:
                analysis_data["mechanisms"] = {
                    "tumor_suppressor_mechanisms": [],
                    "oncogenic_mechanisms": [],
                    "mutations_described": False,
                    "mutation_details": None,
                }

            # Fix cancers
            if "cancers" not in analysis_data:
                analysis_data["cancers"] = []
            else:
                # Handle case where cancers might be strings instead of dicts
                fixed_cancers = []
                for cancer in analysis_data["cancers"]:
                    if isinstance(cancer, str):
                        # Convert string to minimal cancer object
                        logger.debug(f"Converting string cancer '{cancer}' to dict")
                        cancer = {
                            "type": cancer,
                            "role": "unclear",
                            "evidence_mentioned": [],
                            "confidence": "low",
                            "quote_from_abstract": None,
                        }
                    elif not isinstance(cancer, dict):
                        # Skip non-dict, non-string items
                        logger.warning(f"Skipping invalid cancer item: {type(cancer)}")
                        continue

                    # Fix role
                    if "role" in cancer and cancer["role"] not in [
                        "tumor_suppressor",
                        "oncogene",
                        "both",
                        "unclear",
                    ]:
                        cancer["role"] = "unclear"

                    # Fix confidence
                    if "confidence" in cancer and cancer["confidence"] not in [
                        "high",
                        "medium",
                        "low",
                    ]:
                        cancer["confidence"] = "low"

                    # Remove extra fields
                    valid_fields = {
                        "type",
                        "role",
                        "evidence_mentioned",
                        "confidence",
                        "quote_from_abstract",
                    }
                    extra_fields = set(cancer.keys()) - valid_fields
                    for field in extra_fields:
                        del cancer[field]

                    fixed_cancers.append(cancer)

                # Replace with fixed cancers
                analysis_data["cancers"] = fixed_cancers

            # Try validation again
            try:
                return AgentAnalysis(**analysis_data)
            except ValidationError as ve2:
                logger.error(f"Could not recover response: {ve2}")
                raise ValueError(f"Invalid analysis format: {ve2}") from ve2
