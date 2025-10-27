"""Export manual annotation results to CSV format.

This module exports simplified manual annotations to CSV for comparison
with LLM predictions. The CSV format matches the key fields from the
LLM comparison CSV to enable direct quantitative comparison.
"""

import csv
import json
from pathlib import Path

from loguru import logger


def export_manual_to_csv(
    json_file: Path,
    output_csv: Path,
    search_term: str,
    gene: str,
    annotator_name: str = "human",
) -> None:
    """Export manual annotations from JSON to CSV format.

    Creates one row per cancer classification (not per article).
    If an article has multiple cancer types, it will have multiple rows.
    CSV format is compatible with LLM comparison CSV for easy comparison.

    Args:
        json_file: Path to manual_analysis_results.json
        output_csv: Path to output CSV file
        search_term: Search term used
        gene: Target gene
        annotator_name: Name/ID of human annotator (default: "human")

    Raises:
        ValueError: If no valid data found or JSON format is invalid
        FileNotFoundError: If json_file does not exist
    """
    if not json_file.exists():
        raise FileNotFoundError(f"Manual analysis file not found: {json_file}")

    try:
        with open(json_file) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {json_file}: {e}") from e

    if not isinstance(data, list):
        raise ValueError(
            f"Expected JSON array of articles, got {type(data).__name__}"
        )

    rows = []

    for article in data:
        pmid = article.get("pmid", "")
        title = article.get("title", "")

        # Get boolean flags
        has_clinical = article.get("has_clinical", False)
        has_basic = article.get("has_basic", False)
        has_mutations = article.get("has_mutations", False)

        # Process each cancer classification
        cancers = article.get("cancers", [])

        if not cancers:
            # Article with no cancer classifications - create one row with empty cancer fields
            rows.append(
                {
                    "pmid": pmid,
                    "title": title,
                    "search_term": search_term,
                    "gene": gene,
                    "annotator": annotator_name,
                    "cancer_type": "",
                    "role": "",
                    "confidence": "",
                    "has_clinical": has_clinical,
                    "has_basic": has_basic,
                    "has_mutations": has_mutations,
                }
            )
        else:
            # One row per cancer classification
            for cancer in cancers:
                if not isinstance(cancer, dict):
                    logger.warning(
                        f"PMID {pmid}: Skipping invalid cancer entry (expected dict, got {type(cancer).__name__})"
                    )
                    continue

                cancer_type = cancer.get("type", "")
                role = cancer.get("role", "")
                cancer_confidence = cancer.get("confidence", "")

                rows.append(
                    {
                        "pmid": pmid,
                        "title": title,
                        "search_term": search_term,
                        "gene": gene,
                        "annotator": annotator_name,
                        "cancer_type": cancer_type,
                        "role": role,
                        "confidence": cancer_confidence,
                        "has_clinical": has_clinical,
                        "has_basic": has_basic,
                        "has_mutations": has_mutations,
                    }
                )

    if not rows:
        raise ValueError(f"No valid data found in {json_file}")

    # Write CSV
    fieldnames = [
        # Identifiers
        "pmid",
        "title",
        "search_term",
        "gene",
        "annotator",
        # Cancer classification (one row per cancer type)
        "cancer_type",
        "role",
        "confidence",
        # Study types
        "has_clinical",
        "has_basic",
        # Mechanisms
        "has_mutations",
    ]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"Exported {len(rows)} rows from manual annotations to {output_csv}")


def export_multiple_annotators_to_csv(
    json_files: list[tuple[Path, str]],
    output_csv: Path,
    search_term: str,
    gene: str,
) -> None:
    """Export manual annotations from multiple annotators to single CSV.

    Useful for inter-rater reliability analysis and combining annotations
    from multiple human reviewers.

    Args:
        json_files: List of tuples (json_path, annotator_name)
        output_csv: Path to output CSV file
        search_term: Search term used
        gene: Target gene

    Raises:
        ValueError: If no valid data found
    """
    all_rows = []

    for json_file, annotator_name in json_files:
        if not json_file.exists():
            logger.warning(f"File not found, skipping: {json_file}")
            continue

        try:
            with open(json_file) as f:
                data = json.load(f)

            if not isinstance(data, list):
                logger.warning(
                    f"Invalid format in {json_file}, expected array, got {type(data).__name__}"
                )
                continue

            for article in data:
                pmid = article.get("pmid", "")
                title = article.get("title", "")

                has_clinical = article.get("has_clinical", False)
                has_basic = article.get("has_basic", False)
                has_mutations = article.get("has_mutations", False)

                cancers = article.get("cancers", [])

                if not cancers:
                    all_rows.append(
                        {
                            "pmid": pmid,
                            "title": title,
                            "search_term": search_term,
                            "gene": gene,
                            "annotator": annotator_name,
                            "cancer_type": "",
                            "role": "",
                            "confidence": "",
                            "has_clinical": has_clinical,
                            "has_basic": has_basic,
                            "has_mutations": has_mutations,
                        }
                    )
                else:
                    for cancer in cancers:
                        if not isinstance(cancer, dict):
                            continue

                        all_rows.append(
                            {
                                "pmid": pmid,
                                "title": title,
                                "search_term": search_term,
                                "gene": gene,
                                "annotator": annotator_name,
                                "cancer_type": cancer.get("type", ""),
                                "role": cancer.get("role", ""),
                                "confidence": cancer.get("confidence", ""),
                                "has_clinical": has_clinical,
                                "has_basic": has_basic,
                                "has_mutations": has_mutations,
                            }
                        )

        except Exception as e:
            logger.error(f"Failed to process {json_file}: {e}")
            continue

    if not all_rows:
        raise ValueError("No valid data found in any of the provided files")

    # Write CSV
    fieldnames = [
        "pmid",
        "title",
        "search_term",
        "gene",
        "annotator",
        "cancer_type",
        "role",
        "confidence",
        "has_clinical",
        "has_basic",
        "has_mutations",
    ]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    logger.info(
        f"Exported {len(all_rows)} rows from {len(json_files)} annotators to {output_csv}"
    )
