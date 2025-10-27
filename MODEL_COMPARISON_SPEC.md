# Model Comparison Study Specification

## Overview

This document specifies the exact models, parameters, and configuration used for the multi-provider LLM comparison study in the FYP25 Literature Agents project.

**Study Design:**
- **Objective:** Compare performance of 5 state-of-the-art LLM providers on gene-cancer relationship extraction from PubMed abstracts
- **Dataset:** Same set of PubMed abstracts analyzed by all models
- **Methodology:** Each model analyzes each abstract 5 times to measure consistency
- **Output:** Structured JSON and CSV for quantitative comparison

---

## Models Tested

All models selected as of **October 2025** based on cost-performance characteristics for scientific literature analysis.

### 1. OpenAI GPT-5 Mini

**Model Configuration:**
```python
{
    "provider": "OpenAI",
    "model_id": "gpt-5-mini",
    "friendly_name": "openai_gpt5_mini",
    "api_endpoint": "https://api.openai.com/v1",
    "temperature": 0.2,
    "reasoning_effort": "minimal"
}
```

**Characteristics:**
- **Cost:** $0.25 per 1M input tokens, $2.00 per 1M output tokens
- **Speed:** ~150 tokens/second
- **Context Window:** 400,000 tokens
- **Best For:** Balanced cost-performance, reliable JSON structured output
- **Medical Performance:** Significantly outperforms GPT-4o on medical benchmarks

**API Key Environment Variable:** `OPENAI_API_KEY`

---

### 2. Anthropic Claude Haiku 4.5

**Model Configuration:**
```python
{
    "provider": "Anthropic",
    "model_id": "claude-haiku-4-5-20251001",
    "friendly_name": "anthropic_haiku_4_5",
    "api_endpoint": "https://api.anthropic.com/v1",
    "temperature": 0.2,
    "max_tokens": 4096
}
```

**Characteristics:**
- **Cost:** $1.00 per 1M input tokens, $5.00 per 1M output tokens
- **Speed:** ~120 tokens/second
- **Context Window:** 200,000 tokens
- **Best For:** Budget-friendly accuracy, matches Claude Sonnet 4 performance
- **Implementation:** Uses tool calling API for structured extraction

**API Key Environment Variable:** `ANTHROPIC_API_KEY`

---

### 3. Google Gemini 2.5 Flash

**Model Configuration:**
```python
{
    "provider": "Google",
    "model_id": "gemini-2.5-flash",
    "friendly_name": "google_gemini_2_5_flash",
    "api_endpoint": "https://generativelanguage.googleapis.com/v1",
    "temperature": 0.2,
    "response_mime_type": "application/json"
}
```

**Characteristics:**
- **Cost:** $0.075 per 1M input tokens, $0.30 per 1M output tokens
- **Speed:** ~200 tokens/second
- **Context Window:** 1,048,576 tokens (1M)
- **Best For:** Fast processing with higher rate limits (10 RPM free tier vs 5 RPM for Pro)
- **Rate Limits (Free Tier):** 10 requests/minute, 250 requests/day, 250K tokens/minute
- **Implementation:** Native Pydantic schema support via `response_schema`

**API Key Environment Variable:** `GOOGLE_API_KEY`

---

### 4. DeepSeek V3.1-Terminus

**Model Configuration:**
```python
{
    "provider": "DeepSeek",
    "model_id": "deepseek-chat",
    "friendly_name": "deepseek_v3_1",
    "api_endpoint": "https://api.deepseek.com",
    "temperature": 0.2,
    "response_format": {"type": "json_object"}
}
```

**Characteristics:**
- **Cost:** $0.23 per 1M input tokens, $0.90 per 1M output tokens (**LOWEST**)
- **Speed:** ~80 tokens/second
- **Context Window:** 163,840 tokens
- **Best For:** Cost optimization, high-volume processing
- **Medical Performance:** 85.0% on MMLU-Pro, 80.7% on GPQA-Diamond (graduate-level science)
- **Implementation:** OpenAI-compatible API with JSON mode

**API Key Environment Variable:** `DEEPSEEK_API_KEY`

---

### 5. Groq Llama 3.1 8B Instant

**Model Configuration:**
```python
{
    "provider": "Groq",
    "model_id": "llama-3.1-8b-instant",
    "friendly_name": "groq_llama3_1_8b",
    "api_endpoint": "https://api.groq.com/openai/v1",
    "temperature": 0.2,
    "response_format": {"type": "json_object"}
}
```

