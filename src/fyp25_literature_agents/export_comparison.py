"""Export comparison results to CSV format."""

import csv
import json
from pathlib import Path

from loguru import logger


def export_comparison_to_csv(
    json_files: list[Path],
    output_csv: Path,
    search_term: str,
    gene: str,
) -> None:
    """Export comparison results from multiple JSON files to CSV.

    Creates one row per cancer classification (not per article).
    If an article has multiple cancer types, it will have multiple rows.
    Includes model metadata for comparison.

    Args:
        json_files: List of paths to JSON result files
        output_csv: Path to output CSV file
        search_term: Search term used
        gene: Target gene

    Raises:
        ValueError: If no valid data found
    """
    rows = []

    for json_file in json_files:
        try:
            with open(json_file) as f:
                data = json.load(f)

            # Extract metadata
            metadata = data.get("metadata", {})
            model_name = metadata.get("model_name", "unknown")
            model_id = metadata.get("model_id", "unknown")
            repeat_num = metadata.get("repeat_num", 0)
            analysis_timestamp = metadata.get("timestamp", "")

            # Extract provider from model_name (e.g., "openai_gpt5_mini" -> "openai")
            provider = model_name.split("_")[0] if "_" in model_name else "unknown"

            # Process each article
            for article in data.get("results", []):
                pmid = article.get("pmid", "")
                title = article.get("title", "")
                analysis = article.get("analysis", {})

                # Get study types
                study_types = analysis.get("study_types", {})
                has_clinical = study_types.get("clinical", False)
                clinical_desc = study_types.get("clinical_description") or ""
                has_basic = study_types.get("basic", False)
                basic_desc = study_types.get("basic_description") or ""

                # Get mechanisms
                mechanisms = analysis.get("mechanisms", {})
                has_mutations = mechanisms.get("mutations_described", False)
                mutation_details = mechanisms.get("mutation_details") or ""
                ts_mechanisms = mechanisms.get("tumor_suppressor_mechanisms", [])
                onco_mechanisms = mechanisms.get("oncogenic_mechanisms", [])

                # Overall analysis
                overall_confidence = analysis.get("confidence", "")
                reasoning = analysis.get("reasoning", "")
                ambiguities = analysis.get("ambiguities") or ""
                needs_full_text = analysis.get("needs_full_text", False)

                # Process each cancer classification
                cancers = analysis.get("cancers", [])

                if not cancers:
                    # Article with no cancer classifications - create one row with empty cancer fields
                    rows.append(
                        {
                            "pmid": pmid,
                            "title": title,
                            "search_term": search_term,
                            "gene": gene,
                            "model_id": model_id,
                            "provider": provider,
                            "model_friendly_name": model_name,
                            "repeat_num": repeat_num,
                            "cancer_type": "",
                            "role": "",
                            "confidence": "",
                            "evidence_mentioned": "",
                            "quote_from_abstract": "",
                            "has_clinical": has_clinical,
                            "clinical_description": clinical_desc,
                            "has_basic": has_basic,
                            "basic_description": basic_desc,
                            "has_mutations": has_mutations,
                            "mutation_details": mutation_details,
                            "tumor_suppressor_mechanisms": ";".join(ts_mechanisms),
                            "oncogenic_mechanisms": ";".join(onco_mechanisms),
                            "overall_confidence": overall_confidence,
                            "reasoning": reasoning,
                            "ambiguities": ambiguities,
                            "needs_full_text": needs_full_text,
                            "analysis_timestamp": analysis_timestamp,
                        }
                    )
                else:
                    # One row per cancer classification
                    for cancer in cancers:
                        cancer_type = cancer.get("type", "")
                        role = cancer.get("role", "")
                        cancer_confidence = cancer.get("confidence", "")
                        evidence = cancer.get("evidence_mentioned", [])
                        quote = cancer.get("quote_from_abstract") or ""

                        rows.append(
                            {
                                "pmid": pmid,
                                "title": title,
                                "search_term": search_term,
                                "gene": gene,
                                "model_id": model_id,
                                "provider": provider,
                                "model_friendly_name": model_name,
                                "repeat_num": repeat_num,
                                "cancer_type": cancer_type,
                                "role": role,
                                "confidence": cancer_confidence,
                                "evidence_mentioned": ";".join(evidence),
                                "quote_from_abstract": quote,
                                "has_clinical": has_clinical,
                                "clinical_description": clinical_desc,
                                "has_basic": has_basic,
                                "basic_description": basic_desc,
                                "has_mutations": has_mutations,
                                "mutation_details": mutation_details,
                                "tumor_suppressor_mechanisms": ";".join(ts_mechanisms),
                                "oncogenic_mechanisms": ";".join(onco_mechanisms),
                                "overall_confidence": overall_confidence,
                                "reasoning": reasoning,
                                "ambiguities": ambiguities,
                                "needs_full_text": needs_full_text,
                                "analysis_timestamp": analysis_timestamp,
                            }
                        )

        except Exception as e:
            logger.error(f"Failed to process {json_file}: {e}")
            continue

    if not rows:
        raise ValueError("No valid data found in JSON files")

    # Write CSV
    fieldnames = [
        # Identifiers
        "pmid",
        "title",
        "search_term",
        "gene",
        # Model metadata
        "model_id",
        "provider",
        "model_friendly_name",
        "repeat_num",
        # Cancer classification (one row per cancer type)
        "cancer_type",
        "role",
        "confidence",
        "evidence_mentioned",
        "quote_from_abstract",
        # Study types
        "has_clinical",
        "clinical_description",
        "has_basic",
        "basic_description",
        # Mechanisms
        "has_mutations",
        "mutation_details",
        "tumor_suppressor_mechanisms",
        "oncogenic_mechanisms",
        # Overall analysis
        "overall_confidence",
        "reasoning",
        "ambiguities",
        "needs_full_text",
        # Metadata
        "analysis_timestamp",
    ]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"Exported {len(rows)} rows to {output_csv}")
