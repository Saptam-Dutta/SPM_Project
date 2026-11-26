# SPM Project Control Centre

One Streamlit app that combines the three course apps and adds a risk register.
It is preloaded with the **IoT Device Security Monitoring System** project (plan,
actual, EVM checkpoints, risks, defects), and every AI button uses the one
provider you choose in the sidebar (Google Gemini, OpenAI, Anthropic Claude, or
any OpenAI-compatible API).

| Page | Comes from | What it does |
|---|---|---|
| Overview | new | Plan vs actual schedule, cost, final EVM, defects |
| Charter | charter app | AI drafts the charter, you edit, download `.xlsx` in your template |
| Schedule and resources | resource conflict app | Detects overload; rule-based smoothing, AI advice, resource leveling |
| Cost (EVM) | EVM app | SV/SPI/CV/CPI, EAC, Isolation Forest anomalies, AI report |
| Risks | new | Register, probability x impact heat map, AI suggestions |

## Run (Windows PowerShell)

```powershell
cd spm_control_center
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501. Paste an API key in the sidebar to use the AI buttons.
Everything else (detection, smoothing, leveling, EVM, heat map, charter template
fill using the prepared sample draft) works without a key.

## Folder layout

```
app.py                 sidebar, navigation and the shared AI settings
core/llm_client.py     one wrapper for all AI providers
core/charter.py        charter prompt + template writer (from the charter app)
core/scheduler.py      conflict detection (unchanged from the schedule app)
core/ai_advisor.py     AI smoothing advice (from the schedule app)
core/leveling.py       rule-based smoothing and resource leveling (new)
core/evm.py            EVM maths, Isolation Forest, AI report (from the EVM app)
core/risks.py          risk scoring and AI suggestions (new)
views/                 one file per page
data/                  the IoT project sample data (CSV and JSON)
assets/                Project_Charter_Template.xlsx
```

Effort figures in `data/` are planning estimates (1 person-day = 6 hours, Rs 1,000
per person-day); edit the CSVs to match your own records.
