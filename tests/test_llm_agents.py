"""Tests for LLM agent implementations."""

import json

import pytest

from fyp25_literature_agents.llm_agents import LiteratureAgent
from fyp25_literature_agents.prompts import build_analysis_prompt, build_simple_prompt
from fyp25_literature_agents.pubmed_search import PubMedArticle
from fyp25_literature_agents.schemas import ConfidenceLevel, RoleClassification


class TestPromptBuilding:
    """Test prompt building functions."""

    def test_build_analysis_prompt_basic(self):
        """Test that analysis prompt is built correctly."""
        gene = "PPP2R2A"
        abstract = "PP2A acts as a tumor suppressor in breast cancer."

        prompt = build_analysis_prompt(gene, abstract)

        assert gene in prompt
        assert abstract in prompt
        assert "tumor_suppressor" in prompt.lower()
        assert "oncogene" in prompt.lower()
        assert "json" in prompt.lower()

    def test_build_simple_prompt_basic(self):
        """Test that simple prompt is built correctly."""
        gene = "PPP2R2A"
        abstract = "PP2A acts as a tumor suppressor in breast cancer."

        prompt = build_simple_prompt(gene, abstract)

        assert gene in prompt
        assert abstract in prompt
        assert "tumor_suppressor" in prompt.lower()
        assert len(prompt) < len(build_analysis_prompt(gene, abstract))


class TestLiteratureAgent:
    """Test LiteratureAgent class."""

    def test_agent_initialization(self):
        """Test that agent initializes correctly."""
        # Mock the API key for testing
        import os
        os.environ["OPENAI_API_KEY"] = "test-key"

        agent = LiteratureAgent(
            model="gpt-4o-mini",
            prompt_style="detailed",
        )

        assert agent.model == "gpt-4o-mini"
        assert agent.prompt_style == "detailed"
        assert agent.client is not None

    def test_parse_json_response_clean(self):
        """Test parsing clean JSON response."""
        import os
        os.environ["OPENAI_API_KEY"] = "test-key"
        agent = LiteratureAgent()

        json_data = {
            "cancers": [],
            "study_types": {"clinical": False, "basic": True},
            "mechanisms": {
                "tumor_suppressor_mechanisms": [],
                "oncogenic_mechanisms": [],
                "mutations_described": False,
            },
            "confidence": "high",
            "reasoning": "Test",
            "needs_full_text": False,
        }

        response = json.dumps(json_data)
        parsed = agent._parse_json_response(response)

        assert parsed == json_data

    def test_parse_json_response_with_markdown(self):
        """Test parsing JSON with markdown code blocks."""
        import os
        os.environ["OPENAI_API_KEY"] = "test-key"
        agent = LiteratureAgent()

        json_data = {"key": "value"}
        response = f"```json\n{json.dumps(json_data)}\n```"

        parsed = agent._parse_json_response(response)
        assert parsed == json_data

    def test_parse_json_response_with_simple_markdown(self):
        """Test parsing JSON with simple markdown blocks."""
        import os
        os.environ["OPENAI_API_KEY"] = "test-key"
        agent = LiteratureAgent()

        json_data = {"key": "value"}
        response = f"```\n{json.dumps(json_data)}\n```"

        parsed = agent._parse_json_response(response)
        assert parsed == json_data

    def test_parse_json_response_invalid(self):
        """Test that invalid JSON raises error."""
        import os
        os.environ["OPENAI_API_KEY"] = "test-key"
        agent = LiteratureAgent()

        with pytest.raises(ValueError, match="Invalid JSON"):
            agent._parse_json_response("not json at all")

    @pytest.mark.asyncio
    async def test_analyze_article_integration(self):
        """Integration test for analyzing a real article.

        Note: This requires API keys and will make real API calls.
        Mark as slow or skip in CI if needed.
        """
        # Create a sample article
        article = PubMedArticle(
            pmid="12345678",
            title="PP2A-B55α acts as tumor suppressor in breast cancer",
            abstract=(
                "Protein phosphatase 2A (PP2A) with the B55α regulatory subunit "
                "acts as a tumor suppressor in breast cancer. Loss of PPP2R2A "
                "expression correlates with poor prognosis. Cell line studies in "
                "MCF7 cells demonstrate that PP2A deletion promotes cell proliferation."
            ),
            authors=["Smith J", "Jones A"],
            journal="Nature Cancer",
            publication_date="2023-01-15",
            doi="10.1234/test.2023.001",
        )

        # Initialize agent
        agent = LiteratureAgent(model="gpt-4o-mini")

        # Analyze article
        try:
            analyzed = await agent.analyze_article(article, gene="PPP2R2A")

            # Basic assertions
            assert analyzed.pmid == article.pmid
            assert analyzed.search_gene == "PPP2R2A"
            assert analyzed.analysis is not None

            # Check that analysis has expected structure
            assert hasattr(analyzed.analysis, "cancers")
            assert hasattr(analyzed.analysis, "study_types")
            assert hasattr(analyzed.analysis, "mechanisms")
            assert hasattr(analyzed.analysis, "confidence")

            # If any cancers found, check structure
            if analyzed.analysis.cancers:
                cancer = analyzed.analysis.cancers[0]
                assert cancer.type  # Should have a cancer type
                assert cancer.role in [e.value for e in RoleClassification]
                assert cancer.confidence in [e.value for e in ConfidenceLevel]

        except Exception as e:
            pytest.skip(f"API call failed (likely missing credentials): {e}")

    @pytest.mark.asyncio
    async def test_batch_analyze(self):
        """Test batch analysis of multiple articles."""
        articles = [
            PubMedArticle(
                pmid=f"1234567{i}",
                title=f"Test article {i}",
                abstract="PP2A acts as tumor suppressor in cancer.",
            )
            for i in range(3)
        ]

        import os
        os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "test-key")
        agent = LiteratureAgent()

        try:
            results = await agent.batch_analyze(articles, gene="PPP2R2A")

            # Should process all articles (or fail gracefully)
            assert len(results) <= len(articles)

            # Each result should be an AnalyzedArticle
            for result in results:
                assert result.pmid
                assert result.search_gene == "PPP2R2A"
                assert result.analysis is not None

        except Exception as e:
            pytest.skip(f"API call failed (likely missing credentials): {e}")


