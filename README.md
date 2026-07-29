# GLM Chat — AI Chatbot

A full-stack AI chatbot using **GLM-4.7-Flash** via the [Z.AI SDK](https://github.com/zai-org/zai-python-sdk), with a React frontend and a FastAPI backend.

> **Hosting instructions** → [DEPLOYMENT.md](./DEPLOYMENT.md)

---

## Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Runtime | Node.js | 22.14.0 |
| Package Manager | npm | 10.9.7 |
| Frontend Framework | React | 19.2.8 |
| Build Tool | Vite | 8.1.5 |
| Styling | Tailwind CSS | 3.4.17 |
| Markdown | react-markdown | 10.1.0 |
| Icons | lucide-react | 1.27.0 |
| Backend | Python | 3.12.3 |
| API Framework | FastAPI | 0.115.5 |
| ASGI Server | uvicorn | 0.32.1 |
| AI SDK | zai-sdk | 0.2.3 |
| Storage | Local JSON file | — |

---

## Project Structure

```
/
├── api/
│   ├── main.py              # FastAPI application
│   ├── requirements.txt     # Python dependencies (pinned)
│   ├── .env                 # API key (git-ignored)
│   ├── .env.example         # Example env file
│   └── chat_history.json    # Auto-generated local database
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Root component with state management
│   │   ├── components/      # UI components
│   │   └── utils/api.js     # API client with SSE streaming
│   ├── package.json         # Frontend dependencies (pinned)
│   └── vite.config.js       # Vite configuration with proxy
├── vercel.json              # Root Vercel deployment config
├── render.yaml              # Render.com deployment blueprint
├── start.sh                 # One-command local start script
└── README.md
```

---

## Setup

### 1. Configure API Key

```bash
# Copy the example file
cp api/.env.example api/.env

# Edit it and paste your Z.AI API key
nano api/.env
# ZAI_API_KEY=your-actual-key
```

### 2. Install API Dependencies

```bash
cd api
pip install -r requirements.txt
```

### 3. Install Frontend Dependencies

```bash
cd frontend
npm install
```

---

## Running

### One Command (both services)

```bash
./start.sh
```

### Manually

```bash
# Terminal 1 — API
cd api
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/sessions` | Create new chat session |
| `GET` | `/sessions` | List all sessions |
| `GET` | `/sessions/{id}/messages` | Get session messages |
| `DELETE` | `/sessions/{id}` | Delete a session |
| `POST` | `/chat/stream` | Stream chat response (SSE) |

---

## Features

- **Streaming responses** via Server-Sent Events (SSE)
- **Multi-session** chat with persistent history
- **Thinking process** viewer (collapsible reasoning block)
- **Markdown rendering** with code highlighting
- **Stop generation** button
- **Local JSON database** — no external DB required
- **Mobile-responsive** sidebar
- **Copy message** button on hover
- **Suggestion prompts** on empty state
