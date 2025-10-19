# FYP25 Literature Agents

A Python toolkit for searching PubMed and analyzing scientific literature using AI. Extract structured information about gene-cancer relationships from scientific abstracts.

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd fyp25-literature-agents

# Install dependencies using uv
uv sync
```

## Environment Setup

Create a `.env` file in the project root:

```bash
# Required for AI analysis
OPENAI_API_KEY=your-openai-api-key

# Required for PubMed search
NCBI_EMAIL=your.email@example.com

# Optional: for higher PubMed rate limits (10 req/s instead of 3 req/s)
NCBI_API_KEY=your-ncbi-api-key

# Optional: save detailed logs to file
LOG_FILE=analysis.log
```

Get a free NCBI API key at: https://www.ncbi.nlm.nih.gov/account/

---

## Two Simple APIs

### 1. PubMed Search API

Search and download scientific articles from PubMed.

```python
from fyp25_literature_agents import PubMedSearchConfig, PubMedSearcher

# Setup
config = PubMedSearchConfig(email="your.email@example.com")
searcher = PubMedSearcher(config)

# Search and fetch articles
articles = searcher.search_and_fetch(
    query="PPP2R2A[Title/Abstract] AND cancer[Title/Abstract]",
    max_results=50,
    date_from="2020/01/01",
    date_to="2024/12/31"
)

# Use the data
for article in articles:
    print(f"Title: {article.title}")
    print(f"PMID: {article.pmid}")
    print(f"Abstract: {article.abstract[:200]}...")
```

**What you get:** PubMed articles with title, abstract, authors, journal, publication date, DOI, keywords, and MeSH terms.

**Common queries:**
```python
# Search in title/abstract
"PPP2R2A[Title/Abstract] AND cancer[Title/Abstract]"

# Search with Boolean operators
"cancer AND therapy NOT surgery"

# Search by author
"Smith J[Author]"

# Search by journal
"Nature[Journal]"
```

**Tutorial:** See `examples/pubmed_search_tutorial.ipynb` for interactive examples.

---

### 2. Simple Analysis API

Analyze articles with AI in one function call - searches PubMed, analyzes with GPT, saves results.

```python
from fyp25_literature_agents import analyze_gene_literature

# One function does everything
results = await analyze_gene_literature(
    gene="PPP2R2A",
    max_results=50
)

print(f"Analyzed {results['analyzed_articles']} articles")
print(f"Results saved to: {results['output_file']}")
```

**What you get:** For each article, AI extracts:
- **Cancer types** and gene role (tumor suppressor, oncogene, both, unclear)
- **Evidence** mentioned (deletion, overexpression, mutations, etc.)
- **Study design** (clinical samples, cell lines, animal models)
- **Mechanisms** (how the gene functions in cancer)
- **Confidence** level (high, medium, low)
- **Supporting quotes** from the abstract

**Example output:**
```python
{
  "gene": "PPP2R2A",
  "analyzed_articles": 50,
  "results": [
    {
      "pmid": "12345678",
      "title": "PP2A-B55α acts as tumor suppressor in breast cancer",
      "analysis": {
        "cancers": [
          {
            "type": "breast cancer",
            "role": "tumor_suppressor",
            "evidence_mentioned": ["deletion", "reduced_expression"],
            "confidence": "high",
            "quote_from_abstract": "Loss of PPP2R2A correlates with poor prognosis"
          }
        ],
        "confidence": "high",
        "reasoning": "Abstract explicitly states tumor suppressor role"
      }
    }
  ],
  "summary": {
    "total_cancer_classifications": 67,
    "unique_cancer_types": 15,
    "cancer_types_found": ["breast cancer", "lung cancer", ...],
    "role_distribution": {
      "tumor_suppressor": 45,
      "oncogene": 12,
      "both": 5,
      "unclear": 5
    }
  }
}
```

**Options:**
```python
results = await analyze_gene_literature(
    gene="PPP2R2A",
    search_query=None,              # Optional: custom PubMed query
    max_results=50,                 # Number of articles
    model="gpt-5-nano",            # AI model to use (default: gpt-5-nano)
    max_concurrent=10,              # Parallel processing
    date_from="2020/01/01",        # Optional: filter by date
    date_to="2024/12/31",
    verbose=False,                  # Show detailed logs
)
```

**Tutorial:** See `examples/simple_api_notebook.ipynb` for interactive examples with visualizations.

**Cost estimate** (using gpt-5-nano):
- 10 articles: ~$0.001
- 50 articles: ~$0.005
- 100 articles: ~$0.01

---

## Advanced Usage

### Logging

**Clean console output (default):**
```python
results = await analyze_gene_literature(gene="PPP2R2A", max_results=50)
```
Shows: Progress bar + key messages only

**Verbose mode (for debugging):**
```python
results = await analyze_gene_literature(gene="PPP2R2A", verbose=True)
```
Shows: All DEBUG logs

**File logging:**
```bash
# Set in .env
LOG_FILE=analysis.log
```
Console stays clean, detailed logs saved to file.

### Manual Analysis (Advanced)

For more control, use the components directly:

```python
from fyp25_literature_agents import (
    PubMedSearcher,
    PubMedSearchConfig,
    LiteratureAgent
)

