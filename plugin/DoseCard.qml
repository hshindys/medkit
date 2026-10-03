import QtQuick
import qs.Commons
import qs.Ui

// One dose of one medicine. The card is monochrome: the surface is `bg2`,
// the border `line`, and the *state* is carried by a 3px bar on the left
// edge plus its glyph — brightest when the dose is due, mid when it is
// late, dim when nothing is expected of it.
//
// `dose` is the shape `medkit --plugin-panel` emits. Actions go back through
// the host bar widget, which runs the CLI and refreshes. Drag the card
// right to take it, left to skip it.
BorderSurface {
  id: root

  property var dose: ({})
  property var host: null
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family
  property bool selected: false

  // Set while the card is reacting to its own action: the border flashes
  // accent and the glyph flips to the check before the payload catches up.
  property bool flashing: false
  property real swipeX: 0

  readonly property color tint: root.dose.color ? String(root.dose.color) : Theme.accentDim
  readonly property color stateTint: root.dose.stateColor ? String(root.dose.stateColor) : Theme.fg3
  readonly property bool done: root.dose.state === "taken"
  readonly property bool late: root.dose.state === "overdue"
  readonly property bool skipped: root.dose.state === "skipped"
  readonly property bool hot: hover.hovered

  // Left edge: bright for due, mid for late, dim for idle.
  readonly property color edge: {
    if (root.flashing || root.done) return Theme.stateOk
    if (root.late) return Theme.stateLate
    if (root.dose.state === "due") return Theme.stateDue
    return Theme.stateIdle
  }

  readonly property string stateGlyph: {
    if (root.flashing || root.done) return Theme.glyphTaken
    if (root.late) return Theme.glyphOverdue
    if (root.skipped) return Theme.glyphSkipped
    if (root.dose.state === "due") return Theme.glyphDue
    return Theme.glyphPill
  }

  implicitHeight: Style.space(72)
  height: implicitHeight
  radius: Style.cornerRadius
  x: root.swipeX

  color: root.selected ? Theme.bg3 : (root.hot ? Theme.bg3 : Theme.bg2)
  borderSpec: Border.flat(
    root.flashing ? Theme.accent
      : root.selected ? Theme.accent
      : root.hot ? Theme.accentDim
      : Theme.line,
    Math.max(1, root.selected || root.flashing ? 2 : Style.normalBorderWidth)
  )

  Behavior on color { ColorAnimation { duration: 120 } }
  Behavior on swipeX {
    enabled: !swipeArea.pressed
    NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
  }

  function flash() {
    root.flashing = true
    flashTimer.restart()
  }

  function settleSwipe() {
    if (root.swipeX > 60) {
      root.flash()
      if (root.host) root.host.take(root.dose.name)
    } else if (root.swipeX < -60) {
      if (root.host) root.host.skip(root.dose.name)
    }
    root.swipeX = 0
  }

  Timer {
    id: flashTimer
    interval: Theme.flashTake
    onTriggered: root.flashing = false
  }

  function detail() {
    var parts = []
    if (root.dose.dose) parts.push(root.dose.dose)
    if (root.dose.days > 0) parts.push(root.dose.days + "-day course")
    else if (root.dose.category === "emergency") parts.push("ongoing")
    if (root.dose.notes) parts.push(root.dose.notes)
    if (root.dose.stock !== null && root.dose.stock !== undefined)
      parts.push(root.dose.stock + " left")
    if (root.late && root.dose.overdueMin > 0)
      parts.push(root.dose.overdueMin + " min late")
    return parts.join("  ·  ")
  }

  // Swipe surface. Declared under the buttons so a tap on Take still lands
  // on Take, and so a vertical drag falls through to the panel's Flickable.
  MouseArea {
    id: swipeArea
    anchors.fill: parent
    property real startX: 0
    property real origin: 0
    onPressed: function(mouse) {
      root.swipeX = 0
      startX = mouse.x
      origin = root.swipeX
    }
    onPositionChanged: {
      if (!pressed) return
      var dx = mouse.x - startX
      if (Math.abs(dx) < 10) return
      root.swipeX = Math.max(-140, Math.min(140, origin + dx))
    }
    onReleased: root.settleSwipe()
    onCanceled: root.swipeX = 0
  }

  // The hint revealed while you are dragging.
  Text {
    anchors.right: parent.right
    anchors.rightMargin: Style.space(16)
    anchors.verticalCenter: parent.verticalCenter
    textFormat: Text.PlainText
    text: Theme.glyphTaken + "  take"
    visible: root.swipeX > 14
    opacity: Math.min(1, Math.max(0, (root.swipeX - 14) / 60))
    color: Theme.fg0
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
    font.bold: true
  }

  Text {
    anchors.left: parent.left
    anchors.leftMargin: Style.space(60)
    anchors.verticalCenter: parent.verticalCenter
    textFormat: Text.PlainText
    text: Theme.glyphSkipped + "  skip"
    visible: root.swipeX < -14
    opacity: Math.min(1, Math.max(0, (-root.swipeX - 14) / 60))
    color: Theme.fg2
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
    font.bold: true
  }

  Rectangle {
    anchors.left: parent.left
    anchors.verticalCenter: parent.verticalCenter
    width: Style.space(3)
    height: parent.height - Style.space(20)
    radius: width / 2
    color: root.edge

    Behavior on color { ColorAnimation { duration: 140 } }
  }

  PillIcon {
    id: pill
    anchors.left: parent.left
    anchors.leftMargin: Style.space(14)
    anchors.verticalCenter: parent.verticalCenter
    size: Style.space(40)
    path: root.dose.icon || ""
    tint: root.stateTint
    glyph: root.stateGlyph
    fontFamily: root.fontFamily
  }

  Row {
    id: chips
    anchors.right: parent.right
    anchors.rightMargin: Style.space(14)
    anchors.top: parent.top
    anchors.topMargin: Style.space(12)
    spacing: Style.space(6)

    ChipButton {
      text: root.dose.clock || ""
      tint: Theme.fg2
      fontFamily: root.fontFamily
      clickable: false
      tooltip: "Scheduled time"
    }

    ChipButton {
      visible: root.dose.low === true || root.dose.out === true
      text: (root.dose.out ? "OUT" : (root.dose.stock + " left"))
      tint: root.dose.out ? Theme.danger : Theme.fg1
      filled: root.dose.out === true
      fontFamily: root.fontFamily
      clickable: false
      tooltip: "Pills left in this box"
    }

    ChipButton {
      text: root.stateGlyph + " " + (root.dose.stateLabel || "")
      tint: root.stateTint
      filled: root.done || root.late
      fontFamily: root.fontFamily
      clickable: false
      tooltip: "State of this dose"
    }
  }

  Text {
    id: name
    anchors.left: pill.right
    anchors.leftMargin: Style.space(10)
    anchors.right: chips.left
    anchors.rightMargin: Style.space(8)
    anchors.top: parent.top
    anchors.topMargin: Style.space(11)
    textFormat: Text.PlainText
    text: root.dose.name || ""
    elide: Text.ElideRight
    color: root.done ? Theme.fg2 : Theme.fg0
    font.family: root.fontFamily
    font.pixelSize: Style.font.subtitle
    font.bold: true
  }

  Text {
    id: sub
    anchors.left: pill.right
    anchors.leftMargin: Style.space(10)
    anchors.right: actions.left
    anchors.rightMargin: Style.space(10)
    anchors.top: name.bottom
    anchors.topMargin: Style.space(3)
    textFormat: Text.PlainText
    text: root.detail()
    elide: Text.ElideRight
    color: root.late ? Theme.fg1 : Theme.fg3
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
  }

  Row {
    id: actions
    anchors.right: parent.right
    anchors.rightMargin: Style.space(14)
    anchors.bottom: parent.bottom
    anchors.bottomMargin: Style.space(11)
    spacing: Style.space(6)

    Text {
      visible: root.done || root.skipped
      anchors.verticalCenter: parent.verticalCenter
      textFormat: Text.PlainText
      text: (root.skipped ? "skipped" : "taken") + (root.dose.takenAt ? " " + root.dose.takenAt : "")
      color: root.skipped ? Theme.fg3 : Theme.stateOk
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      font.bold: true
    }

    ChipButton {
      visible: !root.done
      text: "Take"
      filled: true
      fontFamily: root.fontFamily
      tooltip: "Mark this dose as taken"
      onClicked: {
        root.flash()
        if (root.host) root.host.take(root.dose.name)
      }
    }

    ChipButton {
      visible: !root.done
      text: "Skip"
      fontFamily: root.fontFamily
      tooltip: "Skip this dose"
      onClicked: if (root.host) root.host.skip(root.dose.name)
    }

    // Beside every dose: the same edit form the dashboard's Edit button
    // opens — time, medicine, and course days when it is an emergency.
    ChipButton {
      text: Theme.glyphEdit + " Edit"
      fontFamily: root.fontFamily
      tooltip: "Edit this medicine"
      onClicked: if (root.host) root.host.editMedicine(root.dose.name)
    }

    // Beside every dose: hands the dashboard the delete confirmation for
    // this medicine (it always asks before dropping anything).
    ChipButton {
      text: Theme.glyphDelete + " Delete"
      fontFamily: root.fontFamily
      tooltip: "Delete this medicine"
      onClicked: if (root.host) root.host.deleteMedicine(root.dose.name)
    }
  }

  HoverHandler {
    id: hover
  }
}
