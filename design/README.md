# Design source

Imported from the Claude Design project **Aplicativo de aprendizado personalizado**
(`401570ba-3b33-4923-ba3f-8f40573c403d`) with the `claude_design` MCP.

## Contents

| Path | What it is |
| --- | --- |
| `Notter Estudos.dc.html` | The design canvas — eight screens as one `<x-dc>` template with `{{ }}` bindings, `sc-for` / `sc-if` directives, and a `DCLogic` component holding the state and fixture data. |
| `support.js` | The `dc-runtime` bundle the canvas needs to render standalone. Generated; do not edit. |
| `_ds/nocturne-…/styles.css` | The Nocturne token sheet and component layer. The one stylesheet the design links. |
| `_ds/nocturne-…/readme.md` | The Nocturne guide: direction, color, type, components, do and don't. |
| `_ds/nocturne-…/_ds_bundle.js` | The design-system JS bundle. Empty — Nocturne ships no components, only CSS. |

Not imported: `uploads/` (reference screenshots) and `.thumbnail`, neither of
which the canvas references.

## Relationship to the implementation

`frontend/` is the implementation of `Notter Estudos.dc.html`. The mapping:

| Canvas | Implementation |
| --- | --- |
| `<sc-if value="{{ isHome }}">` … one branch per screen | `frontend/src/pages/*.tsx`, switched in `src/App.tsx` |
| `class Component extends DCLogic` — `state` + `renderVals()` | `src/hooks/appState.ts` (reducer) and `src/hooks/useAppState.tsx` (context) |
| Module-level fixture arrays (`FASES`, `BIBLIOTECA`, `QUIZ`, `IDIOMAS`, …) | `src/api/*.ts`, typed against `src/types` |
| Inline `dangerouslySetInnerHTML` SVG strings (`I.home`, …) | `src/components/ui/icons.tsx`, as real elements |
| Colour and geometry literals repeated inline | `src/lib/tokens.ts`, plus `src/styles/nocturne.css` (a copy of the sheet above) |
| Arithmetic inlined in `renderVals()` (heatmap, month grid, sparklines, filters) | `src/lib/dashboard.ts`, `src/lib/library.ts`, `src/lib/language.ts`, `src/lib/highlight.ts` — pure and unit-tested |

Re-import with `DesignSync` (`get_file`) if the canvas changes upstream. The
canvas is the source of truth for layout and copy; `frontend/` is the source of
truth for behaviour.
