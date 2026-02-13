#!/usr/bin/env python3
"""
Example Usage of Multigrade AI Content Generator

This script demonstrates how to use the content_generator module
to create various types of educational content for multigrade classrooms.
"""

import os
from content_generator import (
    initialize_gemini_api,
    generate_course_plan,
    generate_activity,
    generate_worksheet,
    generate_assessment,
    generate_visual_aid,
    generate_peer_activity,
    AgentType,
    TeachingContext
)

def main():
    print("🎓 Multigrade AI Content Generator - Example Usage")
    print("=" * 50)
    
    # Check if API key is available
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY environment variable not set.")
        print("Please set your Gemini API key:")
        print("export GEMINI_API_KEY='your_api_key_here'")
        return
    
    # Initialize the API
    try:
        initialize_gemini_api()
        print("✅ Gemini API initialized successfully\n")
    except Exception as e:
        print(f"❌ Failed to initialize API: {e}")
        return
    
    # Example 1: Generate a daily course plan
    print("📅 Example 1: Generating Daily Course Plan")
    print("-" * 40)
    
    course_plan = generate_course_plan(
        grades=["Grade 1", "Grade 2", "Grade 3"],
        subjects=["Mathematics"],
        topic="Addition and Subtraction Basics",
        duration_minutes=60,
        class_size=25,
        learning_objectives=[
            "Grade 1: Count and add objects up to 10",
            "Grade 2: Add and subtract two-digit numbers without regrouping",
            "Grade 3: Solve word problems involving addition and subtraction"
        ]
    )
    
    if course_plan["success"]:
        print("✅ Course plan generated successfully!")
        if isinstance(course_plan["content"], dict):
            print(f"Lesson Title: {course_plan['content'].get('lesson_title', 'N/A')}")
            print(f"Duration: {course_plan['content'].get('total_duration', 'N/A')} minutes")
        print()
    else:
        print(f"❌ Error: {course_plan['error']}\n")
    
    # Example 2: Generate a learning activity
    print("🎯 Example 2: Generating Learning Activity")
    print("-" * 40)
    
    activity = generate_activity(
        grades=["Grade 1", "Grade 2"],
        subjects=["Science"],
        topic="Plant Life Cycle",
        duration_minutes=30,
        class_size=20,
        activity_type="hands-on"
    )
    
    if activity["success"]:
        print("✅ Activity generated successfully!")
        if isinstance(activity["content"], dict):
            print(f"Activity Title: {activity['content'].get('activity_title', 'N/A')}")
            print(f"Type: {activity['content'].get('activity_type', 'N/A')}")
        print()
    else:
        print(f"❌ Error: {activity['error']}\n")
    
    # Example 3: Generate a worksheet
    print("📝 Example 3: Generating Worksheet")
    print("-" * 40)
    
    worksheet = generate_worksheet(
        grades=["Grade 2", "Grade 3"],
        subjects=["English"],
        topic="Reading Comprehension",
        difficulty_level="intermediate"
    )
    
    if worksheet["success"]:
        print("✅ Worksheet generated successfully!")
        if isinstance(worksheet["content"], dict):
            print(f"Worksheet Title: {worksheet['content'].get('worksheet_title', 'N/A')}")
            print(f"Grade Levels: {', '.join(worksheet['content'].get('grade_levels', []))}")
        print()
    else:
        print(f"❌ Error: {worksheet['error']}\n")
    
    # Example 4: Generate an assessment
    print("📊 Example 4: Generating Assessment")
    print("-" * 40)
    
    assessment = generate_assessment(
        grades=["Grade 1", "Grade 2", "Grade 3"],
        subjects=["Mathematics"],
        topic="Number Recognition and Counting",
        assessment_type="formative"
    )
    
    if assessment["success"]:
        print("✅ Assessment generated successfully!")
        if isinstance(assessment["content"], dict):
            print(f"Assessment Title: {assessment['content'].get('assessment_title', 'N/A')}")
            print(f"Type: {assessment['content'].get('assessment_type', 'N/A')}")
        print()
    else:
        print(f"❌ Error: {assessment['error']}\n")
    
    # Example 5: Generate visual aids
    print("🎨 Example 5: Generating Visual Aid")
    print("-" * 40)
    
    visual_aid = generate_visual_aid(
        grades=["Grade 1", "Grade 2", "Grade 3", "Grade 4"],
        subjects=["Science"],
        topic="Solar System",
        aid_type="poster"
    )
    
    if visual_aid["success"]:
        print("✅ Visual aid generated successfully!")
        if isinstance(visual_aid["content"], dict):
            print(f"Visual Aid Title: {visual_aid['content'].get('visual_aid_title', 'N/A')}")
            print(f"Type: {visual_aid['content'].get('aid_type', 'N/A')}")
        print()
    else:
        print(f"❌ Error: {visual_aid['error']}\n")
    
    # Example 6: Generate peer activity
    print("🤝 Example 6: Generating Peer Activity")
    print("-" * 40)
    
    peer_activity = generate_peer_activity(
        grades=["Grade 2", "Grade 3", "Grade 4"],
        subjects=["English"],
        topic="Creative Story Writing",
        class_size=24,
        collaboration_type="buddy_system"
    )
    
    if peer_activity["success"]:
        print("✅ Peer activity generated successfully!")
        if isinstance(peer_activity["content"], dict):
            print(f"Activity Title: {peer_activity['content'].get('activity_title', 'N/A')}")
            print(f"Collaboration Type: {peer_activity['content'].get('collaboration_type', 'N/A')}")
        print()
    else:
        print(f"❌ Error: {peer_activity['error']}\n")
    
    print("🎉 All examples completed!")
    print("\nℹ️  You can now use these functions in your own applications.")
    print("📚 See content_generator.py for more details and customization options.")

if __name__ == "__main__":
    main()
