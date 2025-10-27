# Manual vs LLM Comparison Workflow

Complete workflow for comparing manual human annotations against LLM predictions for literature analysis.

## Quick Start

```bash
# 1. Generate LLM predictions (run once)
jupyter notebook examples/model_comparison_demo.ipynb

# 2. Create manual annotations using template
# Edit: manual_analysis_results.json
# (See manual_analysis_template.txt for format)

# 3. Export manual annotations to CSV
python examples/export_manual_demo.py

# 4. Compare and analyze
jupyter notebook examples/compare_manual_vs_llm.ipynb
```

## Workflow Overview

```
┌─────────────────────┐
│   PubMed Search     │
│  (shared dataset)   │
└──────────┬──────────┘
           │
           ├────────────────────┬───────────────────┐
           │                    │                   │
           ▼                    ▼                   ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  LLM Analysis    │  │  LLM Analysis    │  │  Manual Analysis │
│  (5 models × N)  │  │  (repeated runs) │  │  (1+ humans)     │
└──────────┬───────┘  └────────┬─────────┘  └────────┬─────────┘
           │                    │                      │
           ▼                    ▼                      ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  JSON Results    │  │  JSON Results    │  │  JSON Results    │
│  (per model)     │  │  (per repeat)    │  │  (per annotator) │
└──────────┬───────┘  └────────┬─────────┘  └────────┬─────────┘
           │                    │                      │
           └────────────────────┴──────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  Export to CSV        │
                    │  (one row per cancer) │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  Quantitative Metrics │
                    │  - Precision          │
                    │  - Recall             │
                    │  - F1 Score           │
                    │  - Agreement          │
                    └───────────────────────┘
```

## Data Flow

### 1. LLM Analysis → JSON → CSV

**Input**: PubMed abstracts
**Process**: 5 models × N repeats = multiple JSON files
**Output**: `model_comparison_results.csv`

```python
from fyp25_literature_agents import run_model_comparison, export_comparison_to_csv

# Run LLM analysis
results = await run_model_comparison(
    search_term="PPP2R2A AND cancer",
    gene="PPP2R2A",
    max_results=25,
    n_repeats=5
)

# Export to CSV
export_comparison_to_csv(
    json_files=[Path("openai_gpt5_mini_r0.json"), ...],
    output_csv=Path("model_comparison_results.csv"),
    search_term="PPP2R2A AND cancer",
    gene="PPP2R2A"
)
```

### 2. Manual Analysis → JSON → CSV

**Input**: Same PubMed abstracts (matched by PMID)
**Process**: Human annotators analyze manually
**Output**: `manual_analysis_results.csv`

```python
from fyp25_literature_agents import export_manual_to_csv

# Export manual annotations
export_manual_to_csv(
    json_file=Path("manual_analysis_results.json"),
    output_csv=Path("manual_analysis_results.csv"),
    search_term="PPP2R2A AND cancer",
    gene="PPP2R2A",
    annotator_name="human"
)
```

### 3. Merge and Compare

**Input**: Both CSVs
**Process**: Merge on `pmid` + `cancer_type`
**Output**: Quantitative metrics

```python
import pandas as pd

# Load both datasets
df_manual = pd.read_csv("manual_analysis_results.csv")
df_llm = pd.read_csv("model_comparison_results.csv")

# Select one model
df_model = df_llm[
    (df_llm['model_friendly_name'] == 'openai_gpt5_mini') &
    (df_llm['repeat_num'] == 0)
]

# Merge on PMID and cancer type
df_merged = pd.merge(
    df_manual,
    df_model,
    on=['pmid', 'cancer_type'],
    suffixes=('_manual', '_llm'),
    how='outer',
    indicator=True
)
```

## CSV Format Compatibility

Both manual and LLM CSVs share the same key fields for comparison:

### Shared Fields (for alignment)
- `pmid` - PubMed ID
- `title` - Article title
- `search_term` - Query used
- `gene` - Target gene
- `cancer_type` - Specific cancer (one row per cancer)

### Classification Fields (for comparison)
- `role` - tumor_suppressor | oncogene | both | unclear
- `confidence` - high | medium | low
- `has_clinical` - Boolean
- `has_basic` - Boolean
- `has_mutations` - Boolean