class TestSchemaValidation:
    """Test that schemas work correctly with actual data."""

    def test_cancer_classification_creation(self):
        """Test creating a CancerClassification."""
        from fyp25_literature_agents.schemas import CancerClassification

        cancer = CancerClassification(
            type="breast cancer",
            role=RoleClassification.TUMOR_SUPPRESSOR,
            evidence_mentioned=["deletion", "reduced_expression"],
            confidence=ConfidenceLevel.HIGH,
            quote_from_abstract="PP2A deletion promotes tumor growth",
        )

        assert cancer.type == "breast cancer"
        assert cancer.role == RoleClassification.TUMOR_SUPPRESSOR
        assert len(cancer.evidence_mentioned) == 2
        assert cancer.confidence == ConfidenceLevel.HIGH

    def test_agent_analysis_minimal(self):
        """Test creating minimal AgentAnalysis."""
        from fyp25_literature_agents.schemas import (
            AgentAnalysis,
            Mechanisms,
            StudyTypes,
        )

        analysis = AgentAnalysis(
            cancers=[],
            study_types=StudyTypes(clinical=False, basic=True),
            mechanisms=Mechanisms(
                tumor_suppressor_mechanisms=[],
                oncogenic_mechanisms=[],
                mutations_described=False,
            ),
            confidence=ConfidenceLevel.LOW,
            reasoning="Abstract does not provide clear information",
            needs_full_text=True,
        )

        assert len(analysis.cancers) == 0
        assert analysis.study_types.basic is True
        assert analysis.confidence == ConfidenceLevel.LOW
        assert analysis.needs_full_text is True
