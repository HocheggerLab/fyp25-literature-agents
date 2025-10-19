"""Prompt templates for literature analysis agents."""

from fyp25_literature_agents.schemas import (
    AgentAnalysis,
    CancerClassification,
    Mechanisms,
    StudyTypes,
)

# Core definitions for classification
TUMOR_SUPPRESSOR_DEFINITION = """
A gene is a TUMOR SUPPRESSOR if:
- Its LOSS, DELETION, or INACTIVATION promotes cancer
- Reduced expression correlates with worse outcomes
- Mutations are loss-of-function
- It normally PREVENTS uncontrolled growth

Key phrases indicating tumor suppressor:
- "deletion of {gene} promotes..."
- "loss of {gene} results in increased proliferation"
- "{gene} inactivation leads to..."
- "reduced {gene} expression correlates with..."
- "restoration of {gene} suppresses..."
"""

ONCOGENE_DEFINITION = """
A gene is an ONCOGENE if:
- Its GAIN, OVEREXPRESSION, or ACTIVATION promotes cancer
- Increased expression correlates with worse outcomes
- Mutations are gain-of-function or activating
- It drives uncontrolled growth when active

Key phrases indicating oncogene:
- "{gene} overexpression drives..."
- "{gene} amplification promotes..."
- "activating mutations in {gene}..."
- "knockdown or inhibition results in loss of tumour growth"
- "increased {gene} correlates with..."
"""


def get_json_schema_example() -> str:
    """Get JSON schema example for the response format."""
    example = AgentAnalysis(
        cancers=[
            CancerClassification(
                type="breast cancer",
                role="tumor_suppressor",
                evidence_mentioned=["deletion", "reduced_expression"],
                confidence="high",
                quote_from_abstract="PP2A deletion promotes tumor growth in breast cancer",
            )
        ],
        study_types=StudyTypes(
            clinical=True,
            clinical_description="47 breast cancer patient samples",
            basic=True,
            basic_description="MCF7 and MDA-MB-231 cell lines",
        ),
        mechanisms=Mechanisms(
            tumor_suppressor_mechanisms=["deletion", "loss_of_function"],
            oncogenic_mechanisms=[],
            mutations_described=False,
            mutation_details=None,
        ),
        confidence="high",
        reasoning="Abstract explicitly states PP2A deletion promotes cancer growth",
        ambiguities=None,
        needs_full_text=False,
    )
    return example.model_dump_json(indent=2)