**Characteristics:**
- **Cost:** $0.05 per 1M input tokens, $0.08 per 1M output tokens (**CHEAPEST**)
- **Speed:** ~2,600 tokens/second (**FASTEST**)
- **Context Window:** 131,072 tokens
- **Best For:** Ultra-fast processing via LPU infrastructure, highest free tier limits
- **Rate Limits (Free Tier):** 30 requests/minute, 6K tokens/minute
- **Implementation:** OpenAI-compatible API

**API Key Environment Variable:** `GROQ_API_KEY`

---

## Shared Parameters

All models use the following standardized parameters for consistency:

### Temperature
```python
temperature = 0.2
```
**Rationale:** Low temperature (0.2) ensures deterministic, factual extraction while allowing minimal variation for measuring consistency across repeats.

### System Prompt
All models receive the same system prompt:
```
"You are a scientific literature analyst specializing in cancer genetics.
You extract structured information from abstracts and respond only with valid JSON."
```

### User Prompt
All models use the **"simple" prompt style** from `prompts.py`:
- Focuses on clear examples and structured output
- Emphasizes specific gene focus (not all genes in abstract)
- Includes role definitions (tumor suppressor vs oncogene)
- Provides JSON schema example

### JSON Output Format
All models must return structured output conforming to the `AgentAnalysis` Pydantic schema:

```python
{
    "cancers": [
        {
            "type": str,  # e.g., "breast cancer"
            "role": str,  # tumor_suppressor | oncogene | both | unclear
            "evidence_mentioned": list[str],
            "confidence": str,  # high | medium | low
            "quote_from_abstract": str | None
        }
    ],
    "study_types": {
        "clinical": bool,
        "clinical_description": str | None,
        "basic": bool,
        "basic_description": str | None
    },
    "mechanisms": {
        "tumor_suppressor_mechanisms": list[str],
        "oncogenic_mechanisms": list[str],
        "mutations_described": bool,
        "mutation_details": str | None
    },
    "confidence": str,  # high | medium | low
    "reasoning": str,
    "ambiguities": str | None,
    "needs_full_text": bool
}
```

---

## Study Protocol

### Execution Workflow

1. **PubMed Search (Once)**
   - Query PubMed with specified search term
   - Retrieve up to `max_results` abstracts
   - Save to `pubmed_articles.json` (shared dataset)

2. **Model Initialization**
   - Initialize all 5 providers with API keys from environment
   - Validate API connectivity
   - Skip models with missing API keys (with warning)

