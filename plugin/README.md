# MedKit bar widget (Omarchy plugin)

A small Omarchy shell bar widget for **MedKit**, the medication tracker: a
colored status dot plus the next dose time, today's progress, and a low-stock
warning.

- **Left / right click** — open the MedKit dashboard; click again to close it.
- **Hover** — tooltip with next dose, doses taken, and low-stock count.
- The dot is green (all done), amber (a dose is due / stock low), red
  (overdue or emergency supply low), gray (nothing due yet).
- Refreshes every 30 seconds, and on bar IPC `refresh`.

The tracker itself lives in [`hshindys/medkit`](https://github.com/hshindys/medkit)
(GTK3 tray + dashboard, reminders, emergency medicines, systemd units).

## Requirements

- [MedKit](https://github.com/hshindys/medkit) checked out at `~/medkit`
  (`bin/medkit` provides `--plugin-status` and `--dashboard-toggle`).
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
| `MedKitBar.qml` | the bar widget |
| `LICENSE` | MIT |

## Versioning

Bump `version` in `manifest.json` on every change so users get the update
through `omarchy plugin update hshindys.medkit`.
