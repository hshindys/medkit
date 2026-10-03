import QtQuick
import qs.Commons
import qs.Ui
import ".."

// The panel's segmented control: five pills, one surface. The selected
// segment is the brightest thing in the row (`bg3` + `fg0`), the rest sit
// in `fg2` until you hover them — luminance carries the state, the glyph
// says which view you are looking at.
Row {
  id: root

  property var model: []
  property string current: ""
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family

  signal chosen(string id)

  spacing: Style.space(6)

  function glyphFor(id) {
    if (id === "doses") return Theme.glyphPill
    if (id === "safety") return Theme.glyphSafety
    if (id === "health") return Theme.glyphHealth
    if (id === "reports") return Theme.glyphReports
    if (id === "card") return Theme.glyphCard
    return Theme.glyphPill
  }

  Repeater {
    model: root.model

    delegate: Item {
      id: seg

      required property var modelData

      readonly property bool selected: root.current === String(seg.modelData.id)
      readonly property int badge: Number(seg.modelData.badge || 0)

      width: segRow.implicitWidth + Style.space(26)
      height: Style.space(34)

      Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: seg.selected
          ? Theme.bg3
          : (segMouse.containsMouse ? Theme.bg2 : "transparent")
        border.width: seg.selected ? 1 : 0
        border.color: Theme.accentDim

        Behavior on color { ColorAnimation { duration: 120 } }
      }

      Row {
        id: segRow
        anchors.centerIn: parent
        spacing: Style.space(7)

        Text {
          anchors.verticalCenter: parent.verticalCenter
          textFormat: Text.PlainText
          text: root.glyphFor(String(seg.modelData.id))
          color: seg.selected ? Theme.accent : Theme.fg3
          font.family: root.fontFamily
          font.pixelSize: Style.font.icon
        }

        Text {
          anchors.verticalCenter: parent.verticalCenter
          textFormat: Text.PlainText
          text: String(seg.modelData.label || "")
          color: seg.selected ? Theme.fg0 : Theme.fg2
          font.family: root.fontFamily
          font.pixelSize: Style.font.subtitle
          font.bold: seg.selected
        }

        Rectangle {
          visible: seg.badge > 0
          anchors.verticalCenter: parent.verticalCenter
          width: badgeText.implicitWidth + Style.space(10)
          height: Style.space(17)
          radius: height / 2
          color: seg.selected ? Theme.accent : Theme.bg3
          border.width: 1
          border.color: seg.selected ? Theme.accent : Theme.line

          Text {
            id: badgeText
            anchors.centerIn: parent
            textFormat: Text.PlainText
            text: String(seg.badge)
            color: seg.selected ? Theme.bg0 : Theme.fg1
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            font.bold: true
          }
        }
      }

      MouseArea {
        id: segMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.chosen(String(seg.modelData.id))
      }
    }
  }
}
