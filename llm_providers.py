"""
LLM provider abstraction for bilkalkyl car analysis.

Configuration via environment variables:
  LLM_PROVIDER   - "openai" (default) or "anthropic"
  LLM_MODEL      - override default model for chosen provider
  OPENAI_API_KEY - required for openai
  ANTHROPIC_API_KEY - required for anthropic
"""

import os
import json
import re
from abc import ABC, abstractmethod

SYSTEM_PROMPT = """Du är en svensk bilkostnadsanalytiker. Analysera given information om en bil och returnera ENBART giltig JSON — ingen annan text, inga kommentarer.

Returnera exakt detta JSON-schema:
{
  "name": "Kortnamn, t.ex. 'Volvo V60 D4 2019'",
  "model": "Kort beskrivning, t.ex. 'Diesel, 2019, ~9 000 mil'",
  "inkop": 185000,
  "kwh_mil": 0.0,
  "liter_mil": 0.72,
  "depr_rate": 0.09,
  "svc_month": 450,
  "road_bes": 360,
  "insurance_month": 700
}

Riktlinjer:
- inkop: inköpspris i SEK.
  Om ett pris finns i annonstexten: använd det priset (inkl. moms om båda anges).
  Om inget pris finns (regnummer-sökning): uppskatta BEGAGNAT marknadsvärde — ALDRIG nypriset.
  Använd dessa riktmärken för svenska marknaden 2024–2025:

  Elbilar (elbil, EV):
    1 år gammal, lågt miltal (<5 000 mil):  75% av nypris
    2 år gammal, normalt miltal (5–15 000): 60–65% av nypris
    3 år gammal, normalt miltal:            50–55% av nypris
    4+ år gammal:                           40–50% av nypris
    Varje 10 000 mil utöver snittet: -5% ytterligare

  Bensin/Diesel:
    1–2 år gammal, lågt miltal:             70–75% av nypris
    3–4 år gammal, normalt miltal:          55–65% av nypris
    5–7 år gammal:                          40–55% av nypris
    Varje 10 000 mil utöver snittet: -4% ytterligare

  Ungefärliga nypris (Sverige inkl. moms) för referens:
    Volvo XC40 Recharge: 550 000 kr
    Volvo XC60 Recharge: 700 000 kr
    Tesla Model 3 LR: 520 000 kr
    Kia EV6: 490 000 kr
    Skoda Enyaq 80: 560 000 kr
    VW ID.4: 480 000 kr
    BMW 3-serie: 450 000 kr
    Volvo V60 bensin: 400 000 kr
    Skoda Octavia bensin: 300 000 kr
- kwh_mil: kWh per mil (1 mil = 10 km). Sätt 0 för bensin-/dieselbilar.
  VIKTIGT: För elbilar MÅSTE detta vara > 0.
  Typvärden: Volvo XC40 Recharge 2.3, Tesla Model 3 2.1, Kia EV6 2.2, VW ID.4 2.4, Skoda Enyaq 2.3, Polestar 2 2.2.
- liter_mil: liter per mil. Sätt 0 för elbilar.
  VIKTIGT: För bensin-/dieselbilar MÅSTE detta vara > 0. Typvärden: bensin 0.7–1.0, diesel 0.6–0.8.
- depr_rate: ÅRLIG värdeminsknings­takt som decimal.
  Typvärden: elbil <4 år: 0.10–0.12, elbil äldre: 0.08–0.10,
  bensin/diesel nyare: 0.07–0.09, bensin/diesel äldre: 0.05–0.07
- svc_month: genomsnittlig månatlig service/underhåll i SEK
  (elbil: 250–400, bensin ny: 400–600, bensin äldre: 600–900)
- road_bes: ÅRLIG vägskatt i SEK (beroende på bränsletyp och CO2-utsläpp)
  Elbil: 360–750 SEK/år, bensin: 360–5000+ SEK/år
- insurance_month: uppskattad månatlig försäkring i SEK
  Halvförsäkring för äldre bilar (>8 000 mil): 200–400 kr/mån
  Helförsäkring för nyare bilar (<8 000 mil): 500–1200 kr/mån

Var realistisk med svenska marknadsförhållanden 2024–2025.
Om specifik information saknas, uppskatta rimligt utifrån biltyp och årsmodell."""


class LLMProvider(ABC):
    @abstractmethod
    def analyze_car(self, user_content: str) -> dict:
        pass

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return json.loads(match.group())
        return json.loads(text)


class OpenAIProvider(LLMProvider):
    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model = os.getenv("LLM_MODEL", self.DEFAULT_MODEL).split("#")[0].strip()

    def analyze_car(self, user_content: str) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content[:5000]},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        return self._parse_json(response.choices[0].message.content)


class AnthropicProvider(LLMProvider):
    DEFAULT_MODEL = "claude-haiku-4-5-20251001"

    def __init__(self):
        import anthropic
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = os.getenv("LLM_MODEL", self.DEFAULT_MODEL).split("#")[0].strip()

    def analyze_car(self, user_content: str) -> dict:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT + "\n\nSvara ENBART med JSON-objektet, inget annat.",
            messages=[{"role": "user", "content": user_content[:5000]}],
        )
        return self._parse_json(message.content[0].text)


_PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}


def get_provider() -> LLMProvider:
    raw = os.getenv("LLM_PROVIDER", "openai")
    name = raw.split("#")[0].strip().lower()
    cls = _PROVIDERS.get(name)
    if not cls:
        raise ValueError(
            f"Okänd LLM-leverantör: {name!r}. Tillgängliga: {list(_PROVIDERS)}"
        )
    return cls()
