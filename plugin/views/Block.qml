import QtQuick
import qs.Commons
import qs.Ui
import ".."

BorderSurface {
  id: root

  property string title: ""
  property string meta: ""
  // One glyph family, one size, before the label. Marks what the block is.
  property string glyph: ""
  property color tint: Theme.accentDim
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family
  property real fontSize: Style.font.caption
  // Heavier border = the block is trying to stop you. Bright, not red.
  property bool heavy: false

  default property alias rows: body.data

  readonly property color dim: Theme.fg2

  width: parent ? parent.width : implicitWidth
  implicitHeight: body.implicitHeight + root.contentTopInset + root.contentBottomInset
  height: implicitHeight
  radius: Style.cornerRadius
  padding: Style.space(16)
  color: Theme.bg2
  borderSpec: Border.flat(root.heavy ? Theme.alpha(root.tint, 0.65) : Theme.line,
    Math.max(1, root.heavy ? 2 : Style.normalBorderWidth))

  Column {
    id: body
    x: root.contentLeftInset
    y: root.contentTopInset
    width: root.width - root.contentLeftInset - root.contentRightInset
    spacing: Style.space(9)

    Item {
      visible: root.title !== ""
      width: parent.width
      height: visible ? head.implicitHeight : 0

      Row {
        id: head
        width: parent.width
        spacing: Style.space(7)

        Text {
          visible: root.glyph !== ""
          textFormat: Text.PlainText
          text: root.glyph
          color: root.tint
          font.family: root.fontFamily
          font.pixelSize: Style.font.icon
          verticalAlignment: Text.AlignVCenter
        }

        Text {
          id: titleText
          textFormat: Text.PlainText
          text: root.title
          width: Math.min(implicitWidth, Math.max(0, parent.width - (metaText.visible ? metaText.implicitWidth + Style.space(8) : 0)))
          color: root.tint
          font.family: root.fontFamily
          font.pixelSize: root.fontSize
          font.bold: true
          font.letterSpacing: 1.1
          elide: Text.ElideRight
          verticalAlignment: Text.AlignVCenter
        }

        Item {
          width: Math.max(0, parent.width - titleText.implicitWidth - metaText.implicitWidth - Style.space(8))
          height: 1
        }

        Text {
          id: metaText
          visible: root.meta !== ""
          textFormat: Text.PlainText
          text: root.meta
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: root.fontSize
          font.bold: true
          verticalAlignment: Text.AlignVCenter
        }
      }
    }
  }
}
