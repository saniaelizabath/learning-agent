# 🎓 Multigrade AI Teaching Assistant

A comprehensive AI-powered teaching assistant designed specifically for multigrade classrooms (Grades 1-4). This application leverages Google's Gemini AI to provide specialized teaching tools that accommodate multiple grade levels simultaneously.

## ✨ Features

### 🤖 Six Specialized AI Agents

1. **📅 Course Planner**: Generate day-to-day lesson plans for multigrade classes with differentiated instruction
2. **🎯 Activity Generator**: Create engaging activities adapted for different grade levels
3. **📝 Worksheet Generator**: Design differentiated worksheets with grade-appropriate content
4. **📊 Assessment Generator**: Build comprehensive assessments for multigrade evaluation
5. **🎨 Visual Aids Generator**: Create descriptions for educational visual materials
6. **🤝 Peer Activity Generator**: Design cross-grade collaborative learning activities

### 🏫 Multigrade-Specific Features

- **Grade-Differentiated Content**: All materials are automatically adapted for Grades 1-4
- **Cross-Grade Collaboration**: Peer-to-peer activities that promote mentoring between grades
- **Classroom Management**: Strategies for managing multiple grade levels simultaneously
- **Resource Optimization**: Shared materials and activities across grade levels
- **Flexible Grouping**: Dynamic student grouping strategies for multigrade settings

### 📚 Content Management

- PDF upload and automatic topic extraction
- Firebase integration for content storage and retrieval
- Generated content organization by subject and chapter
- Version tracking for AI-generated materials

## 🚀 Setup Instructions

### Prerequisites

1. **Python 3.8+**
2. **Google Gemini API Key**
3. **Firebase Project** (for content storage)

### Installation

1. **Clone or download the project files**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Google Gemini API**:
   - Get your API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Choose one of these setup methods:
   
   **Method 1: Environment Variable (Recommended)**
   ```bash
   # Linux/Mac
   export GEMINI_API_KEY="your_api_key_here"
   
   # Windows Command Prompt
   set GEMINI_API_KEY=your_api_key_here
   
   # Windows PowerShell
   $env:GEMINI_API_KEY="your_api_key_here"
   ```
   
   **Method 2: .env File**
   - Create a `.env` file in the project root
   - Add: `GEMINI_API_KEY=your_api_key_here`
   
   **Method 3: In-App Setup**
   - Run the app without API key
   - Use the "Quick Setup" option in the interface

4. **Set up Firebase**:
   - Create a new Firebase project at [Firebase Console](https://console.firebase.google.com/)
   - Enable Firestore Database
   - Download service account credentials as `firebase_config.json`
   - Place the file in the project root directory

5. **Run the application**:
   ```bash
   streamlit run app.py
   ```

## 🎯 Usage Guide

### Getting Started

1. **Launch the app** and verify Gemini API and Firebase connections
2. **Select grades and subjects** from the sidebar for your multigrade class
3. **Choose an AI agent** based on what you want to create
4. **Configure classroom context** (class size, duration, etc.)

### Content Management Workflow

1. **Upload PDF content** using the "Content Management" agent
2. **Extract topics** automatically from your curriculum materials
3. **Generate teaching materials** using specialized AI agents
4. **Review and save** generated content to Firebase
5. **Browse and reuse** saved materials in "Browse & Review"

### Example Workflows

#### Creating a Daily Lesson Plan
1. Select "Course Planner" agent
2. Enter lesson topic (e.g., "Addition and Subtraction")
3. Specify learning objectives for each grade
4. Generate comprehensive multigrade lesson plan
5. Review timeline, activities, and differentiation strategies

#### Generating Cross-Grade Activities
1. Choose "Peer Activity Generator"
2. Set collaboration topic (e.g., "Story Writing Together")
3. Select collaboration type (Buddy System, Mixed Groups, etc.)
4. Generate structured peer learning activities
5. Review role definitions and station rotations

#### Creating Differentiated Worksheets
1. Use "Worksheet Generator" agent
2. Specify topic and difficulty range
3. Generate grade-specific question sets
4. Review answer keys and extension activities
5. Save for classroom use

## 🏗️ Architecture

### AI Agent System
- **Modular design** with specialized agents for different teaching needs
- **Context-aware generation** using classroom parameters
- **JSON-structured outputs** for consistent formatting
- **Error handling** and fallback mechanisms

### Data Storage
- **Firebase Firestore** for scalable content storage
- **Hierarchical organization** by subject, chapter, and topic
- **AI content versioning** with generation timestamps
- **Multigrade metadata** for content applicability

### User Interface
- **Streamlit-based** responsive web interface
- **Agent selection** with specialized input forms
- **Real-time feedback** and progress indicators
- **Content visualization** with structured displays

## 🎨 Customization

### Adding New Subjects
Modify the `SUBJECTS` list in `app.py`:
```python
SUBJECTS = ["English", "Mathematics", "Science", "Social Studies", "Hindi", "Art & Craft", "Your New Subject"]
```

### Extending Grade Ranges
Update the `GRADES` list for different grade configurations:
```python
GRADES = ["Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5"]
```

### Custom Agent Prompts
Modify agent prompts in the `AGENT_PROMPTS` dictionary to customize AI behavior for your specific curriculum needs.

## 🔧 Troubleshooting

### Common Issues

1. **Gemini API not working**:
   - Verify your API key is correct
   - Check internet connection
   - Ensure API quotas are not exceeded

2. **Firebase connection failed**:
   - Verify `firebase_config.json` is in the correct location
   - Check Firebase project permissions
   - Ensure Firestore is enabled

3. **PDF processing errors**:
   - Ensure PDF files are text-readable (not scanned images)
   - Check file size limits
   - Verify PDF structure matches expected format

### Performance Tips

- **Use smaller class sizes** for faster AI generation
- **Cache results** by saving generated content to Firebase
- **Limit concurrent generations** to avoid API rate limits
- **Optimize PDF sizes** for faster processing

## 📖 Educational Benefits

### For Teachers
- **Time-saving**: Automated generation of teaching materials
- **Differentiation**: Built-in grade-level adaptations
- **Consistency**: Structured, curriculum-aligned content
- **Flexibility**: Customizable for different classroom needs

### For Students
- **Appropriate challenge levels** for each grade
- **Peer learning opportunities** across grades
- **Varied learning modalities** (visual, kinesthetic, collaborative)
- **Progressive skill development** through differentiated activities

### For Multigrade Classrooms
- **Efficient resource use** with shared materials
- **Cross-grade mentoring** opportunities
- **Synchronized learning** across grade levels
- **Inclusive participation** for all students

## 🤝 Contributing

We welcome contributions to improve the Multigrade AI Teaching Assistant:

1. **Report bugs** and suggest features via issues
2. **Submit pull requests** for improvements
3. **Share curriculum adaptations** for different educational systems
4. **Provide feedback** on agent effectiveness

## 📄 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

- **Google Gemini** for powerful AI capabilities
- **Firebase** for reliable data storage
- **Streamlit** for intuitive UI framework
- **Educational community** for feedback and requirements

---

**Created for educators, by educators. Empowering multigrade classrooms with AI-driven teaching tools.**
