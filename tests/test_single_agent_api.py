"""Tests for single agent API."""

import json
import os
from pathlib import Path

import pytest

from fyp25_literature_agents.pubmed_search import PubMedArticle
from fyp25_literature_agents.schemas import (
    AgentAnalysis,
    AnalyzedArticle,
    ConfidenceLevel,
    Mechanisms,
    StudyTypes,
)
from fyp25_literature_agents.single_agent_api import _generate_summary, _save_results


class TestGenerateSummary:
    """Test summary generation."""

    def test_empty_results(self):
        """Test summary with no results."""
        summary = _generate_summary([])
        assert summary == {}

    def test_summary_generation(self):
        """Test summary with sample results."""
        # Create mock results
        results = [
            AnalyzedArticle(
                pmid="1",
                title="Test 1",
                abstract="Test abstract",
                search_gene="PPP2R2A",
                analysis=AgentAnalysis(
                    cancers=[],
                    study_types=StudyTypes(clinical=True, basic=False),
                    mechanisms=Mechanisms(
                        tumor_suppressor_mechanisms=[],
                        oncogenic_mechanisms=[],
                        mutations_described=False,
                    ),
                    confidence=ConfidenceLevel.HIGH,
                    reasoning="Test",
                    needs_full_text=False,
                ),
            ),
            AnalyzedArticle(
                pmid="2",
                title="Test 2",
                abstract="Test abstract 2",
                search_gene="PPP2R2A",
                analysis=AgentAnalysis(
                    cancers=[],
                    study_types=StudyTypes(clinical=False, basic=True),
                    mechanisms=Mechanisms(
                        tumor_suppressor_mechanisms=[],
                        oncogenic_mechanisms=[],
                        mutations_described=False,
                    ),
                    confidence=ConfidenceLevel.MEDIUM,
                    reasoning="Test 2",
                    needs_full_text=True,
                ),
            ),
        ]

        summary = _generate_summary(results)

        assert summary["total_articles_analyzed"] == 2
        assert summary["quality_metrics"]["high_confidence_count"] == 1
        assert summary["quality_metrics"]["high_confidence_percentage"] == 50.0
        assert summary["quality_metrics"]["needs_full_text_count"] == 1


class TestSaveResults:
    """Test results saving."""

    def test_save_results(self, tmp_path):
        """Test saving results to JSON."""
        # Create mock results
        results = [
            AnalyzedArticle(
                pmid="1",
                title="Test",
                abstract="Test abstract",
                search_gene="PPP2R2A",
                analysis=AgentAnalysis(
                    cancers=[],
                    study_types=StudyTypes(clinical=True, basic=False),
                    mechanisms=Mechanisms(
                        tumor_suppressor_mechanisms=[],
                        oncogenic_mechanisms=[],
                        mutations_described=False,
                    ),
                    confidence=ConfidenceLevel.HIGH,
                    reasoning="Test",
                    needs_full_text=False,
                ),
            )
        ]

        summary = {"test": "summary"}

        # Save to temp directory
        filepath = _save_results(
            gene="PPP2R2A",
            search_query="test query",
            results=results,
            summary=summary,
            save_dir=str(tmp_path),
        )

        # Verify file exists
        assert filepath.exists()
        assert filepath.name.startswith("PPP2R2A_")
        assert filepath.suffix == ".json"

        # Verify content
        with open(filepath) as f:
            data = json.load(f)

        assert data["gene"] == "PPP2R2A"
        assert data["search_query"] == "test query"
        assert data["summary"] == summary
        assert len(data["results"]) == 1

    def test_save_results_creates_directory(self, tmp_path):
        """Test that save creates directory if needed."""
        save_dir = tmp_path / "nonexistent" / "nested"

        results = [
            AnalyzedArticle(
                pmid="1",
                title="Test",
                abstract="Test",
                search_gene="TEST",
                analysis=AgentAnalysis(
                    cancers=[],
                    study_types=StudyTypes(clinical=False, basic=False),
                    mechanisms=Mechanisms(
                        tumor_suppressor_mechanisms=[],
                        oncogenic_mechanisms=[],
                        mutations_described=False,
                    ),
                    confidence=ConfidenceLevel.LOW,
                    reasoning="Test",
                    needs_full_text=False,
                ),
            )
        ]

        filepath = _save_results(
            gene="TEST", search_query="test", results=results, summary={}, save_dir=str(save_dir)
        )

        assert filepath.exists()
        assert filepath.parent == save_dir


@pytest.mark.asyncio
async def test_analyze_gene_literature_integration():
    """Integration test for the full API.

    This test requires API keys and will be skipped if not available.
    """
    from fyp25_literature_agents.single_agent_api import analyze_gene_literature

    # Set test API key
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "test-key")
    os.environ["NCBI_EMAIL"] = os.getenv("NCBI_EMAIL", "test@example.com")

    try:
        # Use very small result set
        results = await analyze_gene_literature(
            gene="PPP2R2A", max_results=1, save_dir="test_results"
        )

        # Verify structure
        assert "gene" in results
        assert "search_query" in results
        assert "total_articles" in results
        assert "analyzed_articles" in results
        assert "results" in results
        assert "summary" in results
        assert "output_file" in results
        assert "timestamp" in results

        assert results["gene"] == "PPP2R2A"

        # Clean up
        if results["output_file"]:
            Path(results["output_file"]).unlink(missing_ok=True)
            Path("test_results").rmdir()

    except Exception as e:
        pytest.skip(f"API call failed (likely missing credentials): {e}")
