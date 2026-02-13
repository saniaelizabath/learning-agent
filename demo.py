import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import re
import io
import firebase_admin
from firebase_admin import credentials, firestore

# ---------------- PAGE CONFIG (must be first Streamlit call) ----------------
st.set_page_config(page_title="Textbook Topic Splitter", layout="wide")

# ---------------- FIREBASE SETUP ----------------
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_config.json")  # your service account JSON
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ---------------- REGEX PATTERNS ----------------
TOPIC_REGEX = re.compile(
    r"(Two Little Hands|Parts of the Body|Let us [A-Za-z]+|Picture\s+(Talk|Time)|"
    r"Sight words|New words|Alphabet song|Letter sounds|Odd One Out|Note to the teacher)",
    re.IGNORECASE
)
MERGE_WITH_PREVIOUS = {"sight words", "new words", "note to the teacher"}


# ---------------- PDF SPLITTING + TEXT EXTRACTION ----------------
def split_pdf_by_topics(pdf_file):
    """Splits a chapter PDF into topic-based sections and returns [(filename, pdf_bytes, text_content), ...]"""
    topics = []
    reader = PdfReader(pdf_file)

    with pdfplumber.open(pdf_file) as pdf:
        current_topic = None
        topic_writer = PdfWriter()
        topic_count = 0
        topic_text = []  # store text for current topic

        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""

            # Detect topic header
            match = TOPIC_REGEX.search(text)
            if match:
                header_text = match.group(0).strip()
                normalized = header_text.lower()

                if normalized in MERGE_WITH_PREVIOUS and current_topic is not None:
                    pass  # continue same topic
                else:
                    # Save current topic
                    if current_topic is not None and len(topic_writer.pages) > 0:
                        pdf_bytes = io.BytesIO()
                        topic_writer.write(pdf_bytes)
                        pdf_bytes.seek(0)
                        full_text = "\n".join(topic_text).strip()
                        topics.append((f"{topic_count:02d}_{current_topic}.pdf", pdf_bytes, full_text))

                        # reset for new topic
                        topic_writer = PdfWriter()
                        topic_text = []

                    # Start new topic
                    current_topic = re.sub(r"\s+", "_", header_text)
                    topic_count += 1

            # Add page + text
            topic_writer.add_page(reader.pages[i])
            if text.strip():
                topic_text.append(text.strip())

        # Save last topic
        if current_topic is not None and len(topic_writer.pages) > 0:
            pdf_bytes = io.BytesIO()
            topic_writer.write(pdf_bytes)
            pdf_bytes.seek(0)
            full_text = "\n".join(topic_text).strip()
            topics.append((f"{topic_count:02d}_{current_topic}.pdf", pdf_bytes, full_text))

    return topics


# ---------------- FIREBASE SAVE ----------------
def save_to_firebase(class_name, subject, chapter, topics):
    """
    Save extracted topics (title + content) into Firestore with schema:
    class -> subject -> chapter -> topics
    """
    class_ref = db.collection("classes").document(class_name)
    subject_ref = class_ref.collection("subjects").document(subject)
    chapter_ref = subject_ref.collection("chapters").document(chapter)

    for i, (filename, _, content) in enumerate(topics, 1):
        chapter_ref.collection("topics").document(f"topic{i}").set({
            "title": filename.replace(".pdf", ""),
            "content": content
        })


# ---------------- STREAMLIT APP ----------------
st.title("📘 NCERT Topic Splitter & Firebase Uploader")

class_name = st.text_input("Enter Class (e.g., Class1)")
subject = st.text_input("Enter Subject (e.g., English)")
chapter_name = st.text_input("Enter Chapter Name (e.g., Chapter1)")
uploaded_file = st.file_uploader("Upload Chapter PDF", type=["pdf"])

if uploaded_file and subject and chapter_name and class_name:
    st.subheader(f"📖 Processing {uploaded_file.name}")
    topics = split_pdf_by_topics(uploaded_file)

    st.success(f"Extracted {len(topics)} topics")

    # Show topics in Streamlit
    for i, (filename, _, content) in enumerate(topics, 1):
        with st.expander(f"Topic {i}: {filename}"):
            st.text_area("Extracted Text", content, height=200)

    if st.button("🚀 Save to Firebase"):
        save_to_firebase(class_name, subject, chapter_name, topics)
        st.success("✅ Full text content saved to Firebase Firestore!")
