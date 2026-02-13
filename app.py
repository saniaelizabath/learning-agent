import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import re
import io
import json
import time
from typing import Dict, Any, Optional, List
import os
import requests
from dataclasses import dataclass
from enum import Enum
import base64
from datetime import datetime, timedelta
import uuid

import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip

# ---------------- PAGE CONFIG (must be first Streamlit call) ----------------
st.set_page_config(page_title="Multigrade AI Teaching Assistant", layout="wide", page_icon="🎓")

# ---------------- CONFIGURATION ----------------
GEMINI_API_KEY = "AIzaSyA-qKWQmW0Boiwz8HG8P32lYN0KDtu4ISc"
GEMINI_MODEL = "gemini-2.5-pro"
MAX_TOKENS = 2048
TEMPERATURE = 0.7

# Grade configurations
GRADES = ["Grade 1", "Grade 2", "Grade 3", "Grade 4"]
SUBJECTS = ["English", "Mathematics", "Science", "Social Studies", "Hindi", "Art & Craft"]

# AI Agent Types
class AgentType(Enum):
    COURSE_PLANNER = "course_planner"
    ACTIVITY_GENERATOR = "activity_generator"
    WORKSHEET_GENERATOR = "worksheet_generator"
    ASSESSMENT_GENERATOR = "assessment_generator"
    VISUAL_AIDS_GENERATOR = "visual_aids_generator"
    PEER_ACTIVITY_GENERATOR = "peer_activity_generator"

@dataclass
class TeachingContext:
    grades: List[str]
    subjects: List[str]
    topic: str
    duration_minutes: int
    class_size: int
    learning_objectives: List[str]

# ---------------- GEMINI API SETUP ----------------
@st.cache_resource
def init_gemini():
    if not GEMINI_API_KEY:
        st.error("❌ GEMINI_API_KEY environment variable not set.")
        st.info("Please set your Gemini API key using one of these methods:")
        st.code("""
# Option 1: Environment variable (recommended)
export GEMINI_API_KEY="your_api_key_here"

# Option 2: Windows Command Prompt
set GEMINI_API_KEY=your_api_key_here

# Option 3: Add to .env file
GEMINI_API_KEY=your_api_key_here
        """)
        st.info("💡 Get your API key from: https://makersuite.google.com/app/apikey")
        return False
    
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        # Test the connection with a simple prompt
        test_response = model.generate_content("Say 'API connection successful'")
        st.success("✅ Successfully connected to Gemini API!")
        return True
    except Exception as e:
        error_msg = str(e)
        if "API_KEY_INVALID" in error_msg or "expired" in error_msg.lower():
            st.error("❌ Invalid or expired Gemini API key.")
            st.info("Please check your API key and generate a new one if needed:")
            st.info("🔗 https://makersuite.google.com/app/apikey")
        elif "quota" in error_msg.lower():
            st.error("✅ Ready to generate")
        else:
            st.error(f"❌ Gemini API initialization failed: {e}")
        return False

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
            test_collection = db.collection("multigrade_content").limit(1).get()
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