# Step 1: Search PubMed
config = PubMedSearchConfig(email="your.email@example.com")
searcher = PubMedSearcher(config)
articles = searcher.search_and_fetch("PPP2R2A", max_results=10)

# Step 2: Analyze with AI
agent = LiteratureAgent(model="gpt-5-nano", prompt_style="simple")

for article in articles:
    analyzed = await agent.analyze_article(article, gene="PPP2R2A")
    print(f"PMID: {analyzed.pmid}")
    print(f"Confidence: {analyzed.analysis.confidence}")
    for cancer in analyzed.analysis.cancers:
        print(f"  {cancer.type}: {cancer.role}")
```

---

## Examples

**Interactive notebooks:**
- `examples/simple_api_notebook.ipynb` - AI analysis tutorial
- `examples/pubmed_search_tutorial.ipynb` - PubMed search tutorial

**Python scripts:**
- `examples/simple_api_example.py` - Quick AI analysis examples
- `examples/basic_pubmed_search.py` - PubMed search examples

**Run examples:**
```bash
# Jupyter notebooks
uv run jupyter lab

# Python scripts
uv run python examples/simple_api_example.py
```

---

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=fyp25_literature_agents

# Linting
uv run ruff check src/ tests/
```

---

## Project Structure

```
fyp25-literature-agents/
├── src/fyp25_literature_agents/
│   ├── pubmed_search.py         # PubMed API
│   ├── single_agent_api.py      # Simple analysis API
│   ├── llm_agents.py            # AI analysis engine
│   ├── prompts.py               # AI prompts
│   ├── schemas.py               # Data models
│   └── logging_config.py        # Logging setup
├── examples/
│   ├── simple_api_notebook.ipynb
│   ├── pubmed_search_tutorial.ipynb
│   └── *.py scripts
├── tests/
└── .env                         # Your API keys (create this)
```

---

## Key Features

✅ **Simple APIs** - One function call for search or analysis
✅ **AI-powered** - Extracts structured data from abstracts
✅ **Fast** - Parallel processing with progress bars
✅ **Cost-efficient** - ~$0.01 per 100 articles
✅ **Type-safe** - Pydantic validation for all data
✅ **Clean output** - Smart logging with DEBUG/INFO levels
✅ **Auto-recovery** - Handles AI response errors gracefully
✅ **Jupyter-friendly** - Works great in notebooks

---

## Support

For questions or issues: hh65@sussex.ac.uk

---

## Quick Reference

### PubMed Search
```python
from fyp25_literature_agents import PubMedSearcher, PubMedSearchConfig

config = PubMedSearchConfig(email="your@email.com")
searcher = PubMedSearcher(config)
articles = searcher.search_and_fetch("your query", max_results=50)
```

### AI Analysis
```python
from fyp25_literature_agents import analyze_gene_literature

results = await analyze_gene_literature(gene="PPP2R2A", max_results=50)
```

That's it! 🚀
