import QtQuick
import qs.Commons
import qs.Ui

Row {
  id: root

  property var model: []
  property string current: ""
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family

  signal chosen(string id)

  spacing: Style.space(6)

  Repeater {
    model: root.model

    delegate: Item {
      id: seg

      required property var modelData

      readonly property bool selected: root.current === String(seg.modelData.id)
      readonly property color accent: String(seg.modelData.color || root.foreground)
      readonly property int badge: Number(seg.modelData.badge || 0)

      width: segRow.implicitWidth + Style.space(26)
      height: Style.space(34)

      Rectangle {
        anchors.fill: parent
        radius: Style.cornerRadius
        color: seg.selected
          ? Util.alpha(seg.accent, 0.20)
          : (segMouse.containsMouse ? Util.alpha(seg.accent, 0.10) : "transparent")

        Behavior on color { ColorAnimation { duration: 120 } }
      }

      Row {
        id: segRow
        anchors.centerIn: parent
        spacing: Style.space(7)

        Text {
          anchors.verticalCenter: parent.verticalCenter
          textFormat: Text.PlainText
          text: String(seg.modelData.label || "")
          color: seg.selected ? root.foreground : Qt.darker(root.foreground, 1.5)
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
          color: Util.alpha(seg.accent, seg.selected ? 0.95 : 0.75)

          Text {
            id: badgeText
            anchors.centerIn: parent
            textFormat: Text.PlainText
            text: String(seg.badge)
            color: "#0d1016"
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            font.bold: true
          }
        }
      }

      Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: Style.space(3)
        radius: height / 2
        color: seg.selected ? seg.accent : "transparent"

        Behavior on color { ColorAnimation { duration: 140 } }
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
