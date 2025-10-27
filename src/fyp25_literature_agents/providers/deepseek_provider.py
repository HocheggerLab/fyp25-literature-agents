"""DeepSeek provider implementation."""

import json

from loguru import logger
from openai import AsyncOpenAI
from pydantic import ValidationError

from fyp25_literature_agents.providers.base import LLMProvider
from fyp25_literature_agents.schemas import AgentAnalysis


class DeepSeekProvider(LLMProvider):
    """DeepSeek API provider for literature analysis.

    Uses DeepSeek V3.1-Terminus model via OpenAI-compatible API.
    Best for cost optimization while maintaining high accuracy.
    """

    def __init__(
        self,
        model_id: str = "deepseek-chat",
        api_key: str | None = None,
        temperature: float = 0.2,
        **kwargs,
    ):
        """Initialize DeepSeek provider.

        Args:
            model_id: DeepSeek model identifier (default: "deepseek-chat")
            api_key: DeepSeek API key
            temperature: Temperature for generation (default: 0.2)
            **kwargs: Additional parameters
        """
        super().__init__(
            model_id=model_id,
            api_key=api_key,
            base_url="https://api.deepseek.com",
            temperature=temperature,
            **kwargs,
        )
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        logger.debug(f"Initialized DeepSeek provider with model: {model_id}")

    async def analyze_abstract(
        self, abstract: str, gene: str, prompt: str
    ) -> AgentAnalysis:
        """Analyze abstract using DeepSeek API.

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
            logger.debug(f"Calling DeepSeek {self.model_id} for gene {gene}")

            response = await self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a scientific literature analyst specializing in cancer genetics. Extract structured information from abstracts and respond with valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=self.temperature,
            )

            response_text = response.choices[0].message.content
            logger.debug(f"DeepSeek response received: {response_text[:200]}...")

            # Parse JSON
            data = self._parse_json_response(response_text)

            # Validate with Pydantic
            analysis = self._validate_and_fix(data)

            logger.debug(
                f"DeepSeek analysis complete: {len(analysis.cancers)} cancer(s), "
                f"confidence={analysis.confidence}"
            )

            return analysis

        except Exception as e:
            logger.error(f"DeepSeek API error for {self.model_id}: {e}")
            raise RuntimeError(f"DeepSeek API request failed: {e}") from e

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
