"""FYP25 Literature Agents - PubMed search and analysis toolkit."""

from fyp25_literature_agents.llm_agents import LiteratureAgent
from fyp25_literature_agents.logging_config import setup_logging
from fyp25_literature_agents.prompts import build_analysis_prompt, build_simple_prompt
from fyp25_literature_agents.pubmed_search import (
    PubMedArticle,
    PubMedSearchConfig,
    PubMedSearcher,
)
from fyp25_literature_agents.schemas import (
    AgentAnalysis,
    AgentResult,
    AnalyzedArticle,
    CancerClassification,
    ConfidenceLevel,
    RoleClassification,
)
from fyp25_literature_agents.single_agent_api import (
    analyze_gene_literature,
    analyze_gene_literature_sync,
)

__all__ = [
    # PubMed search
    "PubMedArticle",
    "PubMedSearchConfig",
    "PubMedSearcher",
    # LLM agents
    "LiteratureAgent",
    # Simple API
    "analyze_gene_literature",
    "analyze_gene_literature_sync",
    # Logging
    "setup_logging",
    # Prompts
    "build_analysis_prompt",
    "build_simple_prompt",
    # Schemas
    "AgentAnalysis",
    "AgentResult",
    "AnalyzedArticle",
    "CancerClassification",
    "ConfidenceLevel",
    "RoleClassification",
]

__version__ = "0.1.0"
