# Bilkalkyl — Leasing vs. Köp

Interaktiv kostnadskalkylator för att jämföra leasing mot köp av bil. Stöder dynamisk tilläggning av valfri bil via Blocket-annons eller registreringsnummer — analyserad med AI.

## Funktioner

- Jämför leasing mot flera köpalternativ (elbil, bensin, begagnad)
- Justera förutsättningar: mil/år, jämförelseperiod, elpris, kapitalkostnad
- Lägg till valfri bil via Blocket-URL, klistrad annonstext eller registreringsnummer
- AI uppskattar inköpspris, förbrukning, värdeminskning, försäkring och skatt
- Byt LLM-leverantör via miljövariabel (OpenAI eller Anthropic)

## Kom igång

### 1. Klona och skapa virtuell miljö

```bash
git clone <repo-url>
cd car-cost

python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Konfigurera API-nyckel

```bash
cp .env.example .env
```

Öppna `.env` och fyll i din OpenAI-nyckel:

```
OPENAI_API_KEY=sk-...
```

### 3. Starta servern

```bash
python app.py
```

Öppna [http://localhost:5000](http://localhost:5000) i webbläsaren.

## Byta LLM

Ändra i `.env`:

| Variabel | Värde | Beskrivning |
|---|---|---|
| `LLM_PROVIDER` | `openai` (default) | OpenAI API |
| `LLM_PROVIDER` | `anthropic` | Anthropic API |
| `LLM_MODEL` | `gpt-4o-mini` | Valfri modelloverride |

För Anthropic, lägg till `ANTHROPIC_API_KEY=sk-ant-...` i `.env`.

## Lägga till ny LLM-leverantör

Skapa en ny klass i [llm_providers.py](llm_providers.py) som ärver från `LLMProvider` och implementerar `analyze_car(user_content: str) -> dict`. Registrera den i `_PROVIDERS`-dict:en längst ned i filen.

## Projektstruktur

```
car-cost/
├── bilkalkyl.html    # Frontend (standalone SPA)
├── app.py            # Flask-backend
├── llm_providers.py  # LLM-abstraktion
├── requirements.txt
└── .env.example
```

## Kostnadsmodell

Månadskostnad per bil = värdeminskning + kapitalkostnad + drivmedel + försäkring + service + vägskatt

- **Värdeminskning** — inköpspris × årlig deprRate / 12
- **Kapitalkostnad** — alternativkostnad eller ränta på fullt inköpspris
- **Total kostnad** över vald period = månadskostnad × 12 × år (värdeminskning och kapital är redan inräknade månadsvis)
