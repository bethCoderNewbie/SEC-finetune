"""
Streamlit application for SEC 10-K Risk Analysis
MVP for testing the end-to-end NLP pipeline
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import settings
from src.preprocessing.parser import SECFilingParser
from src.preprocessing.extractor import RiskFactorExtractor
from src.preprocessing.cleaning import TextCleaner
from src.preprocessing.segmenter import RiskSegmenter
from src.analysis.inference import RiskClassifier


# Page configuration
st.set_page_config(
    page_title="SEC 10-K Risk Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS using Paper Dashboard color scheme
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Muli:wght@300;400;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

:root {
    --primary-color: #cf223a;
    --info-color: #ac9590;
    --success-color: #738549;
    --warning-color: #f17511;
    --danger-color: #f44336;
    --dark-bg: #0f244d;
    --muted-color: #9f8d82;
    --text-dark: #403d39;
    --text-light: #66615b;
    --border-color: #dbcdc6;
}

/* Global font */
html, body, [class*="css"] {
    font-family: 'Muli', 'Helvetica', Arial, sans-serif !important;
}

/* Main container */
.main {
    background-color: #f4f3ef;
}

/* Headers */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Muli', 'Helvetica', Arial, sans-serif !important;
    color: var(--text-dark) !important;
}

h1 {
    font-size: 3.2em !important;
    font-weight: 400 !important;
}

h2 {
    font-size: 2.6em !important;
}

h3 {
    font-size: 1.825em !important;
    line-height: 1.4 !important;
}

/* Sidebar styling */
section[data-testid="stSidebar"] {
    background-color: var(--dark-bg) !important;
}

section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] div {
    color: white !important;
}

/* Buttons */
.stButton > button {
    background-color: var(--primary-color) !important;
    color: white !important;
    border: 2px solid var(--primary-color) !important;
    border-radius: 4px !important;
    font-weight: 600 !important;
    padding: 12px 30px !important;
    font-family: 'Muli', sans-serif !important;
    transition: all 0.3s ease !important;
}

.stButton > button:hover {
    background-color: #b01e33 !important;
    border-color: #b01e33 !important;
    box-shadow: 0 4px 8px rgba(207, 34, 58, 0.3) !important;
}

/* Download button */
.stDownloadButton > button {
    background-color: var(--success-color) !important;
    color: white !important;
    border: 2px solid var(--success-color) !important;
}

.stDownloadButton > button:hover {
    background-color: #5f6d3c !important;
}

/* Info/Success/Warning/Error messages */
.stAlert {
    border-radius: 4px !important;
    font-family: 'Muli', sans-serif !important;
}

div[data-baseweb="notification"] {
    border-radius: 4px !important;
}

/* Progress bar */
.stProgress > div > div > div {
    background-color: var(--primary-color) !important;
}

/* Dataframe styling */
.dataframe {
    font-family: 'Muli', sans-serif !important;
    border: 1px solid var(--border-color) !important;
}

/* Metrics */
div[data-testid="stMetric"] {
    background-color: white;
    padding: 20px;
    border-radius: 4px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

div[data-testid="stMetricValue"] {
    color: var(--primary-color) !important;
    font-size: 2em !important;
    font-weight: 600 !important;
}

div[data-testid="stMetricLabel"] {
    color: var(--text-light) !important;
    font-size: 0.9em !important;
    text-transform: uppercase !important;
    font-weight: 600 !important;
}

/* Expander */
.streamlit-expanderHeader {
    background-color: #fafafa !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 4px !important;
    font-family: 'Muli', sans-serif !important;
}

/* Select box */
.stSelectbox label {
    color: var(--text-dark) !important;
    font-weight: 600 !important;
}

/* Text area */
.stTextArea label {
    color: var(--text-dark) !important;
    font-weight: 600 !important;
}

/* Custom card styling */
.custom-card {
    background: white;
    padding: 25px;
    border-radius: 6px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    margin: 15px 0;
}

/* Material Icons styling */
.material-symbols-outlined {
    font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 48;
    vertical-align: middle;
    font-size: 1.5em;
}
</style>
""", unsafe_allow_html=True)

# Title with Material Icon
st.markdown("""
<h1>
<span class="material-symbols-outlined" style="font-size: 1.2em; color: #cf223a;">analytics</span>
SEC 10-K Risk Factor Analyzer
</h1>
""", unsafe_allow_html=True)

