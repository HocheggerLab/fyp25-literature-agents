# Jupyter Notebook Logging Guide

## Problem: Too Many Logs in Jupyter

If you're seeing all the detailed logs in your Jupyter notebook even with `LOG_FILE=analysis.log` set, here's what's happening and how to fix it.

## Understanding the Logging System

The logging system has two outputs:

1. **Console (Jupyter cells)**: Shows important INFO messages and progress bars
2. **File (analysis.log)**: Saves detailed DEBUG logs to file

## Default Behavior (Clean Output)

When you run:
```python
results = await analyze_gene_literature(gene="PPP2R2A", max_results=10)
```

You should see:
```
14:30:22 | INFO     | Starting analysis for gene: PPP2R2A
14:30:22 | INFO     | Analyzing 10 articles for PPP2R2A (max 10 concurrent)
⠋ Analyzing PPP2R2A ━━━━━━━━━━━━━━ 5/10 • 00:05
14:30:27 | INFO     | Batch analysis complete: 10/10 successful
```

**Not** dozens of lines about "Fixed confidence", "Processing article", etc.

## What Gets Hidden (in Console)

In non-verbose mode, these messages are hidden from console but saved to `analysis.log`:
- `"Fixed confidence: moderate -> low"`
- `"Fixed cancer role: unknown -> unclear"`
- `"Processing article 1/50: 12345678"`
- `"✓ Completed 1/50: 12345678"`
- `"Processing batch 1 (10 articles)"`
- `"Attempting to fix incomplete response"`
- `"Successfully recovered incomplete response"`
- All DEBUG level messages

## What Gets Shown (in Console)

- Key INFO messages (starting analysis, batch complete)
- WARNING and ERROR messages (always shown)
- Progress bar (visual progress)

## If You're Still Seeing All Logs

### Solution 1: Restart Jupyter Kernel

The logging configuration persists across cell executions. To reset:

1. In Jupyter: **Kernel → Restart Kernel**
2. Re-run the setup cell:
   ```python
   from dotenv import load_dotenv
   from fyp25_literature_agents import analyze_gene_literature

   load_dotenv(override=True)
   print("✓ Ready to go!")
   ```

### Solution 2: Manually Configure Logging First

Add this at the top of your notebook (first cell):
```python
from fyp25_literature_agents import setup_logging

# Configure logging once at the start
setup_logging(verbose=False)  # Clean output
# setup_logging(verbose=True)  # Show all logs (for debugging)
```

Then in later cells:
```python
results = await analyze_gene_literature(gene="PPP2R2A", max_results=10)
# Logging is already configured, won't reconfigure
```

### Solution 3: Force Reconfigure

If you need to change logging mid-session:
```python
from fyp25_literature_agents import setup_logging

# Switch to clean mode
setup_logging(verbose=False, force=True)

# Or switch to verbose mode
setup_logging(verbose=True, force=True)
```

## .env Configuration

Your `.env` file should have:

```bash
# For file logging (recommended)
LOG_FILE=analysis.log

# For no file logging (comment out)
# LOG_FILE=analysis.log
```

**Do NOT use** `LOG_FILE=True` - it should be a file path or commented out.

## Recommended Workflow

### For Clean Jupyter Output

**Cell 1: Setup**
```python
from dotenv import load_dotenv
from fyp25_literature_agents import analyze_gene_literature, setup_logging

load_dotenv(override=True)

# Configure clean logging (once at start)
setup_logging(verbose=False)

print("✓ Ready to go!")
```

**Cell 2+: Analysis**
```python
results = await analyze_gene_literature(
    gene="PPP2R2A",
    max_results=10
)
```

You'll see:
- Clean console output in Jupyter
- Detailed logs saved to `analysis.log` file
- Progress bar during processing

### For Debugging in Jupyter

If you need to see all logs for troubleshooting:

```python
results = await analyze_gene_literature(
    gene="PPP2R2A",
    max_results=10,
    verbose=True  # Show all DEBUG logs
)
```

Or configure verbose mode globally:
```python
setup_logging(verbose=True, force=True)
```

## File Logging Benefits

With `LOG_FILE=analysis.log`:

✅ Clean Jupyter output (easy to read)
✅ Detailed logs saved to file (for debugging later)
✅ Automatic log rotation (10MB chunks)
✅ Compressed old logs (saves space)
✅ 7-day retention (auto-cleanup)

## Checking Your Logs

To see what's being saved to file:
```bash
tail -f analysis.log

# Or
cat analysis.log | grep "ERROR"
cat analysis.log | grep "Fixed confidence"
```

## Summary

| Setting | Console Output | File Output |
|---------|---------------|-------------|
| Default (no LOG_FILE) | Clean INFO + progress | None |
| LOG_FILE=analysis.log | Clean INFO + progress | Detailed DEBUG |
| verbose=True | All DEBUG logs | Detailed DEBUG (if LOG_FILE set) |
| verbose=False | Clean INFO only | Detailed DEBUG (if LOG_FILE set) |

**Key Point**: The `LOG_FILE` setting enables file logging but keeps console clean. The `verbose` parameter controls console verbosity.
