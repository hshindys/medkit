import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.Commons
import qs.Ui
import "views"

PanelWindow {
  id: root

  property var health: ({})
  property var host: null
  property bool opened: false
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family

  readonly property var card: health.emergency || ({})
  readonly property color dim: Qt.darker(root.foreground, 1.4)

  visible: root.opened
  anchors { top: true; bottom: true; left: true; right: true }
  color: "transparent"

  WlrLayershell.namespace: "omarchy-medkit-emergency"
  WlrLayershell.layer: WlrLayer.Overlay
  WlrLayershell.keyboardFocus: root.opened ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
  exclusionMode: ExclusionMode.Ignore

  function open() { root.opened = true }
  function close() {
    root.opened = false
    if (root.host && typeof root.host.hideEmergency === "function") root.host.hideEmergency()
  }
  function toggle() { root.opened ? root.close() : root.open() }
  onOpenedChanged: if (root.opened)
    Qt.callLater(function() { keys.forceActiveFocus() })

  Rectangle {
    anchors.fill: parent
    color: Color.menu.scrim
  }

  MouseArea {
    anchors.fill: parent
    onClicked: root.close()
  }

  BorderSurface {
    id: surface

    anchors.centerIn: parent
    width: Math.min(Style.space(860), parent.width - Style.space(24) * 2)
    height: Math.min(parent.height - Style.space(48), content.implicitHeight + Style.space(36) * 2)
    radius: Style.cornerRadius
    color: Color.menu.background
    borderSpec: Border.surfaceSpec("menu", "border", Color.menu.border, Math.max(1, Style.space(2)))

    MouseArea { anchors.fill: parent; onClicked: {} }

    PanelKeyCatcher {
      id: keys
      anchors.fill: parent
      onCloseRequested: root.close()
      onTextKey: function(t) {
        var key = t.toLowerCase()
        if (key === "c" || key === "q") root.close()
      }
      Flickable {
        id: scroll
        anchors.fill: parent
        anchors.margins: Style.space(20)
        contentWidth: width
        contentHeight: content.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height

        Column {
          id: content
          width: scroll.width
          spacing: Style.space(14)

          PanelHero {
            width: parent.width
            title: "Medical emergency card"
            meta: "OFFLINE · SHOWS WITHOUT NETWORK"
            detail: String(root.card.bloodType || "").toUpperCase()
            foreground: root.foreground
            fontFamily: root.fontFamily

            iconComponent: Component {
              Text {
                text: ""
                color: Color.accent
                font.family: root.fontFamily
                font.pixelSize: Style.font.display
              }
            }
          }

          CardView {
            width: parent.width
            card: root.card
            host: root.host
            foreground: root.foreground
            fontFamily: root.fontFamily
            hero: true
          }

          PanelSeparator { foreground: root.foreground }

          Text {
            width: parent.width
            textFormat: Text.PlainText
            text: "Esc or click outside to close · " + String(root.card.updatedDate || "never updated")
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
        }
      }
    }
  }
}
