"""Unit tests for PubMed search functionality."""

from unittest.mock import MagicMock, patch

import pytest

from fyp25_literature_agents.pubmed_search import (
    PubMedArticle,
    PubMedSearchConfig,
    PubMedSearcher,
)


class TestPubMedArticle:
    """Test PubMedArticle model."""

    def test_valid_article(self):
        """Test creating a valid article."""
        article = PubMedArticle(
            pmid="12345678",
            title="Test Article",
            abstract="This is a test abstract",
            authors=["John Doe", "Jane Smith"],
            journal="Nature",
            publication_date="2024-01-15",
            doi="10.1234/test",
            keywords=["test", "article"],
            mesh_terms=["Humans", "Research"],
        )

        assert article.pmid == "12345678"
        assert article.title == "Test Article"
        assert len(article.authors) == 2

    def test_pmid_validation_empty(self):
        """Test PMID validation fails for empty string."""
        with pytest.raises(ValueError, match="PMID cannot be empty"):
            PubMedArticle(pmid="", title="Test")

    def test_pmid_validation_whitespace(self):
        """Test PMID validation strips whitespace."""
        article = PubMedArticle(pmid="  12345678  ", title="Test")
        assert article.pmid == "12345678"

    def test_default_values(self):
        """Test default values for optional fields."""
        article = PubMedArticle(pmid="12345678", title="Test Article")

        assert article.abstract == ""
        assert article.authors == []
        assert article.journal == ""
        assert article.publication_date == ""
        assert article.doi == ""
        assert article.keywords == []
        assert article.mesh_terms == []


class TestPubMedSearchConfig:
    """Test PubMedSearchConfig model."""

    def test_valid_config(self):
        """Test creating a valid configuration."""
        config = PubMedSearchConfig(
            email="test@example.com", tool="test-tool", api_key="test-key", retmax=50
        )

        assert config.email == "test@example.com"
        assert config.tool == "test-tool"
        assert config.api_key == "test-key"
        assert config.retmax == 50

    def test_email_validation_empty(self):
        """Test email validation fails for empty string."""
        with pytest.raises(ValueError, match="Email is required"):
            PubMedSearchConfig(email="")

    def test_email_validation_whitespace(self):
        """Test email validation strips whitespace."""
        config = PubMedSearchConfig(email="  test@example.com  ")
        assert config.email == "test@example.com"

    def test_default_values(self):
        """Test default values."""
        config = PubMedSearchConfig(email="test@example.com")

        assert config.tool == "fyp25-literature-agents"
        assert config.api_key is None
        assert config.retmax == 100
        assert config.batch_size == 50

    def test_retmax_validation(self):
        """Test retmax validation."""
        with pytest.raises(ValueError):
            PubMedSearchConfig(email="test@example.com", retmax=0)

        with pytest.raises(ValueError):
            PubMedSearchConfig(email="test@example.com", retmax=20000)


