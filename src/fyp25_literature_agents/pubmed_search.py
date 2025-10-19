"""PubMed search functionality using Biopython's Entrez API."""

import os
from typing import Any

from Bio import Entrez
from loguru import logger
from pydantic import BaseModel, Field, field_validator


class PubMedArticle(BaseModel):
    """Model representing a PubMed article."""

    pmid: str = Field(..., description="PubMed ID")
    title: str = Field(..., description="Article title")
    abstract: str = Field(default="", description="Article abstract")
    authors: list[str] = Field(default_factory=list, description="List of authors")
    journal: str = Field(default="", description="Journal name")
    publication_date: str = Field(default="", description="Publication date")
    doi: str = Field(default="", description="Digital Object Identifier")
    keywords: list[str] = Field(default_factory=list, description="Article keywords")
    mesh_terms: list[str] = Field(default_factory=list, description="MeSH terms")

    @field_validator("pmid")
    @classmethod
    def validate_pmid(cls, v: str) -> str:
        """Validate PMID is not empty."""
        if not v or not v.strip():
            raise ValueError("PMID cannot be empty")
        return v.strip()


class PubMedSearchConfig(BaseModel):
    """Configuration for PubMed searches."""

    email: str | None = Field(default=None, description="Email for NCBI Entrez (required by NCBI)")
    tool: str = Field(default="fyp25-literature-agents", description="Tool name")
    api_key: str | None = Field(default=None, description="NCBI API key (optional)")
    retmax: int = Field(default=100, ge=1, le=10000, description="Maximum results per query")
    batch_size: int = Field(default=50, ge=1, le=500, description="Batch size for fetching")

    def __init__(self, **data):
        """Initialize config, using NCBI_EMAIL env var if email not provided."""
        if data.get("email") is None:
            data["email"] = os.getenv("NCBI_EMAIL")

        # Also check for NCBI_API_KEY env var if not provided
        if data.get("api_key") is None:
            data["api_key"] = os.getenv("NCBI_API_KEY")

        super().__init__(**data)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str:
        """Validate email is not empty."""
        if not v or not v.strip():
            raise ValueError(
                "Email is required for NCBI Entrez API. "
                "Set NCBI_EMAIL environment variable or pass email parameter."
            )
        return v.strip()


