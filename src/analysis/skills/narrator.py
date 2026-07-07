"""
summarize_cluster skill — LLM-generated narrative for a risk cluster (Phase C).

Execution priority:
  1. Claude Code CLI (`claude -p`) — uses OAuth subscription account; no API key needed.
  2. Anthropic SDK — fallback when CLI is absent and ANTHROPIC_API_KEY is set.

Blocking call; streaming deferred to Phase F per OQ-A01 resolution in RFC-008 §3.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from typing import List

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a financial risk analyst summarizing SEC 10-K filing risk factors. "
    "Write concise, factual summaries grounded in the provided text. "
    "Do not add opinions or investment advice."
)

_USER_TEMPLATE = (
    "The following risk segments have been classified as '{archetype}' "
    "(SASB dimension: {sasb_topic}).\n\n"
    "Write a 1–3 sentence narrative summary of the key risk theme across these segments:\n\n"
    "{segments_text}\n\n"
    "Summary (1–3 sentences):"
)


def claude_cli_available() -> bool:
    """Return True if the `claude` CLI binary is on PATH."""
    return shutil.which("claude") is not None


def summarize_cluster(
    archetype: str,
    representative_segments: List[str],
    sasb_topic: str = "",
    model: str = "claude-opus-4-6",
    max_tokens: int = 256,
    temperature: float = 0.2,
) -> str:
    """
    Generate a 1–3 sentence narrative summary for a SASB risk cluster.

    Tries the Claude Code CLI first (subscription billing), then falls back to
    the Anthropic SDK if ANTHROPIC_API_KEY is set and the CLI is absent.

    Args:
        archetype:               SASB archetype key (e.g. "business_model").
        representative_segments: Up to 5 representative segment texts.
        sasb_topic:              SASB material topic string (empty string if unknown).
        model:                   Claude model ID — passed to SDK fallback only; the CLI
                                 uses the subscription account's configured model.
        max_tokens:              Maximum output tokens (SDK fallback only).
        temperature:             Sampling temperature (SDK fallback only).

    Returns:
        Narrative summary string.

    Raises:
        RuntimeError: If the CLI exits non-zero.
        ImportError:  If SDK fallback is chosen but `anthropic` is not installed.
        Exception:    On other errors — callers should catch and log.
    """
    snippets = [seg[:400] for seg in representative_segments[:5]]
    segments_text = "\n\n".join(f"- {s}" for s in snippets)

    user_content = _USER_TEMPLATE.format(
        archetype=archetype.replace("_", " "),
        sasb_topic=sasb_topic or "general risk",
        segments_text=segments_text,
    )

    if claude_cli_available():
        return _summarize_via_cli(archetype, user_content)
    return _summarize_via_sdk(archetype, user_content, model, max_tokens, temperature)


def _summarize_via_cli(archetype: str, user_content: str) -> str:
    """Invoke `claude -p` with a combined system + user prompt."""
    full_prompt = f"{_SYSTEM_PROMPT}\n\n{user_content}"
    try:
        proc = subprocess.run(
            ["claude", "-p", full_prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("claude CLI timed out after 120s") from exc

    if proc.returncode != 0:
        raise RuntimeError(
            f"claude CLI exited {proc.returncode}: {proc.stderr.strip()}"
        )

    summary = proc.stdout.strip()
    logger.info("summarize_cluster (CLI): %s → %d chars", archetype, len(summary))
    return summary


def _summarize_via_sdk(
    archetype: str,
    user_content: str,
    model: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """Call the Anthropic Messages API (requires ANTHROPIC_API_KEY in environment)."""
    try:
        import anthropic  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "The 'anthropic' package is required for SDK fallback in summarize_cluster. "
            "Run: pip install anthropic"
        ) from exc

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    text_blocks = [b.text for b in response.content if hasattr(b, "text")]
    summary = " ".join(text_blocks).strip()
    logger.info("summarize_cluster (SDK): %s → %d chars", archetype, len(summary))
    return summary
