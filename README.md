# AutoRAG Tool

A user-friendly tool for Retrieval Augmented Generation (RAG) with a modern UI.

## Features

- Ingest documents from multiple sources:
  - File Upload (PDF, DOCX, TXT)
  - MySQL database
  - Web URLs
- Configurable LLM backends:
  - Local models (free)
  - HuggingFace (free tier with rate limits or paid API)
  - Azure OpenAI (paid)
- Simple query interface
- Agent-based reasoning mode
- Shareable results

## Tech Stack

- **Backend**: FastAPI, LangChain, FAISS vector store
- **Frontend**: React.js with TailwindCSS
- **Deployment**: Docker

## Getting Started

### Prerequisites

- Docker and Docker Compose
- For local LLM hosting: GPU recommended (but CPU will work)

### Installation

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/autorag-tool.git
   cd autorag-tool
   ```

2. Start the application with Docker Compose
   ```bash
   docker-compose up
   ```

3. Access the application
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000

### Manual Setup (without Docker)

#### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Usage

1. Configure Data Source:
   - Go to "/config" route
   - Select your data source type (MySQL, File, URL)
   - Configure your LLM provider
   - Click "Connect" to ingest your data

2. Ask Questions:
   - Go to "/query" route
   - Enter your question in the input field
   - Click "Ask" to get a response using RAG
   - Use "Agent (Reasoning)" for more complex queries

3. View Results:
   - Full results are displayed in the "/results" route

## License

MIT

## Acknowledgements

- [LangChain](https://github.com/langchain-ai/langchain)
- [FAISS](https://github.com/facebookresearch/faiss)
- [FastAPI](https://fastapi.tiangolo.com/)
- [React](https://reactjs.org/)
- [TailwindCSS](https://tailwindcss.com/) 