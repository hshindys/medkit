# MedKit

A medication tracker for Omarchy (Hyprland / Wayland) with a **real system tray
icon**, a GTK dashboard, systemd-driven reminders and a daily summary appended
to the health vault.

**Tray mode: real StatusNotifier / AppIndicator tray icon** (GTK3 +
`libayatana-appindicator3`, host = quickshell). No layer-shell fallback was
needed — `/usr/lib/libayatana-appindicator3.so.1` is present on this machine.

---

## Run it

```bash
~/medkit/bin/medkit --gui        # tray icon + dashboard (default)
~/medkit/bin/medkit --dashboard  # open the dashboard (forwards to the running tray)
~/medkit/bin/medkit --wizard     # pill-count wizard
~/medkit/bin/medkit --status     # print today's status
~/medkit/bin/medkit --tick       # evaluate the schedule and notify (what the timer runs)
~/medkit/bin/medkit --tick --dry-run   # same, but send nothing
~/medkit/bin/medkit --vault-summary    # append today's summary to لوحة-الصحة.md
~/medkit/bin/medkit --take "Evening pill"     # mark the next dose as taken
~/medkit/bin/medkit --skip "Evening pill"     # mark the next dose as skipped
~/medkit/bin/medkit --set-count "Evening pill" 24
~/medkit/bin/medkit --edit "Evening pill"    # dashboard opens on that medicine's form
~/medkit/bin/medkit --delete "Evening pill"  # dashboard asks before dropping it
~/medkit/bin/medkit --test-notify       # fire one real notification
~/medkit/bin/medkit --headless-test     # logic self test (sandboxed)
~/medkit/bin/medkit-sni                 # prove the tray icon is registered on the bus
```

`python3 -m medkit` works too when run from `~/medkit/`.

### First launch

On first start the pill-count wizard opens. It asks for the **real** number of
pills you have for each medicine — nothing is guessed, `stock` stays `null`
until you answer. Reminders stay disabled until every count is filled in
(`wizard_done` in `medicines.json`). You can close it with **Later** and reopen
it with `~/medkit/bin/medkit --wizard`.

### Tray icon behaviour

| State | Icon |
|---|---|
| nothing due yet / setup pending | neutral |
| all of today's doses taken | green |
| a dose is due now (or overdue < 2 h) | amber |
| a dose overdue > 2 h, or an emergency medicine at/below `refill_at` | red |
| any medicine at/below `refill_at` | count badge drawn into the icon + tooltip `MedKit — N low on stock` |

* **Left-click** → dashboard (the host sends `StatusNotifierItem.Activate`,
  which the app handles).
* **Right-click** → menu: *Today's status* · *Mark dose taken* · *Manage
  medicines* · *Quit*.

Omarchy puts unpinned tray items in the collapsed drawer: hover the `<` chevron
at the right end of the bar, then right-click the chevron → *Tray icons* →
**Pin** to keep MedKit always visible.

---

## Add / edit / delete a medicine

GUI: tray → *Manage medicines* → `+` / edit / delete. Fields:

| Field | Meaning |
|---|---|
| `name` | Arabic or English |
| `dose` | e.g. `10 mg` |
| `times` | one or more `HH:MM`, comma separated (`09:00, 20:00`) |
| `stock` | pills left (empty = not counted yet) |
| `refill_at` | warn at or below this many pills (default `2`) |
| `notes` | e.g. `بعد الأكل، مش على معدة فاضية` |
| `category` | `normal` or `emergency` |
| `days` | course length in days (`0` = ongoing) |
| `active` | inactive medicines are not scheduled |
| `emergency_contacts` | shown with emergency alerts |

Every row carries its own **Edit** and **Delete** button — in *MEDICINES*,
beside each dose in *TODAY'S DOSES*, in the red EMERGENCY section, in the
**EMERGENCY** window, and in the bar panel. One form covers editing: name,
dose, times, stock, refill point, course days, notes, category and contacts —
and it carries **Delete** too, so an existing medicine can be dropped from the
form itself. Every delete asks *"Delete …? Its dose history stays in the log."*
first; nothing is ever removed silently.

Everything is plain JSON — edit `~/.local/share/medkit/medicines.json` if you
prefer.

