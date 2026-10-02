import QtQuick
import qs.Commons

// A medicine's own pill, animated and in its own colour. Falls back to a
// this glyph when the GIF cannot be read (or is still being generated),
// so a card is never blank.
Item {
  id: root

  property string path: ""
  property color tint: Color.accent
  property real size: Style.space(34)
  property string fontFamily: Style.font.family
  // Shown when the medicine's own artwork is missing: the pill by default,
  // or whatever glyph the caller asks for — the panel header asks for the
  // medication bottle, because "nothing due" is not one specific pill.
  property string glyph: "󰐂"

  implicitWidth: size
  implicitHeight: size

  AnimatedImage {
    id: pill
    anchors.fill: parent
    source: root.path ? Util.fileUrl(root.path) : ""
    fillMode: Image.PreserveAspectFit
    visible: status === Image.Ready
  }

  Text {
    anchors.centerIn: parent
    text: root.glyph
    color: root.tint
    font.family: root.fontFamily
    font.pixelSize: root.size * 0.55
    visible: pill.status !== Image.Ready
  }
}