### LLM-Only Fields
- `model_id` - Technical model identifier
- `provider` - openai | anthropic | google | deepseek | groq
- `model_friendly_name` - Display name
- `repeat_num` - Which repeat (0-based)
- `evidence_mentioned` - List of evidence types
- `quote_from_abstract` - Relevant quote
- `clinical_description` - Description of clinical studies
- `basic_description` - Description of basic research
- `mutation_details` - Details about mutations
- `tumor_suppressor_mechanisms` - List of TS mechanisms
- `oncogenic_mechanisms` - List of oncogenic mechanisms
- `overall_confidence` - Overall confidence level
- `reasoning` - LLM's reasoning
- `ambiguities` - Noted ambiguities
- `needs_full_text` - Boolean flag
- `analysis_timestamp` - When analyzed

### Manual-Only Fields
- `annotator` - Annotator name/ID

## Metrics Explained

### Cancer Detection Metrics

Treating manual annotations as **ground truth**:

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **True Positive (TP)** | Both found same cancer | Model correctly identified cancer |
| **False Positive (FP)** | Model only | Model hallucinated cancer |
| **False Negative (FN)** | Human only | Model missed cancer |
| **Precision** | TP / (TP + FP) | Of model's predictions, how many correct? |
| **Recall** | TP / (TP + FN) | Of real cancers, how many did model find? |
| **F1 Score** | 2 × P × R / (P + R) | Balanced metric (harmonic mean) |

### Role Classification Metrics

For cancers found by **both** model and human:

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **Role Accuracy** | Matching roles / Total shared | How often does model get role right? |
| **Confusion Matrix** | Cross-tabulation | Which roles are confused? |

### Boolean Flag Metrics

At article level (not cancer level):

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **Agreement** | Matching flags / Total articles | How often do model and human agree? |
| **True Positive Rate** | Both True / Human True | Sensitivity |
| **True Negative Rate** | Both False / Human False | Specificity |

### Inter-Rater Agreement (Multiple Annotators)

| Metric | Range | Interpretation |
|--------|-------|----------------|
| **Percent Agreement** | 0-100% | Simple agreement percentage |
| **Cohen's Kappa** | -1 to +1 | Agreement beyond chance |

**Cohen's Kappa Interpretation:**
- < 0.00: Poor
- 0.00-0.20: Slight
- 0.21-0.40: Fair
- 0.41-0.60: Moderate
- 0.61-0.80: Substantial
- 0.81-1.00: Almost perfect

## Example Analysis Results

### Cancer Detection Performance

```
Model: openai_gpt5_mini (repeat 0)
----------------------------------------
True Positives:      18
False Positives:      2
False Negatives:      3
----------------------------------------
Precision:        0.900  (90% of model predictions correct)
Recall:           0.857  (86% of real cancers found)
F1 Score:         0.878  (balanced performance)
```

### Role Classification Accuracy

```
Role Accuracy (for 18 shared cancers): 0.833 (83%)

Confusion Matrix:
                    Model
Human               TS    ONC   BOTH  UNCLEAR
tumor_suppressor    10     1     0      1
oncogene             0     4     0      1
unclear              0     0     0      1

TS = tumor_suppressor, ONC = oncogene
```

### Boolean Flag Agreement

```
has_clinical:   Agreement 21/25 (84%)
has_basic:      Agreement 23/25 (92%)
has_mutations:  Agreement 19/25 (76%)
```

## Model Comparison Example

Average performance across 5 repeats:

| Model | Precision | Recall | F1 Score | Role Acc | Consistency |
|-------|-----------|--------|----------|----------|-------------|
| Anthropic Haiku 4.5 | 0.89 ± 0.03 | 0.85 ± 0.04 | 0.87 ± 0.02 | 0.82 | High |
| OpenAI GPT-5 Mini | 0.86 ± 0.08 | 0.79 ± 0.09 | 0.82 ± 0.07 | 0.78 | Medium |
| Google Gemini 2.5 | 0.92 ± 0.02 | 0.88 ± 0.03 | 0.90 ± 0.01 | 0.85 | High |
| DeepSeek V3 | 0.83 ± 0.06 | 0.81 ± 0.05 | 0.82 ± 0.04 | 0.76 | Medium |
| Groq Llama 3.1 8B | 0.78 ± 0.11 | 0.74 ± 0.12 | 0.76 ± 0.10 | 0.71 | Low |

