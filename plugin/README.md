# MedKit bar widget (Omarchy plugin)

A small Omarchy shell bar widget for **MedKit**, the medication tracker: a
colored status dot plus the next dose time, today's progress, and a low-stock
warning.

- **Left / right click** — open the MedKit dashboard; click again to close it.
- **Edit** on a dose card (or a low-stock row) opens the dashboard straight on
  that medicine's edit form — time, dose, and course days when it is an
  emergency.
- **Delete** on a dose card (or a low-stock row) opens the dashboard on that
  medicine's confirmation dialog — the panel never deletes on its own.
- **Hover** — tooltip with next dose, doses taken, and low-stock count.
- The dot is green (all done), amber (a dose is due / stock low), red
  (overdue or emergency supply low), gray (nothing due yet).
- Refreshes every 30 seconds, and on bar IPC `refresh`.

The tracker itself lives in [`hshindys/medkit`](https://github.com/hshindys/medkit)
(GTK3 tray + dashboard, reminders, emergency medicines, systemd units).

## Requirements

- [MedKit](https://github.com/hshindys/medkit) checked out at `~/medkit`
  (`bin/medkit` provides `--plugin-panel`, `--take`, `--skip`, `--refill`,
  `--add-medicine`, `--edit`, `--delete`, `--notify-due` and `--dashboard-toggle`).
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
| `MedKitBar.qml` | the bar widget: data, actions, panel host |
| `Panel.qml` | the click-open dose panel (tabs, doses, low stock, footer) |
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
