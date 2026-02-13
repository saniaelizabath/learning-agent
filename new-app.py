import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import re
import io
import json
import time
from typing import Dict, Any, Optional
import os
import requests

import firebase_admin
from firebase_admin import credentials, firestore

# ---------------- PAGE CONFIG (must be first Streamlit call) ----------------
st.set_page_config(page_title="NCERT AI Teaching Assistant", layout="wide", page_icon="📚")

# ---------------- CONFIGURATION ----------------
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
MAX_TOKENS = 2048
TEMPERATURE = 0.3
TOP_P = 0.9

# ---------------- FIREBASE SETUP ----------------
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        try:
            config_paths = [
                "firebase_config.json",
                "./firebase_config.json",
                "config/firebase_config.json",
                "../firebase_config.json"
            ]
            cred = None
            for path in config_paths:
                try:
                    if os.path.exists(path):
                        cred = credentials.Certificate(path)
                        st.success(f"✅ Found Firebase config at: {path}")
                        break
                except Exception:
                    continue
            if not cred:
                st.error("❌ Firebase config file not found. Please ensure 'firebase_config.json' exists in your project directory.")
                return None
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            test_collection = db.collection("subjects").limit(1).get()
            st.success("✅ Successfully connected to Firestore!")
            return db
        except Exception as e:
            st.error(f"❌ Firebase initialization failed: {e}")
            st.error("Please check your Firebase credentials and internet connection.")
            return None
    return firestore.client()

def get_db_client():
    db = init_firebase()
    if not db:
        raise Exception("Firebase not initialized")
    return db

# ---------------- REGEX PATTERNS ----------------
TOPIC_REGEX = re.compile(
    r"(Two Little Hands|Parts of the Body|Let us [A-Za-z]+|Picture\s+(Talk|Time)|"
    r"Sight words|New words|Alphabet song|Letter sounds|Odd One Out|Note to the teacher)",
    re.IGNORECASE
)
MERGE_WITH_PREVIOUS = {"sight words", "new words", "note to the teacher"}

# ---------------- AI PROMPTS ----------------
SYSTEM_PROMPT = (
    "You are an expert K-12 lesson designer who creates concise, classroom-ready teaching plans. "
    "Output should be practical, specific, and age-appropriate. Avoid fluff."
)

USER_PROMPT_TEMPLATE = """You will receive the topic text extracted from a textbook chapter.

Return a STRUCTURED plan as compact JSON (no Markdown fences) with the keys below:

{{
  "title": string, 
  "estimated_duration_min": integer,
  "learning_objectives": [string, ...],
  "prerequisites": [string, ...],
  "key_vocabulary": [string, ...],
  "materials_needed": [string, ...],
  "engage_warmup": [{{"step": integer, "instruction": string}}],
  "explicit_instruction": [{{"step": integer, "instruction": string}}],
  "guided_practice": [{{"step": integer, "instruction": string}}],
  "independent_practice": [{{"task": string, "success_criteria": [string, ...]}}],
  "differentiation": {{
      "support": [string, ...],
      "challenge": [string, ...]
  }},
  "assessment": {{
      "formative_checks": [string, ...],
      "exit_ticket": string,
      "rubric_points": [string, ...]
  }},
  "misconceptions_and_fixes": [string, ...],
  "blackboard_notes": [string, ...],
  "home_connection": [string, ...],
  "teacher_tips": [string, ...]
}}

Constraints:
- Keep it focused on THIS topic only.
- If the text is mostly sight words/new words, tailor for phonics/recognition games.
- If it's picture talk/time, emphasize observation, questioning, and speaking.
- Keep steps actionable; avoid long paragraphs.
- Produce VALID JSON only.

CONTEXT:
Class: {class_name}
Subject: {subject}
Chapter: {chapter}
Topic title (from filename): {topic_title}

TOPIC TEXT:
\"\"\"{topic_text}\"\"\"
"""

# ---------------- AI FUNCTIONS ----------------
def call_ollama_api(prompt: str) -> str:
    import requests
    url = f"{OLLAMA_HOST}/api/generate"
    full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": full_prompt,
        "options": {
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
        },
        "stream": False
    }
    try:
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Ollama API call failed: {e}")
    except Exception as e:
        raise RuntimeError(f"Error processing Ollama response: {e}")

