"""Anthropic provider implementation."""

from loguru import logger
from pydantic import ValidationError

from fyp25_literature_agents.providers.base import LLMProvider
from fyp25_literature_agents.schemas import AgentAnalysis


class AnthropicProvider(LLMProvider):
    """Anthropic API provider for literature analysis.

    Uses Claude 4.5 Haiku via tool calling for structured extraction.
    Best for budget-friendly accuracy with strong instruction following.
    """

    def __init__(
        self,
        model_id: str = "claude-4.5-haiku-20251015",
        api_key: str | None = None,
        temperature: float = 0.2,
        **kwargs,
    ):
        """Initialize Anthropic provider.

        Args:
            model_id: Anthropic model identifier (default: "claude-4.5-haiku-20251015")
            api_key: Anthropic API key
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

        # Import here to avoid requiring anthropic for other providers
        try:
            import anthropic

            self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
            logger.debug(f"Initialized Anthropic provider with model: {model_id}")
        except ImportError as e:
            raise ImportError(
                "anthropic package not installed. Install with: pip install anthropic"
            ) from e

    async def analyze_abstract(
        self, abstract: str, gene: str, prompt: str
    ) -> AgentAnalysis:
        """Analyze abstract using Anthropic API with tool calling.

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
            logger.debug(f"Calling Anthropic {self.model_id} for gene {gene}")

            # Convert Pydantic schema to tool definition
            tools = [
                {
                    "name": "extract_gene_cancer_analysis",
                    "description": "Extract structured gene-cancer relationship analysis from abstract",
                    "input_schema": AgentAnalysis.model_json_schema(),
                }
            ]

            response = await self.client.messages.create(
                model=self.model_id,
                max_tokens=4096,
                temperature=self.temperature,
                tools=tools,
                tool_choice={"type": "tool", "name": "extract_gene_cancer_analysis"},
                messages=[{"role": "user", "content": prompt}],
            )

            logger.debug(f"Anthropic response received: {response.stop_reason}")

            # Extract tool use from response
            tool_use = None
            for block in response.content:
                if block.type == "tool_use":
                    tool_use = block
                    break

            if not tool_use:
                raise ValueError("No tool use found in Anthropic response")

            # Get the input data from tool use
            analysis_data = tool_use.input
            logger.debug(f"Anthropic tool input keys: {list(analysis_data.keys())}")

            # Validate with Pydantic
            analysis = self._validate_and_fix(analysis_data)

            logger.debug(
                f"Anthropic analysis complete: {len(analysis.cancers)} cancer(s), "
                f"confidence={analysis.confidence}"
            )

            return analysis

        except Exception as e:
            logger.error(f"Anthropic API error for {self.model_id}: {e}")
            raise RuntimeError(f"Anthropic API request failed: {e}") from e

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
