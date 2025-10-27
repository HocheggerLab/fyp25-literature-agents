# Manual Annotation Guide

This guide explains how to create manual annotations of PubMed abstracts and export them to CSV format for comparison with LLM predictions.

## Overview

The manual annotation workflow allows students to:
1. Manually analyze PubMed abstracts using a simplified template
2. Export manual annotations to CSV format
3. Compare manual annotations with LLM predictions quantitatively
4. Calculate precision, recall, F1 score, and inter-rater agreement

## Step 1: Create Manual Annotations

### Using the Template

Open `manual_analysis_template.txt` which provides:
- Instructions for annotators
- Categorical value options (role, confidence levels)
- A completed example
- JSON template structure

### JSON Format

Your manual annotations should be saved as `manual_analysis_results.json` with this structure:

```json
[
  {
    "pmid": "12345678",
    "title": "Article title here",
    "cancers": [
      {
        "type": "breast cancer",
        "role": "tumor_suppressor",
        "confidence": "high"
      }
    ],
    "has_clinical": true,
    "has_basic": false,
    "has_mutations": true
  }
]
```

### Field Descriptions

**Required Fields:**
- `pmid` (string): PubMed ID for matching with LLM results
- `title` (string): Article title for quick reference
- `cancers` (array): List of cancer classifications (can be empty `[]`)
  - `type` (string): Specific cancer type (e.g., "breast cancer", "lung cancer")
  - `role` (string): One of: `"tumor_suppressor"`, `"oncogene"`, `"both"`, `"unclear"`
  - `confidence` (string): One of: `"high"`, `"medium"`, `"low"`
- `has_clinical` (boolean): Are clinical studies described? (patients, trials, clinical data)
- `has_basic` (boolean): Is basic research described? (cell lines, animal models, in vitro)
- `has_mutations` (boolean): Are mutations/variants mentioned?

### Role Classification Guidelines

- **tumor_suppressor**: Gene loss/deletion/downregulation promotes cancer
  - Keywords: "deletion", "loss", "downregulation", "inactivation", "suppresses"
- **oncogene**: Gene overexpression/amplification/activation drives cancer
  - Keywords: "overexpression", "amplification", "activation", "upregulation", "promotes"
- **both**: Gene shows both tumor suppressor and oncogenic properties in same abstract
- **unclear**: Role cannot be determined from abstract alone

### Confidence Level Guidelines

- **high**: Strong, clear evidence with direct statements about gene-cancer relationship
- **medium**: Good evidence but some uncertainty or indirect statements
- **low**: Weak evidence, unclear, or highly ambiguous

## Step 2: Export Manual Annotations to CSV

### Using Python Script

```python
from pathlib import Path
from fyp25_literature_agents import export_manual_to_csv, setup_logging

# Setup logging
setup_logging()

# Export single annotator
export_manual_to_csv(
    json_file=Path("manual_analysis_results.json"),
    output_csv=Path("manual_analysis_results.csv"),
    search_term="PPP2R2A AND cancer",
    gene="PPP2R2A",
    annotator_name="annotator_1",
)
```

### Using Demo Script

```bash
cd examples
python export_manual_demo.py
```

### CSV Output Format

The CSV will have these columns:
- `pmid`: PubMed ID
- `title`: Article title
- `search_term`: Search query used
- `gene`: Target gene
- `annotator`: Annotator name/ID
- `cancer_type`: Specific cancer type (one row per cancer)
- `role`: Role classification
- `confidence`: Confidence level
- `has_clinical`: Boolean flag
- `has_basic`: Boolean flag
- `has_mutations`: Boolean flag

**Important**: The CSV creates **one row per cancer classification**, not per article. If an article has multiple cancer types, it will have multiple rows with duplicated metadata.

## Step 3: Compare with LLM Predictions

### Using Jupyter Notebook

Open `examples/compare_manual_vs_llm.ipynb` for a complete workflow that:

1. Exports manual annotations to CSV
2. Loads both manual and LLM comparison CSVs
3. Aligns predictions by PMID and cancer type
4. Calculates precision, recall, F1 score
5. Analyzes role classification agreement
6. Compares boolean flags (has_clinical, has_basic, has_mutations)
7. Visualizes model performance across all models and repeats

### Key Metrics

**Cancer Detection Metrics:**
- **True Positives (TP)**: Both human and model found the same cancer
- **False Positives (FP)**: Model found cancer, human didn't
- **False Negatives (FN)**: Human found cancer, model missed it
- **Precision**: TP / (TP + FP) - Of all cancers model found, how many were correct?
- **Recall**: TP / (TP + FN) - Of all real cancers, how many did model find?
- **F1 Score**: Harmonic mean of precision and recall

**Role Classification Metrics:**
- **Role Accuracy**: For shared cancer classifications, how often did model get the role correct?
- **Role Confusion Matrix**: Shows which roles are confused (e.g., tumor_suppressor vs oncogene)

**Boolean Flag Metrics:**
- **Agreement**: Percentage of articles where human and model agree on flag value
- **Confusion Matrix**: Shows patterns of agreement/disagreement

