"""
Post-installation script to download required spaCy language models
Run this after installing the package: python setup_nlp_models.py
"""

import subprocess
import sys


def download_spacy_model(model_name="en_core_web_sm"):
    """
    Download spaCy language model

    Args:
        model_name: Name of the spaCy model to download
            - en_core_web_sm (12 MB) - Default, fast
            - en_core_web_md (40 MB) - Better accuracy
            - en_core_web_lg (560 MB) - Best accuracy
    """
    print(f"Downloading spaCy model: {model_name}")
    print("=" * 60)

    try:
        # Try to load the model first to see if it's already installed
        import spacy
        try:
            nlp = spacy.load(model_name)
            print(f"✓ Model '{model_name}' is already installed!")
            return True
        except OSError:
            print(f"Model '{model_name}' not found. Downloading...")

        # Download the model
        subprocess.check_call(
            [sys.executable, "-m", "spacy", "download", model_name],
            stdout=sys.stdout,
            stderr=sys.stderr
        )

        # Verify installation
        nlp = spacy.load(model_name)
        print(f"\n✓ Successfully installed spaCy model: {model_name}")
        print(f"  Pipeline components: {nlp.pipe_names}")
        print(f"  Vocabulary size: {len(nlp.vocab)}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"\n✗ Error downloading model: {e}")
        return False
    except ImportError:
        print("\n✗ spaCy is not installed!")
        print("  Install it with: pip install spacy")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return False


def main():
    """Main setup function"""
    print("=" * 60)
    print("SEC Filing Analyzer - NLP Models Setup")
    print("=" * 60)
    print()

    print("This script will download the required spaCy language models.")
    print()

    # Ask user which model to download
    print("Available models:")
    print("  1. en_core_web_sm (12 MB)  - Small, fast (RECOMMENDED)")
    print("  2. en_core_web_md (40 MB)  - Medium, better accuracy")
    print("  3. en_core_web_lg (560 MB) - Large, best accuracy")
    print()

    choice = input("Select model to download (1-3) [default: 1]: ").strip()

    model_map = {
        "1": "en_core_web_sm",
        "2": "en_core_web_md",
        "3": "en_core_web_lg",
        "": "en_core_web_sm",  # default
    }

    model_name = model_map.get(choice, "en_core_web_sm")
    print()

    # Download the selected model
    success = download_spacy_model(model_name)

    print()
    print("=" * 60)
    if success:
        print("✓ Setup completed successfully!")
        print()
        print("You can now use the text cleaning module:")
        print("  from src.preprocessing.cleaning import TextCleaner")
        print()
        print("Example:")
        print("  cleaner = TextCleaner(use_lemmatization=True)")
        print("  cleaned = cleaner.clean_text(text, deep_clean=True)")
    else:
        print("✗ Setup failed. Please install models manually:")
        print(f"  python -m spacy download {model_name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