# ---------------- MULTIAGENT AI SYSTEM ----------------
class MultigradeAIAgent:
    def __init__(self, agent_type: AgentType):
        self.agent_type = agent_type
        self.model = genai.GenerativeModel(GEMINI_MODEL)
        
    def generate_content(self, prompt: str, context: TeachingContext) -> Dict[str, Any]:
        try:
            response = self.model.generate_content(prompt)
            return {"success": True, "content": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

# ---------------- AI AGENT PROMPTS ----------------
AGENT_PROMPTS = {
    AgentType.COURSE_PLANNER: {
        "system": """You are a multigrade classroom course planning specialist. You create comprehensive daily lesson plans 
        that accommodate multiple grade levels (1-4) simultaneously, ensuring differentiated instruction and smooth transitions 
        between activities for different grade groups.""",
        "template": """Create a detailed daily course plan for a multigrade classroom.
        
        CONTEXT:
        - Grades: {grades}
        - Subject(s): {subjects}
        - Topic: {topic}
        - Duration: {duration_minutes} minutes
        - Class Size: {class_size} students
        - Learning Objectives: {learning_objectives}
        
        Return a JSON structure with:
        {{
            "lesson_title": "string",
            "total_duration": "integer (minutes)",
            "grade_groupings": [
                {{
                    "grade": "string",
                    "group_size": "integer",
                    "specific_objectives": ["string"],
                    "materials": ["string"]
                }}
            ],
            "timeline": [
                {{
                    "time_slot": "string (e.g., 0-10 min)",
                    "activity": "string",
                    "grade_1_task": "string",
                    "grade_2_task": "string", 
                    "grade_3_task": "string",
                    "grade_4_task": "string",
                    "teacher_role": "string",
                    "transitions": "string"
                }}
            ],
            "assessment_checkpoints": [
                {{
                    "time": "string",
                    "grade": "string",
                    "assessment_type": "string",
                    "success_criteria": "string"
                }}
            ],
            "classroom_management": {{
                "setup": "string",
                "behavior_strategies": ["string"],
                "attention_signals": ["string"]
            }},
            "differentiation_strategies": {{
                "support_students": ["string"],
                "advanced_students": ["string"],
                "english_learners": ["string"]
            }},
            "homework_assignments": [
                {{
                    "grade": "string",
                    "task": "string",
                    "estimated_time": "integer (minutes)"
                }}
            ]
        }}"""
    },
    
    AgentType.ACTIVITY_GENERATOR: {
        "system": """You are a creative educational activity designer specializing in multigrade classrooms. 
        You create engaging, hands-on activities that can be adapted for different grade levels while maintaining 
        the core learning objectives.""",
        "template": """Generate creative learning activities for a multigrade classroom.
        
        CONTEXT:
        - Grades: {grades}
        - Subject(s): {subjects}
        - Topic: {topic}
        - Duration: {duration_minutes} minutes
        - Class Size: {class_size} students
        
        Return a JSON structure with:
        {{
            "activity_title": "string",
            "activity_type": "string (individual/group/whole-class/stations)",
            "estimated_duration": "integer (minutes)",
            "materials_needed": ["string"],
            "setup_instructions": "string",
            "grade_adaptations": [
                {{
                    "grade": "string",
                    "instructions": "string",
                    "examples": ["string"],
                    "success_criteria": ["string"],
                    "extension_activities": ["string"]
                }}
            ],
            "step_by_step_process": [
                {{
                    "step": "integer",
                    "instruction": "string",
                    "time_estimate": "integer (minutes)",
                    "teacher_notes": "string"
                }}
            ],
            "assessment_rubric": [
                {{
                    "criteria": "string",
                    "beginner": "string",
                    "developing": "string", 
                    "proficient": "string",
                    "advanced": "string"
                }}
            ],
            "variations": [
                {{
                    "variation_name": "string",
                    "description": "string",
                    "suitable_for": ["string"]
                }}
            ]
        }}"""
    },
    
    AgentType.WORKSHEET_GENERATOR: {
        "system": """You are a worksheet creation specialist for multigrade classrooms. You design printable worksheets 
        that provide differentiated practice opportunities for students in grades 1-4.""",
        "template": """Create a comprehensive worksheet set for multigrade classroom practice.
        
        CONTEXT:
        - Grades: {grades}
        - Subject(s): {subjects}
        - Topic: {topic}
        - Skill Level Range: Beginning to Advanced
        
        Return a JSON structure with:
        {{
            "worksheet_title": "string",
            "subject": "string",
            "topic": "string",
            "grade_levels": ["string"],
            "instructions": {{
                "teacher_notes": "string",
                "student_instructions": "string",
                "time_estimate": "integer (minutes)"
            }},
            "sections": [
                {{
                    "section_title": "string",
                    "difficulty_level": "string (beginner/intermediate/advanced)",
                    "grade_target": "string",
                    "questions": [
                        {{
                            "question_number": "integer",
                            "question_text": "string",
                            "question_type": "string (multiple_choice/fill_blank/short_answer/drawing/matching)",
                            "options": ["string"] or null,
                            "correct_answer": "string",
                            "explanation": "string",
                            "points": "integer"
                        }}
                    ]
                }}
            ],
            "answer_key": {{
                "section_answers": [
                    {{
                        "section": "string",
                        "answers": ["string"],
                        "explanations": ["string"]
                    }}
                ]
            }},
            "extension_activities": [
                {{
                    "activity": "string",
                    "suitable_for": "string (grade level)",
                    "materials_needed": ["string"]
                }}
            ]
        }}"""
    },
    
    AgentType.ASSESSMENT_GENERATOR: {
        "system": """You are an assessment design expert for multigrade classrooms. You create fair, comprehensive 
        assessments that evaluate student understanding across different grade levels and learning styles.""",
        "template": """Design a comprehensive assessment strategy for multigrade classroom evaluation.
        
        CONTEXT:
        - Grades: {grades}
        - Subject(s): {subjects}
        - Topic: {topic}
        - Assessment Type: Formative and Summative
        
        Return a JSON structure with:
        {{
            "assessment_title": "string",
            "assessment_type": "string (formative/summative/diagnostic)",
            "duration": "integer (minutes)",
            "grade_adaptations": [
                {{
                    "grade": "string",
                    "assessment_method": "string",
                    "success_criteria": ["string"],
                    "accommodations": ["string"]
                }}
            ],
            "assessment_components": [
                {{
                    "component_name": "string",
                    "weight_percentage": "integer",
                    "description": "string",
                    "grade_specific_tasks": [
                        {{
                            "grade": "string",
                            "task": "string",
                            "scoring_rubric": {{
                                "excellent": "string",
                                "good": "string",
                                "satisfactory": "string",
                                "needs_improvement": "string"
                            }}
                        }}
                    ]
                }}
            ],
            "formative_checks": [
                {{
                    "checkpoint": "string",
                    "method": "string",
                    "frequency": "string",
                    "feedback_strategy": "string"
                }}
            ],
            "data_collection": {{
                "observation_checklist": ["string"],
                "portfolio_items": ["string"],
                "self_assessment_tools": ["string"]
            }}
        }}"""
    },
    
    AgentType.VISUAL_AIDS_GENERATOR: {
        "system": """You are a visual learning specialist who creates descriptions for educational visual aids, 
        charts, diagrams, and interactive displays suitable for multigrade classrooms.""",
        "template": """Design visual aids and learning materials for multigrade classroom instruction.
        
        CONTEXT:
        - Grades: {grades}
        - Subject(s): {subjects}
        - Topic: {topic}
        - Visual Learning Objectives: Support comprehension and engagement
        
        Return a JSON structure with:
        {{
            "visual_aid_title": "string",
            "aid_type": "string (poster/chart/diagram/interactive_board/manipulatives)",
            "materials_needed": ["string"],
            "size_specifications": "string",
            "content_description": {{
                "main_visual": "string (detailed description)",
                "text_elements": ["string"],
                "color_scheme": "string",
                "layout_description": "string"
            }},
            "grade_specific_elements": [
                {{
                    "grade": "string",
                    "visual_focus": "string",
                    "interaction_method": "string",
                    "learning_support": "string"
                }}
            ],
            "usage_instructions": {{
                "setup": "string",
                "introduction_script": "string",
                "interaction_activities": ["string"],
                "maintenance_tips": ["string"]
            }},
            "digital_alternatives": [
                {{
                    "platform": "string",
                    "description": "string",
                    "accessibility_features": ["string"]
                }}
            ]
        }}"""
    },
    
    AgentType.PEER_ACTIVITY_GENERATOR: {
        "system": """You are a collaborative learning specialist who designs peer-to-peer activities that promote 
        cross-grade interaction, mentoring, and cooperative learning in multigrade settings.""",
        "template": """Create peer-to-peer learning activities for multigrade classroom collaboration.
        
        CONTEXT:
        - Grades: {grades}
        - Subject(s): {subjects}
        - Topic: {topic}
        - Class Size: {class_size} students
        - Collaboration Goal: Cross-grade learning and mentoring
        
        Return a JSON structure with:
        {{
            "activity_title": "string",
            "collaboration_type": "string (buddy_system/mixed_groups/mentoring/stations)",
            "duration": "integer (minutes)",
            "grouping_strategy": {{
                "group_size": "integer",
                "grade_mixing": "string",
                "pairing_criteria": ["string"],
                "rotation_schedule": "string"
            }},
            "role_definitions": [
                {{
                    "role_name": "string",
                    "suitable_grades": ["string"],
                    "responsibilities": ["string"],
                    "skills_developed": ["string"]
                }}
            ],
            "activity_stations": [
                {{
                    "station_name": "string",
                    "learning_objective": "string",
                    "materials": ["string"],
                    "instructions": {{
                        "mentor_guide": "string",
                        "learner_tasks": "string",
                        "collaboration_prompts": ["string"]
                    }},
                    "time_allocation": "integer (minutes)"
                }}
            ],
            "assessment_strategies": {{
                "peer_feedback_forms": ["string"],
                "self_reflection_prompts": ["string"],
                "teacher_observation_points": ["string"]
            }},
            "differentiation": {{
                "support_strategies": ["string"],
                "challenge_extensions": ["string"],
                "inclusion_accommodations": ["string"]
            }}
        }}"""
    }
}

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

# ---------------- AI AGENT FUNCTIONS ----------------
def create_agent(agent_type: AgentType) -> MultigradeAIAgent:
    """Factory function to create AI agents"""
    return MultigradeAIAgent(agent_type)

def generate_with_agent(agent_type: AgentType, context: TeachingContext, additional_params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate content using specified AI agent"""
    try:
        agent = create_agent(agent_type)
        prompt_data = AGENT_PROMPTS[agent_type]
        
        # Format the prompt with context
        formatted_prompt = f"{prompt_data['system']}\n\n{prompt_data['template'].format(
            grades=', '.join(context.grades),
            subjects=', '.join(context.subjects),
            topic=context.topic,
            duration_minutes=context.duration_minutes,
            class_size=context.class_size,
            learning_objectives=', '.join(context.learning_objectives)
        )}"
        
        if additional_params:
            formatted_prompt += f"\n\nAdditional Parameters: {json.dumps(additional_params)}"
        
        result = agent.generate_content(formatted_prompt, context)
        
        if result["success"]:
            # Try to parse JSON response
            try:
                parsed_content = json.loads(result["content"])
                return {
                    "success": True,
                    "content": parsed_content,
                    "raw_content": result["content"],
                    "agent_type": agent_type.value
                }
            except json.JSONDecodeError:
                # If JSON parsing fails, return raw content
                return {
                    "success": True,
                    "content": result["content"],
                    "raw_content": result["content"],
                    "agent_type": agent_type.value,
                    "note": "Content returned as raw text (not JSON)"
                }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Agent generation failed: {str(e)}",
            "agent_type": agent_type.value
        }

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

def save_to_firebase(subject, chapter, topics, grades=None):
    """Save content to Firebase with multigrade structure"""
    try:
        db = get_db_client()
        if grades is None:
            grades = GRADES
            
        # Create a multigrade content structure
        content_ref = db.collection("multigrade_content").document(f"{normalize_name(subject)}_{normalize_name(chapter)}")
        
        content_data = {
            "subject": subject,
            "chapter": chapter,
            "applicable_grades": grades,
            "created_at": firestore.SERVER_TIMESTAMP,
            "topics": {}
        }
        
        for i, (filename, _, content) in enumerate(topics, 1):
            topic_id = f"topic_{i}"
            content_data["topics"][topic_id] = {
                "title": filename.replace(".pdf", ""),
                "content": content,
                "ai_generated_content": {}
            }
        
        content_ref.set(content_data)
        st.success(f"✅ Saved {len(topics)} topics for grades {', '.join(grades)}")
        
    except Exception as e:
        st.error(f"Error saving to Firebase: {e}")
        st.error("Please check your Firebase connection and try again.")

def save_ai_content(subject, chapter, topic_id, agent_type: AgentType, content_data):
    """Save AI-generated content to Firebase"""
    try:
        db = get_db_client()
        content_ref = db.collection("multigrade_content").document(f"{normalize_name(subject)}_{normalize_name(chapter)}")
        
        # Update the specific topic with AI content
        update_path = f"topics.{topic_id}.ai_generated_content.{agent_type.value}"
        content_ref.update({
            update_path: {
                "content": content_data,
                "generated_at": firestore.SERVER_TIMESTAMP,
                "model": GEMINI_MODEL
            }
        })
        return True
        
    except Exception as e:
        st.error(f"Error saving AI content: {e}")
        return False

# ---------------- FIREBASE QUERY FUNCTIONS ----------------
def get_multigrade_content():
    """Get all multigrade content from Firebase"""
    try:
        db = get_db_client()
        content_docs = db.collection("multigrade_content").stream()
        content_list = []
        
        for doc in content_docs:
            data = doc.to_dict()
            content_list.append({
                "id": doc.id,
                "subject": data.get("subject", ""),
                "chapter": data.get("chapter", ""),
                "applicable_grades": data.get("applicable_grades", []),
                "topics": data.get("topics", {}),
                "created_at": data.get("created_at")
            })
        
        return content_list
    except Exception as e:
        st.error(f"Error fetching multigrade content: {e}")
        return []

def get_subjects_and_chapters():
    """Get unique subjects and chapters from multigrade content"""
    try:
        content_list = get_multigrade_content()
        subjects = list(set([item["subject"] for item in content_list if item["subject"]]))
        
        subject_chapters = {}
        for item in content_list:
            subject = item["subject"]
            chapter = item["chapter"]
            if subject not in subject_chapters:
                subject_chapters[subject] = []
            if chapter not in subject_chapters[subject]:
                subject_chapters[subject].append(chapter)
        
        return subjects, subject_chapters
    except Exception as e:
        st.error(f"Error organizing subjects and chapters: {e}")
        return [], {}

def get_content_by_subject_chapter(subject, chapter):
    """Get specific content by subject and chapter"""
    try:
        db = get_db_client()
        doc_id = f"{normalize_name(subject)}_{normalize_name(chapter)}"
        doc = db.collection("multigrade_content").document(doc_id).get()
        
        if doc.exists:
            return doc.to_dict()
        else:
            return None
    except Exception as e:
        st.error(f"Error fetching content: {e}")
        return None

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
    st.title("🎓 Multigrade AI Teaching Assistant")
    st.markdown("**Comprehensive AI-powered teaching tools for grades 1-4 multigrade classrooms**")
    
    # Initialize APIs
    firebase_status = init_firebase()
    
    # Handle Gemini API setup with fallback option
    gemini_status = init_gemini()
    
    if not gemini_status and not GEMINI_API_KEY:
        st.warning("⚠️ Gemini API not configured via environment variable.")
        
        with st.expander("🔧 Quick Setup - Enter API Key"):
            st.markdown("**Temporary API Key Input** (for this session only)")
            api_key_input = st.text_input(
                "Enter your Gemini API Key:", 
                type="password",
                help="Get your API key from https://makersuite.google.com/app/apikey"
            )
            
            if api_key_input:
                try:
                    import os
                    os.environ["GEMINI_API_KEY"] = api_key_input
                    # Clear cache and retry
                    st.cache_resource.clear()
                    genai.configure(api_key=api_key_input)
                    model = genai.GenerativeModel(GEMINI_MODEL)
                    test_response = model.generate_content("Say 'API connection successful'")
                    st.success("✅ API key validated! You can now use all AI agents.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Invalid API key: {e}")
        
        st.info("💡 **For permanent setup**, set the environment variable before running the app:")
        st.code("export GEMINI_API_KEY='your_api_key_here'")
        
    if not gemini_status and not GEMINI_API_KEY:
        st.stop()
    
    st.sidebar.title("🎯 AI Teaching Agents")
    
    # Agent selection
    selected_agent = st.sidebar.selectbox(
        "Choose AI Agent",
        [
            "📅 Course Planner",
            "🎯 Activity Generator", 
            "📝 Worksheet Generator",
            "📊 Assessment Generator",
            "🎨 Visual Aids Generator",
            "🤝 Peer Activity Generator",
            "📄 Content Management",
            "📖 Browse & Review"
        ]
    )
    
    # Common context sidebar
    st.sidebar.subheader("🏫 Classroom Context")
    selected_grades = st.sidebar.multiselect("Select Grades", GRADES, default=["Grade 1", "Grade 2"])
    selected_subjects = st.sidebar.multiselect("Select Subjects", SUBJECTS, default=["English"])
    class_size = st.sidebar.slider("Class Size", 5, 50, 20)
    lesson_duration = st.sidebar.slider("Lesson Duration (minutes)", 15, 120, 45)

    # Main content area based on selected agent
    if selected_agent == "📅 Course Planner":
        handle_course_planner(selected_grades, selected_subjects, class_size, lesson_duration)
    elif selected_agent == "🎯 Activity Generator":
        handle_activity_generator(selected_grades, selected_subjects, class_size, lesson_duration)
    elif selected_agent == "📝 Worksheet Generator":
        handle_worksheet_generator(selected_grades, selected_subjects, class_size, lesson_duration)
    elif selected_agent == "📊 Assessment Generator":
        handle_assessment_generator(selected_grades, selected_subjects, class_size, lesson_duration)
    elif selected_agent == "🎨 Visual Aids Generator":
        handle_visual_aids_generator(selected_grades, selected_subjects, class_size, lesson_duration)
    elif selected_agent == "🤝 Peer Activity Generator":
        handle_peer_activity_generator(selected_grades, selected_subjects, class_size, lesson_duration)
    elif selected_agent == "📄 Content Management":
        handle_content_management(selected_grades)
    elif selected_agent == "📖 Browse & Review":
        handle_browse_review()

# ---------------- AGENT HANDLERS ----------------
def handle_course_planner(grades, subjects, class_size, duration):
    st.header("📅 Daily Course Planner for Multigrade Classes")
    st.markdown("Generate comprehensive daily lesson plans that accommodate multiple grade levels simultaneously.")
    
    col1, col2 = st.columns(2)
    with col1:
        topic = st.text_input("Lesson Topic", placeholder="e.g., Addition and Subtraction")
        learning_objectives = st.text_area(
            "Learning Objectives (one per line)", 
            placeholder="Grade 1: Count and add objects up to 10\nGrade 2: Add two-digit numbers\nGrade 3: Solve word problems with addition"
        )
    with col2:
        subjects_str = ', '.join(subjects) if subjects else "Not selected"
        grades_str = ', '.join(grades) if grades else "Not selected"
        st.info(f"**Selected Grades:** {grades_str}\n\n**Subjects:** {subjects_str}\n\n**Class Size:** {class_size}\n\n**Duration:** {duration} min")
    
    if st.button("🚀 Generate Course Plan", type="primary"):
        if not topic or not learning_objectives or not grades or not subjects:
            st.error("Please fill in all required fields and select grades/subjects.")
            return
            
        objectives_list = [obj.strip() for obj in learning_objectives.split('\n') if obj.strip()]
        
        context = TeachingContext(
            grades=grades,
            subjects=subjects,
            topic=topic,
            duration_minutes=duration,
            class_size=class_size,
            learning_objectives=objectives_list
        )
        
        with st.spinner("Generating comprehensive course plan..."):
            result = generate_with_agent(AgentType.COURSE_PLANNER, context)
            
        if result["success"]:
            st.success("✅ Course plan generated successfully!")
            
            if isinstance(result["content"], dict):
                display_course_plan(result["content"])
                
                # Save option
                if st.button("💾 Save to Firebase"):
                    if subjects and topic:
                        success = save_ai_content(subjects[0], topic, "course_plan", AgentType.COURSE_PLANNER, result["content"])
                        if success:
                            st.success("✅ Course plan saved!")
            else:
                st.markdown("### Generated Course Plan")
                st.markdown(result["content"])
        else:
            st.error(f"❌ Error generating course plan: {result.get('error', 'Unknown error')}")

def handle_activity_generator(grades, subjects, class_size, duration):
    st.header("🎯 Learning Activity Generator")
    st.markdown("Create engaging, hands-on activities adapted for different grade levels.")
    
    col1, col2 = st.columns(2)
    with col1:
        topic = st.text_input("Activity Topic", placeholder="e.g., Plant Life Cycle")
        activity_type = st.selectbox("Activity Type", ["Individual Work", "Group Activity", "Whole Class", "Learning Stations"])
    with col2:
        st.info(f"**Grades:** {', '.join(grades) if grades else 'Not selected'}\n\n**Subjects:** {', '.join(subjects) if subjects else 'Not selected'}")
    
    if st.button("🎯 Generate Activity", type="primary"):
        if not topic or not grades or not subjects:
            st.error("Please fill in topic and select grades/subjects.")
            return
            
        context = TeachingContext(
            grades=grades,
            subjects=subjects,
            topic=topic,
            duration_minutes=duration,
            class_size=class_size,
            learning_objectives=[f"Engage {grade} students in {topic}" for grade in grades]
        )
        
        with st.spinner("Creating engaging activity..."):
            result = generate_with_agent(AgentType.ACTIVITY_GENERATOR, context, {"activity_type": activity_type})
            
        if result["success"]:
            st.success("✅ Activity generated successfully!")
            if isinstance(result["content"], dict):
                display_activity(result["content"])
            else:
                st.markdown(result["content"])
        else:
            st.error(f"❌ Error: {result.get('error', 'Unknown error')}")

def handle_content_management(grades):
    st.header("📄 Content Management")
    st.markdown("Upload PDFs and manage multigrade content.")
    
    col1, col2 = st.columns(2)
    with col1:
        subject = st.selectbox("Subject", SUBJECTS)
        chapter_name = st.text_input("Chapter Name", placeholder="e.g., Chapter 1: Introduction")
    with col2:
        selected_grades_for_content = st.multiselect("Applicable Grades", GRADES, default=grades)
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
                save_to_firebase(subject, chapter_name, topics, selected_grades_for_content)
            st.success("✅ Topics saved to Firebase!")

def handle_worksheet_generator(grades, subjects, class_size, duration):
    st.header("📝 Worksheet Generator")
    st.markdown("Create differentiated worksheets for multiple grade levels.")
    
    col1, col2 = st.columns(2)
    with col1:
        topic = st.text_input("Worksheet Topic", placeholder="e.g., Fractions Practice")
        difficulty_level = st.selectbox("Difficulty Range", ["Beginner to Intermediate", "Intermediate to Advanced", "Mixed Levels"])
    with col2:
        st.info(f"**Grades:** {', '.join(grades) if grades else 'Not selected'}\n\n**Subjects:** {', '.join(subjects) if subjects else 'Not selected'}")
    
    if st.button("📝 Generate Worksheet", type="primary"):
        if not topic or not grades or not subjects:
            st.error("Please fill in topic and select grades/subjects.")
            return
            
        context = TeachingContext(
            grades=grades, subjects=subjects, topic=topic,
            duration_minutes=duration, class_size=class_size,
            learning_objectives=[f"Practice {topic} skills for {grade}" for grade in grades]
        )
        
        with st.spinner("Creating differentiated worksheet..."):
            result = generate_with_agent(AgentType.WORKSHEET_GENERATOR, context, {"difficulty_level": difficulty_level})
            
        if result["success"]:
            st.success("✅ Worksheet generated successfully!")
            if isinstance(result["content"], dict):
                display_worksheet(result["content"])
            else:
                st.markdown(result["content"])
        else:
            st.error(f"❌ Error: {result.get('error', 'Unknown error')}")

def handle_assessment_generator(grades, subjects, class_size, duration):
    st.header("📊 Assessment Generator")
    st.markdown("Design comprehensive assessments for multigrade evaluation.")
    
    col1, col2 = st.columns(2)
    with col1:
        topic = st.text_input("Assessment Topic", placeholder="e.g., Reading Comprehension")
        assessment_type = st.selectbox("Assessment Type", ["Formative", "Summative", "Diagnostic", "Mixed"])
    with col2:
        st.info(f"**Grades:** {', '.join(grades) if grades else 'Not selected'}\n\n**Subjects:** {', '.join(subjects) if subjects else 'Not selected'}")
    
    if st.button("📊 Generate Assessment", type="primary"):
        if not topic or not grades or not subjects:
            st.error("Please fill in topic and select grades/subjects.")
            return
            
        context = TeachingContext(
            grades=grades, subjects=subjects, topic=topic,
            duration_minutes=duration, class_size=class_size,
            learning_objectives=[f"Assess {topic} understanding for {grade}" for grade in grades]
        )
        
        with st.spinner("Creating comprehensive assessment..."):
            result = generate_with_agent(AgentType.ASSESSMENT_GENERATOR, context, {"assessment_type": assessment_type})
            
        if result["success"]:
            st.success("✅ Assessment generated successfully!")
            if isinstance(result["content"], dict):
                display_assessment(result["content"])
            else:
                st.markdown(result["content"])
        else:
            st.error(f"❌ Error: {result.get('error', 'Unknown error')}")

def handle_visual_aids_generator(grades, subjects, class_size, duration):
    st.header("🎨 Visual Aids Generator")
    st.markdown("Create descriptions for visual learning materials and displays.")
    
    col1, col2 = st.columns(2)
    with col1:
        topic = st.text_input("Visual Aid Topic", placeholder="e.g., Solar System")
        aid_type = st.selectbox("Aid Type", ["Poster", "Chart", "Diagram", "Interactive Board", "Manipulatives"])
    with col2:
        st.info(f"**Grades:** {', '.join(grades) if grades else 'Not selected'}\n\n**Subjects:** {', '.join(subjects) if subjects else 'Not selected'}")
    
    if st.button("🎨 Generate Visual Aid", type="primary"):
        if not topic or not grades or not subjects:
            st.error("Please fill in topic and select grades/subjects.")
            return
            
        context = TeachingContext(
            grades=grades, subjects=subjects, topic=topic,
            duration_minutes=duration, class_size=class_size,
            learning_objectives=[f"Support visual learning of {topic} for {grade}" for grade in grades]
        )
        
        with st.spinner("Creating visual aid description..."):
            result = generate_with_agent(AgentType.VISUAL_AIDS_GENERATOR, context, {"aid_type": aid_type})
            
        if result["success"]:
            st.success("✅ Visual aid design generated successfully!")
            if isinstance(result["content"], dict):
                display_visual_aid(result["content"])
            else:
                st.markdown(result["content"])
        else:
            st.error(f"❌ Error: {result.get('error', 'Unknown error')}")

def handle_peer_activity_generator(grades, subjects, class_size, duration):
    st.header("🤝 Peer-to-Peer Activity Generator")
    st.markdown("Design collaborative activities that promote cross-grade learning and mentoring.")
    
    col1, col2 = st.columns(2)
    with col1:
        topic = st.text_input("Collaboration Topic", placeholder="e.g., Story Writing Together")
        collaboration_type = st.selectbox("Collaboration Type", ["Buddy System", "Mixed Groups", "Mentoring", "Learning Stations"])
    with col2:
        st.info(f"**Grades:** {', '.join(grades) if grades else 'Not selected'}\n\n**Class Size:** {class_size}")
    
    if st.button("🤝 Generate Peer Activity", type="primary"):
        if not topic or not grades or not subjects:
            st.error("Please fill in topic and select grades/subjects.")
            return
            
        context = TeachingContext(
            grades=grades, subjects=subjects, topic=topic,
            duration_minutes=duration, class_size=class_size,
            learning_objectives=[f"Foster peer learning in {topic} across grades" for grade in grades]
        )
        
        with st.spinner("Creating peer collaboration activity..."):
            result = generate_with_agent(AgentType.PEER_ACTIVITY_GENERATOR, context, {"collaboration_type": collaboration_type})
            
        if result["success"]:
            st.success("✅ Peer activity generated successfully!")
            if isinstance(result["content"], dict):
                display_peer_activity(result["content"])
            else:
                st.markdown(result["content"])
        else:
            st.error(f"❌ Error: {result.get('error', 'Unknown error')}")

def handle_browse_review():
    st.header("📖 Browse & Review Generated Content")
    st.markdown("Review and manage all AI-generated teaching materials.")
    
    subjects, subject_chapters = get_subjects_and_chapters()
    
    if not subjects:
        st.info("No content found. Please upload some PDF content first.")
        return
    
    col1, col2 = st.columns(2)
    with col1:
        selected_subject = st.selectbox("Select Subject", [""] + subjects)
    with col2:
        chapters = subject_chapters.get(selected_subject, []) if selected_subject else []
        selected_chapter = st.selectbox("Select Chapter", [""] + chapters)
    
    if selected_subject and selected_chapter:
        content_data = get_content_by_subject_chapter(selected_subject, selected_chapter)
        
        if content_data:
            st.subheader(f"Content: {selected_subject} > {selected_chapter}")
            st.write(f"**Applicable Grades:** {', '.join(content_data.get('applicable_grades', []))}")
            
            topics = content_data.get('topics', {})
            for topic_id, topic_data in topics.items():
                with st.expander(f"📚 {topic_data.get('title', topic_id)}"):
                    
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.subheader("📄 Original Content")
                        st.text_area("", topic_data.get('content', ''), height=150, key=f"orig_{topic_id}")
                    
                    with col2:
                        ai_content = topic_data.get('ai_generated_content', {})
                        st.subheader("🤖 AI Generated")
                        
                        for agent_type, ai_data in ai_content.items():
                            st.write(f"✅ {agent_type.replace('_', ' ').title()}")
                    
                    # Display AI content if available
                    if ai_content:
                        st.subheader("Generated Materials")
                        
                        for agent_type, ai_data in ai_content.items():
                            with st.expander(f"{agent_type.replace('_', ' ').title()}"):
                                if isinstance(ai_data.get('content'), dict):
                                    st.json(ai_data['content'])
                                else:
                                    st.markdown(ai_data.get('content', 'No content available'))

# ---------------- DISPLAY FUNCTIONS ----------------
def display_course_plan(plan_data):
    st.subheader("📅 Generated Course Plan")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Lesson Title", plan_data.get('lesson_title', 'N/A'))
        st.metric("Duration", f"{plan_data.get('total_duration', 'N/A')} minutes")
    
    with col2:
        grade_groupings = plan_data.get('grade_groupings', [])
        if grade_groupings:
            st.write("**Grade Groupings:**")
            for group in grade_groupings:
                st.write(f"- {group.get('grade', 'N/A')}: {group.get('group_size', 'N/A')} students")
    
    # Timeline
    if 'timeline' in plan_data:
        st.subheader("📊 Lesson Timeline")
        timeline_df = []
        for item in plan_data['timeline']:
            timeline_df.append({
                'Time': item.get('time_slot', ''),
                'Activity': item.get('activity', ''),
                'Grade 1': item.get('grade_1_task', ''),
                'Grade 2': item.get('grade_2_task', ''),
                'Grade 3': item.get('grade_3_task', ''),
                'Grade 4': item.get('grade_4_task', '')
            })
        if timeline_df:
            st.dataframe(timeline_df, use_container_width=True)

def display_activity(activity_data):
    st.subheader("🎯 Generated Activity")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Activity Title", activity_data.get('activity_title', 'N/A'))
        st.metric("Type", activity_data.get('activity_type', 'N/A'))
    with col2:
        st.metric("Duration", f"{activity_data.get('estimated_duration', 'N/A')} minutes")
    
    if 'materials_needed' in activity_data:
        st.subheader("📦 Materials Needed")
        for material in activity_data['materials_needed']:
            st.write(f"• {material}")

def display_worksheet(worksheet_data):
    st.subheader("📝 Generated Worksheet")
    
    st.metric("Title", worksheet_data.get('worksheet_title', 'N/A'))
    
    if 'sections' in worksheet_data:
        st.subheader("📋 Worksheet Sections")
        for section in worksheet_data['sections']:
            with st.expander(f"{section.get('section_title', 'Section')} - {section.get('difficulty_level', 'N/A')}"):
                questions = section.get('questions', [])
                for q in questions:
                    st.write(f"**Q{q.get('question_number', '?')}:** {q.get('question_text', 'N/A')}")

def display_assessment(assessment_data):
    st.subheader("📊 Generated Assessment")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Title", assessment_data.get('assessment_title', 'N/A'))
        st.metric("Type", assessment_data.get('assessment_type', 'N/A'))
    with col2:
        st.metric("Duration", f"{assessment_data.get('duration', 'N/A')} minutes")

def display_visual_aid(visual_data):
    st.subheader("🎨 Generated Visual Aid Design")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Title", visual_data.get('visual_aid_title', 'N/A'))
        st.metric("Type", visual_data.get('aid_type', 'N/A'))
    with col2:
        st.metric("Size", visual_data.get('size_specifications', 'N/A'))

def display_peer_activity(peer_data):
    st.subheader("🤝 Generated Peer Activity")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Activity Title", peer_data.get('activity_title', 'N/A'))
        st.metric("Collaboration Type", peer_data.get('collaboration_type', 'N/A'))
    with col2:
        st.metric("Duration", f"{peer_data.get('duration', 'N/A')} minutes")

if __name__ == "__main__":
    main()