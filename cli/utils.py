import questionary
from typing import List, Optional, Tuple, Dict

from rich.console import Console

from cli.models import AnalystType
from tradingagents.llm_clients.model_catalog import get_model_options

console = Console()

TICKER_INPUT_EXAMPLES = "Ví dụ: SPY, VHM.VN, CNC.TO, 7203.T, 0700.HK"

ANALYST_ORDER = [
    ("Phân tích thị trường (Market)", AnalystType.MARKET),
    ("Phân tích mạng xã hội (Social)", AnalystType.SOCIAL),
    ("Phân tích tin tức (News)", AnalystType.NEWS),
    ("Phân tích cơ bản (Fundamentals)", AnalystType.FUNDAMENTALS),
]


def get_ticker() -> str:
    """Prompt the user to enter a ticker symbol."""
    ticker = questionary.text(
        f"Nhập mã chứng khoán cần phân tích ({TICKER_INPUT_EXAMPLES}):",
        validate=lambda x: len(x.strip()) > 0 or "Vui lòng nhập mã hợp lệ.",
        style=questionary.Style(
            [
                ("text", "fg:green"),
                ("highlighted", "noinherit"),
            ]
        ),
    ).ask()

    if not ticker:
        console.print("\n[red]Chưa nhập mã chứng khoán. Thoát...[/red]")
        exit(1)

    return normalize_ticker_symbol(ticker)


def normalize_ticker_symbol(ticker: str) -> str:
    """Normalize ticker input while preserving exchange suffixes."""
    return ticker.strip().upper()


def get_analysis_date() -> str:
    """Prompt the user to enter a date in YYYY-MM-DD format."""
    import re
    from datetime import datetime

    def validate_date(date_str: str) -> bool:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return False
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    date = questionary.text(
        "Ngày phân tích (YYYY-MM-DD):",
        validate=lambda x: validate_date(x.strip())
        or "Nhập ngày đúng định dạng YYYY-MM-DD.",
        style=questionary.Style(
            [
                ("text", "fg:green"),
                ("highlighted", "noinherit"),
            ]
        ),
    ).ask()

    if not date:
        console.print("\n[red]Chưa nhập ngày. Thoát...[/red]")
        exit(1)

    return date.strip()


def select_analysts() -> List[AnalystType]:
    """Select analysts using an interactive checkbox."""
    choices = questionary.checkbox(
        "Chọn [nhóm phân tích]:",
        choices=[
            questionary.Choice(display, value=value) for display, value in ANALYST_ORDER
        ],
        instruction="\n- Space: chọn/bỏ chọn\n- a: chọn/bỏ tất cả\n- Enter: xong",
        validate=lambda x: len(x) > 0 or "Phải chọn ít nhất một chuyên viên phân tích.",
        style=questionary.Style(
            [
                ("checkbox-selected", "fg:green"),
                ("selected", "fg:green noinherit"),
                ("highlighted", "noinherit"),
                ("pointer", "noinherit"),
            ]
        ),
    ).ask()

    if not choices:
        console.print("\n[red]Chưa chọn chuyên viên phân tích. Thoát...[/red]")
        exit(1)

    return choices


