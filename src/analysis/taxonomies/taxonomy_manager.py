"""
Taxonomy Manager for SASB SICS Alignment.

This module handles the mapping between SEC filing metadata (SIC codes)
and SASB Industries/Topics. It allows the system to dynamically select
the correct risk labels for a given company based on its industry.

Pydantic V2 compliant implementation.

Usage:
    from src.analysis.taxonomies.taxonomy_manager import TaxonomyManager

    manager = TaxonomyManager()

    # Get industry for a SIC code
    industry = manager.get_industry_for_sic("7372")
    # Returns: "Software & IT Services"

    # Get topics for a SIC code
    topics = manager.get_topics_for_sic("7372")
    # Returns: {"Data_Security": "...", "Recruiting...": "..."}
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import SettingsConfigDict

from src.config import settings

logger = logging.getLogger(__name__)


# ===========================
# Pydantic V2 Models for SASB Topics
# ===========================

class SASBTopic(BaseModel):
    """A single SASB disclosure topic."""
    model_config = SettingsConfigDict(frozen=True)

    name: str = Field(..., description="Topic identifier (e.g., 'Data_Security')")
    description: str = Field(..., description="Full description of the topic")


class SASBIndustry(BaseModel):
    """SASB Industry with its associated topics."""
    model_config = SettingsConfigDict(frozen=True)

    name: str = Field(..., description="Industry name (e.g., 'Software & IT Services')")
    topics: List[SASBTopic] = Field(default_factory=list, description="List of disclosure topics")

    def get_topics_dict(self) -> Dict[str, str]:
        """Return topics as {name: description} dictionary."""
        return {topic.name: topic.description for topic in self.topics}


class SASBMapping(BaseModel):
    """Complete SASB mapping configuration."""
    model_config = SettingsConfigDict(
        arbitrary_types_allowed=True,
        validate_default=True
    )

    sic_to_sasb: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping from SIC codes to SASB industry names"
    )
    sasb_topics: Dict[str, List[SASBTopic]] = Field(
        default_factory=dict,
        description="Mapping from industry names to their topics"
    )

    @field_validator('sic_to_sasb', mode='before')
    @classmethod
    def validate_sic_codes(cls, v: Dict) -> Dict[str, str]:
        """Ensure all SIC codes are strings."""
        return {str(k): str(v_val) for k, v_val in v.items()}

    @field_validator('sasb_topics', mode='before')
    @classmethod
    def validate_topics(cls, v: Dict) -> Dict[str, List[SASBTopic]]:
        """Convert raw topic dicts to SASBTopic models."""
        result = {}
        for industry, topics in v.items():
            if isinstance(topics, list):
                result[industry] = [
                    SASBTopic(**t) if isinstance(t, dict) else t
                    for t in topics
                ]
            else:
                result[industry] = topics
        return result

    @classmethod
    def load_from_json(cls, path: Path) -> "SASBMapping":
        """Load mapping from a JSON file."""
        if not path.exists():
            logger.warning(f"SASB mapping file not found at {path}")
            return cls()

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls(**data)
        except Exception as e:
            logger.error(f"Failed to load SASB mappings from {path}: {e}")
            return cls()


# ===========================
# Taxonomy Manager
# ===========================

class TaxonomyManager:
    """
    Manages industry mappings and risk taxonomies.

    Uses Pydantic V2 models for data validation.
    """

    def __init__(self, mapping_file: str = "sasb_sics_mapping.json"):
        """
        Initialize the manager.

        Args:
            mapping_file: Filename of the SASB mapping JSON in the taxonomies dir.
        """
        self.mapping_path = settings.paths.taxonomies_dir / mapping_file
        self._mapping: Optional[SASBMapping] = None
        self._load_mappings()

    def _load_mappings(self) -> None:
        """Load the JSON mapping file into Pydantic models."""
        self._mapping = SASBMapping.load_from_json(self.mapping_path)

        if self._mapping.sic_to_sasb:
            logger.info(
                f"Loaded SASB mappings: {len(self._mapping.sic_to_sasb)} SIC codes, "
                f"{len(self._mapping.sasb_topics)} Industries."
            )

    @property
    def sic_map(self) -> Dict[str, str]:
        """Legacy accessor for SIC to SASB mapping."""
        return self._mapping.sic_to_sasb if self._mapping else {}

    @property
    def topic_map(self) -> Dict[str, List[SASBTopic]]:
        """Legacy accessor for SASB topics mapping."""
        return self._mapping.sasb_topics if self._mapping else {}

    def get_industry_for_sic(self, sic_code: Union[str, int, None]) -> Optional[str]:
        """
        Get the SASB Industry name for a given SIC code.

        Args:
            sic_code: The 3 or 4 digit SIC code (e.g., "7372" or 7372).

        Returns:
            Industry string or None if not found.
        """
        if sic_code is None:
            return None

        sic_str = str(sic_code).strip()
        return self.sic_map.get(sic_str)

    def get_topics_for_industry(self, industry: str) -> Dict[str, str]:
        """
        Get risk topics for a specific SASB industry.

        Args:
            industry: The exact SASB industry name string.

        Returns:
            Dictionary mapping {TopicName: Description}.
        """
        topics_list = self.topic_map.get(industry, [])
        return {t.name: t.description for t in topics_list}

    def get_topics_for_sic(self, sic_code: Union[str, int, None]) -> Dict[str, str]:
        """
        Get the relevant risk topics for a company based on its SIC code.

        Args:
            sic_code: The SIC code.

        Returns:
            Dictionary mapping {TopicName: Description}.
            Returns empty dict if SIC or Industry not found.
        """
        industry = self.get_industry_for_sic(sic_code)
        if not industry:
            logger.warning(f"No SASB industry found for SIC code: {sic_code}")
            return {}

        topics = self.get_topics_for_industry(industry)
        if not topics:
            logger.warning(f"No topics defined for industry: {industry}")

        return topics

    def get_all_industries(self) -> List[str]:
        """Get list of all available SASB industries."""
        return list(self.topic_map.keys())

    def get_all_sic_codes(self) -> List[str]:
        """Get list of all mapped SIC codes."""
        return list(self.sic_map.keys())
