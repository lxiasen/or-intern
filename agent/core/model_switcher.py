"""Model-switching logic for the interactive CLI's ``/model`` command.

Exposes:
* ``probe_and_switch_model`` — async: fires a 1-token probe to validate
  the model and resolve the effort cascade, then commits the switch
  (or rejects it on hard error).

The probe's cascade lives in ``agent.core.effort_probe``; this module
glues it to CLI output + session state.
"""

from __future__ import annotations

import asyncio

from litellm import acompletion

from agent.core.effort_probe import ProbeInconclusive, probe_effort
from agent.core.llm_params import _resolve_llm_params
from agent.core.local_models import is_local_model_id

_LOCAL_PROBE_TIMEOUT = 15.0


async def _probe_local_model(model_id: str) -> None:
    params = _resolve_llm_params(model_id)
    await asyncio.wait_for(
        acompletion(
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            stream=False,
            **params,
        ),
        timeout=_LOCAL_PROBE_TIMEOUT,
    )


async def probe_and_switch_model(
    model_index: int,
    config,
    session,
    console,
) -> None:
    """Validate model+effort with a 1-token ping, cache the effective effort,
    then commit the switch.

    Three visible outcomes:

    * ✓ ``effort: <level>`` — model accepted the preferred effort (or a
      fallback from the cascade; the note explains if so)
    * ✓ ``effort: off`` — model doesn't support thinking; we'll strip it
    * ✗ hard error (auth, model-not-found, quota) — we reject the switch
      and keep the current model so the user isn't stranded

    For non-local models, transient errors (5xx, timeout) complete the switch
    with a yellow warning; the next real call re-surfaces the error if it's
    persistent. Local models reject every probe error, including timeouts, and
    keep the current model.
    """
    if model_index < 0 or model_index >= len(config.models):
        console.print(f"[bold red]Invalid model index:[/bold red] {model_index + 1}")
        return

    prev_index = config.active_model_index
    target = config.models[model_index]
    model_id = target.name

    if is_local_model_id(model_id):
        console.print(f"[dim]checking local model {model_id}...[/dim]")
        try:
            await _probe_local_model(model_id)
        except Exception as e:
            console.print(f"[bold red]Switch failed:[/bold red] {e}")
            console.print(
                f"[dim]Keeping current model: {config.current_model.name}[/dim]"
            )
            return

        _commit_switch(model_index, config, session, effective=None, cache=True)
        label = target.display_name or model_id
        console.print(
            f"[green]Switched to [{model_index + 1}] {label}[/green] "
            f"[dim](effort: off)[/dim]"
        )
        return

    preference = target.reasoning_effort

    if not preference:
        _commit_switch(model_index, config, session, effective=None, cache=False)
        label = target.display_name or model_id
        console.print(
            f"[green]Switched to [{model_index + 1}] {label}[/green] "
            f"[dim](effort: off)[/dim]"
        )
        return

    console.print(f"[dim]checking {model_id} (effort: {preference})...[/dim]")
    try:
        outcome = await probe_effort(
            model_id, preference, getattr(session, "hf_token", None), session=session,
            api_key=target.api_key, api_base=target.api_base,
        )
    except ProbeInconclusive as e:
        _commit_switch(model_index, config, session, effective=None, cache=False)
        label = target.display_name or model_id
        console.print(
            f"[yellow]Switched to [{model_index + 1}] {label}[/yellow] "
            f"[dim](couldn't validate: {e}; will verify on first message)[/dim]"
        )
        return
    except Exception as e:
        console.print(f"[bold red]Switch failed:[/bold red] {e}")
        console.print(
            f"[dim]Keeping current model: {config.current_model.name}[/dim]"
        )
        return

    _commit_switch(
        model_index,
        config,
        session,
        effective=outcome.effective_effort,
        cache=True,
    )
    label = target.display_name or model_id
    effort_label = outcome.effective_effort or "off"
    suffix = f" — {outcome.note}" if outcome.note else ""
    console.print(
        f"[green]Switched to [{model_index + 1}] {label}[/green] "
        f"[dim](effort: {effort_label}{suffix}, {outcome.elapsed_ms}ms)[/dim]"
    )


def _commit_switch(model_index, config, session, effective, cache: bool) -> None:
    """Apply the switch to the session (or bare config if no session yet).

    ``effective`` is the probe's resolved effort; ``cache=True`` stores it
    in the session's per-model cache so real calls use the resolved level
    instead of re-probing. ``cache=False`` (inconclusive probe / effort
    off) leaves the cache untouched — next call falls back to preference.
    """
    model_name = config.models[model_index].name

    if session is not None:
        session.update_model(model_index)
        if cache:
            session.model_effective_effort[model_name] = effective
        else:
            session.model_effective_effort.pop(model_name, None)
    else:
        config.active_model_index = model_index
