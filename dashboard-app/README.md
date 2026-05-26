# Dashboard App

A full-stack analytics dashboard application with a **React + Vite frontend** and **FastAPI backend** that processes and visualizes data using charts and interactive components.

## Overview

The Dashboard App is designed to provide an intuitive interface for data analysis and visualization. It features:

- **Frontend**: Modern React application with Vite bundler, featuring interactive charts with Recharts and beautiful UI components with Lucide React icons
- **Backend**: FastAPI-based REST API that handles data processing, file uploads, and serves analytics data
- **Data Processing**: Python-based data processor for handling spreadsheets and data transformations
- **Deployment**: Ready for deployment on Render with Docker support

## Project Structure

```
dashboard-app/
├── frontend/               # React + Vite application
│   ├── src/               # React components and pages
│   ├── public/            # Static assets
│   ├── package.json       # Frontend dependencies
│   ├── vite.config.js     # Vite configuration
│   ├── index.html         # Entry HTML file
│   └── README.md          # Frontend-specific documentation
├── backend/               # FastAPI Python application
│   ├── main.py            # FastAPI app and API endpoints
│   ├── data_processor.py  # Data processing logic
│   ├── requirements.txt   # Python dependencies
│   └── runtime.txt        # Python version specification
├── package.json           # Root dependencies
├── render.yaml            # Render deployment configuration
└── README.md              # This file
```

## Tech Stack

### Frontend
- **React 18** - JavaScript UI library
- **Vite 4** - Fast build tool and dev server
- **Recharts** - React charting library
- **Lucide React** - Icon library
- **Axios** - HTTP client

### Backend
- **FastAPI** - Modern Python web framework
- **Uvicorn** - ASGI server
- **Pandas** - Data manipulation and analysis
- **OpenPyXL** - Excel file handling
- **Python-dotenv** - Environment variable management

## Prerequisites

- **Node.js** (v16 or higher) - for frontend
- **Python** (3.10 or higher) - for backend
- **npm** or **yarn** - package manager

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/shazanjustin/gravitas-skills.git
cd gravitas-skills/dashboard-app
```

### 2. Frontend Setup

```bash
cd frontend
npm install
```

### 3. Backend Setup

```bash
cd ../backend
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 4. Environment Variables

Create a `.env` file in the `backend/` directory:

```env
GROQ_API_KEY=your_api_key_here
```

## Running the Application

### Option 1: Run Frontend and Backend Separately

**Terminal 1 - Frontend (React Dev Server)**
```bash
cd frontend
npm run dev
```
The frontend will be available at `http://localhost:5173`

**Terminal 2 - Backend (FastAPI)**
```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
The API will be available at `http://localhost:8000`

Access the API documentation at `http://localhost:8000/docs` (Swagger UI)

### Option 2: Build for Production

**Build Frontend**
```bash
cd frontend
npm run build
```
The built files will be in `frontend/dist/`

**Run Backend in Production**
```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Available Scripts

### Frontend

```bash
npm run dev       # Start development server
npm run build     # Build for production
npm run preview   # Preview production build
npm run lint      # Run ESLint
```

### Backend

```bash
uvicorn main:app --reload              # Development with auto-reload
uvicorn main:app --host 0.0.0.0 --port 8000  # Production mode
```

## API Endpoints

The backend provides the following main endpoints (see `backend/main.py` for full API documentation):

- `GET /` - Health check
- `POST /upload` - Upload and process data files
- `GET /analytics` - Get analytics data
- `GET /docs` - Interactive API documentation (Swagger UI)

For complete endpoint documentation, visit `http://localhost:8000/docs` when running the backend.

## Deployment

### Deploy on Render

The application is configured for deployment on Render using the `render.yaml` configuration file.

1. Push your repository to GitHub
2. Connect your GitHub repository to Render
3. Render will automatically use the `render.yaml` configuration
4. Set the `GROQ_API_KEY` environment variable in the Render dashboard
5. Deploy!

The backend will run on the Python runtime with FastAPI/Uvicorn, and the frontend can be deployed as a static site or served by the backend.

## Development Workflow

1. **Frontend Development**: The Vite dev server provides hot module replacement (HMR) for instant feedback
2. **Backend Development**: FastAPI's `--reload` flag automatically restarts on code changes
3. **API Testing**: Use the Swagger UI at `http://localhost:8000/docs`
4. **Data Processing**: Modify `backend/data_processor.py` to customize data handling logic

## Troubleshooting

### Port Already in Use
If port 5173 (frontend) or 8000 (backend) is already in use:

```bash
# Frontend: Use --port flag
npm run dev -- --port 5174

# Backend: Use --port argument
uvicorn main:app --reload --port 8001
```

### CORS Issues
The backend should be configured to accept requests from the frontend. Update CORS settings in `backend/main.py` if needed.

### Missing Dependencies
Ensure you've run:
```bash
npm install          # Frontend
pip install -r requirements.txt  # Backend
```

### Virtual Environment Not Activating
Ensure you're in the `backend/` directory and try:
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

## Contributing

1. Create a feature branch
2. Make your changes
3. Test thoroughly (both frontend and backend)
4. Submit a pull request

## License

Part of the Gravitas Skills project.

## Support

For issues or questions, please refer to the main repository or create an issue in the GitHub repository.
