"""
Installation validation script
Run this to verify all dependencies are correctly installed
"""

import sys
from typing import Tuple


def check_import(module_name: str, package_name: str = None) -> Tuple[bool, str]:
    """
    Check if a module can be imported

    Args:
        module_name: Name of the module to import
        package_name: Display name (if different from module_name)

    Returns:
        Tuple of (success, version_or_error)
    """
    package_name = package_name or module_name
    try:
        module = __import__(module_name)
        version = getattr(module, '__version__', 'installed')
        return True, version
    except ImportError as e:
        return False, str(e)


def check_spacy_model(model_name: str = "en_core_web_sm") -> Tuple[bool, str]:
    """
    Check if spaCy model is installed

    Args:
        model_name: Name of spaCy model to check

    Returns:
        Tuple of (success, message)
    """
    try:
        import spacy
        nlp = spacy.load(model_name)
        return True, f"Model loaded (vocab: {len(nlp.vocab):,} words)"
    except ImportError:
        return False, "spaCy not installed"
    except OSError:
        return False, f"Model '{model_name}' not found"
    except Exception as e:
        return False, str(e)


def main():
    """Run installation checks"""
    print("=" * 70)
    print("SEC Filing Analyzer - Installation Check")
    print("=" * 70)
    print()

    # Core dependencies
    print("Checking Core Dependencies:")
    print("-" * 70)

    core_deps = [
        ("spacy", "spaCy"),
        ("transformers", "Transformers"),
        ("torch", "PyTorch"),
        ("pandas", "Pandas"),
        ("numpy", "NumPy"),
        ("sklearn", "scikit-learn"),
        ("streamlit", "Streamlit"),
        ("bs4", "BeautifulSoup4"),
        ("lxml", "lxml"),
    ]

    all_core_ok = True
    for module, display_name in core_deps:
        success, version = check_import(module, display_name)
        status = "[OK]" if success else "[MISSING]"
        if success:
            print(f"  {status} {display_name:20} {version}")
        else:
            print(f"  {status} {display_name:20} NOT INSTALLED")
            all_core_ok = False

    print()

    # SEC-specific dependencies
    print("Checking SEC Parsing Dependencies:")
    print("-" * 70)

    sec_deps = [
        ("sec_parser", "sec-parser"),
        ("sec_downloader", "sec-downloader"),
    ]

    all_sec_ok = True
    for module, display_name in sec_deps:
        success, version = check_import(module, display_name)
        status = "[OK]" if success else "[MISSING]"
        if success:
            print(f"  {status} {display_name:20} {version}")
        else:
            print(f"  {status} {display_name:20} NOT INSTALLED")
            all_sec_ok = False

    print()

    # Check spaCy model
    print("Checking spaCy Language Model:")
    print("-" * 70)

    model_success, model_info = check_spacy_model("en_core_web_sm")
    status = "[OK]" if model_success else "[MISSING]"
    print(f"  {status} en_core_web_sm:     {model_info}")

    if not model_success:
        print()
        print("  [WARNING] spaCy model not installed!")
        print("  Run: python -m spacy download en_core_web_sm")
        print("  Or:  python setup_nlp_models.py")

    print()

    # Check text cleaning module
    print("Checking Text Cleaning Module:")
    print("-" * 70)

    try:
        from src.preprocessing.cleaning import TextCleaner, clean_filing_text
        print("  [OK] TextCleaner imported successfully")

        # Try to create cleaner
        cleaner = TextCleaner()
        print("  [OK] TextCleaner initialized (basic mode)")

        if model_success:
            cleaner_advanced = TextCleaner(use_lemmatization=True)
            if cleaner_advanced.nlp:
                print("  [OK] TextCleaner initialized (advanced NLP mode)")
                cleaning_ok = True
            else:
                print("  [WARNING] Advanced NLP mode not available")
                cleaning_ok = False
        else:
            print("  [WARNING] Advanced NLP mode requires spaCy model")
            cleaning_ok = False

    except Exception as e:
        print(f"  [ERROR] Error loading cleaning module: {e}")
        cleaning_ok = False

    print()

    # Summary
    print("=" * 70)
    print("Installation Summary:")
    print("=" * 70)

    if all_core_ok and all_sec_ok and model_success and cleaning_ok:
        print("[SUCCESS] ALL CHECKS PASSED - Installation is complete!")
        print()
        print("You can now use the text cleaning module:")
        print("  from src.preprocessing.cleaning import TextCleaner")
        print()
        print("Try the examples:")
        print("  python src/preprocessing/cleaning.py")
        print("  python tests/test_cleaning.py")
        return_code = 0
    else:
        print("[FAILED] SOME CHECKS FAILED - Installation incomplete")
        print()

        if not all_core_ok:
            print("Missing core dependencies:")
            print("  Run: pip install -e .")

        if not all_sec_ok:
            print("Missing SEC parsing libraries:")
            print("  Run: pip install sec-parser sec-downloader")

        if not model_success:
            print("Missing spaCy language model:")
            print("  Run: python -m spacy download en_core_web_sm")
            print("  Or:  python setup_nlp_models.py")

        if not cleaning_ok:
            print("Text cleaning module not working:")
            print("  Ensure all dependencies are installed")
            print("  Check: python src/preprocessing/cleaning.py")

        return_code = 1

    print()
    print("For detailed installation instructions, see: INSTALLATION.md")
    print("=" * 70)

    return return_code


if __name__ == "__main__":
    sys.exit(main())
