from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from openai import OpenAI

try:
    from json_repair import repair_json
except ImportError:
    def repair_json(s: str) -> str:  # type: ignore[misc]
        return s

log = logging.getLogger(__name__)

_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "ollama": {"base_url": "http://localhost:11434/v1", "api_key": "ollama"},
    "vllm":   {"base_url": "http://localhost:8000/v1",  "api_key": "vllm"},
}

_CHARS_PER_TOKEN = 3.0
_TOKEN_SAFETY_BUFFER = 300
_MIN_OUTPUT_TOKENS = 256


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return text.strip()


# --------------------------------------------------------------------------
# Fallback parser for models (e.g. some vLLM chat templates) that render
# tool calls into `message.content` as custom non-JSON syntax instead of
# populating the OpenAI-style `tool_calls` field:
#
#   <|tool_call>call:NAME{key:value,key2:value2}<tool_call|>
#
# where strings are wrapped as <|"|>text<|"|> and object keys are bare
# (unquoted) identifiers rather than valid JSON. None of vLLM's built-in
# --tool-call-parser options recognize this, so we parse it ourselves.
# --------------------------------------------------------------------------
_STR_DELIM = '<|"|>'
_TOOL_CALL_START_RE = re.compile(r'<\|tool_call>call:([A-Za-z0-9_]+)')
_TOOL_CALL_END_RE = re.compile(r'\s*<tool_call\|>')


class _CustomArgParser:
    """Recursive-descent parser for the pseudo-JSON argument syntax above."""

    def __init__(self, s: str) -> None:
        self.s = s
        self.i = 0
        self.n = len(s)

    def parse_value(self) -> Any:
        self._skip_ws()
        if self.s.startswith(_STR_DELIM, self.i):
            return self._parse_string()
        if self.i < self.n and self.s[self.i] == "{":
            return self._parse_object()
        if self.i < self.n and self.s[self.i] == "[":
            return self._parse_array()
        if self.s.startswith("true", self.i):
            self.i += 4
            return True
        if self.s.startswith("false", self.i):
            self.i += 5
            return False
        return self._parse_bare()

    def _skip_ws(self) -> None:
        while self.i < self.n and self.s[self.i] in " \t\n\r":
            self.i += 1

    def _parse_string(self) -> str:
        self.i += len(_STR_DELIM)
        end = self.s.find(_STR_DELIM, self.i)
        if end == -1:
            end = self.n
        val = self.s[self.i:end]
        self.i = end + len(_STR_DELIM)
        return val

    def _parse_key(self) -> str:
        if self.s.startswith(_STR_DELIM, self.i):
            return self._parse_string()
        start = self.i
        while self.i < self.n and self.s[self.i] != ":":
            self.i += 1
        return self.s[start:self.i].strip()

    def _parse_object(self) -> dict:
        self.i += 1  # consume '{'
        obj: dict[str, Any] = {}
        self._skip_ws()
        if self.i < self.n and self.s[self.i] == "}":
            self.i += 1
            return obj
        while True:
            self._skip_ws()
            key = self._parse_key()
            self._skip_ws()
            if self.i < self.n and self.s[self.i] == ":":
                self.i += 1
            value = self.parse_value()
            obj[key] = value
            self._skip_ws()
            if self.i < self.n and self.s[self.i] == ",":
                self.i += 1
                continue
            if self.i < self.n and self.s[self.i] == "}":
                self.i += 1
            break
        return obj

    def _parse_array(self) -> list:
        self.i += 1  # consume '['
        arr: list[Any] = []
        self._skip_ws()
        if self.i < self.n and self.s[self.i] == "]":
            self.i += 1
            return arr
        while True:
            arr.append(self.parse_value())
            self._skip_ws()
            if self.i < self.n and self.s[self.i] == ",":
                self.i += 1
                continue
            if self.i < self.n and self.s[self.i] == "]":
                self.i += 1
            break
        return arr

    def _parse_bare(self) -> Any:
        start = self.i
        depth = 0
        while self.i < self.n:
            c = self.s[self.i]
            if c in ",}]" and depth == 0:
                break
            if c in "{[":
                depth += 1
            elif c in "}]":
                depth -= 1
            self.i += 1
        raw = self.s[start:self.i].strip()
        try:
            return int(raw)
        except ValueError:
            pass
        try:
            return float(raw)
        except ValueError:
            pass
        return raw


