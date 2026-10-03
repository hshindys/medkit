from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from . import actions


class Wizard(Gtk.Window):
    def __init__(
        self,
        parent: Gtk.Window | None = None,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(title="MedKit — count your pills")
        self.set_default_size(520, 520)
        self.set_border_width(16)
        if parent is not None:
            self.set_transient_for(parent)
        self.on_done = on_done
        self.entries: dict[str, Gtk.Entry] = {}

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.pack_start(
            Gtk.Label(
                label="Enter the real number of pills you have for each medicine.\n"
                "Reminders stay disabled until every count is filled in.",
                xalign=0,
            ),
            False,
            False,
            0,
        )

        document, _, _ = actions.snapshot()
        grid = Gtk.Grid(column_spacing=10, row_spacing=8)
        for index, medicine in enumerate(document.medicines):
            detail = ", ".join(medicine.times)
            if medicine.dose:
                detail = f"{medicine.dose} · {detail}"
            grid.attach(Gtk.Label(label=medicine.name, xalign=0), 0, index, 1, 1)
            grid.attach(Gtk.Label(label=detail, xalign=0), 1, index, 1, 1)
            entry = Gtk.Entry()
            entry.set_width_chars(6)
            entry.set_placeholder_text("pills")
            entry.connect("changed", self._on_changed)
            self.entries[medicine.name] = entry
            grid.attach(entry, 2, index, 1, 1)
        box.pack_start(grid, False, False, 0)

        self.error_label = Gtk.Label(label="", xalign=0)
        self.error_label.set_markup('<span foreground="#f2f4f7"></span>')
        box.pack_start(self.error_label, False, False, 0)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        later = Gtk.Button(label="Later")
        later.connect("clicked", lambda *_: self.close())
        buttons.pack_end(later, False, False, 0)
        self.save_button = Gtk.Button(label="Save counts and enable reminders")
        self.save_button.connect("clicked", self._on_save)
        self.save_button.set_sensitive(False)
        buttons.pack_end(self.save_button, False, False, 0)
        box.pack_start(buttons, False, False, 0)

        self.add(box)
        self.show_all()

    def _on_changed(self, _entry: Gtk.Entry) -> None:
        ready = all(
            entry.get_text().strip().isdigit() for entry in self.entries.values()
        )
        self.save_button.set_sensitive(ready)

    def _on_save(self, _button: Gtk.Button) -> None:
        counts = {
            name: int(entry.get_text().strip())
            for name, entry in self.entries.items()
        }
        try:
            message = actions.complete_setup(counts)
        except actions.ActionError as error:
            self.error_label.set_markup(
                f'<span foreground="#f2f4f7">{error}</span>'
            )
            return
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="MedKit is live",
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()
        self.close()
        if self.on_done is not None:
            self.on_done()
