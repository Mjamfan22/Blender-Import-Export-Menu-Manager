# Changelog

## 1.1.2 — 2026-10-26

- Collapsed every entry into one compact row containing its dotted drag handle,
  visibility toggle, readable label, operator ID, group, and arrow controls.
- Updated drag distance tracking for the new single-row entry height.
- Added public project, maintainer, and support metadata for the GitHub release.

## 1.1.1 — 2026-10-26

- Replaced click-to-grab reordering with dotted press-and-hold handles for
  entries and groups.
- Reordering now follows vertical mouse movement and commits when the mouse is
  released, allowing long-distance moves in a single gesture with no typing.
- Fixed mouse-release handling so repeated drags work reliably.
- Kept search-safe reordering and the existing one-step arrow controls.

## 1.1.0 — 2026-10-26

- Added modal grip reordering for entries and groups.
- Added accelerated Shift movement plus wheel, arrow, Page, Home, and End
  controls while placing an item.
- Added lossless cancellation that restores the exact pre-move ordering state.
- Kept the existing one-step arrow controls as an accessible fallback.

## 1.0.1 — 2026-10-25

- Kept dynamic group-enum strings alive for Blender RNA safety.
- Expanded `operator_enum` callbacks into individually configurable entries.
- Added visible diagnostics for unsupported third-party menu layout calls.
- Hardened preference, specialty-add-on, and UI regression testing.

## 1.0.0 — 2026-10-25

- Initial Blender 5.2 LTS release.
- Independent Import and Export entry visibility, labels, grouping, and order.
- Automatic discovery of menu callbacks from newly registered format add-ons.
- Non-destructive callback interception and exact normal-menu restoration.
