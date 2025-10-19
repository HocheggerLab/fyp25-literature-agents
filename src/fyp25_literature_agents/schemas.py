"""Pydantic models for literature analysis results."""

from enum import Enum

from pydantic import BaseModel, Field


class RoleClassification(str, Enum):
    """Classification of gene role in cancer."""

    TUMOR_SUPPRESSOR = "tumor_suppressor"
    ONCOGENE = "oncogene"
    BOTH = "both"
    UNCLEAR = "unclear"


class ConfidenceLevel(str, Enum):
    """Confidence level for classification."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CancerClassification(BaseModel):
    """Classification for a specific cancer type."""

    type: str = Field(..., description="Specific cancer type (e.g., 'breast cancer')")
    role: RoleClassification = Field(..., description="Gene role in this cancer")
    evidence_mentioned: list[str] = Field(
        default_factory=list, description="Evidence types mentioned in abstract"
    )
    confidence: ConfidenceLevel = Field(..., description="Confidence in classification")
    quote_from_abstract: str | None = Field(
        default=None, description="Optional: exact phrase supporting classification"
    )


class StudyTypes(BaseModel):
    """Study design information."""

    clinical: bool = Field(..., description="Whether study includes clinical data")
    clinical_description: str | None = Field(
        default=None, description="Description of clinical aspects"
    )
    basic: bool = Field(..., description="Whether study includes basic research")
    basic_description: str | None = Field(
        default=None, description="Description of basic research aspects"
    )


class Mechanisms(BaseModel):
    """Mechanistic information extracted from abstract."""

    tumor_suppressor_mechanisms: list[str] = Field(
        default_factory=list,
        description="Mechanisms indicating tumor suppressor role (deletion, inactivation, etc.)",
    )
    oncogenic_mechanisms: list[str] = Field(
        default_factory=list,
        description="Mechanisms indicating oncogenic role (overexpression, activation, etc.)",
    )
    mutations_described: bool = Field(
        ..., description="Whether specific mutations are described"
    )
    mutation_details: str | None = Field(
        default=None, description="Details about mutations if described"
    )


class AgentAnalysis(BaseModel):
    """Analysis result from a single agent."""

    cancers: list[CancerClassification] = Field(
        default_factory=list, description="List of cancer classifications"
    )
    study_types: StudyTypes = Field(..., description="Study design information")
    mechanisms: Mechanisms = Field(..., description="Mechanistic information")
    confidence: ConfidenceLevel = Field(
        ..., description="Overall confidence in analysis"
    )
    reasoning: str = Field(..., description="Brief explanation of classification")
    ambiguities: str | None = Field(
        default=None, description="Any unclear aspects noted"
    )
    needs_full_text: bool = Field(
        ..., description="Whether full text analysis is recommended"
    )


class AgentResult(BaseModel):
    """Complete result from a single agent including metadata."""

    model: str = Field(..., description="Model identifier (e.g., 'gpt-4o-mini')")
    timestamp: str = Field(..., description="ISO timestamp of analysis")
    analysis: AgentAnalysis = Field(..., description="The analysis result")


class ConsensusStatus(str, Enum):
    """Status of consensus between agents."""

    FULL_CONSENSUS = "full_consensus"
    PARTIAL_CONSENSUS = "partial_consensus"
    CONFLICT = "conflict"


class MergedCancerClassification(BaseModel):
    """Merged cancer classification with consensus information."""

    type: str = Field(..., description="Specific cancer type")
    role: RoleClassification = Field(..., description="Agreed upon gene role")
    evidence_mentioned: list[str] = Field(
        default_factory=list, description="Merged evidence types"
    )
    confidence: ConfidenceLevel = Field(..., description="Consensus confidence level")
    agent_agreement: bool = Field(
        ..., description="Whether both agents agreed on classification"
    )


class MergedResult(BaseModel):
    """Merged result from dual-agent analysis."""

    cancers: list[MergedCancerClassification] = Field(
        default_factory=list, description="Merged cancer classifications"
    )
    study_types: StudyTypes = Field(..., description="Merged study types")
    mechanisms: Mechanisms = Field(..., description="Merged mechanisms")
    needs_full_text: bool = Field(
        ..., description="Whether full text is recommended"
    )
    full_text_reasons: list[str] = Field(
        default_factory=list, description="Reasons for full text recommendation"
    )
    overall_confidence: ConfidenceLevel = Field(
        ..., description="Overall confidence in merged result"
    )


class DualAgentAnalysis(BaseModel):
    """Complete dual-agent analysis with consensus information."""

    consensus_status: ConsensusStatus = Field(
        ..., description="Status of agent consensus"
    )
    agent_a: AgentResult = Field(..., description="Result from agent A")
    agent_b: AgentResult = Field(..., description="Result from agent B")
    merged_result: MergedResult = Field(..., description="Merged consensus result")


class AnalyzedArticle(BaseModel):
    """Complete analyzed article with metadata and analysis."""

    # Article metadata
    pmid: str = Field(..., description="PubMed ID")
    doi: str = Field(default="", description="Digital Object Identifier")
    title: str = Field(..., description="Article title")
    year: str = Field(default="", description="Publication year")
    authors: list[str] = Field(default_factory=list, description="List of authors")
    journal: str = Field(default="", description="Journal name")
    abstract: str = Field(..., description="Article abstract")

    # Search context
    search_gene: str = Field(
        ..., description="Target gene for this analysis (e.g., 'PPP2R2A')"
    )

    # Analysis result (single agent for now, dual-agent later)
    analysis: AgentAnalysis = Field(..., description="Single agent analysis result")

    # Future: dual_agent_analysis: DualAgentAnalysis | None = None
