# Aivoa CRM - AI-First HCP Module (Log Interaction Screen)

Aivoa CRM is an AI-first Customer Relationship Management (CRM) system designed for Life Sciences and pharmaceutical field representatives. It features a dual-interface **Log Interaction Screen** that lets reps log interactions with Healthcare Professionals (HCPs) either via a structured form or through an intelligent conversational AI chatbot.

## Core Features & Tech Stack

- **React Frontend**: Built using Vite, React 18, and Redux Toolkit for clean, asynchronous state management.
- **Python FastAPI Backend**: Fast, RESTful endpoints coupled with SQLAlchemy ORM running a local SQLite instance (representing MySQL/Postgres structures).
- **LangGraph AI Agent**: A state-machine agent powered by LangGraph to parse unstructured field logs, determine actions, and route details to standard tools.
- **Groq LLM / Smart Fallback**: Utilizes Groq's `gemma2-9b-it` model when a `GROQ_API_KEY` is provided. If not, it falls back to a smart, pattern-matching regex parser simulating agent transitions and tool execution for offline evaluation.
- **Premium Glassmorphic Design**: Customized CSS stylesheet (`index.css`) styling utilizing a dark mode theme, neon glow outlines, hover micro-animations, and the Google Inter font.

---

## LangGraph AI Agent & 5 Sales Tools

The LangGraph agent manages the conversational log flow. When a representative types or pastes unstructured meeting notes, the agent coordinates the following 5 custom tools:

1. **`get_hcp_profile`**: Retrieves the doctor's details (clinic, address, email) and recent interaction/task history.
2. **`log_interaction`**: Summarizes meeting discussions, scores sentiment (Positive/Neutral/Negative), tags discussed medical products, and creates log entries.
3. **`edit_interaction`**: Modifies the fields (channel, sentiment, tags, notes) of an existing logged meeting.
4. **`schedule_followup`**: Registers a task/calendar event for future action with the HCP.
5. **`generate_followup_email`**: Drafts a professional, context-aware email template customized to the meeting notes.

---

## Getting Started

### 1. Prerequisites
- **Python** (version 3.10 or higher)
- **NodeJS** & **npm**

### 2. Backend Setup
1. Open a terminal and navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Install the Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. *(Optional)* Add your Groq API token inside the `.env` file:
   ```env
   GROQ_API_KEY=your-actual-groq-key-here
   ```
   *If left empty, the application automatically runs in **Mock Fallback Mode** with smart simulated tool triggers.*
4. Start the FastAPI server using Uvicorn:
   ```bash
   python -m uvicorn app.main:app --reload --port 8000
   ```
   The API documentation will be available at `http://localhost:8000/docs`.

### 3. Frontend Setup
1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install node dependencies:
   ```bash
   npm install
   ```
3. Launch the Vite development server:
   ```bash
   npm run dev
   ```
   Open your browser and navigate to the link shown (typically `http://localhost:5173`).

---

## Verification & Walkthrough Instructions

### Step 1: Seed the Database
When you first open the app, click the **"Seed Demo Data"** button in the top left. This initializes the SQLite database with 4 doctors (e.g. Dr. Jenkins, Dr. Mercer) and 5 drug products (e.g. Lipitor, Nexium, Gilenya) and fills in sample interaction logs.

### Step 2: Conversational Logging
Select **Dr. Sarah Jenkins** from the directory. Go to the **AI Chat Assistant** tab and send the following unstructured text:
> *"Just finished a virtual call with Dr. Jenkins today. We discussed Nexium efficacy profiles. She was happy with the safety guidelines and requested printed brochures. Let's schedule a task next Friday to mail them."*

**AI Agent Response**:
1. The assistant parses the text.
2. It detects a virtual call channel and tags **Nexium** as the product discussed.
3. It updates the doctor's recent sentiment to **Positive** in the profile card.
4. It calls `log_interaction` and updates the Timeline.
5. It automatically calls `schedule_followup` to schedule the brochures mailer task for next Friday.
6. It triggers `generate_followup_email` to output a draft email in the **AI Generated Email Draft** side-panel.

### Step 3: Structured Form Logging
Switch to the **Structured Logging Form** tab. Fill out the fields manually, check product tags, write notes, and click **Log Interaction** to test manual data sync.

### Step 4: Editing Interactions
Find any logged card in the **Interaction Timeline** at the bottom. Click **"Edit Log"** to open the modal. Edit the notes, change the channel to "Phone", or change the sentiment. Click **Save Changes** and verify it updates in the timeline and profile sentiment tags.

### Step 5: Follow-Up Action Board
View scheduled follow-ups in the **Follow-Up Scheduler** column. Toggle the checkbox next to any task to mark it as **Completed** or create new tasks manually.
