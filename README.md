# RatePilot — Currency intelligence, simplified.

An original Flask-based currency intelligence workspace for conversion, market exploration, historical trends, rate watching, comparison, and travel budgeting.

## Run
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Exchange data
RatePilot uses the public Frankfurter API by default. You can override `EXCHANGE_API_BASE` in `.env` if needed.

## Features
- Public landing experience — no forced login
- Live currency conversion
- Market board
- Historical trend chart
- Currency comparison
- Rate Watch with optional targets
- Travel Budget planner
- Optional authentication
- Saved conversions
- Dark/light theme
- Responsive UI
- Graceful API failure handling

## Note
Rates depend on the external exchange-rate service. The app does not fabricate live rates.
