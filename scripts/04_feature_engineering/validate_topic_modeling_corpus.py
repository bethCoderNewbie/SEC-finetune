"""
Corpus Validation Utility for Topic Modeling

This script helps you validate that your Item 1A corpus meets the requirements
for optimal LDA training before investing time in model training.

Usage:
    python scripts/04_feature_engineering/validate_topic_modeling_corpus.py
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple
from collections import Counter
import numpy as np

from src.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


class CorpusValidator:
    """
    Validates corpus quality for LDA topic modeling.
    """

    def __init__(self, documents: List[Dict]):
        """
        Initialize validator.

        Args:
            documents: List of dicts with 'text' and optional metadata
        """
        self.documents = documents
        self.texts = [doc.get('text', '') for doc in documents]
        self.results = {}

    def validate_all(self) -> Dict:
        """Run all validation checks."""
        logger.info("=" * 80)
        logger.info("TOPIC MODELING CORPUS VALIDATION")
        logger.info("=" * 80)

        self.results['corpus_size'] = self._check_corpus_size()
        self.results['document_lengths'] = self._check_document_lengths()
        self.results['vocabulary'] = self._check_vocabulary()
        self.results['diversity'] = self._check_diversity()
        self.results['quality'] = self._check_text_quality()
        self.results['overall'] = self._overall_assessment()

        return self.results

    def _check_corpus_size(self) -> Dict:
        """Check if corpus size is adequate."""
        logger.info("\n1. CORPUS SIZE")
        logger.info("-" * 80)

        num_docs = len(self.documents)

        status = "❌ INSUFFICIENT"
        recommendation = "Need at least 200 documents for reliable topics"

        if num_docs >= 500:
            status = "✅ EXCELLENT"
            recommendation = "Corpus size is optimal for high-quality topics"
        elif num_docs >= 200:
            status = "✅ GOOD"
            recommendation = "Corpus size is sufficient for production use"
        elif num_docs >= 100:
            status = "⚠️  ACCEPTABLE"
            recommendation = "Usable but consider adding more documents"
        elif num_docs >= 50:
            status = "⚠️  MINIMAL"
            recommendation = "OK for prototyping only, add more for production"

        logger.info(f"Number of documents: {num_docs}")
        logger.info(f"Status: {status}")
        logger.info(f"Recommendation: {recommendation}")

        return {
            'num_documents': num_docs,
            'status': status,
            'recommendation': recommendation,
            'pass': num_docs >= 200
        }

    def _check_document_lengths(self) -> Dict:
        """Check document length statistics."""
        logger.info("\n2. DOCUMENT LENGTHS")
        logger.info("-" * 80)

        lengths = [len(text.split()) for text in self.texts]
        avg_length = np.mean(lengths)
        median_length = np.median(lengths)
        std_length = np.std(lengths)
        min_length = np.min(lengths)
        max_length = np.max(lengths)

        # Check for issues
        issues = []
        warnings = []

        too_short = sum(1 for l in lengths if l < 500)
        if too_short > 0:
            issues.append(f"{too_short} documents < 500 words (too short)")

        too_long = sum(1 for l in lengths if l > 10000)
        if too_long > 0:
            warnings.append(f"{too_long} documents > 10,000 words (consider chunking)")

        if avg_length < 1000:
            issues.append("Average length < 1,000 words (documents too short)")
        elif avg_length > 8000:
            warnings.append("Average length > 8,000 words (may want to truncate)")

        status = "✅ GOOD"
        if issues:
            status = "❌ ISSUES FOUND"
        elif warnings:
            status = "⚠️  WARNINGS"

        logger.info(f"Average length: {avg_length:.0f} words")
        logger.info(f"Median length: {median_length:.0f} words")
        logger.info(f"Std deviation: {std_length:.0f} words")
        logger.info(f"Range: {min_length} - {max_length} words")
        logger.info(f"Status: {status}")

        if issues:
            logger.info("\n⚠️  ISSUES:")
            for issue in issues:
                logger.info(f"  - {issue}")

        if warnings:
            logger.info("\n⚠️  WARNINGS:")
            for warning in warnings:
                logger.info(f"  - {warning}")

        return {
            'avg_length': avg_length,
            'median_length': median_length,
            'std_length': std_length,
            'min_length': min_length,
            'max_length': max_length,
            'too_short': too_short,
            'too_long': too_long,
            'status': status,
            'issues': issues,
            'warnings': warnings,
            'pass': len(issues) == 0
        }

    def _check_vocabulary(self) -> Dict:
        """Check vocabulary size and distribution."""
        logger.info("\n3. VOCABULARY")
        logger.info("-" * 80)

        # Build vocabulary
        all_words = []
        for text in self.texts:
            words = text.lower().split()
            all_words.extend(words)

        vocab = set(all_words)
        vocab_size = len(vocab)

        # Word frequency distribution
        word_freq = Counter(all_words)
        most_common = word_freq.most_common(20)

        # Check for issues
        status = "✅ GOOD"
        issues = []
        recommendations = []

        if vocab_size < 1000:
            status = "❌ TOO SMALL"
            issues.append("Vocabulary < 1,000 words (corpus too small or low diversity)")
            recommendations.append("Add more documents or check text quality")
        elif vocab_size < 3000:
            status = "⚠️  SMALL"
            issues.append("Vocabulary < 3,000 words (may have limited topics)")
            recommendations.append("Consider adding more documents")
        elif vocab_size > 15000:
            status = "⚠️  VERY LARGE"
            issues.append("Vocabulary > 15,000 words (may slow training)")
            recommendations.append("Will be filtered during preprocessing")

        # Check if most common words are generic (sign of poor preprocessing)
        generic_words = {'the', 'a', 'an', 'and', 'or', 'but', 'of', 'to', 'in', 'for'}
        top_10_words = [word for word, _ in most_common[:10]]
        generic_in_top10 = sum(1 for w in top_10_words if w in generic_words)

        if generic_in_top10 > 5:
            issues.append("Many generic words in top 10 (needs better preprocessing)")
            recommendations.append("Apply stopword removal before training")

        logger.info(f"Vocabulary size: {vocab_size:,} unique words")
        logger.info(f"Total words: {len(all_words):,}")
        logger.info(f"Status: {status}")

        logger.info(f"\nTop 20 most common words:")
        for word, count in most_common:
            logger.info(f"  {word}: {count:,}")

        if issues:
            logger.info("\n⚠️  ISSUES:")
            for issue in issues:
                logger.info(f"  - {issue}")

        if recommendations:
            logger.info("\n💡 RECOMMENDATIONS:")
            for rec in recommendations:
                logger.info(f"  - {rec}")

        return {
            'vocab_size': vocab_size,
            'total_words': len(all_words),
            'most_common': most_common[:20],
            'status': status,
            'issues': issues,
            'recommendations': recommendations,
            'pass': 3000 <= vocab_size <= 15000
        }

    def _check_diversity(self) -> Dict:
        """Check corpus diversity (industries, companies, time)."""
        logger.info("\n4. CORPUS DIVERSITY")
        logger.info("-" * 80)

        # Extract metadata
        companies = [doc.get('company', 'unknown') for doc in self.documents]
        industries = [doc.get('industry', 'unknown') for doc in self.documents]
        years = [doc.get('filing_year', 'unknown') for doc in self.documents]

        unique_companies = len(set(companies))
        unique_industries = len(set(industries))
        unique_years = len(set(years))

        # Industry distribution
        industry_counts = Counter(industries)
        year_counts = Counter(years)

        # Check diversity
        issues = []
        recommendations = []
        status = "✅ GOOD"

        if unique_companies < 40:
            issues.append(f"Only {unique_companies} unique companies (low diversity)")
            recommendations.append("Add more companies for better generalization")
            status = "⚠️  LOW DIVERSITY"

        if unique_industries < 5:
            issues.append(f"Only {unique_industries} industries (very limited)")
            recommendations.append("Add documents from more industry sectors")
            status = "❌ INSUFFICIENT DIVERSITY"

        if unique_years < 2:
            issues.append("Documents from single year only")
            recommendations.append("Consider multi-year corpus for temporal coverage")

        # Check for extreme imbalance
        if unique_industries > 1:
            max_industry_pct = max(industry_counts.values()) / len(self.documents)
            if max_industry_pct > 0.5:
                issues.append(f"One industry dominates (>{max_industry_pct:.0%} of corpus)")
                recommendations.append("Balance industry representation")

        logger.info(f"Unique companies: {unique_companies}")
        logger.info(f"Unique industries: {unique_industries}")
        logger.info(f"Unique years: {unique_years}")
        logger.info(f"Status: {status}")

        if unique_industries > 1 and unique_industries <= 20:
            logger.info(f"\nIndustry distribution:")
            for industry, count in industry_counts.most_common():
                pct = count / len(self.documents) * 100
                logger.info(f"  {industry}: {count} ({pct:.1f}%)")

        if unique_years > 1:
            logger.info(f"\nYear distribution:")
            for year, count in sorted(year_counts.items(), reverse=True):
                pct = count / len(self.documents) * 100
                logger.info(f"  {year}: {count} ({pct:.1f}%)")

        if issues:
            logger.info("\n⚠️  DIVERSITY ISSUES:")
            for issue in issues:
                logger.info(f"  - {issue}")

        if recommendations:
            logger.info("\n💡 RECOMMENDATIONS:")
            for rec in recommendations:
                logger.info(f"  - {rec}")

        return {
            'unique_companies': unique_companies,
            'unique_industries': unique_industries,
            'unique_years': unique_years,
            'industry_distribution': dict(industry_counts),
            'year_distribution': dict(year_counts),
            'status': status,
            'issues': issues,
            'recommendations': recommendations,
            'pass': unique_companies >= 40 and unique_industries >= 5
        }

    def _check_text_quality(self) -> Dict:
        """Check text quality (encoding, special chars, etc)."""
        logger.info("\n5. TEXT QUALITY")
        logger.info("-" * 80)

        issues = []
        warnings = []

        # Check for common quality issues
        empty_docs = sum(1 for text in self.texts if len(text.strip()) == 0)
        if empty_docs > 0:
            issues.append(f"{empty_docs} empty documents")

        # Check for excessive HTML/special characters
        html_heavy = 0
        mostly_numbers = 0
        mostly_uppercase = 0

        for text in self.texts:
            if not text:
                continue

            # HTML tags
            if text.count('<') > 50 or text.count('>') > 50:
                html_heavy += 1

            # Numbers
            if sum(c.isdigit() for c in text) / len(text) > 0.15:
                mostly_numbers += 1

            # Uppercase
            alpha_chars = sum(c.isalpha() for c in text)
            if alpha_chars > 0:
                upper_pct = sum(c.isupper() for c in text if c.isalpha()) / alpha_chars
                if upper_pct > 0.4:
                    mostly_uppercase += 1

        if html_heavy > 0:
            issues.append(f"{html_heavy} documents with excessive HTML tags")
        if mostly_numbers > len(self.texts) * 0.1:
            warnings.append(f"{mostly_numbers} documents are mostly numbers")
        if mostly_uppercase > len(self.texts) * 0.1:
            warnings.append(f"{mostly_uppercase} documents are mostly uppercase")

        # Check for risk-related content
        risk_keywords = ['risk', 'could', 'may', 'uncertain', 'adverse', 'negatively']
        has_risk_content = 0
        for text in self.texts:
            if any(keyword in text.lower() for keyword in risk_keywords):
                has_risk_content += 1

        risk_pct = has_risk_content / len(self.texts) if self.texts else 0
        if risk_pct < 0.7:
            warnings.append(
                f"Only {risk_pct:.0%} of documents contain risk keywords "
                "(may not be Item 1A sections)"
            )

        status = "✅ GOOD"
        if issues:
            status = "❌ QUALITY ISSUES"
        elif warnings:
            status = "⚠️  WARNINGS"

        logger.info(f"Empty documents: {empty_docs}")
        logger.info(f"HTML-heavy documents: {html_heavy}")
        logger.info(f"Number-heavy documents: {mostly_numbers}")
        logger.info(f"Uppercase-heavy documents: {mostly_uppercase}")
        logger.info(f"Documents with risk content: {has_risk_content} ({risk_pct:.0%})")
        logger.info(f"Status: {status}")

        if issues:
            logger.info("\n⚠️  QUALITY ISSUES:")
            for issue in issues:
                logger.info(f"  - {issue}")

        if warnings:
            logger.info("\n⚠️  WARNINGS:")
            for warning in warnings:
                logger.info(f"  - {warning}")

        return {
            'empty_docs': empty_docs,
            'html_heavy': html_heavy,
            'mostly_numbers': mostly_numbers,
            'mostly_uppercase': mostly_uppercase,
            'has_risk_content': has_risk_content,
            'risk_content_pct': risk_pct,
            'status': status,
            'issues': issues,
            'warnings': warnings,
            'pass': len(issues) == 0
        }

    def _overall_assessment(self) -> Dict:
        """Provide overall assessment and recommendations."""
        logger.info("\n" + "=" * 80)
        logger.info("OVERALL ASSESSMENT")
        logger.info("=" * 80)

        # Count passes/fails
        checks = [
            ('Corpus Size', self.results['corpus_size']['pass']),
            ('Document Lengths', self.results['document_lengths']['pass']),
            ('Vocabulary', self.results['vocabulary']['pass']),
            ('Diversity', self.results['diversity']['pass']),
            ('Text Quality', self.results['quality']['pass']),
        ]

        passed = sum(1 for _, p in checks if p)
        total = len(checks)

        logger.info(f"\nValidation Results: {passed}/{total} checks passed")
        logger.info("")

        for check_name, check_pass in checks:
            status = "✅ PASS" if check_pass else "❌ FAIL"
            logger.info(f"  {check_name}: {status}")

        # Overall recommendation
        logger.info("\n" + "-" * 80)

        if passed == total:
            recommendation = "READY FOR TRAINING"
            message = (
                "🎉 Your corpus meets all requirements!\n\n"
                "You can proceed with LDA training. Expected results:\n"
                f"  - Training time: ~{self._estimate_training_time()} minutes\n"
                f"  - Inference latency: ~{self._estimate_inference_latency()}ms\n"
                f"  - Expected coherence: {self._estimate_coherence()}\n\n"
                "Recommended configuration:\n"
                "  - num_topics: 15\n"
                "  - passes: 10\n"
                "  - iterations: 100"
            )
        elif passed >= 3:
            recommendation = "ACCEPTABLE WITH IMPROVEMENTS"
            message = (
                "⚠️  Your corpus is usable but has some issues.\n\n"
                "You can train a model, but quality may be suboptimal.\n"
                "Review the issues above and consider improvements."
            )
        else:
            recommendation = "NOT READY"
            message = (
                "❌ Your corpus needs significant improvements.\n\n"
                "Training now will likely produce poor results.\n"
                "Address the issues above before proceeding."
            )

        logger.info(f"RECOMMENDATION: {recommendation}")
        logger.info("")
        logger.info(message)
        logger.info("")
        logger.info("=" * 80)

        return {
            'passed_checks': passed,
            'total_checks': total,
            'recommendation': recommendation,
            'ready_for_training': passed >= 4,
        }

    def _estimate_training_time(self) -> str:
        """Estimate training time based on corpus size."""
        n = self.results['corpus_size']['num_documents']
        if n < 100:
            return "2-3"
        elif n < 300:
            return "5-8"
        elif n < 500:
            return "8-12"
        else:
            return "12-20"

    def _estimate_inference_latency(self) -> str:
        """Estimate inference latency."""
        vocab = self.results['vocabulary']['vocab_size']
        if vocab < 3000:
            return "60-80"
        elif vocab < 5000:
            return "80-100"
        elif vocab < 8000:
            return "100-120"
        else:
            return "120-150"

    def _estimate_coherence(self) -> str:
        """Estimate expected coherence score."""
        n = self.results['corpus_size']['num_documents']
        diversity_pass = self.results['diversity']['pass']

        if n >= 500 and diversity_pass:
            return "0.50-0.55 (excellent)"
        elif n >= 300 and diversity_pass:
            return "0.45-0.50 (good)"
        elif n >= 200:
            return "0.40-0.45 (acceptable)"
        else:
            return "0.35-0.40 (poor)"


def load_corpus_from_extracted_data() -> List[Dict]:
    """Load Item 1A corpus from extracted data directory."""
    extracted_dir = settings.paths.extracted_data_dir
    documents = []

    logger.info(f"Loading corpus from: {extracted_dir}")

    for json_file in extracted_dir.glob("*_extracted.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # Extract Item 1A section
                if 'sections' in data and 'part1item1a' in data['sections']:
                    item1a = data['sections']['part1item1a']
                    documents.append({
                        'text': item1a.get('text', ''),
                        'company': data.get('company', 'unknown'),
                        'industry': data.get('industry', 'unknown'),
                        'filing_year': data.get('filing_date', '')[:4] if data.get('filing_date') else 'unknown',
                        'form_type': data.get('form_type', '10-K'),
                    })
        except Exception as e:
            logger.warning(f"Failed to load {json_file}: {e}")

    logger.info(f"Loaded {len(documents)} Item 1A sections\n")
    return documents


def main():
    """Main validation workflow."""
    # Load corpus
    corpus = load_corpus_from_extracted_data()

    if not corpus:
        logger.error(
            "No Item 1A sections found. Please run section extraction first:\n"
            "  python scripts/02_extraction/extract_sections.py"
        )
        return

    # Validate
    validator = CorpusValidator(corpus)
    results = validator.validate_all()

    # Save results
    output_dir = settings.paths.logs_dir / "corpus_validation"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "validation_results.json"

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"\nDetailed results saved to: {output_file}")


if __name__ == "__main__":
    main()