**Interpretation:**
- **Gemini 2.5** has highest F1 score and best consistency
- **Anthropic Haiku** is second best with good balance
- **Groq Llama** has lowest performance and high variability

## Use Cases

### 1. Model Selection
Choose the best-performing model for your literature screening pipeline based on quantitative metrics.

### 2. Error Analysis
Identify systematic errors:
- Which cancer types are frequently missed?
- Which roles are confused most often?
- Do models over-predict or under-predict?

### 3. Quality Assurance
Use manual annotations to validate LLM outputs in production:
- Sample 10-20% of articles for manual review
- Calculate ongoing precision/recall
- Set alert thresholds (e.g., F1 < 0.80)

### 4. Training Data
Use manual annotations to:
- Fine-tune models
- Create few-shot examples
- Improve prompts

### 5. Research Publication
Demonstrate rigor:
- Inter-rater agreement (multiple annotators)
- Quantitative metrics vs gold standard
- Model comparison with statistical significance

## Common Issues

### Issue: No overlapping cancers found

**Symptom**: `_merge` shows mostly `left_only` and `right_only`

**Causes:**
1. Different PMIDs (not same dataset)
2. Different cancer type naming (e.g., "breast cancer" vs "breast carcinoma")
3. Model systematically missing all cancers (very low recall)

**Fix:**
- Ensure manual and LLM analyzed same PMIDs
- Normalize cancer type names (lowercase, strip whitespace)
- Check if model has major issues

### Issue: High FP, low FN (precision low, recall high)

**Symptom**: Model finds many cancers humans didn't

**Causes:**
1. Model over-predicting (hallucinating)
2. Human annotations too conservative
3. Ambiguous abstracts

**Fix:**
- Review `right_only` entries manually
- Check if human missed some obvious cancers
- Consider adjusting prompt to be more conservative

### Issue: Low FP, high FN (precision high, recall low)

**Symptom**: Model misses many cancers humans found

**Causes:**
1. Model too conservative
2. Prompt too strict
3. Context window truncation

**Fix:**
- Review `left_only` entries manually
- Adjust prompt to be more liberal
- Check if abstracts were truncated

### Issue: Role confusion between TS and ONC

**Symptom**: High cancer detection but low role accuracy

**Causes:**
1. Ambiguous abstracts
2. Model misinterpreting biological mechanisms
3. Inconsistent role definitions

**Fix:**
- Review confused cases manually
- Improve role definitions in prompt
- Add few-shot examples of ambiguous cases

## Files Reference

| File | Purpose |
|------|---------|
| `manual_analysis_template.txt` | Template for students |
| `manual_analysis_results.json` | Manual annotations (JSON) |
| `manual_analysis_results.csv` | Manual annotations (CSV) |
| `model_comparison_results.csv` | LLM predictions (CSV) |
| `export_manual_demo.py` | Export manual annotations |
| `compare_manual_vs_llm.ipynb` | Full comparison workflow |
| `MANUAL_ANNOTATION_GUIDE.md` | Detailed annotation guide |
| `MODEL_COMPARISON_SPEC.md` | LLM comparison documentation |

## Next Steps

1. **Generate LLM predictions**: Run `model_comparison_demo.ipynb`
2. **Create manual annotations**: Use `manual_analysis_template.txt`
3. **Export manual CSV**: Run `export_manual_demo.py`
4. **Compare and analyze**: Run `compare_manual_vs_llm.ipynb`
5. **Interpret results**: Use metrics to select best model
6. **Publish findings**: Include metrics in thesis/paper

## Support

For issues or questions:
- Check `MANUAL_ANNOTATION_GUIDE.md` for annotation guidelines
- Check `MODEL_COMPARISON_SPEC.md` for LLM comparison details
- Review example notebooks in `examples/`
- Consult module documentation: `help(export_manual_to_csv)`