### Example Analysis Code

```python
import pandas as pd

# Load data
df_manual = pd.read_csv("manual_analysis_results.csv")
df_llm = pd.read_csv("model_comparison_results.csv")

# Select one model for comparison
df_model = df_llm[
    (df_llm['model_friendly_name'] == 'openai_gpt5_mini') &
    (df_llm['repeat_num'] == 0)
]

# Merge on PMID and cancer_type
df_comparison = pd.merge(
    df_manual,
    df_model,
    on=['pmid', 'cancer_type'],
    suffixes=('_manual', '_llm'),
    how='outer',
    indicator=True
)

# Calculate metrics
tp = len(df_comparison[df_comparison['_merge'] == 'both'])
fp = len(df_comparison[df_comparison['_merge'] == 'right_only'])
fn = len(df_comparison[df_comparison['_merge'] == 'left_only'])

precision = tp / (tp + fp) if (tp + fp) > 0 else 0
recall = tp / (tp + fn) if (tp + fn) > 0 else 0
f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

print(f"Precision: {precision:.3f}")
print(f"Recall: {recall:.3f}")
print(f"F1 Score: {f1:.3f}")
```

## Step 4: Multiple Annotators (Inter-Rater Reliability)

### Create Multiple Annotation Files

Have each annotator create their own JSON file:
- `manual_analysis_annotator1.json`
- `manual_analysis_annotator2.json`
- `manual_analysis_annotator3.json`

### Export Combined CSV

```python
from fyp25_literature_agents import export_multiple_annotators_to_csv

export_multiple_annotators_to_csv(
    json_files=[
        (Path("manual_analysis_annotator1.json"), "annotator_1"),
        (Path("manual_analysis_annotator2.json"), "annotator_2"),
        (Path("manual_analysis_annotator3.json"), "annotator_3"),
    ],
    output_csv=Path("manual_analysis_combined.csv"),
    search_term="PPP2R2A AND cancer",
    gene="PPP2R2A",
)
```

### Calculate Inter-Rater Agreement

```python
import pandas as pd
from sklearn.metrics import cohen_kappa_score

df = pd.read_csv("manual_analysis_combined.csv")

# Get annotations for same PMID+cancer from two annotators
df_a1 = df[df['annotator'] == 'annotator_1']
df_a2 = df[df['annotator'] == 'annotator_2']

df_paired = pd.merge(
    df_a1, df_a2,
    on=['pmid', 'cancer_type'],
    suffixes=('_a1', '_a2')
)

# Cohen's Kappa for role classification
kappa = cohen_kappa_score(df_paired['role_a1'], df_paired['role_a2'])
print(f"Inter-rater agreement (Cohen's Kappa): {kappa:.3f}")

# Interpretation:
# < 0.00: Poor agreement
# 0.00-0.20: Slight agreement
# 0.21-0.40: Fair agreement
# 0.41-0.60: Moderate agreement
# 0.61-0.80: Substantial agreement
# 0.81-1.00: Almost perfect agreement
```

## Tips for Manual Analysis

1. **Read carefully**: Read each abstract multiple times to ensure accurate classification
2. **Be specific**: Use specific cancer types ("breast cancer" not just "cancer")
3. **Be honest**: Use "unclear" and "low" confidence when appropriate
4. **Check for mutations**: Look for keywords like "mutation", "variant", "deletion", "alteration"
5. **Identify study types**: Distinguish clinical (patients) from basic (cell lines, models)
6. **Multiple cancers**: List each cancer type separately if gene has different roles
7. **No cancer**: Use empty `cancers: []` array when PPP2R2A discussed outside cancer context

## Common Pitfalls

1. **Over-interpreting**: Don't infer information not explicitly stated in abstract
2. **Confirmation bias**: Be objective - don't force ambiguous abstracts into clear categories
3. **Skipping full text**: Mark `needs_full_text: true` in manual notes if abstract insufficient
4. **Role confusion**: Be careful distinguishing tumor suppressor (loss promotes cancer) from oncogene (gain promotes cancer)
5. **Multiple roles**: Use `"both"` only if abstract explicitly describes both roles, not if uncertain

## File Organization

Recommended project structure:
```
project/
├── manual_analysis_template.txt       # Template for students
├── manual_analysis_results.json       # Your annotations (gitignored)
├── manual_analysis_results.csv        # Exported CSV (gitignored)
├── model_comparison_results.csv       # LLM predictions (gitignored)
├── examples/
│   ├── export_manual_demo.py         # Export script
│   └── compare_manual_vs_llm.ipynb   # Comparison notebook
└── results/
    ├── manual/                        # Manual annotation results
    └── llm/                          # LLM prediction results
```

## References

- Full LLM comparison workflow: `MODEL_COMPARISON_SPEC.md`
- Example notebooks: `examples/model_comparison_demo.ipynb`
- Manual template: `manual_analysis_template.txt`
- Schema definitions: `src/fyp25_literature_agents/schemas.py`
