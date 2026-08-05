"""Cau hinh chung.

README muc 9.4: TEN MODEL phai khai bao ro trong SOURCE CODE (khong dat trong .env),
va ghi lai trong logging/metadata.json. File nay la noi khai bao do.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# =====================================================================
# MODEL - khai bao trong code theo README muc 9.4.
# Rang buoc: MOI agent chi duoc dung model <= 10B tham so (README muc 9.1).
# Dem TONG tham so, khong phai active params: model MoE 20B la VI PHAM.
# =====================================================================
MODEL_NAME = "qwen2.5:7b"
MODEL_PARAMETER_SIZE = "7B"
MODEL_PROVIDER = "ollama"

# Doi provider chi can doi 2 bien nay trong .env, khong sua code:
#   Groq        https://api.groq.com/openai/v1        + llama-3.1-8b-instant
#   Together    https://api.together.xyz/v1
#   OpenRouter  https://openrouter.ai/api/v1
#   Ollama      http://localhost:11434/v1
# Dung "or" chu khong dung default cua getenv: .env de trong tra ve chuoi rong,
# chuoi rong lot qua default va lam SDK bao "Missing credentials".
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or "http://localhost:11434/v1"
LLM_API_KEY = os.getenv("LLM_API_KEY") or "ollama"

TEMPERATURE = 0.0  # bai nay can tinh on dinh, khong can sang tao
MAX_TOKENS = 800
LLM_TIMEOUT_S = 60
LLM_MAX_RETRIES = 3

# =====================================================================
# Duong dan
# =====================================================================
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
LOG_DIR = ROOT / "logging"

TRACE_PATH = LOG_DIR / "trace.jsonl"
METADATA_PATH = LOG_DIR / "metadata.json"

POLICY_VERSION = "EC_POLICY_V1"

# Gioi han schema (README muc 6). Verifier cat bot neu vuot.
MAX_IDS_PER_ENTITY = 5
MAX_EVIDENCE = 10
MAX_ROOT_CAUSES = 3
MAX_RESPONSIBLE_PARTIES = 3
MAX_ACTIONS = 5

# Sai so cho phep khi doi soat payment vs item + freight (README muc 4).
PAYMENT_TOLERANCE_BRL = 0.10