def safe_parse_json(s: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(s)
    except Exception:
        s2 = s.strip().strip("`").strip()
        try:
            return json.loads(s2)
        except Exception:
            return None

def plan_json_to_markdown(plan: Dict[str, Any]) -> str:
    def bullets(items) -> str:
        return "".join(f"- {it}\n" for it in items) if items else ""
    out = []
    out.append(f"# {plan.get('title', 'Teaching Plan')}")
    out.append(f"**Estimated Duration:** {plan.get('estimated_duration_min', '-')} minutes\n")
    out.append("## Learning Objectives")
    out.append(bullets(plan.get("learning_objectives", [])))
    out.append("## Prerequisites")
    out.append(bullets(plan.get("prerequisites", [])))
    out.append("## Key Vocabulary")
    out.append(bullets(plan.get("key_vocabulary", [])))
    out.append("## Materials Needed")
    out.append(bullets(plan.get("materials_needed", [])))
    out.append("## Engagement & Warmup")
    for step in plan.get("engage_warmup", []):
        if isinstance(step, dict):
            out.append(f"- **Step {step.get('step', '')}:** {step.get('instruction', '')}")
        else:
            out.append(f"- {step}")
    out.append("\n## Explicit Instruction")
    for step in plan.get("explicit_instruction", []):
        if isinstance(step, dict):
            out.append(f"- **Step {step.get('step', '')}:** {step.get('instruction', '')}")
        else:
            out.append(f"- {step}")
    out.append("\n## Guided Practice")
    for step in plan.get("guided_practice", []):
        if isinstance(step, dict):
            out.append(f"- **Step {step.get('step', '')}:** {step.get('instruction', '')}")
        else:
            out.append(f"- {step}")
    out.append("\n## Independent Practice")
    for task in plan.get("independent_practice", []):
        if isinstance(task, dict):
            out.append(f"- **Task:** {task.get('task', '')}")
            sc = task.get("success_criteria", [])
            if sc:
                out.append("  - **Success criteria:**")
                out.extend([f"    - {c}" for c in sc])
    out.append("\n## Differentiation")
    diff = plan.get("differentiation", {})
    out.append("### Support")
    out.append(bullets(diff.get("support", [])))
    out.append("### Challenge")
    out.append(bullets(diff.get("challenge", [])))
    out.append("## Assessment")
    assess = plan.get("assessment", {})
    out.append("### Formative Checks")
    out.append(bullets(assess.get("formative_checks", [])))
    out.append(f"### Exit Ticket\n{assess.get('exit_ticket', '')}\n")
    out.append("### Rubric Points")
    out.append(bullets(assess.get("rubric_points", [])))
    out.append("## Common Misconceptions & Fixes")
    out.append(bullets(plan.get("misconceptions_and_fixes", [])))
    out.append("## Blackboard Notes")
    out.append(bullets(plan.get("blackboard_notes", [])))
    out.append("## Home Connection")
    out.append(bullets(plan.get("home_connection", [])))
    out.append("## Teacher Tips")
    out.append(bullets(plan.get("teacher_tips", [])))
    return "\n".join(out)

def generate_teaching_plan(class_name: str, subject: str, chapter: str, topic_title: str, topic_text: str) -> Dict[str, Any]:
    user_prompt = USER_PROMPT_TEMPLATE.format(
        class_name=class_name,
        subject=subject,
        chapter=chapter,
        topic_title=topic_title,
        topic_text=topic_text[:12000]
    )
    raw = call_ollama_api(user_prompt)
    plan = safe_parse_json(raw)
    if not plan:
        retry_prompt = user_prompt + "\n\nIMPORTANT: Return ONLY valid JSON format, no explanations or markdown."
        raw = call_ollama_api(retry_prompt)
        plan = safe_parse_json(raw)
    if not plan:
        raise ValueError("Model did not return valid JSON after retry. Raw response: " + raw[:500])
    plan_md = plan_json_to_markdown(plan)
    return {"plan_json": plan, "plan_markdown": plan_md}

# ---------------- PDF PROCESSING ----------------
def split_pdf_by_topics(pdf_file):
    topics = []
    reader = PdfReader(pdf_file)
    with pdfplumber.open(pdf_file) as pdf:
        current_topic = None
        topic_writer = PdfWriter()
        topic_count = 0
        topic_text = []
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            match = TOPIC_REGEX.search(text)
            if match:
                header_text = match.group(0).strip()
                normalized = header_text.lower()
                if normalized in MERGE_WITH_PREVIOUS and current_topic is not None:
                    pass
                else:
                    if current_topic is not None and len(topic_writer.pages) > 0:
                        pdf_bytes = io.BytesIO()
                        topic_writer.write(pdf_bytes)
                        pdf_bytes.seek(0)
                        full_text = "\n".join(topic_text).strip()
                        topics.append((f"{topic_count:02d}_{current_topic}.pdf", pdf_bytes, full_text))
                        topic_writer = PdfWriter()
                        topic_text = []
                    current_topic = re.sub(r"\s+", "_", header_text)
                    topic_count += 1
            topic_writer.add_page(reader.pages[i])
            if text.strip():
                topic_text.append(text.strip())
        if current_topic is not None and len(topic_writer.pages) > 0:
            pdf_bytes = io.BytesIO()
            topic_writer.write(pdf_bytes)
            pdf_bytes.seek(0)
            full_text = "\n".join(topic_text).strip()
            topics.append((f"{topic_count:02d}_{current_topic}.pdf", pdf_bytes, full_text))
    return topics

def normalize_name(name: str) -> str:
    return re.sub(r'\s+', '_', name.strip())

def save_to_firebase(subject, chapter, topics):
    try:
        db = get_db_client()
        subject_ref = db.collection("subjects").document(normalize_name(subject))
        chapter_ref = subject_ref.collection("chapters").document(normalize_name(chapter))
        for i, (filename, _, content) in enumerate(topics, 1):
            chapter_ref.collection("topics").document(f"topic{i}").set({
                "title": filename.replace(".pdf", ""),
                "content": content
            })
    except Exception as e:
        st.error(f"Error saving to Firebase: {e}")
        st.error("Please check your Firebase connection and try again.")

# ---------------- FIREBASE QUERY FUNCTIONS ----------------
def get_subjects():
    try:
        db = get_db_client()
        subjects = db.collection("subjects").stream()
        subject_list = [subj.id for subj in subjects]
        st.write(f"Debug: Found {len(subject_list)} subjects: {subject_list}")
        return subject_list
    except Exception as e:
        st.error(f"Error fetching subjects: {e}")
        st.error("Please check your Firebase connection and try refreshing the page.")
        return []

def get_chapters(subject):
    if not subject:
        return []
    try:
        db = get_db_client()
        chapters = db.collection("subjects").document(normalize_name(subject)).collection("chapters").stream()
        chapter_list = [chap.id for chap in chapters]
        st.write(f"Debug: Found {len(chapter_list)} chapters for {subject}: {chapter_list}")
        return chapter_list
    except Exception as e:
        st.error(f"Error fetching chapters: {e}")
        st.error("Please check your Firebase connection and try refreshing the page.")
        return []

def get_topics(subject, chapter):
    if not subject or not chapter:
        return []
    try:
        db = get_db_client()
        topics_ref = (db.collection("subjects").document(normalize_name(subject))
                     .collection("chapters").document(normalize_name(chapter))
                     .collection("topics"))
        topics = topics_ref.stream()
        topic_list = [(topic.id, topic.to_dict()) for topic in topics]
        st.write(f"Debug: Found {len(topic_list)} topics for {subject}/{chapter}")
        return topic_list
    except Exception as e:
        st.error(f"Error fetching topics: {e}")
        st.error("Please check your Firebase connection and try refreshing the page.")
        return []

def save_teaching_plan(subject, chapter, topic_id, plan_data):
    try:
        db = get_db_client()
        topic_ref = (db.collection("subjects").document(normalize_name(subject))
                    .collection("chapters").document(normalize_name(chapter))
                    .collection("topics").document(topic_id))
        topic_ref.set({
            "ai_plan_json": plan_data["plan_json"],
            "ai_plan_markdown": plan_data["plan_markdown"],
            "ai_model": f"ollama:{OLLAMA_MODEL}",
            "ai_timestamp": firestore.SERVER_TIMESTAMP,
        }, merge=True)
        return True
    except Exception as e:
        st.error(f"Error saving plan: {e}")
        st.error("Please check your Firebase connection and try again.")
        return False

# ---------------- STREAMLIT UI ----------------
def main():
    st.title("📚 NCERT AI Teaching Assistant")
    st.markdown("Upload PDFs, extract topics, and generate AI-powered teaching plans!")

    st.sidebar.title("Navigation")
    mode = st.sidebar.radio("Choose Mode", ["📄 PDF Upload & Processing", "🤖 AI Teaching Plans", "📖 Browse Content"])

    if mode == "🤖 AI Teaching Plans":
        try:
            import requests
            response = requests.get(f"{OLLAMA_HOST}/api/version", timeout=5)
            if response.status_code != 200:
                st.warning("⚠️ Cannot connect to Ollama. Make sure Ollama is running on " + OLLAMA_HOST)
        except Exception:
            st.error("❌ Ollama server not accessible. Please start Ollama and ensure the model is available.")
            st.code(f"ollama serve  # Start Ollama server\nollama pull {OLLAMA_MODEL}  # Ensure model is available")

    if mode == "📄 PDF Upload & Processing":
        st.header("📄 PDF Upload & Topic Extraction")
        col1, col2 = st.columns(2)
        with col1:
            subject = st.text_input("Enter Subject (e.g., English)")
        with col2:
            chapter_name = st.text_input("Enter Chapter Name (e.g., U1 Chapter 1)")
            uploaded_file = st.file_uploader("Upload Chapter PDF", type=["pdf"])
        if uploaded_file and subject and chapter_name:
            st.subheader(f"📖 Processing {uploaded_file.name}")
            with st.spinner("Extracting topics from PDF..."):
                topics = split_pdf_by_topics(uploaded_file)
            st.success(f"✅ Extracted {len(topics)} topics")
            for i, (filename, _, content) in enumerate(topics, 1):
                with st.expander(f"Topic {i}: {filename}"):
                    st.text_area("Extracted Text", content, height=200, key=f"topic_{i}")
            if st.button("🚀 Save to Firebase", type="primary"):
                with st.spinner("Saving to Firebase..."):
                    save_to_firebase(subject, chapter_name, topics)
                st.success("✅ Topics saved to Firebase!")

    elif mode == "🤖 AI Teaching Plans":
        st.header("🤖 AI Teaching Plan Generator (Local Mistral)")
        try:
            import requests
            response = requests.get(f"{OLLAMA_HOST}/api/version", timeout=2)
            if response.status_code == 200:
                st.success(f"✅ Connected to Ollama at {OLLAMA_HOST}")
                models_response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
                if models_response.status_code == 200:
                    models = models_response.json().get("models", [])
                    model_names = [m["name"] for m in models]
                    if OLLAMA_MODEL in model_names or any(OLLAMA_MODEL in name for name in model_names):
                        st.success(f"✅ Model '{OLLAMA_MODEL}' is available")
                    else:
                        st.error(f"❌ Model '{OLLAMA_MODEL}' not found. Available models: {model_names}")
                        st.code(f"ollama pull {OLLAMA_MODEL}")
            else:
                st.error(f"❌ Ollama server responded with status {response.status_code}")
        except Exception as e:
            st.error(f"❌ Cannot connect to Ollama: {e}")
            st.info(f"Make sure Ollama is running: `ollama serve`")
            return
        st.subheader("🔍 Debug Information")
        if st.button("🔄 Refresh Data"):
            st.cache_resource.clear()
            st.success("Cache cleared! Data will be refreshed on next request.")
            st.rerun()
        with st.expander("Firebase Connection Details"):
            try:
                db = get_db_client()
                st.success("✅ Database connection established")
                st.write("Testing connection with fresh data...")
                collections = list(db.collections())
                st.write("Available root collections:")
                for collection in collections:
                    st.write(f"- {collection.id}")
                test_subjects = db.collection("subjects").limit(3).stream()
                subject_count = len(list(test_subjects))
                st.write(f"Sample data test: Found {subject_count} subjects in database")
                if subject_count > 0:
                    st.success("✅ Firebase data fetching is working properly")
                else:
                    st.warning("⚠️ No data found in subjects collection")
            except Exception as e:
                st.error(f"❌ Firebase connection error: {e}")
                st.error("Please check your Firebase credentials and internet connection.")
        col1, col2 = st.columns(2)
        with col1:
            subjects = get_subjects()
            selected_subject = st.selectbox("Select Subject", [""] + subjects)
        with col2:
            chapters = get_chapters(selected_subject) if selected_subject else []
            selected_chapter = st.selectbox("Select Chapter", [""] + chapters)
        if selected_subject and selected_chapter:
            topics = get_topics(selected_subject, selected_chapter)
            if topics:
                st.subheader(f"Topics in {selected_subject} > {selected_chapter}")
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"Found {len(topics)} topics")
                with col2:
                    if st.button("🚀 Generate All Plans", type="primary"):
                        generate_all_plans(selected_subject, selected_chapter, topics)
                for topic_id, topic_data in topics:
                    with st.expander(f"📝 {topic_data.get('title', topic_id)}"):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.text_area("Content", topic_data.get('content', ''), height=150, key=f"content_{topic_id}")
                        with col2:
                            has_plan = 'ai_plan_markdown' in topic_data
                            if has_plan:
                                st.success("✅ Plan exists")
                                if st.button("🔄 Regenerate", key=f"regen_{topic_id}"):
                                    generate_single_plan(selected_subject, selected_chapter, topic_id, topic_data)
                            else:
                                if st.button("🤖 Generate Plan", key=f"gen_{topic_id}"):
                                    generate_single_plan(selected_subject, selected_chapter, topic_id, topic_data)
                        if 'ai_plan_markdown' in topic_data:
                            st.markdown("### 📋 Teaching Plan")
                            st.markdown(topic_data['ai_plan_markdown'])
            else:
                st.info("No topics found. Upload a PDF first!")

    elif mode == "📖 Browse Content":
        st.header("📖 Browse Content")
        col1, col2 = st.columns(2)
        with col1:
            subjects = get_subjects()
            selected_subject = st.selectbox("Select Subject", [""] + subjects)
        with col2:
            chapters = get_chapters(selected_subject) if selected_subject else []
            selected_chapter = st.selectbox("Select Chapter", [""] + chapters)
        if selected_subject and selected_chapter:
            topics = get_topics(selected_subject, selected_chapter)
            if topics:
                for topic_id, topic_data in topics:
                    with st.expander(f"📖 {topic_data.get('title', topic_id)}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.subheader("📄 Content")
                            st.text_area("", topic_data.get('content', ''), height=300)
                        with col2:
                            if 'ai_plan_markdown' in topic_data:
                                st.subheader("🤖 AI Teaching Plan")
                                st.markdown(topic_data['ai_plan_markdown'])
                            else:
                                st.info("No teaching plan generated yet.")

def generate_single_plan(subject, chapter, topic_id, topic_data):
    with st.spinner(f"Generating teaching plan for {topic_data.get('title', topic_id)}..."):
        try:
            plan_data = generate_teaching_plan(
                "", subject, chapter,
                topic_data.get('title', ''),
                topic_data.get('content', '')
            )
            if save_teaching_plan(subject, chapter, topic_id, plan_data):
                st.success("✅ Teaching plan generated and saved!")
                st.rerun()
            else:
                st.error("❌ Failed to save teaching plan.")
        except Exception as e:
            st.error(f"❌ Error generating plan: {e}")

def generate_all_plans(subject, chapter, topics):
    progress_bar = st.progress(0)
    status_text = st.empty()
    success_count = 0
    total_topics = len(topics)
    for i, (topic_id, topic_data) in enumerate(topics):
        if 'ai_plan_markdown' in topic_data:
            status_text.text(f"Skipping {topic_data.get('title', topic_id)} (already exists)")
            success_count += 1
        else:
            status_text.text(f"Generating plan for {topic_data.get('title', topic_id)}...")
            try:
                plan_data = generate_teaching_plan(
                    "", subject, chapter,
                    topic_data.get('title', ''),
                    topic_data.get('content', '')
                )
                if save_teaching_plan(subject, chapter, topic_id, plan_data):
                    success_count += 1
                time.sleep(1)
            except Exception as e:
                st.error(f"Error generating plan for {topic_id}: {e}")
        progress_bar.progress((i + 1) / total_topics)
    status_text.text(f"Completed! Generated {success_count}/{total_topics} plans.")
    st.success(f"✅ Generated {success_count} teaching plans!")
    time.sleep(2)
    st.rerun()

if __name__ == "__main__":
    main()