def select_research_depth() -> int:
    """Select research depth using an interactive selection."""

    # Define research depth options with their corresponding values
    DEPTH_OPTIONS = [
        ("Nông — Phân tích nhanh, ít vòng tranh luận và thảo luận chiến lược", 1),
        ("Trung bình — Cân bằng, số vòng tranh luận vừa phải", 3),
        ("Sâu — Nghiên cứu toàn diện, tranh luận và thảo luận chiến lược kỹ", 5),
    ]

    choice = questionary.select(
        "Chọn [độ sâu nghiên cứu]:",
        choices=[
            questionary.Choice(display, value=value) for display, value in DEPTH_OPTIONS
        ],
        instruction="\n- Mũi tên: di chuyển\n- Enter: chọn",
        style=questionary.Style(
            [
                ("selected", "fg:yellow noinherit"),
                ("highlighted", "fg:yellow noinherit"),
                ("pointer", "fg:yellow noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        console.print("\n[red]Chưa chọn độ sâu nghiên cứu. Thoát...[/red]")
        exit(1)

    return choice


def _fetch_openrouter_models() -> List[Tuple[str, str]]:
    """Fetch available models from the OpenRouter API."""
    import requests
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        resp.raise_for_status()
        models = resp.json().get("data", [])
        return [(m.get("name") or m["id"], m["id"]) for m in models]
    except Exception as e:
        console.print(f"\n[yellow]Không tải được danh sách model OpenRouter: {e}[/yellow]")
        return []


def select_openrouter_model() -> str:
    """Select an OpenRouter model from the newest available, or enter a custom ID."""
    models = _fetch_openrouter_models()

    choices = [questionary.Choice(name, value=mid) for name, mid in models[:5]]
    choices.append(questionary.Choice("Tự nhập model ID", value="custom"))

    choice = questionary.select(
        "Chọn model OpenRouter (mới nhất có sẵn):",
        choices=choices,
        instruction="\n- Mũi tên: di chuyển\n- Enter: chọn",
        style=questionary.Style([
            ("selected", "fg:magenta noinherit"),
            ("highlighted", "fg:magenta noinherit"),
            ("pointer", "fg:magenta noinherit"),
        ]),
    ).ask()

    if choice is None or choice == "custom":
        return questionary.text(
            "Nhập OpenRouter model ID (vd: google/gemma-4-26b-a4b-it):",
            validate=lambda x: len(x.strip()) > 0 or "Vui lòng nhập model ID.",
        ).ask().strip()

    return choice


def _prompt_custom_model_id() -> str:
    """Prompt user to type a custom model ID."""
    return questionary.text(
        "Nhập model ID:",
        validate=lambda x: len(x.strip()) > 0 or "Vui lòng nhập model ID.",
    ).ask().strip()


def _select_model(provider: str, mode: str) -> str:
    """Select a model for the given provider and mode (quick/deep)."""
    if provider.lower() == "openrouter":
        return select_openrouter_model()

    if provider.lower() == "azure":
        return questionary.text(
            f"Tên triển khai Azure ({mode}-thinking):",
            validate=lambda x: len(x.strip()) > 0 or "Vui lòng nhập tên deployment.",
        ).ask().strip()

    choice = questionary.select(
        f"Chọn [LLM {mode.title()}-thinking]:",
        choices=[
            questionary.Choice(display, value=value)
            for display, value in get_model_options(provider, mode)
        ],
        instruction="\n- Mũi tên: di chuyển\n- Enter: chọn",
        style=questionary.Style(
            [
                ("selected", "fg:magenta noinherit"),
                ("highlighted", "fg:magenta noinherit"),
                ("pointer", "fg:magenta noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        console.print(f"\n[red]Chưa chọn LLM {mode}-thinking. Thoát...[/red]")
        exit(1)

    if choice == "custom":
        return _prompt_custom_model_id()

    return choice


def select_shallow_thinking_agent(provider) -> str:
    """Select shallow thinking llm engine using an interactive selection."""
    return _select_model(provider, "quick")


def select_deep_thinking_agent(provider) -> str:
    """Select deep thinking llm engine using an interactive selection."""
    return _select_model(provider, "deep")

def select_llm_provider() -> tuple[str, str | None]:
    """Select the LLM provider and its API endpoint."""
    # (display_name, provider_key, base_url)
    PROVIDERS = [
        ("OpenAI", "openai", "https://api.openai.com/v1"),
        ("Google", "google", None),
        ("Anthropic", "anthropic", "https://api.anthropic.com/"),
        ("xAI", "xai", "https://api.x.ai/v1"),
        ("DeepSeek", "deepseek", "https://api.deepseek.com"),
        ("Qwen", "qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        ("GLM", "glm", "https://open.bigmodel.cn/api/paas/v4/"),
        ("OpenRouter", "openrouter", "https://openrouter.ai/api/v1"),
        ("Azure OpenAI", "azure", None),
        ("Ollama", "ollama", "http://localhost:11434/v1"),
    ]

    choice = questionary.select(
        "Chọn nhà cung cấp LLM:",
        choices=[
            questionary.Choice(display, value=(provider_key, url))
            for display, provider_key, url in PROVIDERS
        ],
        instruction="\n- Mũi tên: di chuyển\n- Enter: chọn",
        style=questionary.Style(
            [
                ("selected", "fg:magenta noinherit"),
                ("highlighted", "fg:magenta noinherit"),
                ("pointer", "fg:magenta noinherit"),
            ]
        ),
    ).ask()
    
    if choice is None:
        console.print("\n[red]Chưa chọn nhà cung cấp LLM. Thoát...[/red]")
        exit(1)

    provider, url = choice
    return provider, url


def ask_openai_reasoning_effort() -> str:
    """Ask for OpenAI reasoning effort level."""
    choices = [
        questionary.Choice("Trung bình (mặc định)", "medium"),
        questionary.Choice("Cao (kỹ hơn)", "high"),
        questionary.Choice("Thấp (nhanh hơn)", "low"),
    ]
    return questionary.select(
        "Mức Reasoning Effort (OpenAI):",
        choices=choices,
        style=questionary.Style([
            ("selected", "fg:cyan noinherit"),
            ("highlighted", "fg:cyan noinherit"),
            ("pointer", "fg:cyan noinherit"),
        ]),
    ).ask()


def ask_anthropic_effort() -> str | None:
    """Ask for Anthropic effort level.

    Controls token usage and response thoroughness on Claude 4.5+ and 4.6 models.
    """
    return questionary.select(
        "Mức Effort (Anthropic):",
        choices=[
            questionary.Choice("Cao (khuyến nghị)", "high"),
            questionary.Choice("Trung bình (cân bằng)", "medium"),
            questionary.Choice("Thấp (nhanh, rẻ hơn)", "low"),
        ],
        style=questionary.Style([
            ("selected", "fg:cyan noinherit"),
            ("highlighted", "fg:cyan noinherit"),
            ("pointer", "fg:cyan noinherit"),
        ]),
    ).ask()


def ask_gemini_thinking_config() -> str | None:
    """Ask for Gemini thinking configuration.

    Returns thinking_level: "high" or "minimal".
    Client maps to appropriate API param based on model series.
    """
    return questionary.select(
        "Chế độ Thinking (Gemini):",
        choices=[
            questionary.Choice("Bật Thinking (khuyến nghị)", "high"),
            questionary.Choice("Tối thiểu / Tắt Thinking", "minimal"),
        ],
        style=questionary.Style([
            ("selected", "fg:green noinherit"),
            ("highlighted", "fg:green noinherit"),
            ("pointer", "fg:green noinherit"),
        ]),
    ).ask()


def ask_output_language() -> str:
    """Ask for report output language."""
    choice = questionary.select(
        "Ngôn ngữ báo cáo đầu ra:",
        choices=[
            questionary.Choice("Tiếng Việt (mặc định)", "Vietnamese"),
            questionary.Choice("English", "English"),
            questionary.Choice("Chinese (中文)", "Chinese"),
            questionary.Choice("Japanese (日本語)", "Japanese"),
            questionary.Choice("Korean (한국어)", "Korean"),
            questionary.Choice("Hindi (हिन्दी)", "Hindi"),
            questionary.Choice("Spanish (Español)", "Spanish"),
            questionary.Choice("Portuguese (Português)", "Portuguese"),
            questionary.Choice("French (Français)", "French"),
            questionary.Choice("German (Deutsch)", "German"),
            questionary.Choice("Arabic (العربية)", "Arabic"),
            questionary.Choice("Russian (Русский)", "Russian"),
            questionary.Choice("Ngôn ngữ khác (tự nhập)", "custom"),
        ],
        style=questionary.Style([
            ("selected", "fg:yellow noinherit"),
            ("highlighted", "fg:yellow noinherit"),
            ("pointer", "fg:yellow noinherit"),
        ]),
    ).ask()

    if choice == "custom":
        return questionary.text(
            "Tên ngôn ngữ (vd: Turkish, Thai, Indonesian):",
            validate=lambda x: len(x.strip()) > 0 or "Vui lòng nhập tên ngôn ngữ.",
        ).ask().strip()

    return choice
