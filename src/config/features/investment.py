"""Investment feature engine configuration (PRD-006 Tier 1)."""

import re

from pydantic import BaseModel, Field, PrivateAttr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_config() -> dict:
    return load_yaml_section("features/investment.yaml", "investment")


# --- Sub-config models (nested under InvestmentConfig) ---


class StopwordsConfig(BaseModel):
    """Finance-domain stopwords for TF-IDF filtering."""

    finance_terms: list[str] = Field(default_factory=lambda: [
        "company", "corporation", "operations", "financial", "results",
        "shall", "hereby", "pursuant", "section", "amendment", "filed",
        "thereof", "therein", "thereon", "herein", "fiscal", "quarter",
        "respectively", "approximately", "consolidated", "statements",
        "related", "reported", "included", "period", "ended", "item",
        "form", "act", "part", "note", "notes", "total", "amounts",
        # SEC boilerplate phrases (bigrams matched by ngram_range=2)
        "forward looking", "looking statements", "safe harbor",
        "actual results", "differ materially", "risk factors",
        "annual report", "exchange commission", "securities exchange",
        "exchange act", "fiscal year", "year ended",
        "incorporated herein", "common stock",
        # SEC structural terms (generic across all 10-Ks)
        "registrant", "exhibit", "filing", "securities", "commission",
        "annual", "report", "described",
    ])
    replace_defaults: bool = False


class NERConfig(BaseModel):
    """NER post-processing rules for product name reclassification."""

    product_names: list[str] = Field(default_factory=lambda: [
        "Mac", "MacBook", "iPad", "iPhone", "iMac",
        "Apple Watch", "Apple TV", "Apple Vision", "Apple Music",
        "Apple Pay", "Apple Card", "Apple Arcade", "Apple News",
        "Apple Fitness", "Apple Intelligence",
        "AirPods", "AirTag", "HomePod", "Beats", "Safari",
        "App Store", "iCloud", "Siri",
        "macOS", "iOS", "iPadOS", "watchOS", "tvOS", "visionOS",
    ])
    min_entity_length: int = 2
    regulatory_bodies: list[str] = Field(default_factory=lambda: [
        "SEC", "FASB", "PCAOB", "FINRA", "OCC", "FDIC", "CFTC",
        "DOJ", "FTC", "EPA", "FDA", "CFPB", "FHFA", "NCUA",
    ])

    _product_pattern: re.Pattern = PrivateAttr()
    _regulatory_pattern: re.Pattern = PrivateAttr()

    @model_validator(mode="after")
    def _compile_patterns(self) -> "NERConfig":
        escaped = [re.escape(n) for n in self.product_names]
        pattern = r"[®™]|^(?:" + "|".join(escaped) + r")"
        self._product_pattern = re.compile(pattern, re.IGNORECASE)
        body_alts = "|".join(re.escape(b) for b in self.regulatory_bodies)
        self._regulatory_pattern = re.compile(
            r"\b(?:" + body_alts + r")\b"
        )
        return self


class InputValidationConfig(BaseModel):
    """Pre-analysis input validation gate for filing sections."""

    required_sections: list[str] = Field(
        default_factory=lambda: ["item_1", "item_1a", "item_7", "item_8"]
    )
    recommended_sections: list[str] = Field(
        default_factory=lambda: ["item_1b", "item_1c", "item_2", "item_7a"]
    )
    min_section_words: int = 50
    boilerplate_phrases: list[str] = Field(default_factory=lambda: [
        "this page intentionally left blank",
        "not applicable",
        "none",
        "the information required by this item",
        "incorporated by reference",
    ])
    boilerplate_max_ratio: float = 0.80
    halt_on_failure: bool = False


class GoingConcernConfig(BaseModel):
    """Controls which sections are checked for going concern signals."""

    enabled_sections: list[str] = Field(
        default_factory=lambda: ["item_8", "item_1a", "item_7"]
    )
    auditor_opinion_sections: list[str] = Field(
        default_factory=lambda: ["item_8"]
    )


class CybersecurityConfig(BaseModel):
    """Cybersecurity incident detection terms."""

    incident_terms: list[str] = Field(default_factory=lambda: [
        "breach", "ransomware", "phishing", "malware",
        "unauthorized access", "data breach", "cyber attack",
        "cyber incident", "security incident",
    ])


class SummarizerConfig(BaseModel):
    """Domain-aware re-scoring rules for extractive summarization."""

    boilerplate_patterns: list[str] = Field(default_factory=lambda: [
        "in our opinion",
        "we have audited",
        "we audited",
        "registered with the PCAOB",
        "in accordance with the standards",
        "in accordance with standards",
        "present fairly",
        "we are a public accounting firm",
        "we are public accounting firm",
        "conducted our audits in accordance",
        "conducted our audit in accordance",
    ])
    finding_keywords: list[str] = Field(default_factory=lambda: [
        "material weakness",
        "going concern",
        "significant deficienc",
        "adverse",
        "qualified opinion",
        "contingent",
        "litigation",
        "restatement",
        "impairment",
        "write-down",
        "charge of",
    ])
    finding_boost: float = 0.3
    finding_boost_cap: float = 0.9
    boilerplate_penalty: float = 0.5
    candidate_multiplier: int = 3

    _boilerplate_re: re.Pattern = PrivateAttr()
    _finding_re: re.Pattern = PrivateAttr()

    @model_validator(mode="after")
    def _compile_patterns(self) -> "SummarizerConfig":
        self._boilerplate_re = re.compile(
            r"(?:" + "|".join(re.escape(p) for p in self.boilerplate_patterns) + r")",
            re.IGNORECASE,
        )
        monetary = r"\$[\d,.]+\s*(?:billion|million)|€[\d,.]+\s*(?:billion|million)"
        kw_alt = "|".join(re.escape(k) for k in self.finding_keywords)
        self._finding_re = re.compile(
            r"(?:" + monetary + r"|" + kw_alt + r")",
            re.IGNORECASE,
        )
        return self


