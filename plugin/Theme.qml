pragma Singleton
import QtQuick

// One ramp for the whole widget. No hue anywhere: state is carried by
// luminance and by the glyph, never by colour, so the panel, the card and
// the dashboard all read as the same surface.
QtObject {
  // Base surfaces — darker than any previous build, never pure black.
  readonly property color bg0:  "#0a0b0d"   // deepest (overlay backdrop)
  readonly property color bg1:  "#101114"   // panel background
  readonly property color bg2:  "#16181c"   // card background
  readonly property color bg3:  "#1d2025"   // hover / raised
  readonly property color line: "#25292f"   // borders, dividers

  // Foreground ramp.
  readonly property color fg0:  "#f2f4f7"   // primary text
  readonly property color fg1:  "#c3c8d0"   // secondary text
  readonly property color fg2:  "#8b919b"   // muted / labels
  readonly property color fg3:  "#5a6068"   // disabled / hints

  // The single accent — a cold off-white. Active state only.
  readonly property color accent:   "#e6e8ec"
  readonly property color accentDim: "#9aa0a8"

  // State by luminance, paired with a glyph so it never reads ambiguous.
  readonly property color stateOk:   "#c3c8d0"   // all done
  readonly property color stateDue:  "#f2f4f7"   // due now (brightest)
  readonly property color stateLate: "#8b919b"   // overdue (dimmer + icon)
  readonly property color stateIdle: "#5a6068"   // nothing due

  // Severity: brightest is worst. Danger keeps the surface monochrome and
  // says so with the heaviest border instead of red.
  readonly property color severe: stateDue
  readonly property color moderate: fg1
  readonly property color mild: fg2
  readonly property color danger: fg0
  readonly property color dangerDim: fg2

  // Surfaces as (colour, opacity) pairs, so callers can build Qt.rgba depth.
  readonly property color scrim: bg0
  readonly property real scrimOpacity: 0.82
  readonly property real panelOpacity: 0.96

  // One family, one weight, one size scale. No emoji anywhere.
  readonly property string glyphPill: "󰐂"
  readonly property string glyphTaken: "󰄬"
  readonly property string glyphDue: "󰅐"
  readonly property string glyphOverdue: "󰅙"
  readonly property string glyphSkipped: "󰜺"
  readonly property string glyphEmergency: "󰅻"
  readonly property string glyphRefill: "󰐽"
  readonly property string glyphSafety: "󰒃"
  readonly property string glyphHealth: "󰈸"
  readonly property string glyphReports: "󰈙"
  readonly property string glyphCard: "󰈞"
  readonly property string glyphDashboard: "󰒓"
  readonly property string glyphAdd: "󰐕"
  readonly property string glyphEdit: "󰏫"
  readonly property string glyphDelete: "󰆴"
  readonly property string glyphSettings: "󰒓"
  readonly property string glyphClose: "󰅖"
  readonly property string glyphChevron: "󰅂"
  readonly property string glyphHelp: "󰮯"
  readonly property string glyphSearch: "󰍫"
  readonly property string glyphChart: "󰈙"
  readonly property string glyphWarn: "󰀦"

  // Motion. Every duration here is short enough to feel instant and long
  // enough to read as a change of state.
  readonly property int fadePanel: 120
  readonly property int fadeView: 140
  readonly property int flashTake: 300
  readonly property int pulseDue: 400
  readonly property int breathe: 2000
  readonly property int shimmer: 900
  readonly property int countUp: 300
  readonly property int tooltipDelay: 450

  function at(opacity) { return Qt.rgba(bg0.r, bg0.g, bg0.b, opacity) }
  function mix(over, under, alpha) {
    return Qt.rgba(over.r * alpha + under.r * (1 - alpha),
                   over.g * alpha + under.g * (1 - alpha),
                   over.b * alpha + under.b * (1 - alpha), 1)
  }
  function alpha(color, value) {
    return Qt.rgba(color.r, color.g, color.b, value)
  }
  // Contrast helper: two grays that still separate at small sizes.
  function onSurface(color) {
    return color === fg0 || color === accent || color === stateDue
  }
}
