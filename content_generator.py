"""
Multigrade AI Content Generator Module

This module contains all the AI content generation functionality for the 
Multigrade AI Teaching Assistant. It includes specialized agents for generating 
various types of educational content for multigrade classrooms (Grades 1-4).
"""

import json
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

import google.generativeai as genai

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip

# ---------------- CONFIGURATION ----------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"
MAX_TOKENS = 2048
TEMPERATURE = 0.7

# Grade configurations
GRADES = ["Grade 1", "Grade 2", "Grade 3", "Grade 4"]
SUBJECTS = ["English", "Mathematics", "Science", "Social Studies", "Hindi", "Art & Craft"]

# ---------------- DATA STRUCTURES ----------------
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

# ---------------- CORE FUNCTIONS ----------------
def initialize_gemini_api(api_key: str = None) -> bool:
    """Initialize Gemini API with provided or environment API key"""
    key = api_key or GEMINI_API_KEY
    if not key:
        raise ValueError("Gemini API key not provided")
    
    try:
        genai.configure(api_key=key)
        # Test the connection
        model = genai.GenerativeModel(GEMINI_MODEL)
        test_response = model.generate_content("Say 'API connection successful'")
        return True
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Gemini API: {e}")

def create_agent(agent_type: AgentType) -> MultigradeAIAgent:
    """Factory function to create AI agents"""
    return MultigradeAIAgent(agent_type)

def generate_content_with_agent(
    agent_type: AgentType, 
    context: TeachingContext, 
    additional_params: Dict[str, Any] = None
) -> Dict[str, Any]:
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

# ---------------- SPECIALIZED CONTENT GENERATORS ----------------
def generate_course_plan(
    grades: List[str], 
    subjects: List[str], 
    topic: str, 
    duration_minutes: int, 
    class_size: int, 
    learning_objectives: List[str]
) -> Dict[str, Any]:
    """Generate a comprehensive daily course plan for multigrade classroom"""
    context = TeachingContext(
        grades=grades,
        subjects=subjects,
        topic=topic,
        duration_minutes=duration_minutes,
        class_size=class_size,
        learning_objectives=learning_objectives
    )
    return generate_content_with_agent(AgentType.COURSE_PLANNER, context)

def generate_activity(
    grades: List[str], 
    subjects: List[str], 
    topic: str, 
    duration_minutes: int, 
    class_size: int,
    activity_type: str = "group"
) -> Dict[str, Any]:
    """Generate engaging learning activities for multigrade classroom"""
    context = TeachingContext(
        grades=grades,
        subjects=subjects,
        topic=topic,
        duration_minutes=duration_minutes,
        class_size=class_size,
        learning_objectives=[f"Engage {grade} students in {topic}" for grade in grades]
    )
    return generate_content_with_agent(
        AgentType.ACTIVITY_GENERATOR, 
        context, 
        {"activity_type": activity_type}
    )

def generate_worksheet(
    grades: List[str], 
    subjects: List[str], 
    topic: str,
    difficulty_level: str = "mixed"
) -> Dict[str, Any]:
    """Generate differentiated worksheets for multigrade practice"""
    context = TeachingContext(
        grades=grades,
        subjects=subjects,
        topic=topic,
        duration_minutes=30,  # Default worksheet time
        class_size=20,  # Default class size for worksheets
        learning_objectives=[f"Practice {topic} skills for {grade}" for grade in grades]
    )
    return generate_content_with_agent(
        AgentType.WORKSHEET_GENERATOR, 
        context, 
        {"difficulty_level": difficulty_level}
    )

def generate_assessment(
    grades: List[str], 
    subjects: List[str], 
    topic: str,
    assessment_type: str = "formative"
) -> Dict[str, Any]:
    """Generate comprehensive assessments for multigrade evaluation"""
    context = TeachingContext(
        grades=grades,
        subjects=subjects,
        topic=topic,
        duration_minutes=30,  # Default assessment time
        class_size=20,  # Default class size
        learning_objectives=[f"Assess {topic} understanding for {grade}" for grade in grades]
    )
    return generate_content_with_agent(
        AgentType.ASSESSMENT_GENERATOR, 
        context, 
        {"assessment_type": assessment_type}
    )

def generate_visual_aid(
    grades: List[str], 
    subjects: List[str], 
    topic: str,
    aid_type: str = "poster"
) -> Dict[str, Any]:
    """Generate visual aid descriptions for multigrade classroom"""
    context = TeachingContext(
        grades=grades,
        subjects=subjects,
        topic=topic,
        duration_minutes=45,  # Default lesson duration
        class_size=20,  # Default class size
        learning_objectives=[f"Support visual learning of {topic} for {grade}" for grade in grades]
    )
    return generate_content_with_agent(
        AgentType.VISUAL_AIDS_GENERATOR, 
        context, 
        {"aid_type": aid_type}
    )

def generate_peer_activity(
    grades: List[str], 
    subjects: List[str], 
    topic: str, 
    class_size: int,
    collaboration_type: str = "mixed_groups"
) -> Dict[str, Any]:
    """Generate peer-to-peer learning activities for cross-grade collaboration"""
    context = TeachingContext(
        grades=grades,
        subjects=subjects,
        topic=topic,
        duration_minutes=45,  # Default duration for peer activities
        class_size=class_size,
        learning_objectives=[f"Foster peer learning in {topic} across grades"]
    )
    return generate_content_with_agent(
        AgentType.PEER_ACTIVITY_GENERATOR, 
        context, 
        {"collaboration_type": collaboration_type}
    )

# ---------------- UTILITY FUNCTIONS ----------------
def safe_parse_json(s: str) -> Optional[Dict[str, Any]]:
    """Safely parse JSON string with fallback options"""
    try:
        return json.loads(s)
    except Exception:
        s2 = s.strip().strip("`").strip()
        try:
            return json.loads(s2)
        except Exception:
            return None

def validate_context(context: TeachingContext) -> bool:
    """Validate TeachingContext has required fields"""
    return all([
        context.grades,
        context.subjects,
        context.topic,
        context.duration_minutes > 0,
        context.class_size > 0
    ])

# ---------------- EXAMPLE USAGE ----------------
if __name__ == "__main__":
    # Example usage of the content generator
    print("🎓 Multigrade AI Content Generator")
    print("==================================")
    
    # Initialize API (you need to set GEMINI_API_KEY environment variable)
    try:
        initialize_gemini_api()
        print("✅ Gemini API initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize API: {e}")
        exit(1)
    
    # Example: Generate a course plan
    result = generate_course_plan(
        grades=["Grade 1", "Grade 2"],
        subjects=["Mathematics"],
        topic="Addition and Subtraction",
        duration_minutes=45,
        class_size=20,
        learning_objectives=[
            "Grade 1: Count and add objects up to 10",
            "Grade 2: Add and subtract two-digit numbers"
        ]
    )
    
    if result["success"]:
        print("✅ Course plan generated successfully!")
        print(json.dumps(result["content"], indent=2))
    else:
        print(f"❌ Failed to generate course plan: {result['error']}")
