# MedSim

Hospital floor-plan simulation. Upload a floor plan image, Claude vision identifies zones, agents navigate with A* pathfinding, and Claude generates a bottleneck report with projected time savings.

Flow: **Upload** floor plan -> **Simulate** patients/nurses/doctors -> **Report** bottlenecks and projected annual minutes saved.

## Backend setup

```
cd backend
python -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # macOS/Linux
pip install -r requirements.txt
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY=sk-ant-...
uvicorn app.main:app --reload --port 8000
```

Health check: http://localhost:8000/

## Frontend setup

```
cd frontend
npm install
cp .env.example .env
npm run dev
```

Opens at http://localhost:5173.
