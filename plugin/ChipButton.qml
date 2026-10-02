import QtQuick
import qs.Commons
import qs.Ui

// A small tinted pill button: the tint is the caller's colour (a medicine's
// own hue, a tab's accent), so every action row reads as its own card rather
// than one grey control repeated down the panel.
BorderSurface {
  id: root

  property string text: ""
  property color tint: Color.accent
  property color foreground: Color.foreground
  property bool clickable: true
  property bool filled: false
  property string fontFamily: Style.font.family
  property real fontSize: Style.font.caption

  signal clicked()

  readonly property bool hot: mouse.containsMouse && clickable

  implicitWidth: caption.implicitWidth + Style.space(18)
  implicitHeight: caption.implicitHeight + Style.space(12)
  radius: Style.cornerRadius

  color: !clickable
    ? Util.alpha(tint, 0.06)
    : mouse.pressed
      ? Util.alpha(tint, filled ? 0.60 : 0.38)
      : hot
        ? Util.alpha(tint, filled ? 0.48 : 0.30)
        : Util.alpha(tint, filled ? 0.34 : 0.15)
  borderSpec: Border.flat(
    clickable ? (hot ? tint : Util.alpha(tint, 0.55)) : Util.alpha(tint, 0.25),
    Math.max(1, Style.normalBorderWidth)
  )

  Behavior on color { ColorAnimation { duration: 100 } }

  Text {
    id: caption
    anchors.centerIn: parent
    textFormat: Text.PlainText
    text: root.text
    color: root.filled
      ? "#ffffff"
      : (root.clickable ? root.foreground : Qt.darker(root.foreground, 1.9))
    font.family: root.fontFamily
    font.pixelSize: root.fontSize
    font.bold: true
  }

  MouseArea {
    id: mouse
    anchors.fill: parent
    hoverEnabled: true
    enabled: root.clickable
    cursorShape: Qt.PointingHandCursor
    onClicked: root.clicked()
  }
}