CLI equivalents: `--set-count NAME N`, `--take NAME`, `--skip NAME`,
`--edit NAME` (opens the dashboard straight onto that medicine's form),
`--delete NAME` (opens the dashboard on that medicine's delete confirmation).

### Emergency medicines

Set `category` to `emergency`. They get: a red EMERGENCY section pinned at the
top of the dashboard, a one-click **EMERGENCY** button that opens the list with
`emergency_contacts`, red tray colour when at/below `refill_at`, and — at
`0` pills — a critical notification plus a timestamped line in
`~/.local/share/medkit/emergency.log`.

Quick add from that red section (or from the **EMERGENCY** window): only three
fields — medicine name, time (`HH:MM`, comma separated for several) and how
many days the course lasts (`0` = ongoing).

Every emergency row shows that course length (`for N days`, or `ongoing`) and
sits beside **Edit** and **Delete**, so the times, the medicine and the number
of days are all reachable — and the medicine removable — from the red section,
the **EMERGENCY** window or the bar panel, no trip through *MEDICINES* needed.

---

## systemd units (user level, no sudo)

Source of truth: `~/medkit/systemd/`. Install/refresh them with:

```bash
~/medkit/bin/medkit-install-systemd
```

which is equivalent to:

```bash
cp ~/medkit/systemd/* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now medkit-tick.timer medkit-vault.timer medkit-tray.service
```

| Unit | What it does |
|---|---|
| `medkit-tick.timer` | every 60 s (`OnUnitActiveSec=60s`, first run 20 s after boot) |
| `medkit-tick.service` | oneshot → `medkit --tick`, sends the notifications |
| `medkit-vault.timer` | daily `OnCalendar=*-*-* 21:30:00`, `Persistent=true` |
| `medkit-vault.service` | oneshot → `medkit --vault-summary` |
| `medkit-tray.service` | starts the tray with the session (`WantedBy=default.target`, `Restart=on-failure`) |

Useful commands:

```bash
systemctl --user list-timers | grep medkit
systemctl --user status medkit-tick.service
journalctl --user -u medkit-tick.service -n 20
systemctl --user restart medkit-tray.service
```

Notification rules implemented by the tick:

* first reminder at the scheduled time, then at +15 and +30 minutes — **3 max**
* `-u critical` escalation once, 60 minutes after the scheduled time
* restock alert at `stock <= refill_at`, at most once per day per medicine
  (also logged as `action: "restock"` in `history.jsonl`)
* emergency `0` pills → critical alert + `emergency.log` line
* every notification key is persisted in `state.json`, so a reboot, a restarted
  timer or a duplicate tick never re-sends anything

---

## Keybindings

Nothing under `~/.config/hypr/` was modified. If you want shortcuts, add these
yourself to `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + SHIFT + M", "MedKit dashboard", "~/medkit/bin/medkit --dashboard")
o.bind("SUPER + SHIFT + N", "MedKit status", "alacritty -e ~/medkit/bin/medkit --status")
```

---

## Bar widget (Omarchy plugin)

`plugin/` holds a Quickshell bar widget — status dot, next dose time, daily
progress and low-stock warnings; click toggles a dose panel (doses, low stock,
emergency) and each of its rows carries **Take** / **Skip** / **Edit** /
**Delete**, where **Edit** opens the dashboard straight on that medicine's form
(time, dose, and course days for emergencies) and **Delete** opens the
dashboard on its delete confirmation. It is published as its own repository:

```bash
omarchy plugin add https://github.com/hshindys/omarchy-medkit.git --enable
```

Validate a local copy with `omarchy plugin validate ./plugin`.

---

## Data files

| Path | Contents |
|---|---|
| `~/.local/share/medkit/medicines.json` | medicine database + `wizard_done` |
| `~/.local/share/medkit/history.jsonl` | one JSON object per line: `{"ts","medicine","action"}` with `action` ∈ `taken` / `skipped` / `restock` |
| `~/.local/share/medkit/state.json` | notification de-duplication keys |
| `~/.local/share/medkit/emergency.log` | timestamped out-of-stock lines |
| `~/.local/share/medkit/icons/` | generated colour + badge tray icons |
| `~/.config/systemd/user/medkit-*` | the units |
| `~/.config/medkit/config.json` | optional `{"vault_file": "/path/to/لوحة-الصحة.md"}` override |
| `~/Vaults/00-صحتي-والعناية/لوحة-الصحة.md` | the **only** vault file ever written (21:30 summary) |

The vault file is resolved from `$MEDKIT_VAULT_FILE`, then from
`~/.config/medkit/config.json`, then from that default — no personal path is
baked into the source. Nothing else on this machine is written to. No sudo is
used anywhere.

---

## Verify

```bash
~/medkit/bin/medkit --headless-test    # full logic self test in a sandbox
~/medkit/bin/medkit --test-notify      # prints the notification id
~/medkit/bin/medkit-sni                # StatusNotifier registry + item properties
systemctl --user list-timers | grep medkit
```

## Layout

```
~/medkit/
├── bin/medkit               single entry point (executable)
├── bin/medkit-sni           tray-icon proof script
├── bin/medkit-install-systemd
├── medkit/
│   ├── paths.py  models.py  store.py     data layer
│   ├── engine.py                          schedule, colours, adherence, streaks
│   ├── notify.py  tick.py                 notification planning + de-duplication
│   ├── actions.py                         mark taken / skipped, CRUD, counts
│   ├── vault.py                           21:30 health-vault summary
│   ├── render.py                           cairo tray icons (colour + badge)
│   ├── tray.py  dashboard.py  wizard.py   GTK3 UI
│   ├── selftest.py  cli.py                --headless-test, argument parsing
├── systemd/                             unit files
├── plugin/                              Omarchy bar widget (published as omarchy-medkit)
├── LICENSE                              MIT
└── README.md
```

Python 3.14 stdlib + PyGObject/GTK3/PyCairo already installed on this machine —
no venv and no third-party package is required.

## License

MIT — see [LICENSE](LICENSE).
