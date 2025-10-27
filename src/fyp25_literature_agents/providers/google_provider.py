"""Google Gemini provider implementation."""

from loguru import logger
from pydantic import ValidationError

from fyp25_literature_agents.providers.base import LLMProvider
from fyp25_literature_agents.schemas import AgentAnalysis


class GoogleProvider(LLMProvider):
    """Google Gemini API provider for literature analysis.

    Uses Gemini 3.0 Pro with native Pydantic schema support.
    Best for complex reasoning with 1M token context window.
    """

    def __init__(
        self,
        model_id: str = "gemini-3.0-pro",
        api_key: str | None = None,
        temperature: float = 0.2,
        **kwargs,
    ):
        """Initialize Google provider.

        Args:
            model_id: Google model identifier (default: "gemini-3.0-pro")
            api_key: Google API key
            temperature: Temperature for generation (default: 0.2)
            **kwargs: Additional parameters
        """
        super().__init__(
            model_id=model_id,
            api_key=api_key,
            base_url=None,
            temperature=temperature,
            **kwargs,
        )

        # Import here to avoid requiring google-genai for other providers
        try:
            from google import genai

            self.client = genai.Client(api_key=self.api_key)
            logger.debug(f"Initialized Google provider with model: {model_id}")
        except ImportError as e:
            raise ImportError(
                "google-genai package not installed. Install with: pip install google-genai"
            ) from e

    async def analyze_abstract(
        self, abstract: str, gene: str, prompt: str
    ) -> AgentAnalysis:
        """Analyze abstract using Google Gemini API.

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
            logger.debug(f"Calling Google {self.model_id} for gene {gene}")

            # Use generate_content with structured output
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": AgentAnalysis,  # Direct Pydantic support
                    "temperature": self.temperature,
                },
            )

            logger.debug(f"Google response received")

            # Gemini returns parsed Pydantic object directly
            if hasattr(response, "parsed") and response.parsed:
                analysis = response.parsed
                logger.debug(
                    f"Google analysis complete: {len(analysis.cancers)} cancer(s), "
                    f"confidence={analysis.confidence}"
                )
                return analysis
            else:
                # Fallback: parse from text
                logger.debug("Parsed object not available, parsing from text")
                import json

                analysis_data = json.loads(response.text)
                analysis = self._validate_and_fix(analysis_data)
                return analysis

        except Exception as e:
            logger.error(f"Google API error for {self.model_id}: {e}")
            raise RuntimeError(f"Google API request failed: {e}") from e

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
