import QtQuick
import qs.Commons
import qs.Ui

// One dose of one medicine. The card is tinted by the medicine's own pill
// colour on the left edge and in the action buttons, so a morning list reads
// as a row of different medicines rather than one grey list repeated.
//
// `dose` is the shape `medkit --plugin-panel` emits. Actions go back through
// the host bar widget, which runs the CLI and refreshes.
BorderSurface {
  id: root

  property var dose: ({})
  property var host: null
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family

  readonly property color tint: root.dose.color ? String(root.dose.color) : Color.accent
  readonly property color stateTint: root.dose.stateColor ? String(root.dose.stateColor) : Color.accent
  readonly property bool done: root.dose.state === "taken"
  readonly property bool late: root.dose.state === "overdue"
  // A handler rather than a MouseArea: it watches hover without taking the
  // click away from the Take/Skip buttons sitting on top of the card.
  readonly property bool hot: hover.hovered

  implicitHeight: Style.space(72)
  height: implicitHeight
  radius: Style.cornerRadius

  color: hot ? Util.alpha(root.tint, 0.16) : Util.alpha(root.tint, 0.07)
  borderSpec: Border.flat(
    hot ? root.tint : Util.alpha(root.tint, 0.42),
    Math.max(1, Style.normalBorderWidth)
  )

  Behavior on color { ColorAnimation { duration: 120 } }

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

  Rectangle {
    anchors.left: parent.left
    anchors.verticalCenter: parent.verticalCenter
    width: Style.space(4)
    height: parent.height - Style.space(20)
    radius: width / 2
    color: root.tint
  }

  PillIcon {
    id: pill
    anchors.left: parent.left
    anchors.leftMargin: Style.space(14)
    anchors.verticalCenter: parent.verticalCenter
    size: Style.space(40)
    path: root.dose.icon || ""
    tint: root.tint
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
      tint: root.dose.tabColor ? String(root.dose.tabColor) : Color.accent
      fontFamily: root.fontFamily
      clickable: false
    }

    ChipButton {
      visible: root.dose.low === true || root.dose.out === true
      text: root.dose.out ? "OUT" : (root.dose.stock + " left")
      tint: "#ef4444"
      filled: root.dose.out === true
      fontFamily: root.fontFamily
      clickable: false
    }

    ChipButton {
      text: root.dose.stateLabel || ""
      tint: root.stateTint
      filled: root.done || root.late
      fontFamily: root.fontFamily
      clickable: false
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
    color: root.done ? Qt.darker(root.foreground, 1.7) : root.foreground
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
    color: root.late ? root.stateTint : Qt.darker(root.foreground, 1.6)
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
      visible: root.done
      anchors.verticalCenter: parent.verticalCenter
      textFormat: Text.PlainText
      text: "✓ taken" + (root.dose.takenAt ? " " + root.dose.takenAt : "")
      color: "#22c55e"
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      font.bold: true
    }

    ChipButton {
      visible: !root.done
      text: "Take"
      tint: root.tint
      filled: true
      fontFamily: root.fontFamily
      onClicked: if (root.host) root.host.take(root.dose.name)
    }

    ChipButton {
      visible: !root.done
      text: "Skip"
      tint: "#64748b"
      fontFamily: root.fontFamily
      onClicked: if (root.host) root.host.skip(root.dose.name)
    }

    // Beside every dose: the same edit form the dashboard's Edit button
    // opens — time, medicine, and course days when it is an emergency.
    ChipButton {
      text: "Edit"
      tint: "#3b82f6"
      fontFamily: root.fontFamily
      onClicked: if (root.host) root.host.editMedicine(root.dose.name)
    }

    // Beside every dose: hands the dashboard the delete confirmation for
    // this medicine (it always asks before dropping anything).
    ChipButton {
      text: "Delete"
      tint: "#f87171"
      fontFamily: root.fontFamily
      onClicked: if (root.host) root.host.deleteMedicine(root.dose.name)
    }
  }

  HoverHandler {
    id: hover
  }
}
