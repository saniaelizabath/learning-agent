import os
import json
import time
import argparse
from typing import Dict, Any, Iterable, Optional

import firebase_admin
from firebase_admin import credentials, firestore

import requests  # for Ollama backend


# =============== CONFIG ===============
BACKEND = os.getenv("BACKEND", "mistral").lower()  # "mistral" or "ollama"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-large-latest")

# Ollama local settings (if using BACKEND=ollama)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")  # ensure `ollama pull mistral`

# Generation parameters (tweak as needed)
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2048"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))
TOP_P = float(os.getenv("TOP_P", "0.9"))

# Firestore collection names are fixed by your schema
ROOT_COLLECTION = "classes"

# =============== FIREBASE INIT ===============
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_config.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()


# =============== PROMPT TEMPLATES ===============
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
- If it’s picture talk/time, emphasize observation, questioning, and speaking.
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

# Optional: a Markdown pretty-printer for the JSON
def plan_json_to_markdown(plan: Dict[str, Any]) -> str:
    def bullets(items: Iterable[str]) -> str:
        return "".join(f"- {it}\n" for it in items) if items else "-\n"

    out = []
    out.append(f"# {plan.get('title','Teaching Plan')}")
    out.append(f"**Estimated Duration:** {plan.get('estimated_duration_min','-')} minutes\n")

    out.append("## Learning Objectives")
    out.append(bullets(plan.get("learning_objectives", [])))

    out.append("## Prerequisites")
    out.append(bullets(plan.get("prerequisites", [])))

    out.append("## Key Vocabulary")
    out.append(bullets(plan.get("key_vocabulary", [])))

    out.append("## Materials Needed")
    out.append(bullets(plan.get("materials_needed", [])))

    def steps(section_name):
        steps_list = plan.get(section_name, [])
        s = [f"### {section_name.replace('_',' ').title()}"]
        for step in steps_list:
            if isinstance(step, dict):
                s.append(f"- Step {step.get('step','')}: {step.get('instruction','')}")
            else:
                s.append(f"- {step}")
        return "\n".join(s)

    out.append(steps("engage_warmup"))
    out.append(steps("explicit_instruction"))
    out.append(steps("guided_practice"))

    out.append("## Independent Practice")
    for task in plan.get("independent_practice", []):
        if isinstance(task, dict):
            out.append(f"- **Task:** {task.get('task','')}")
            sc = task.get("success_criteria", [])
            if sc:
                out.append("  - Success criteria:")
                out.extend([f"    - {c}" for c in sc])
        else:
            out.append(f"- {task}")

    out.append("## Differentiation")
    diff = plan.get("differentiation", {})
    out.append("**Support**")
    out.append(bullets(diff.get("support", [])))
    out.append("**Challenge**")
    out.append(bullets(diff.get("challenge", [])))

    out.append("## Assessment")
    assess = plan.get("assessment", {})
    out.append("**Formative checks**")
    out.append(bullets(assess.get("formative_checks", [])))
    out.append(f"**Exit ticket:** {assess.get('exit_ticket','')}")
    out.append("**Rubric points**")
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


# =============== LLM CLIENTS ===============
def mistral_api_chat(system_prompt: str, user_prompt: str) -> str:
    """Call official Mistral API (chat-like)."""
    if not MISTRAL_API_KEY:
        raise RuntimeError("Set MISTRAL_API_KEY for BACKEND=mistral.")
    import httpx
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MISTRAL_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_tokens": MAX_TOKENS,
    }
    with httpx.Client(timeout=120) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]


def ollama_generate(prompt: str, model: str = OLLAMA_MODEL) -> str:
    """Call local Ollama generate endpoint."""
    url = f"{OLLAMA_HOST}/api/generate"
    payload = {
        "model": model,
        "prompt": f"{SYSTEM_PROMPT}\n\n{prompt}",
        "options": {
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
        }
    }
    r = requests.post(url, json=payload, timeout=600, stream=True)
    r.raise_for_status()
    # stream returns JSON lines with {"response": "...", "done": bool}
    full = []
    for line in r.iter_lines():
        if not line:
            continue
        chunk = json.loads(line.decode("utf-8"))
        if "response" in chunk:
            full.append(chunk["response"])
    return "".join(full)


def call_llm(system_prompt: str, user_prompt: str) -> str:
    if BACKEND == "mistral":
        return mistral_api_chat(system_prompt, user_prompt)
    elif BACKEND == "ollama":
        return ollama_generate(user_prompt)
    else:
        raise ValueError("BACKEND must be 'mistral' or 'ollama'.")