st.markdown('<h3 style="color: #9f8d82; font-weight: 400;">MVP: Parse → Segment → Categorize → Display</h3>', unsafe_allow_html=True)

# Sidebar with Material Icons
st.sidebar.markdown("""
<h2 style="color: white;">
<span class="material-symbols-outlined">settings</span>
Configuration
</h2>
""", unsafe_allow_html=True)

st.sidebar.markdown("**Pipeline Components:**")
st.sidebar.markdown('<span class="material-symbols-outlined" style="color: #738549; font-size: 1.2em;">check_circle</span> Parser', unsafe_allow_html=True)
st.sidebar.markdown('<span class="material-symbols-outlined" style="color: #738549; font-size: 1.2em;">check_circle</span> Risk Factor Extractor', unsafe_allow_html=True)
st.sidebar.markdown('<span class="material-symbols-outlined" style="color: #738549; font-size: 1.2em;">check_circle</span> Text Cleaner', unsafe_allow_html=True)
st.sidebar.markdown('<span class="material-symbols-outlined" style="color: #738549; font-size: 1.2em;">check_circle</span> Segmenter', unsafe_allow_html=True)
st.sidebar.markdown('<span class="material-symbols-outlined" style="color: #738549; font-size: 1.2em;">check_circle</span> Zero-Shot Classifier', unsafe_allow_html=True)


def get_filing_files():
    """
    Get list of SEC filing files in data/raw/

    File types are configured in config.INPUT_FILE_EXTENSIONS
    Supports: .html, .txt, or both
    """
    raw_dir = settings.paths.raw_data_dir
    if not raw_dir.exists():
        return []

    all_files = []
    for ext in settings.sec_parser.input_file_extensions:
        # Normalize extension (remove leading dot if present)
        ext = ext.lstrip('.')
        pattern = f"*.{ext}"
        all_files.extend(raw_dir.glob(pattern))

    return sorted([f.name for f in all_files])


def run_analysis_pipeline(file_path: Path) -> pd.DataFrame:
    """
    Run the complete analysis pipeline on a filing

    Args:
        file_path: Path to the .txt file

    Returns:
        DataFrame with segments and categories
    """
    # Step 1: Parse the filing
    st.info("🔄 Step 1/5: Parsing filing...")
    parser = SECFilingParser()
    filing = parser.parse_filing(file_path)
    st.success(f"✓ Parsed {len(filing)} semantic elements")

    # Step 2: Extract Risk Factors section
    st.info("🔄 Step 2/5: Extracting Risk Factors section...")
    extractor = RiskFactorExtractor()
    risk_section = extractor.extract(filing)

    if risk_section is None:
        st.error("Could not find Risk Factors section (Item 1A)")
        return pd.DataFrame()

    st.success(f"✓ Extracted {len(risk_section.text):,} characters")

    # Step 3: Clean the text
    st.info("🔄 Step 3/5: Cleaning text...")
    cleaner = TextCleaner()
    clean_text = cleaner.clean_text(risk_section.text)
    st.success(f"✓ Cleaned text: {len(clean_text):,} characters")

    # Step 4: Segment into individual risks
    st.info("🔄 Step 4/5: Segmenting into individual risks...")
    segmenter = RiskSegmenter()
    segments = segmenter.segment_risks(clean_text)
    st.success(f"✓ Found {len(segments)} risk segments")

    if len(segments) == 0:
        st.warning("No risk segments found. The text may not be properly formatted.")
        return pd.DataFrame()

    # Step 5: Classify segments
    st.info("🔄 Step 5/5: Classifying risks (this may take a few minutes)...")

    progress_bar = st.progress(0)
    classifier = RiskClassifier()

    results = []
    for i, segment in enumerate(segments):
        progress_bar.progress((i + 1) / len(segments))
        classification = classifier.classify_segment(segment)

        results.append({
            'Segment #': i + 1,
            'Risk Category': classification['label'],
            'Confidence': f"{classification['score']:.2%}",
            'Segment Text': segment[:500] + "..." if len(segment) > 500 else segment,
            'Full Text': segment,
            'Score': classification['score']
        })

    st.success(f"✓ Classified {len(results)} risk segments")

    # Convert to DataFrame
    df = pd.DataFrame(results)
    return df


# Main UI
st.markdown("---")

# File selection
filing_files = get_filing_files()