class TestPubMedSearcher:
    """Test PubMedSearcher class."""

    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return PubMedSearchConfig(email="test@example.com", retmax=10)

    @pytest.fixture
    def searcher(self, config):
        """Create a PubMedSearcher instance."""
        return PubMedSearcher(config)

    def test_initialization(self, searcher, config):
        """Test searcher initialization."""
        assert searcher.config == config

    @patch("fyp25_literature_agents.pubmed_search.Entrez")
    def test_search_success(self, mock_entrez, searcher):
        """Test successful search."""
        mock_handle = MagicMock()
        mock_handle.__enter__ = MagicMock(return_value=mock_handle)
        mock_handle.__exit__ = MagicMock(return_value=False)

        mock_record = {"IdList": ["12345678", "87654321"], "Count": "2"}

        mock_entrez.esearch.return_value = mock_handle
        mock_entrez.read.return_value = mock_record

        pmids = searcher.search("cancer")

        assert len(pmids) == 2
        assert "12345678" in pmids
        assert "87654321" in pmids

        # Verify default sort is pub_date
        call_kwargs = mock_entrez.esearch.call_args[1]
        assert call_kwargs["sort"] == "pub_date"

    @patch("fyp25_literature_agents.pubmed_search.Entrez")
    def test_search_with_dates(self, mock_entrez, searcher):
        """Test search with date filters."""
        mock_handle = MagicMock()
        mock_handle.__enter__ = MagicMock(return_value=mock_handle)
        mock_handle.__exit__ = MagicMock(return_value=False)

        mock_record = {"IdList": ["12345678"], "Count": "1"}

        mock_entrez.esearch.return_value = mock_handle
        mock_entrez.read.return_value = mock_record

        pmids = searcher.search("cancer", date_from="2020/01/01", date_to="2024/12/31")

        assert len(pmids) == 1
        mock_entrez.esearch.assert_called_once()
        call_kwargs = mock_entrez.esearch.call_args[1]
        assert call_kwargs["mindate"] == "2020/01/01"
        assert call_kwargs["maxdate"] == "2024/12/31"
        assert call_kwargs["datetype"] == "pdat"

    @patch("fyp25_literature_agents.pubmed_search.Entrez")
    def test_search_with_custom_sort(self, mock_entrez, searcher):
        """Test search with custom sort order."""
        mock_handle = MagicMock()
        mock_handle.__enter__ = MagicMock(return_value=mock_handle)
        mock_handle.__exit__ = MagicMock(return_value=False)

        mock_record = {"IdList": ["12345678"], "Count": "1"}

        mock_entrez.esearch.return_value = mock_handle
        mock_entrez.read.return_value = mock_record

        pmids = searcher.search("cancer", sort_by="relevance")

        assert len(pmids) == 1
        mock_entrez.esearch.assert_called_once()
        call_kwargs = mock_entrez.esearch.call_args[1]
        assert call_kwargs["sort"] == "relevance"

    @patch("fyp25_literature_agents.pubmed_search.Entrez")
    def test_search_failure(self, mock_entrez, searcher):
        """Test search failure handling."""
        mock_entrez.esearch.side_effect = Exception("API Error")

        with pytest.raises(RuntimeError, match="Failed to search PubMed"):
            searcher.search("cancer")

    @patch("fyp25_literature_agents.pubmed_search.Entrez")
    def test_fetch_articles_empty_list(self, _mock_entrez, searcher):
        """Test fetching with empty PMID list."""
        articles = searcher.fetch_articles([])
        assert articles == []

    @patch("fyp25_literature_agents.pubmed_search.Entrez")
    def test_fetch_articles_success(self, mock_entrez, searcher):
        """Test successful article fetching."""
        mock_handle = MagicMock()
        mock_handle.__enter__ = MagicMock(return_value=mock_handle)
        mock_handle.__exit__ = MagicMock(return_value=False)

        mock_record = {
            "PubmedArticle": [
                {
                    "MedlineCitation": {
                        "PMID": "12345678",
                        "Article": {
                            "ArticleTitle": "Test Article",
                            "Abstract": {"AbstractText": ["Test abstract"]},
                            "AuthorList": [
                                {"LastName": "Doe", "ForeName": "John"},
                            ],
                            "Journal": {"Title": "Nature"},
                        },
                        "KeywordList": [],
                        "MeshHeadingList": [],
                    },
                    "PubmedData": {"ArticleIdList": []},
                }
            ]
        }

        mock_entrez.efetch.return_value = mock_handle
        mock_entrez.read.return_value = mock_record

        articles = searcher.fetch_articles(["12345678"])

        assert len(articles) == 1
        assert articles[0].pmid == "12345678"
        assert articles[0].title == "Test Article"
        assert articles[0].abstract == "Test abstract"

    @patch("fyp25_literature_agents.pubmed_search.Entrez")
    def test_fetch_articles_batching(self, mock_entrez, searcher):
        """Test article fetching in batches."""
        searcher.config.batch_size = 2
        pmids = ["1", "2", "3", "4", "5"]

        mock_handle = MagicMock()
        mock_handle.__enter__ = MagicMock(return_value=mock_handle)
        mock_handle.__exit__ = MagicMock(return_value=False)

        mock_record = {"PubmedArticle": []}
        mock_entrez.efetch.return_value = mock_handle
        mock_entrez.read.return_value = mock_record

        searcher.fetch_articles(pmids)

        assert mock_entrez.efetch.call_count == 3

    @patch("fyp25_literature_agents.pubmed_search.Entrez")
    def test_parse_article_complete(self, _mock_entrez, searcher):
        """Test parsing a complete article record."""
        record = {
            "MedlineCitation": {
                "PMID": "12345678",
                "Article": {
                    "ArticleTitle": "Complete Test Article",
                    "Abstract": {"AbstractText": ["Part 1", "Part 2"]},
                    "AuthorList": [
                        {"LastName": "Doe", "ForeName": "John"},
                        {"LastName": "Smith", "ForeName": "Jane"},
                    ],
                    "Journal": {
                        "Title": "Nature",
                        "JournalIssue": {
                            "PubDate": {"Year": "2024", "Month": "January"}
                        },
                    },
                    "ArticleDate": [{"Year": "2024", "Month": "1", "Day": "15"}],
                },
                "KeywordList": [["cancer", "research"]],
                "MeshHeadingList": [
                    {"DescriptorName": "Humans"},
                    {"DescriptorName": "Research"},
                ],
            },
            "PubmedData": {
                "ArticleIdList": [
                    MagicMock(attributes={"IdType": "doi"}, __str__=lambda _: "10.1234/test")
                ]
            },
        }

        article = searcher._parse_article(record)

        assert article.pmid == "12345678"
        assert article.title == "Complete Test Article"
        assert article.abstract == "Part 1 Part 2"
        assert len(article.authors) == 2
        assert "John Doe" in article.authors
        assert article.journal == "Nature"
        assert article.publication_date == "2024-01-15"
        assert article.doi == "10.1234/test"
        assert len(article.keywords) == 2
        assert len(article.mesh_terms) == 2

    @patch("fyp25_literature_agents.pubmed_search.Entrez")
    def test_parse_article_missing_pmid(self, _mock_entrez, searcher):
        """Test parsing fails when PMID is missing."""
        record = {"MedlineCitation": {"Article": {"ArticleTitle": "Test"}}}

        with pytest.raises(ValueError, match="Article missing PMID"):
            searcher._parse_article(record)

    @patch("fyp25_literature_agents.pubmed_search.Entrez")
    def test_search_and_fetch(self, mock_entrez, searcher):
        """Test convenience method search_and_fetch."""
        mock_handle = MagicMock()
        mock_handle.__enter__ = MagicMock(return_value=mock_handle)
        mock_handle.__exit__ = MagicMock(return_value=False)

        search_record = {"IdList": ["12345678"], "Count": "1"}
        fetch_record = {
            "PubmedArticle": [
                {
                    "MedlineCitation": {
                        "PMID": "12345678",
                        "Article": {
                            "ArticleTitle": "Test",
                        },
                        "KeywordList": [],
                        "MeshHeadingList": [],
                    },
                    "PubmedData": {"ArticleIdList": []},
                }
            ]
        }

        mock_entrez.esearch.return_value = mock_handle
        mock_entrez.efetch.return_value = mock_handle
        mock_entrez.read.side_effect = [search_record, fetch_record]

        articles = searcher.search_and_fetch("cancer", max_results=5)

        assert len(articles) == 1
        assert articles[0].pmid == "12345678"
