# 🧭 VoyagerAI — Premium AI Travel Planning Agent

An elegant, constraint-aware travel planning engine powered by a single-agent **Gemini 2.5 Pro** loop. It ingests user styles, schedules, dietary needs, and financial boundaries to generate a dynamic, structured day-by-day itinerary with localized tips, custom packing lists, and day-specific replanning capabilities.

---

## 🚀 What is VoyagerAI?

**VoyagerAI** is a production-grade, double-sided application designed for the **Google for Developers PromptWars (Build with AI)** challenge. It bridges a highly sophisticated FastAPI-based backend agent loop with a gorgeous, dark-themed Next.js dashboard. 

Unlike basic LLM wrappers, VoyagerAI uses an advanced **single-agent loop with manual function dispatching**. It operates as a closed-loop controller: generating plans, validating constraints via strict calculations, and dynamically adjusting its planning prompts in real time until an optimal, fully compliant travel plan is constructed.

---

## 🛠️ Key Features (What It Does)

- 📅 **Granular Daily Itineraries**: Splits every single travel day into detailed Morning, Afternoon, and Evening blocks with specific activity names, physical locations, duration estimates, and associated costs.
- ⚖️ **Automated Constraint Audit**: Running a pure-Python math processor, the system validates whether the total daily activity costs, transport budgets, and accommodation estimates exceed your global spending limit.
- 🔄 **Day-by-Day Replanning**: Don't like a specific day's activities? You can request edits (e.g., "Make it more family-friendly" or "Less walking") on *just that day*. The agent updates that day's elements while re-balancing the remaining financial and temporal constraints.
- 💡 **Localized Enrichment**: Injects custom localized tips, safety alerts, weather-appropriate packing lists, and visa recommendations.
- 🎨 **State-of-the-Art Dark UI**: Glassmorphic interfaces with gradient borders, staggered page-load animations, and fully interactive responsive design.

---

## 🧰 Tech Stack

<p align="left">
  <!-- Python -->
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <!-- FastAPI -->
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <!-- Gemini -->
  <img src="https://img.shields.io/badge/Google_Gemini-8E75C2?style=for-the-badge&logo=googlegemini&logoColor=white" alt="Google Gemini" />
  <!-- Next.js -->
  <img src="https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white" alt="Next.js" />
  <!-- React -->
  <img src="https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB" alt="React" />
  <!-- Tailwind CSS -->
  <img src="https://img.shields.io/badge/Tailwind_CSS_v4-38B2AC?style=for-the-badge&logo=tailwindcss&logoColor=white" alt="Tailwind CSS" />
  <!-- Framer Motion -->
  <img src="https://img.shields.io/badge/Framer_Motion-00C5FF?style=for-the-badge&logo=framer&logoColor=white" alt="Framer Motion" />
</p>

- **Backend**: Python 3.11+ / FastAPI / Uvicorn
- **AI Core**: Modern `google-genai` SDK targeting the `gemini-2.5-pro` model
- **Frontend**: Next.js App Router (React 19) / Tailwind CSS v4 / shadcn/ui / Lucide Icons
- **Animation**: Framer Motion (Staggered list cards, fluid layouts, smooth expand/collapse states)

---

## 📐 System Architecture

VoyagerAI uses a single-agent orchestrator with three dedicated tool declarations. The agent operates via a **manual tool-execution loop** (up to 10 iterations) to guarantee high-fidelity data structures:

```mermaid
graph TD
    User([User Travel Preferences]) -->|POST /plan| API[FastAPI Backend]
    API -->|1. Initial Prompt| Agent[Gemini 2.5 Pro Agent]
    
    Agent -->|Call: generate_itinerary| ToolGen[generate_itinerary Tool]
    ToolGen -->|Gemini Sub-call| GeminiModel[JSON Generation]
    
    Agent -->|Call: validate_constraints| ToolVal[validate_constraints Tool]
    ToolVal -->|Pure Python Checks| CalcMath[Daily Cost Math / Budget Verification]
    
    Agent -->|Call: enrich_day| ToolEnrich[enrich_day Tool]
    ToolEnrich -->|Gemini Sub-call| TipsGen[Practical Tips & weather]
    
    Agent -->|Final Text Response| Parser[Clean JSON Text Parser]
    Parser -->|PlanResponse| ReactClient[Next.js Client]
```

---

## 📂 Project Layout

```
├── backend/
│   ├── main.py              # Single-file production FastAPI backend
│   ├── requirements.txt     # Python backend dependencies
│   └── .env                 # API Key configuration (hidden from repository)
├── frontend/
│   ├── app/                 # Next.js App Router entrypoints & CSS
│   ├── components/          # Reusable react widgets (PlanForm, DayCard, etc.)
│   ├── lib/                 # Shared Typescript interfaces & utility bindings
│   ├── package.json         # Javascript dependencies
│   └── tsconfig.json        # Strict compilation rules
└── README.md                # Top-level documentation (this file)
```

---

## ⚙️ Getting Started

### 1. Prerequisites
- **Python**: version 3.11 or higher
- **Node.js**: version 18.x or higher
- **Conda** or a virtual environment manager

### 2. Configure Environment Variables
Create a `.env` file inside the `backend/` folder:
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
GOOGLE_GENAI_USE_VERTEXAI=false
```

### 3. Launch the Backend API
```bash
# Navigate to the backend directory
cd backend

# Create & activate your environment (or use jarvis conda env)
conda activate jarvis # or standard virtualenv

# Install backend dependencies
pip install -r requirements.txt

# Start the uvicorn development server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
The FastAPI documentation will now be available at `http://localhost:8000/docs`.

### 4. Launch the Frontend Application
```bash
# Navigate to the frontend directory
cd ../frontend

# Install node dependencies
npm install

# Start Next.js with Turbopack in development mode
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser to run the application!

---

## 🔌 API Documentation

### `POST /plan`
Accepts traveler parameters, triggers the agent constraint loop, and yields a comprehensive, validated travel plan.
- **Request Body**:
```json
{
  "destination": "Rome",
  "days": 3,
  "budget_usd": 600,
  "travel_style": "cultural",
  "group_type": "couple",
  "dietary": "gluten-free",
  "constraints": "minimize walking distance"
}
```

### `POST /replan-day`
Allows dynamic edits to a specific day while retaining the other days and overall budget constraint parameters.
- **Request Body**:
```json
{
  "itinerary": { ... },
  "day_number": 2,
  "reason": "Rain forecasted. Prefer indoor museums instead of the outdoor tour."
}
```

### `GET /health`
- **Response**: `{"status": "ok"}`

---

## 🛡️ License
Built under the **PromptWars Hackathon** guidelines. Feel free to clone, iterate, and customize this repository.