# =============== FIRESTORE HELPERS ===============
def iter_topics(
    class_name: Optional[str] = None,
    subject: Optional[str] = None,
    chapter: Optional[str] = None
):
    """
    Yields (class_doc_id, subject_doc_id, chapter_doc_id, topic_doc_ref, topic_doc_dict)
    according to the filters provided. If none provided, processes ALL.
    """
    classes_ref = db.collection(ROOT_COLLECTION)

    class_query = [classes_ref.document(class_name)] if class_name else classes_ref.stream()
    for cdoc in ( [classes_ref.document(class_name).get()] if class_name else class_query ):
        cdoc_obj = cdoc if class_name else cdoc
        if class_name:
            if not cdoc_obj.exists:
                continue
        class_id = cdoc.id if hasattr(cdoc, "id") else class_name

        subjects_ref = classes_ref.document(class_id).collection("subjects")
        subj_query = [subjects_ref.document(subject)] if subject else subjects_ref.stream()

        for sdoc in ( [subjects_ref.document(subject).get()] if subject else subj_query ):
            if subject and not sdoc.exists:
                continue
            subject_id = sdoc.id if hasattr(sdoc, "id") else subject

            chapters_ref = subjects_ref.document(subject_id).collection("chapters")
            chap_query = [chapters_ref.document(chapter)] if chapter else chapters_ref.stream()

            for chdoc in ( [chapters_ref.document(chapter).get()] if chapter else chap_query ):
                if chapter and not chdoc.exists:
                    continue
                chapter_id = chdoc.id if hasattr(chdoc, "id") else chapter

                topics_ref = chapters_ref.document(chapter_id).collection("topics")
                for tdoc in topics_ref.stream():
                    yield class_id, subject_id, chapter_id, tdoc.reference, tdoc.to_dict()


def safe_parse_json(s: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(s)
    except Exception:
        # try to trim common JSON noise (e.g., markdown fences)
        s2 = s.strip().strip("`").strip()
        try:
            return json.loads(s2)
        except Exception:
            return None


# =============== MAIN LOGIC ===============
def generate_plan_for_topic(
    class_name: str,
    subject: str,
    chapter: str,
    topic_title: str,
    topic_text: str
) -> Dict[str, Any]:
    user_prompt = USER_PROMPT_TEMPLATE.format(
        class_name=class_name,
        subject=subject,
        chapter=chapter,
        topic_title=topic_title,
        topic_text=topic_text[:12000]  # guardrail for very long texts
    )

    raw = call_llm(SYSTEM_PROMPT, user_prompt)
    plan = safe_parse_json(raw)

    if not plan:
        # Fallback: ask for JSON again succinctly
        retry_prompt = (
            user_prompt +
            "\n\nYour previous output was not valid JSON. "
            "Return ONLY valid JSON now, no explanations."
        )
        raw = call_llm(SYSTEM_PROMPT, retry_prompt)
        plan = safe_parse_json(raw)

    if not plan:
        raise ValueError("Model did not return valid JSON after retry.")

    # also create a markdown version for teacher readability
    plan_md = plan_json_to_markdown(plan)
    return {"plan_json": plan, "plan_markdown": plan_md}


def save_plan_to_topic(topic_ref, plan_bundle: Dict[str, Any]):
    topic_ref.set(
        {
            "ai_plan_json": plan_bundle["plan_json"],
            "ai_plan_markdown": plan_bundle["plan_markdown"],
            "ai_model": f"{BACKEND}:{MISTRAL_MODEL if BACKEND=='mistral' else OLLAMA_MODEL}",
            "ai_timestamp": firestore.SERVER_TIMESTAMP,
        },
        merge=True
    )


def main():
    parser = argparse.ArgumentParser(description="Generate teaching plans from Firestore topics via Mistral.")
    parser.add_argument("--class", dest="class_name", help="Class doc id (e.g., Class1)")
    parser.add_argument("--subject", dest="subject", help="Subject doc id (e.g., English)")
    parser.add_argument("--chapter", dest="chapter", help="Chapter doc id (e.g., Chapter1)")
    parser.add_argument("--sleep", type=float, default=0.8, help="Sleep seconds between requests to be polite")
    args = parser.parse_args()

    count = 0
    for class_id, subject_id, chapter_id, topic_ref, topic_doc in iter_topics(
        class_name=args.class_name, subject=args.subject, chapter=args.chapter
    ):
        title = str(topic_doc.get("title", topic_ref.id))
        content = str(topic_doc.get("content", "")).strip()

        if not content:
            print(f"Skip (no content): {class_id}/{subject_id}/{chapter_id}/{topic_ref.id}")
            continue

        # Skip if already generated (optional)
        if topic_doc.get("ai_plan_json"):
            print(f"Already has ai_plan_json: {class_id}/{subject_id}/{chapter_id}/{topic_ref.id}")
            continue

        print(f"Generating: {class_id}/{subject_id}/{chapter_id}/{title}")
        try:
            plan_bundle = generate_plan_for_topic(class_id, subject_id, chapter_id, title, content)
            save_plan_to_topic(topic_ref, plan_bundle)
            count += 1
        except Exception as e:
            print(f"Failed for {topic_ref.path}: {e}")

        time.sleep(args.sleep)

    print(f"Done. Generated plans for {count} topic(s).")


if __name__ == "__main__":
    main()