def _find_matching_brace(s: str, open_idx: int) -> int | None:
    depth = 0
    i = open_idx
    n = len(s)
    while i < n:
        if s.startswith(_STR_DELIM, i):
            j = s.find(_STR_DELIM, i + len(_STR_DELIM))
            i = (j + len(_STR_DELIM)) if j != -1 else n
            continue
        c = s[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _extract_custom_tool_calls(content: str) -> tuple[list[tuple[str, dict]], str]:
    """Pull `<|tool_call>call:NAME{...}<tool_call|>` blocks out of raw content.

    Returns (list of (name, args_dict), leftover_content_with_calls_removed).
    """
    calls: list[tuple[str, dict]] = []
    spans: list[tuple[int, int]] = []
    pos = 0
    while True:
        m = _TOOL_CALL_START_RE.search(content, pos)
        if not m:
            break
        name = m.group(1)
        brace_start = content.find("{", m.end())
        if brace_start == -1:
            break
        brace_end = _find_matching_brace(content, brace_start)
        if brace_end is None:
            break
        args_str = content[brace_start:brace_end + 1]
        tail = _TOOL_CALL_END_RE.match(content, brace_end + 1)
        call_end = tail.end() if tail else brace_end + 1
        try:
            args = _CustomArgParser(args_str).parse_value()
            if not isinstance(args, dict):
                args = {}
        except Exception:
            args = {}
        calls.append((name, args))
        spans.append((m.start(), call_end))
        pos = call_end
    if not spans:
        return [], content
    pieces = []
    last = 0
    for s, e in spans:
        pieces.append(content[last:s])
        last = e
    pieces.append(content[last:])
    return calls, "".join(pieces).strip()


class LLMClient:
    """
    OpenAI-compatible client (Ollama / vLLM) with:
      - plain text / structured JSON completion (`complete`)
      - a native tool-calling loop (`run_agent_loop`) used by the agentic
        Planner / Worker / Critic — the model decides which tools to call
        and when it is done, rather than following a fixed sequence.
    """

    def __init__(self, provider: str, model: str) -> None:
        self.provider = provider.lower()
        self.model = model
        self.context_window = int(os.getenv("CONTEXT_WINDOW", "8192"))

        defaults = _PROVIDER_DEFAULTS.get(self.provider, {})
        if self.provider == "ollama":
            base_url = os.getenv("OLLAMA_BASE_URL", defaults["base_url"])
            api_key = os.getenv("OLLAMA_API_KEY", defaults["api_key"])
        elif self.provider == "vllm":
            base_url = os.getenv("VLLM_BASE_URL", defaults["base_url"])
            api_key = os.getenv("VLLM_API_KEY", defaults["api_key"])
        else:
            raise ValueError(f"Unknown provider '{provider}'. Use 'ollama' or 'vllm'.")

        self.client = OpenAI(base_url=base_url, api_key=api_key)
        # Qwen3 (and some other chat templates) emit a <think>...</think> block before
        # every response/tool call by default. That's wasted latency for this pipeline's
        # deterministic extraction tasks, so we ask the template to skip it. vLLM forwards
        # this via extra_body; models whose template doesn't check `enable_thinking` just
        # ignore it.
        self._extra_body = {"chat_template_kwargs": {"enable_thinking": False}} if self.provider == "vllm" else None
        log.info("LLMClient ready | provider=%s model=%s context_window=%d base_url=%s",
                  self.provider, self.model, self.context_window, base_url)

    # ------------------------------------------------------------------ #
    # Plain completion (used for Planner's structured plan, Critic report)
    # ------------------------------------------------------------------ #
    def complete_json(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: int = 2000,
        agent_name: str = "",
        trace_writer: Any = None,
        trace_meta: dict | None = None,
    ) -> dict:
        capped = self._cap_max_tokens(messages, max_tokens)

        for m in messages:
            log.debug("[%s] >>> %s: %s", agent_name or "llm", m.get("role"), m.get("content", ""))
        if trace_writer:
            trace_writer.write({"kind": "call_input", "agent": agent_name, "mode": "json",
                                 "messages": messages, **(trace_meta or {})})

        resp = self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=temperature,
            max_tokens=capped, response_format={"type": "json_object"},
            extra_body=self._extra_body,
        )
        raw = resp.choices[0].message.content or "{}"
        log.debug("[%s] <<< raw output: %s", agent_name or "llm", raw)
        if trace_writer:
            trace_writer.write({"kind": "call_output", "agent": agent_name, "mode": "json",
                                 "raw": raw, **(trace_meta or {})})

        parsed = self._parse_json(raw)
        preview = json.dumps(parsed)
        log.info("[%s] output: %s", agent_name or "llm",
                  preview[:300] + ("…" if len(preview) > 300 else ""))
        return parsed

    # ------------------------------------------------------------------ #
    # Agentic tool-calling loop
    # ------------------------------------------------------------------ #
    def run_agent_loop(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict],
        dispatch: "callable",
        max_steps: int = 12,
        temperature: float = 0.1,
        agent_name: str = "",
        trace_writer: Any = None,
        trace_meta: dict | None = None,
    ) -> list[dict]:
        """
        Runs a ReAct-style tool-calling loop until the model stops requesting
        tools (or `max_steps` is hit). Returns the full transcript.

        `dispatch(name, args) -> str` executes a tool call and returns a
        string result that gets fed back to the model as a tool message.
        The model — not this loop — decides which tools to call, in what
        order, how many times, and when it has done enough.

        Every prompt, model turn, and tool call/result is logged (DEBUG for
        full content, INFO for a one-line summary) and, if `trace_writer` is
        given, written to the JSONL trace file for later inspection.
        """
        meta = trace_meta or {}
        tag = f"[{agent_name or 'agent'}" + (f"/{meta.get('task_id')}" if meta.get("task_id") else "") + "]"

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        transcript: list[dict[str, Any]] = list(messages)

        log.debug("%s >>> system: %s", tag, system_prompt)
        log.debug("%s >>> user: %s", tag, user_prompt)
        log.info("%s starting (max_steps=%d)", tag, max_steps)
        if trace_writer:
            trace_writer.write({"kind": "agent_start", "agent": agent_name,
                                 "system_prompt": system_prompt, "user_prompt": user_prompt, **meta})

        for step in range(1, max_steps + 1):
            capped = self._cap_max_tokens(messages, 1200, tools=tools)
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=temperature,
                max_tokens=capped,
                extra_body=self._extra_body,
            )
            choice = resp.choices[0]
            msg = choice.message
            tool_calls_dump = [tc.model_dump() for tc in (msg.tool_calls or [])]
            content_for_history = msg.content or ""

            if not tool_calls_dump and msg.content:
                parsed_calls, leftover = _extract_custom_tool_calls(msg.content)
                if parsed_calls:
                    log.info("%s step %d: recovered %d tool call(s) from non-standard content "
                              "(vLLM tool-call parser didn't recognize this model's format)",
                              tag, step, len(parsed_calls))
                    tool_calls_dump = [
                        {"id": f"call_{step}_{idx}", "type": "function",
                         "function": {"name": name, "arguments": json.dumps(args)}}
                        for idx, (name, args) in enumerate(parsed_calls)
                    ]
                    content_for_history = leftover

            assistant_entry = {"role": "assistant", "content": content_for_history, "tool_calls": tool_calls_dump}
            messages.append({"role": "assistant", "content": content_for_history, "tool_calls": tool_calls_dump or None})
            transcript.append(assistant_entry)

            log.debug("%s step %d <<< assistant content: %s", tag, step, msg.content or "(none)")
            if tool_calls_dump:
                log.info("%s step %d -> calling: %s", tag, step,
                          ", ".join(tc["function"]["name"] for tc in tool_calls_dump))
            else:
                log.info("%s step %d -> no tool call (stopping)", tag, step)
            if trace_writer:
                trace_writer.write({"kind": "assistant_turn", "agent": agent_name, "step": step,
                                     "content": msg.content or "", "tool_calls": tool_calls_dump, **meta})

            if not tool_calls_dump:
                log.debug("%s finished at step %d (no tool call)", tag, step)
                break

            for tc in tool_calls_dump:
                name = tc["function"]["name"]
                try:
                    args = json.loads(_strip_fences(tc["function"]["arguments"] or "{}"))
                except Exception:
                    args = self._parse_json(tc["function"]["arguments"] or "{}")

                log.debug("%s step %d tool_call name=%s args=%s", tag, step, name, args)
                try:
                    result = dispatch(name, args)
                except Exception as exc:  # tool errors are fed back, not fatal
                    result = f"ERROR: {exc}"
                    log.warning("%s tool '%s' raised: %s", tag, name, exc)

                result_preview = str(result)[:300] + ("…" if len(str(result)) > 300 else "")
                log.info("%s step %d tool=%s -> %s", tag, step, name, result_preview)
                if trace_writer:
                    trace_writer.write({"kind": "tool_call", "agent": agent_name, "step": step,
                                         "tool": name, "args": args, "result": str(result), **meta})

                tool_msg = {"role": "tool", "tool_call_id": tc["id"], "content": str(result)[:4000]}
                messages.append(tool_msg)
                transcript.append(tool_msg)

                if name in ("finish_task", "finish", "approve"):
                    log.info("%s completed via '%s'", tag, name)
                    if trace_writer:
                        trace_writer.write({"kind": "agent_end", "agent": agent_name,
                                             "reason": name, "steps": step, **meta})
                    return transcript
        else:
            log.warning("%s hit max_steps=%d without finishing", tag, max_steps)
            if trace_writer:
                trace_writer.write({"kind": "agent_end", "agent": agent_name,
                                     "reason": "max_steps_exhausted", "steps": max_steps, **meta})

        return transcript

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _cap_max_tokens(self, messages: list[dict[str, Any]], requested: int,
                        tools: list[dict] | None = None) -> int:
        input_chars = sum(len(str(m.get("content", ""))) for m in messages)
        if tools:
            # Tool schemas are re-sent (and re-rendered into the prompt by the chat
            # template) on every step of the loop but live outside `messages`, so they
            # must be counted here too or this estimate silently undershoots.
            input_chars += len(json.dumps(tools))
        input_tokens_est = int(input_chars / _CHARS_PER_TOKEN) + _TOKEN_SAFETY_BUFFER
        available = self.context_window - input_tokens_est
        capped = max(_MIN_OUTPUT_TOKENS, min(requested, available))
        if capped < requested:
            log.debug("max_tokens capped %d -> %d (input_est=%d, window=%d)",
                       requested, capped, input_tokens_est, self.context_window)
        return capped

    def _parse_json(self, raw: str) -> dict:
        cleaned = _strip_fences(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            try:
                return json.loads(repair_json(cleaned))
            except Exception as exc:
                log.error("JSON parse failed: %s | snippet=%r", exc, raw[:200])
                return {}
