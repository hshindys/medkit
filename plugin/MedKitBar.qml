import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "hshindys.medkit"

  readonly property string medkitBin: setting(
    "bin",
    Quickshell.env("HOME") + "/medkit/bin/medkit"
  )
  property string medkitState: "neutral"
  property string nextDose: ""
  property int takenCount: 0
  property int totalCount: 0
  property int lowCount: 0
  property bool wizardDone: true

  readonly property string stateColorHex: {
    var hex = { "green": "#22c55e", "amber": "#f59e0b", "red": "#ef4444" }[medkitState] || "#64748b"
    if (lowCount > 0 && (medkitState === "neutral" || medkitState === "green"))
      return "#f59e0b"
    return hex
  }

  readonly property string labelText: {
    if (!wizardDone) return "setup"
    if (nextDose !== "") return nextDose
    if (totalCount > 0) return takenCount + "/" + totalCount
    return "—"
  }

  visible: true
  implicitWidth: root.vertical
    ? barSize
    : label.implicitWidth + Style.space(16)
  implicitHeight: barSize

  function refresh() {
    if (!statusProc.running) statusProc.running = true
  }

  function toggle() {
    if (!toggleProc.running) toggleProc.running = true
  }

  function tipText() {
    if (!wizardDone) return "MedKit — setup needed, click to open the dashboard"
    var tip = "MedKit — "
    tip += nextDose !== "" ? "next dose " + nextDose : "no more doses today"
    tip += " · " + takenCount + "/" + totalCount + " taken"
    if (lowCount > 0) tip += " · " + lowCount + " low on stock"
    return tip
  }

  IpcHandler {
    target: "hshindys.medkit"

    function refresh(): void {
      root.refresh()
    }

    function toggle(): void {
      root.toggle()
    }
  }

  Process {
    id: statusProc
    command: [root.medkitBin, "--plugin-status"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var status
        try {
          status = JSON.parse(text)
        } catch (error) {
          return
        }
        root.medkitState = status.color || "neutral"
        root.nextDose = status.next || ""
        root.takenCount = status.taken || 0
        root.totalCount = status.total || 0
        root.lowCount = status.low || 0
        root.wizardDone = status.wizard !== false
      }
    }
    onExited: function(exitCode) {
      if (exitCode === 0) return
      root.medkitState = "neutral"
      root.nextDose = ""
      root.takenCount = 0
      root.totalCount = 0
      root.lowCount = 0
    }
  }

  Process {
    id: toggleProc
    command: [root.medkitBin, "--dashboard-toggle"]
  }

  Timer {
    interval: 30000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  Item {
    anchors.fill: parent
    anchors.leftMargin: Style.space(8)
    anchors.rightMargin: Style.space(8)
    clip: true

    Text {
      id: label
      anchors.verticalCenter: parent.verticalCenter
      anchors.left: parent.left
      width: root.vertical ? Style.space(12) : parent.width
      textFormat: Text.RichText
      text: "<span style='color:" + root.stateColorHex + ";'>●</span>"
        + (root.vertical ? "" : " " + root.labelText)
      color: root.bar ? root.bar.barForeground : Color.foreground
      font.family: root.bar ? root.bar.fontFamily : Style.font.family
      font.pixelSize: Style.font.caption
      verticalAlignment: Text.AlignVCenter
    }
  }

  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    onClicked: root.toggle()
    onEntered: if (root.bar) root.bar.showTooltip(root, root.tipText())
    onExited: if (root.bar) root.bar.hideTooltip(root)
  }
}
