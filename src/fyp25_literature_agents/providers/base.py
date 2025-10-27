"""Base class for LLM providers."""

from abc import ABC, abstractmethod

from fyp25_literature_agents.schemas import AgentAnalysis


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All provider implementations must inherit from this class and implement
    the analyze_abstract method.
    """

    def __init__(
        self,
        model_id: str,
        api_key: str,
        base_url: str | None = None,
        temperature: float = 0.2,
        **kwargs,
    ):
        """Initialize LLM provider.

        Args:
            model_id: Model identifier (e.g., "gpt-5-mini")
            api_key: API key for the provider
            base_url: Optional base URL for API endpoint
            temperature: Temperature setting for generation (default: 0.2)
            **kwargs: Additional provider-specific parameters
        """
        self.model_id = model_id
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.kwargs = kwargs

    @abstractmethod
    async def analyze_abstract(
        self, abstract: str, gene: str, prompt: str
    ) -> AgentAnalysis:
        """Analyze an abstract and return structured analysis.

        Args:
            abstract: The abstract text to analyze
            gene: Target gene symbol (e.g., "PPP2R2A")
            prompt: The complete prompt to send to the model

        Returns:
            AgentAnalysis object with structured results

        Raises:
            ValueError: If response is invalid or cannot be parsed
            RuntimeError: If API request fails
        """
        pass

    def __repr__(self) -> str:
        """String representation of provider."""
        return f"{self.__class__.__name__}(model_id='{self.model_id}')"