class AnomalyThresholdsConfig(BaseModel):
    """Tier 2 anomaly detection thresholds."""

    uncertainty_median_multiplier: float = 2.0
    uncertainty_absolute: float = 0.03
    litigious_median_multiplier: float = 2.0
    litigious_absolute: float = 0.02
    obfuscation_score: float = 80.0
    fls_ratio: float = 0.30
    negative_sentiment: float = -0.03


# --- Main config ---


class InvestmentConfig(BaseSettings):
    """
    Investment analysis configuration.
    Loads from configs/features/investment.yaml with environment variable overrides.
    """

    model_config = SettingsConfigDict(
        env_prefix="INVESTMENT_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    # FinBERT
    finbert_model: str = Field(
        default_factory=lambda: _get_config().get("finbert_model", "ProsusAI/finbert")
    )
    finbert_max_length: int = Field(
        default_factory=lambda: _get_config().get("finbert_max_length", 512)
    )

    # TF-IDF
    tfidf_top_n: int = Field(
        default_factory=lambda: _get_config().get("tfidf_top_n", 20)
    )
    tfidf_max_features: int = Field(
        default_factory=lambda: _get_config().get("tfidf_max_features", 10000)
    )
    tfidf_ngram_min: int = Field(
        default_factory=lambda: _get_config().get("tfidf_ngram_min", 1)
    )
    tfidf_ngram_max: int = Field(
        default_factory=lambda: _get_config().get("tfidf_ngram_max", 2)
    )
    tfidf_finance_stopwords: list[str] = Field(
        default_factory=lambda: _get_config().get("tfidf_finance_stopwords", [])
    )
    tfidf_sublinear_tf: bool = Field(
        default_factory=lambda: _get_config().get("tfidf_sublinear_tf", True)
    )

    # KeyBERT
    keybert_top_n: int = Field(
        default_factory=lambda: _get_config().get("keybert_top_n", 10)
    )
    keybert_ngram_min: int = Field(
        default_factory=lambda: _get_config().get("keybert_ngram_min", 1)
    )
    keybert_ngram_max: int = Field(
        default_factory=lambda: _get_config().get("keybert_ngram_max", 3)
    )
    keybert_model: str = Field(
        default_factory=lambda: _get_config().get("keybert_model", "all-MiniLM-L6-v2")
    )

    # BERTopic
    bertopic_model: str = Field(
        default_factory=lambda: _get_config().get("bertopic_model", "all-MiniLM-L6-v2")
    )
    bertopic_min_topic_size: int = Field(
        default_factory=lambda: _get_config().get("bertopic_min_topic_size", 5)
    )

    # Summarization
    summary_sentence_count: int = Field(
        default_factory=lambda: _get_config().get("summary_sentence_count", 5)
    )

    # Flag thresholds
    flag_litigation_ratio: float = Field(
        default_factory=lambda: _get_config().get("flag_litigation_ratio", 0.05)
    )
    flag_uncertainty_ratio: float = Field(
        default_factory=lambda: _get_config().get("flag_uncertainty_ratio", 0.08)
    )
    flag_fls_ratio: float = Field(
        default_factory=lambda: _get_config().get("flag_fls_ratio", 0.15)
    )
    flag_yoy_delta_threshold: float = Field(
        default_factory=lambda: _get_config().get("flag_yoy_delta_threshold", 15.0)
    )

    # Tier 2 context
    tier2_max_tokens: int = Field(
        default_factory=lambda: _get_config().get("tier2_max_tokens", 4000)
    )

    # Feature version
    feature_version: str = Field(
        default_factory=lambda: _get_config().get("feature_version", "1.2.0")
    )

    # --- Signal quality sub-configs (ADR-022) ---
    stopwords: StopwordsConfig = Field(
        default_factory=lambda: StopwordsConfig(**_get_config().get("stopwords", {}))
    )
    ner: NERConfig = Field(
        default_factory=lambda: NERConfig(**_get_config().get("ner", {}))
    )
    going_concern: GoingConcernConfig = Field(
        default_factory=lambda: GoingConcernConfig(**_get_config().get("going_concern", {}))
    )
    cybersecurity: CybersecurityConfig = Field(
        default_factory=lambda: CybersecurityConfig(**_get_config().get("cybersecurity", {}))
    )
    summarizer_rules: SummarizerConfig = Field(
        default_factory=lambda: SummarizerConfig(**_get_config().get("summarizer", {}))
    )
    anomaly_thresholds: AnomalyThresholdsConfig = Field(
        default_factory=lambda: AnomalyThresholdsConfig(
            **_get_config().get("anomaly_thresholds", {})
        )
    )
    input_validation: InputValidationConfig = Field(
        default_factory=lambda: InputValidationConfig(
            **_get_config().get("input_validation", {})
        )
    )