if not filing_files:
    # Build friendly extension list for display
    ext_display = ", ".join([f".{ext.lstrip('.')}" for ext in settings.sec_parser.input_file_extensions])
    st.warning(f"⚠️ No {ext_display} files found in `{settings.paths.raw_data_dir}`")
    st.markdown(f"""
    <div class="custom-card">
    <h3><span class="material-symbols-outlined">info</span> Getting Started</h3>
    <p><strong>To use this application:</strong></p>
    <ol>
        <li>Place a 10-K filing file ({ext_display}) in the <code>data/raw/</code> directory</li>
        <li>Refresh this page</li>
        <li>Click "Run Analysis"</li>
    </ol>
    <p><strong>Note:</strong> The sec-parser library requires HTML files for semantic parsing.
    Using .txt files will require a different parsing approach.</p>
    </div>
    """, unsafe_allow_html=True)

    # Show example of where to place files
    example_ext = settings.sec_parser.input_file_extensions[0].lstrip('.')
    st.code(f"Example: {settings.paths.raw_data_dir / f'company_10k.{example_ext}'}", language="text")

else:
    st.success(f"✓ Found {len(filing_files)} file(s) in data/raw/")

    selected_file = st.selectbox(
        "📄 Select a 10-K filing:",
        filing_files,
        help="Choose a filing to analyze"
    )

    st.markdown("---")

    # Run Analysis button
    if st.button("🚀 Run Analysis", type="primary", use_container_width=True):
        file_path = settings.paths.raw_data_dir / selected_file

        with st.spinner("Running analysis pipeline..."):
            try:
                df = run_analysis_pipeline(file_path)

                if not df.empty:
                    st.markdown("---")
                    st.markdown("""
                    <h2>
                    <span class="material-symbols-outlined" style="color: #cf223a;">description</span>
                    Analysis Results
                    </h2>
                    """, unsafe_allow_html=True)

                    # Summary metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Segments", len(df))
                    with col2:
                        avg_confidence = df['Score'].mean()
                        st.metric("Avg Confidence", f"{avg_confidence:.1%}")
                    with col3:
                        unique_categories = df['Risk Category'].nunique()
                        st.metric("Unique Categories", unique_categories)

                    st.markdown("---")

                    # Category distribution
                    st.markdown("""
                    <h3>
                    <span class="material-symbols-outlined">bar_chart</span>
                    Risk Category Distribution
                    </h3>
                    """, unsafe_allow_html=True)
                    category_counts = df['Risk Category'].value_counts()
                    st.bar_chart(category_counts)

                    st.markdown("---")

                    # Results table
                    st.markdown("""
                    <h3>
                    <span class="material-symbols-outlined">table_chart</span>
                    Detailed Results
                    </h3>
                    """, unsafe_allow_html=True)

                    # Display table without full text column
                    display_df = df[['Segment #', 'Risk Category', 'Confidence', 'Segment Text']].copy()
                    st.dataframe(
                        display_df,
                        use_container_width=True,
                        height=400
                    )

                    # Download button
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Results as CSV",
                        data=csv,
                        file_name=f"risk_analysis_{selected_file.replace('.txt', '')}.csv",
                        mime="text/csv"
                    )

                    # Expandable section for full text of each segment
                    st.markdown("---")
                    st.markdown("""
                    <h3>
                    <span class="material-symbols-outlined">search</span>
                    View Full Segment Text
                    </h3>
                    """, unsafe_allow_html=True)

                    for idx, row in df.iterrows():
                        with st.expander(f"Segment {row['Segment #']}: {row['Risk Category']} ({row['Confidence']})"):
                            st.markdown(f"**Category:** {row['Risk Category']}")
                            st.markdown(f"**Confidence:** {row['Confidence']}")
                            st.markdown("**Full Text:**")
                            st.text_area(
                                "Full segment text",
                                row['Full Text'],
                                height=200,
                                key=f"segment_{idx}",
                                label_visibility="collapsed"
                            )

            except Exception as e:
                st.error(f"Error during analysis: {e}")
                st.exception(e)

# Footer
st.markdown("---")
st.markdown("""
<div class="custom-card">
<h4><span class="material-symbols-outlined">lightbulb</span> About this MVP</h4>
<ul>
    <li>Tests the core NLP pipeline: Parse → Segment → Categorize → Display</li>
    <li>Uses zero-shot classification (no model training required)</li>
    <li>Processes local files only (no database or cloud services)</li>
    <li>Built for logical correctness validation, not performance</li>
</ul>
</div>
""", unsafe_allow_html=True)