class PubMedSearcher:
    """Search and retrieve articles from PubMed using Biopython."""

    def __init__(self, config: PubMedSearchConfig):
        """Initialize PubMed searcher with configuration.

        Args:
            config: PubMedSearchConfig object with API settings
        """
        self.config = config
        Entrez.email = config.email
        Entrez.tool = config.tool
        if config.api_key:
            Entrez.api_key = config.api_key
        logger.info(f"Initialized PubMedSearcher with email: {config.email}")

    def search(
        self,
        query: str,
        max_results: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort_by: str = "pub_date",
    ) -> list[str]:
        """Search PubMed and return list of PMIDs.

        Args:
            query: PubMed search query
            max_results: Maximum number of results to return (max 1000). If None, defaults to 1000
            date_from: Start date in YYYY/MM/DD format
            date_to: End date in YYYY/MM/DD format
            sort_by: Sort order - "pub_date" (newest first, default), "relevance", or "pub+date" (oldest first)

        Returns:
            List of PMIDs matching the search query (sorted by sort_by parameter, max 1000)

        Raises:
            RuntimeError: If search fails
        """
        # If max_results not specified, fetch up to 1000 results (reasonable limit)
        # If specified, enforce maximum of 1000
        if max_results is None:
            retmax = 1000
        elif max_results > 1000:
            logger.warning(f"Requested {max_results} results, but limiting to 1000 (maximum allowed)")
            retmax = 1000
        else:
            retmax = max_results

        search_params: dict[str, Any] = {
            "db": "pubmed",
            "term": query,
            "retmax": retmax,
            "sort": sort_by,
        }

        if date_from:
            search_params["mindate"] = date_from
        if date_to:
            search_params["maxdate"] = date_to
        if date_from or date_to:
            search_params["datetype"] = "pdat"

        try:
            logger.info(f"Searching PubMed with query: {query} (max_results={retmax})")
            handle = Entrez.esearch(**search_params)
            record = Entrez.read(handle)
            handle.close()

            pmids = record.get("IdList", [])
            count = int(record.get("Count", 0))

            logger.info(f"Found {count} total results, returning {len(pmids)} PMIDs")
            return pmids

        except Exception as e:
            logger.error(f"PubMed search failed: {e}")
            raise RuntimeError(f"Failed to search PubMed: {e}") from e

    def fetch_articles(self, pmids: list[str]) -> list[PubMedArticle]:
        """Fetch and parse articles from PubMed by PMIDs.

        Args:
            pmids: List of PubMed IDs to fetch

        Returns:
            List of PubMedArticle objects

        Raises:
            RuntimeError: If fetching fails
        """
        if not pmids:
            logger.warning("No PMIDs provided to fetch")
            return []

        articles: list[PubMedArticle] = []
        batch_size = self.config.batch_size

        logger.info(f"Fetching {len(pmids)} articles in batches of {batch_size}")

        for i in range(0, len(pmids), batch_size):
            batch = pmids[i : i + batch_size]
            logger.debug(f"Fetching batch {i // batch_size + 1}: PMIDs {i} to {i + len(batch)}")

            try:
                handle = Entrez.efetch(
                    db="pubmed", id=",".join(batch), rettype="medline", retmode="xml"
                )
                records = Entrez.read(handle)
                handle.close()

                for record in records.get("PubmedArticle", []):
                    try:
                        article = self._parse_article(record)
                        articles.append(article)
                    except Exception as e:
                        pmid = record.get("MedlineCitation", {}).get("PMID", "unknown")
                        logger.warning(f"Failed to parse article {pmid}: {e}")

            except Exception as e:
                logger.error(f"Failed to fetch batch: {e}")
                raise RuntimeError(f"Failed to fetch articles: {e}") from e

        logger.info(f"Successfully fetched and parsed {len(articles)} articles")
        return articles

    def _parse_article(self, record: dict[str, Any]) -> PubMedArticle:
        """Parse a PubMed article record into a PubMedArticle object.

        Args:
            record: Raw PubMed article record from Entrez

        Returns:
            PubMedArticle object

        Raises:
            ValueError: If required fields are missing
        """
        medline = record.get("MedlineCitation", {})
        article_data = medline.get("Article", {})

        # Extract PMID
        pmid = str(medline.get("PMID", ""))
        if not pmid:
            raise ValueError("Article missing PMID")

        # Extract title
        title = article_data.get("ArticleTitle", "")

        # Extract abstract
        abstract_data = article_data.get("Abstract", {})
        abstract_texts = abstract_data.get("AbstractText", [])
        if isinstance(abstract_texts, list):
            abstract = " ".join(str(text) for text in abstract_texts)
        else:
            abstract = str(abstract_texts)

        # Extract authors
        authors: list[str] = []
        author_list = article_data.get("AuthorList", [])
        for author in author_list:
            last_name = author.get("LastName", "")
            fore_name = author.get("ForeName", "")
            if last_name and fore_name:
                authors.append(f"{fore_name} {last_name}")
            elif last_name:
                authors.append(last_name)

        # Extract journal
        journal_data = article_data.get("Journal", {})
        journal = journal_data.get("Title", "")

        # Extract publication date
        pub_date = article_data.get("ArticleDate", [])
        if pub_date and isinstance(pub_date, list):
            date_info = pub_date[0]
            year = date_info.get("Year", "")
            month = date_info.get("Month", "")
            day = date_info.get("Day", "")
            publication_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}" if year else ""
        else:
            # Fallback to journal issue date
            journal_issue = journal_data.get("JournalIssue", {})
            pub_date_info = journal_issue.get("PubDate", {})
            year = pub_date_info.get("Year", "")
            month = pub_date_info.get("Month", "")
            publication_date = f"{year}-{month}" if year else ""

        # Extract DOI
        doi = ""
        article_ids = record.get("PubmedData", {}).get("ArticleIdList", [])
        for article_id in article_ids:
            if article_id.attributes.get("IdType") == "doi":
                doi = str(article_id)
                break

        # Extract keywords
        keywords: list[str] = []
        keyword_list = medline.get("KeywordList", [])
        for kw_group in keyword_list:
            keywords.extend([str(kw) for kw in kw_group])

        # Extract MeSH terms
        mesh_terms: list[str] = []
        mesh_heading_list = medline.get("MeshHeadingList", [])
        for mesh_heading in mesh_heading_list:
            descriptor = mesh_heading.get("DescriptorName", "")
            if descriptor:
                mesh_terms.append(str(descriptor))

        return PubMedArticle(
            pmid=pmid,
            title=title,
            abstract=abstract,
            authors=authors,
            journal=journal,
            publication_date=publication_date,
            doi=doi,
            keywords=keywords,
            mesh_terms=mesh_terms,
        )

    def search_and_fetch(
        self,
        query: str,
        max_results: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort_by: str = "pub_date",
    ) -> list[PubMedArticle]:
        """Convenience method to search and fetch articles in one call.

        Args:
            query: PubMed search query
            max_results: Maximum number of results to return (max 1000). If None, defaults to 1000
            date_from: Start date in YYYY/MM/DD format
            date_to: End date in YYYY/MM/DD format
            sort_by: Sort order - "pub_date" (newest first, default), "relevance", or "pub+date" (oldest first)

        Returns:
            List of PubMedArticle objects (sorted by sort_by parameter, max 1000)
        """
        pmids = self.search(query, max_results, date_from, date_to, sort_by)
        return self.fetch_articles(pmids)