def build_analysis_prompt(gene: str, abstract: str) -> str:
    """Build the complete analysis prompt for a given gene and abstract.

    Args:
        gene: The target gene being analyzed (e.g., 'PPP2R2A')
        abstract: The abstract text to analyze

    Returns:
        Complete prompt string ready to send to LLM
    """
    prompt = f"""You are a scientific literature analyst specializing in cancer genetics.

Your task is to extract structured information from a scientific abstract about the gene **{gene}**.

IMPORTANT: Focus ONLY on information about {gene}. If the abstract mentions multiple genes, analyze only {gene}.

## CLASSIFICATION RULES

{TUMOR_SUPPRESSOR_DEFINITION.format(gene=gene)}

{ONCOGENE_DEFINITION.format(gene=gene)}

## INSTRUCTIONS

1. **Identify ALL cancer types mentioned** (use specific terms: "breast cancer", not "breast")
   - If no cancer is explicitly mentioned, note this in your reasoning

2. **For EACH cancer, determine {gene}'s role:**
   - tumor_suppressor: Gene prevents cancer; loss/inactivation promotes cancer
   - oncogene: Gene promotes cancer; overexpression/activation drives cancer
   - both: Different roles in different contexts within same abstract
   - unclear: Insufficient information

3. **Evidence types to look for:**
   - Tumor suppressor: deletion, loss of function, reduced expression, inactivation, methylation
   - Oncogene: overexpression, activating mutations, amplification, gain of function

4. **Study design:**
   - Clinical: patient samples, clinical trials, human tissue, clinical data
   - Basic: cell lines, animal models, in vitro experiments, molecular mechanisms

5. **Confidence rating:**
   - high: Explicit statements with mechanistic detail
   - medium: Strong implication but not explicit
   - low: Vague or contradictory information

6. **Full text recommendation:**
   - Recommend full text if: abstract is ambiguous, contradictory, or lacks mechanistic detail
   - Do NOT recommend if: classification is clear and well-supported

## ABSTRACT TO ANALYZE

{abstract}

## OUTPUT FORMAT

Respond with VALID JSON ONLY (no markdown code blocks, no explanation).

Use this exact structure:

{get_json_schema_example()}

## IMPORTANT REMINDERS

- Focus ONLY on {gene}
- Extract information directly from the abstract - do not infer beyond what is stated
- If information is unclear, use "unclear" classification and note ambiguities
- Be conservative with confidence ratings
- Quote specific phrases when possible to support classifications

## FIELD TYPES AND VALID VALUES (use EXACT strings)

Required types:
- "role": string - MUST be EXACTLY "tumor_suppressor", "oncogene", "both", or "unclear"
  DO NOT use "unknown", "uncertain", "ambiguous" - ONLY use "unclear"
- "confidence": string - MUST be EXACTLY "high", "medium", or "low"
  DO NOT use "unclear", "unknown", "moderate" - ONLY use "high", "medium", or "low"
- "evidence_mentioned": array of SHORT keywords - e.g., ["deletion", "overexpression", "mutation"]
- "tumor_suppressor_mechanisms": array of SHORT keywords - e.g., ["deletion", "loss_of_function"]
  NOT full sentences - just keywords like "deletion", "reduced_expression", "inactivation"
- "oncogenic_mechanisms": array of SHORT keywords - e.g., ["overexpression", "amplification"]
  NOT full sentences - just keywords like "overexpression", "activating_mutation", "amplification"
- "mutation_details": string or null - single string describing mutations (can be longer description)
- "quote_from_abstract": string or null - exact quote as single string
- "clinical": boolean - true/false for clinical studies
- "basic": boolean - true/false for basic research

Confidence levels:
- "high": Clear, direct evidence
- "medium": Suggestive but indirect evidence
- "low": Weak or ambiguous evidence
- DO NOT use "unclear" for confidence - that's only for role

Now analyze the abstract and respond with JSON only:"""

    return prompt


def build_simple_prompt(gene: str, abstract: str) -> str:
    """Build a simpler, example-driven prompt for comparison (e.g., for Agent B).

    Args:
        gene: The target gene being analyzed
        abstract: The abstract text to analyze

    Returns:
        Simplified prompt string
    """
    prompt = f"""Extract cancer genetics information from this abstract about {gene}.

Classification rules (use EXACT words):
- tumor_suppressor: Loss causes cancer (deletion, inactivation, reduced expression)
- oncogene: Gain causes cancer (overexpression, activating mutations, amplification)
- both: Acts differently in different contexts
- unclear: Not enough information (NOT "unknown" - use "unclear")

Examples:
"{gene} deletion promotes tumor growth" → role: "tumor_suppressor"
"{gene} overexpression drives proliferation" → role: "oncogene"
"{gene} has dual roles depending on context" → role: "both"
"knockdown of {gene} inhibits tumour growth" → role: "oncogene"
"insufficient information about {gene}" → role: "unclear" (NOT "unknown"!)

Abstract:
{abstract}

IMPORTANT - Field types and valid values (use EXACT strings):

Required types:
- "role": string - MUST be EXACTLY "tumor_suppressor", "oncogene", "both", or "unclear"
  DO NOT use "unknown", "uncertain", "ambiguous" - ONLY use "unclear"
- "confidence": string - MUST be EXACTLY "high", "medium", or "low"
  DO NOT use "unclear", "unknown", "moderate" - ONLY use "high", "medium", or "low"
- "evidence_mentioned": array of SHORT keywords - e.g., ["deletion", "overexpression"]
- "tumor_suppressor_mechanisms": array of SHORT keywords - e.g., ["deletion", "loss_of_function"]
  NOT full sentences - just keywords like "deletion", "reduced_expression", "inactivation"
- "oncogenic_mechanisms": array of SHORT keywords - e.g., ["overexpression", "amplification"]
  NOT full sentences - just keywords like "overexpression", "activating_mutation", "amplification"
- "mutation_details": string or null - single string describing mutations (can be longer)
- "quote_from_abstract": string or null - exact quote as single string

Confidence levels:
- "high": Clear, direct evidence
- "medium": Suggestive but indirect evidence
- "low": Weak or ambiguous evidence
- DO NOT use "unclear" for confidence - that's only for role classification

Return JSON only (no markdown, no explanation):
{get_json_schema_example()}"""

    return prompt
