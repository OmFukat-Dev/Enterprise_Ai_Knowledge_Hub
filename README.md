# Enterprise AI Knowledge Hub: Advanced RAG + MLOps (Free Stack)

**Senior/Principal Engineer Level Project** – Zero AWS, Zero Docker, 100% Free, More Advanced Than Most Corporate Projects

## ✨ Features

### Document Processing
- 📄 Marker + Unstructured for perfect PDF/table extraction
- 🔍 Semantic + hierarchical chunking
- 🧠 Context-aware document understanding

### Vector Database
- 🗄️ Qdrant vector DB (local, production-grade)
- 🔍 BGE embeddings + Cross-encoder reranking
- ⚡ High-performance similarity search

### AI & ML
- 🤖 Groq Llama-3.1-70B inference (blazing fast)
- 🧠 Advanced RAG (Retrieval-Augmented Generation)
- 📊 Streamlit evaluation dashboard with MRR/HitRate

### Backend & Infrastructure
- 🚀 FastAPI backend (no Docker needed)
- 🔄 ZenML MLOps pipelines ready
- 📈 Scalable architecture

## 🚀 Quick Start
```bash
venv\Scripts\activate
uvicorn src.api.app:app --reload
# Open http://127.0.0.1:8000/docs
```

### Prerequisites
- Python 3.8+
- pip
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/enterprise-ai-knowledge-hub.git
   cd enterprise-ai-knowledge-hub
   ```

2. **Set up a virtual environment**
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   # OR
   source venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   # Start both backend and frontend
   .\run.bat  # Windows
   # OR
   ./run.sh    # Linux/Mac
   ```
   - Backend API: http://localhost:8000/api/docs
   - Frontend: http://localhost:8501

## 🏗️ Project Structure

```
enterprise-ai-knowledge-hub/
├── src/                    # Source code
│   ├── api/               # FastAPI application
│   ├── ingestion/         # Document processing
│   ├── retrieval/         # Vector store and search
│   └── generation/        # LLM integration
├── data/                  # Processed data storage
├── frontend/              # Streamlit UI components
├── tests/                 # Test cases
├── main.py               # Application entry point
├── dashboard.py          # Streamlit dashboard
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## ⚙️ Configuration

Create a `.env` file in the root directory with your configuration:

```env
# Required
GROQ_API_KEY=your_groq_api_key

# Optional
QDRANT_PATH=./data/qdrant_db
```

## 🛠️ Development

### Running in Development Mode

1. **Start the backend server**
   ```bash
   uvicorn main:app --reload --port 8000
   ```

2. **Start the frontend** (in a new terminal)
   ```bash
   streamlit run dashboard.py
   ```

### Testing

Run the test suite with:
```bash
pytest tests/
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with FastAPI, Streamlit, and Qdrant
- Uses BERT-based sentence transformers for embeddings
- Inspired by modern RAG (Retrieval-Augmented Generation) architectures
- Special thanks to the open-source community for their invaluable tools and libraries