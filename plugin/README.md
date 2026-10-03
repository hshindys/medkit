# MedKit bar widget (Omarchy plugin)

A small Omarchy shell bar widget for **MedKit**, the medication tracker: a
colored status dot plus the next dose time, today's progress, and a low-stock
warning.

- **Left / right click** — open the MedKit panel; click again to close it.
- The panel switches between five views: **doses**, **safety** (drug
  interactions, food/meal timing, pregnancy, missed-dose protocol), **health**
  (adherence, vitals correlation, side effects, refills), **reports** (therapy
  review, weekly/monthly reports) and **card** (the emergency card).
- **Keys** — `1`–`4` jump to a dose tab, `5`–`8` jump to a view (safety,
  health, reports, card), `t` take the next dose, `r` refresh, `e` dashboard,
  `a` add a medicine, `f` refill, `c` open the fullscreen emergency card
  (`Esc`, `q` or `c` closes it again).
- **Emergency card** — a fullscreen overlay (blood type, allergies,
  conditions, contacts, medicines, emergency numbers) that works **fully
  offline**; also exportable as text/PDF through the CLI.
- **Edit** on a dose card (or a low-stock row) opens the dashboard straight on
  that medicine's edit form — time, dose, and course days when it is an
  emergency.
- **Delete** on a dose card (or a low-stock row) opens the dashboard on that
  medicine's confirmation dialog — the panel never deletes on its own.
- **Hover** — tooltip with next dose, doses taken, and low-stock count.
- The dot is green (all done), amber (a dose is due / stock low), red
  (overdue or emergency supply low), gray (nothing due yet).
- Refreshes every 30 seconds, and on bar IPC `refresh`.

IPC (from `omarchy-shell -q ipc`):

| Function | Effect |
|---|---|
| `medicalCard()` | open the emergency-card overlay |
| `closeCard()` | close it |
| `card()` | toggle it |

Every answer on the safety/health views and on the card ends with
*This is not medical advice.* The knowledge base is bundled and offline — no
network call is made.

The tracker itself lives in [`hshindys/medkit`](https://github.com/hshindys/medkit)
(GTK3 tray + dashboard, reminders, emergency medicines, systemd units).

## Requirements

- [MedKit](https://github.com/hshindys/medkit) checked out at `~/medkit`
  (`bin/medkit` provides `--plugin-panel`, `--take`, `--skip`, `--refill`,
  `--add-medicine`, `--edit`, `--delete`, `--notify-due`,
  `--dashboard-toggle`, `--headless-test`, `--emergency-export`,
  `--emergency-call`, `--review-export` and `--review-done`).
- Omarchy shell (Quickshell bar).

```sh
git clone https://github.com/hshindys/medkit.git ~/medkit
~/medkit/bin/medkit-install-systemd   # reminders + daily summary
```

If MedKit lives elsewhere, set `bin` in the widget's shell.json layout entry:

```json
{ "id": "hshindys.medkit", "bin": "/path/to/medkit/bin/medkit" }
```

## Install

```sh
omarchy plugin add https://github.com/hshindys/omarchy-medkit.git --enable
```

From a local checkout of this folder:

```sh
omarchy plugin validate .
cp -r . ~/.config/omarchy/plugins/hshindys.medkit
omarchy-shell shell rescanPlugins
omarchy plugin enable hshindys.medkit --section right
```

Manage it with:

```sh
omarchy plugin list
omarchy plugin update hshindys.medkit
omarchy plugin disable hshindys.medkit
```

## Remove

```sh
omarchy plugin remove hshindys.medkit
```

This deletes the git checkout under `~/.config/omarchy/plugins/` and unloads
the widget from the bar. It touches nothing else — MedKit itself, its data
(`~/.local/share/medkit/`) and its systemd units stay installed.

## Files

| File | Purpose |
|---|---|
| `manifest.json` | Omarchy plugin manifest (id `hshindys.medkit`) |
| `MedKitBar.qml` | the bar widget: data, actions, IPC, panel + overlay host |
| `Panel.qml` | the click-open panel (view switcher, doses, safety, health, reports, card) |
| `views/Block.qml` | the card container every view section uses |
| `views/ViewSwitcher.qml` | the segmented view switcher with badges |
| `views/SafetyView.qml` | interactions, food, pregnancy, missed dose |
| `views/HealthView.qml` | adherence, vitals correlation, side effects, refills |
| `views/ReportsView.qml` | therapy review, weekly / monthly reports |
| `views/CardView.qml` | the emergency card (also rendered fullscreen) |
| `EmergencyOverlay.qml` | the fullscreen, offline emergency card |
| `DoseCard.qml` | one dose: Take · Skip · Edit |
| `ChipButton.qml` | the tinted pill button every action uses |
| `PillIcon.qml` | the medicine's own pill glyph |
| `LICENSE` | MIT |

Editing these locally: the shell logs `Local plugin changed, reloading`, but a
widget that still shows the old code needs `omarchy restart shell` (the shell
ships with `QS_DISABLE_FILE_WATCHER=1`, so a reload can leave the old engine
generation in place).

## Versioning

Bump `version` in `manifest.json` on every change so users get the update
through `omarchy plugin update hshindys.medkit`.