3. **Analysis Grid**
   - **For each model:**
     - **For repeat 1 to 5:**
       - Analyze all abstracts sequentially
       - Save results to `{model_name}_repeat{N}.json`
       - Log any failures
   - **Sequential execution** (not parallel) for easier debugging
   - **Continue on failure** (mark as failed, don't stop entire study)

4. **CSV Export**
   - Flatten all JSON results to CSV
   - **One row per cancer classification** (not per article)
   - Include model metadata: `model_id`, `provider`, `repeat_num`

5. **Metadata Generation**
   - Save study metadata to `metadata.json`
   - Include timing, success rates, model configurations

### Output Structure

```
model_comparison_results/
└── {sanitized_search_term}/
    ├── pubmed_articles.json                    # Original PubMed data
    ├── openai_gpt5_mini_repeat1.json          # 5 files per model
    ├── openai_gpt5_mini_repeat2.json
    ├── openai_gpt5_mini_repeat3.json
    ├── openai_gpt5_mini_repeat4.json
    ├── openai_gpt5_mini_repeat5.json
    ├── anthropic_haiku_4_5_repeat1.json       # 5 files
    ├── ...                                     # (25 JSON files total)
    ├── comparison_results.csv                  # Master CSV
    └── metadata.json                           # Study metadata
```

---

## Error Handling

### Validation and Recovery
All providers implement the same validation logic:

1. **Try standard Pydantic validation**
2. **If ValidationError:**
   - Fix invalid `confidence` values → default to "low"
   - Fix invalid `role` values → default to "unclear"
   - Add missing required fields with defaults
   - Remove extra fields not in schema
   - Retry validation

3. **If still fails:**
   - Log error
   - Mark analysis as failed
   - Continue with next article

### Failed Analyses
- Tracked in `metadata.json` under `"failed_analyses"`
- Includes: `model_name`, `repeat_num`, `error`
- Does not stop entire study

---

## Cost Estimates

For a typical study with **20 abstracts × 5 models × 5 repeats = 500 analyses**:

| Model | Cost per 1K abstracts | Cost for Study (20 abstracts) |
|-------|----------------------|-------------------------------|
| Groq Llama 3.1 8B | $0.15 | **$0.003** |
| Gemini 2.5 Flash | $0.09 | $0.002 |
| DeepSeek | $0.27 | $0.005 |
| GPT-5 Mini | $0.50 | $0.010 |
| Anthropic Haiku | $1.40 | $0.028 |
| **Total (all 5 models)** | **~$2.41** | **~$0.048** |

**With 5 repeats:** ~$0.048 × 5 = **~$0.24 total**

*Estimates assume ~400 input tokens per abstract and ~200 output tokens per analysis.*

---

## Dependencies

### Python Packages Required

```toml
[project.dependencies]
# Core
biopython = ">=1.85"       # PubMed access
pydantic = ">=2.12.3"      # Data validation
loguru = ">=0.7.3"         # Logging
tqdm = ">=4.67.1"          # Progress bars

# LLM Providers
openai = ">=2.5.0"         # OpenAI, DeepSeek, Groq
anthropic = ">=0.39.0"     # Anthropic Claude
google-genai = ">=0.8.0"   # Google Gemini
```

### Environment Variables Required

Create a `.env` file with all API keys:

```bash
# Required for all models
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-api03-...
GOOGLE_API_KEY=AIzaSy...
DEEPSEEK_API_KEY=sk-...
GROQ_API_KEY=gsk_...

# Required for PubMed
NCBI_EMAIL=your@email.com

# Optional
LOG_FILE=analysis.log
LOG_LEVEL=INFO
```

---

## Usage Example

### Jupyter Notebook

```python
from fyp25_literature_agents import run_model_comparison

# Run complete comparison study
results = await run_model_comparison(
    search_term="PPP2R2A AND cancer",
    max_results=20,
    num_repeats=5,
    output_dir="model_comparison_results",
    gene="PPP2R2A",  # Optional, auto-extracted if None
    verbose=True
)

# Check results
print(f"Analyzed {results['num_articles']} articles")
print(f"Tested {len(results['models_tested'])} models")
print(f"CSV file: {results['csv_file']}")
print(f"Failed analyses: {len(results['failed_analyses'])}")
```

### Load Results for Analysis

```python
import pandas as pd

# Load comparison CSV
df = pd.read_csv(results['csv_file'])

# Analyze role classifications across models
role_counts = df.groupby(['model_friendly_name', 'role']).size()
print(role_counts)

# Check consistency across repeats for one model
openai_results = df[df['model_friendly_name'] == 'openai_gpt5_mini']
consistency = openai_results.groupby(['pmid', 'cancer_type', 'role']).size()
print(consistency)
```

---

## Quality Control

### Validation Checks
1. All models use same PubMed dataset
2. All models use same prompts and temperature
3. JSON schema validated via Pydantic for all responses
4. Failed analyses tracked and reported
5. Timestamps recorded for all analyses

### Expected Metrics to Compare
- **Role classification accuracy** (vs manual annotations)
- **Consistency across repeats** (same model, same abstract)
- **Inter-model agreement** (do models agree?)
- **Confidence calibration** (are high-confidence predictions more accurate?)
- **Processing time** (varies by model speed)

---

## Notes

1. **Model IDs are current as of October 2025** - verify availability before running
2. **API keys must be set** in environment or `.env` file
3. **Sequential execution** minimizes API rate limit issues
4. **Temperature = 0.2** allows some variation for consistency testing while maintaining determinism
5. **Reasoning effort = "minimal"** (OpenAI only) optimizes for speed and cost
6. **All providers use JSON mode** for structured output

---

## Version History

- **v1.1 (October 2025):** Updated models for better free tier rate limits
  - OpenAI GPT-5 Mini
  - Anthropic Claude Haiku 4.5 (claude-haiku-4-5-20251001)
  - Google Gemini 2.5 Flash (gemini-2.5-flash) - 10 RPM free tier
  - DeepSeek V3.1-Terminus (deepseek-chat)
  - Groq Llama 3.1 8B Instant (llama-3.1-8b-instant) - 30 RPM free tier

- **v1.0 (October 2025):** Initial specification with 5 providers
  - Used Gemini 2.5 Pro (5 RPM) and Llama 3.3 70B (hit rate limits)
