import QtQuick
import qs.Commons
import qs.Ui

// A monochrome chip: outlined on `line`, filled only when it is the primary
// action of its row. State lives in the label's luminance, never in hue, so
// a row of buttons still reads as one system on a dark surface.
BorderSurface {
  id: root

  property string text: ""
  property color tint: Theme.accent
  property color foreground: Color.foreground
  property bool clickable: true
  property bool filled: false
  property string tooltip: ""
  property string fontFamily: Style.font.family
  property real fontSize: Style.font.caption

  signal clicked()

  readonly property bool hot: mouse.containsMouse && clickable

  implicitWidth: caption.implicitWidth + Style.space(18)
  implicitHeight: caption.implicitHeight + Style.space(12)
  radius: Style.cornerRadius

  color: !clickable
    ? Theme.bg2
    : mouse.pressed
      ? (root.filled ? Theme.accentDim : Theme.bg3)
      : root.filled
        ? (root.hot ? Theme.accentDim : Theme.accent)
        : (root.hot ? Theme.bg3 : Theme.alpha(Theme.bg2, 0.55))
  borderSpec: Border.flat(
    root.filled
      ? Theme.accent
      : root.clickable
        ? (root.hot ? Theme.accentDim : Theme.line)
        : Theme.alpha(root.tint, 0.55),
    Math.max(1, Style.normalBorderWidth)
  )

  Behavior on color { ColorAnimation { duration: 100 } }

  Text {
    id: caption
    anchors.centerIn: parent
    textFormat: Text.PlainText
    text: root.text
    color: root.filled
      ? Theme.bg0
      : root.clickable
        ? Theme.fg1
        : root.tint
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

  PanelToolTip {
    visible: root.tooltip !== "" && mouse.containsMouse
    text: root.tooltip
    panelForeground: Theme.fg1
    panelBackground: Theme.bg3
    panelBorder: Theme.line
    fontFamily: root.fontFamily
  }
}
