import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// MedKit in the bar: today's dose state as a coloured dot plus the next dose
// and the taken/total count. Click opens the panel behind it — the same
// gesture as every other panel widget — right-click still opens the GTK
// dashboard for full management (add, edit, delete, wizard).
//
// This widget owns the data. It runs `medkit --plugin-panel`, watches the
// three files MedKit writes, and hands the parsed payload to Panel.qml, so
// the panel never shells out on its own and every bar instance on every
// monitor shows the same numbers.
BarWidget {
  id: root
  moduleName: "hshindys.medkit"

  readonly property string medkitBin: setting(
    "bin",
    Quickshell.env("HOME") + "/medkit/bin/medkit"
  )

  // The whole payload from --plugin-panel: header, tabs, doses, medicines.
  property var panelData: ({})
  property bool loading: false

  // Convenience reads the bar label and tooltip are built from.
  readonly property string medkitState: String(panelData.color || "neutral")
  readonly property string nextDose: String(panelData.next || "")
  readonly property string nextName: String(panelData.nextName || "")
  readonly property int takenCount: Number(panelData.taken || 0)
  readonly property int totalCount: Number(panelData.total || 0)
  readonly property int lowCount: Number(panelData.low || 0)
  readonly property int emergencyCount: Number(panelData.emergency || 0)
  readonly property bool wizardDone: panelData.wizard !== false

  readonly property string stateColorHex: {
    var hex = { "green": "#22c55e", "amber": "#f59e0b", "red": "#ef4444" }[medkitState] || "#64748b"
    if (lowCount > 0 && (medkitState === "neutral" || medkitState === "green"))
      return "#f59e0b"
    return hex
  }

  // The bar's mark: a pill, tinted with today's state, instead of a bare dot.
  readonly property string pillGlyph: "󰐂"

  readonly property string labelText: {
    if (!wizardDone) return "setup"
    if (nextDose !== "") return nextDose
    if (totalCount > 0) return takenCount + "/" + totalCount
    return "—"
  }

  visible: true
  implicitWidth: root.vertical
    ? barSize
    : barLabel.implicitWidth + Style.space(16)
  implicitHeight: barSize

  function refresh() {
    if (!statusProc.running) statusProc.running = true
  }

  function toggle() {
    if (!toggleProc.running) toggleProc.running = true
  }

  function take(name) {
    actionProc.command = [root.medkitBin, "--take", name]
    actionProc.running = true
  }

  function skip(name) {
    actionProc.command = [root.medkitBin, "--skip", name]
    actionProc.running = true
  }

  function openDashboard() {
    actionProc.command = [root.medkitBin, "--dashboard-toggle"]
    actionProc.running = true
  }

  // Open the dashboard straight onto the add-medicine form.
  function addMedicine() {
    actionProc.command = [root.medkitBin, "--add-medicine"]
    actionProc.running = true
  }

  // Open the dashboard straight onto one medicine's edit form.
  function editMedicine(name) {
    actionProc.command = [root.medkitBin, "--edit", name]
    actionProc.running = true
  }

  // Open the dashboard on one medicine's delete confirmation (never deletes
  // silently — the dashboard always asks first).
  function deleteMedicine(name) {
    actionProc.command = [root.medkitBin, "--delete", name]
    actionProc.running = true
  }

  // Refill one medicine by name, or every medicine that is low when empty.
  function refill(name) {
    actionProc.command = name
      ? [root.medkitBin, "--refill", name]
      : [root.medkitBin, "--refill"]
    actionProc.running = true
  }

  // Fire the due/overdue notice for one tab, once per dose per day.
  function notifyTab(tab) {
    notifyProc.command = [root.medkitBin, "--notify-due", tab]
    notifyProc.running = true
  }

  function tipText() {
    if (!wizardDone) return "MedKit — setup needed, click to open the panel"
    var tip = "MedKit — "
    tip += nextDose !== "" ? "next dose " + nextDose : "no more doses today"
    tip += " · " + takenCount + "/" + totalCount + " taken"
    if (lowCount > 0) tip += " · " + lowCount + " low on stock"
    if (emergencyCount > 0) tip += " · " + emergencyCount + " emergency"
    return tip
  }

  IpcHandler {
    target: "hshindys.medkit"

    function refresh(): void { root.refresh() }
    function toggle(): void { root.togglePanel() }
    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function morning(): void { root.openTab("morning") }
    function evening(): void { root.openTab("evening") }
    function night(): void { root.openTab("night") }
    function emergency(): void { root.openTab("emergency") }
    function addMedicine(): void { root.addMedicine() }
    function editMedicine(name: string): void { root.editMedicine(name) }
    function deleteMedicine(name: string): void { root.deleteMedicine(name) }
    function refill(): void { root.refill("") }
    function refillOne(name: string): void { root.refill(name) }
  }

  Process {
    id: statusProc
    command: [root.medkitBin, "--plugin-panel"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          var payload = JSON.parse(text)
          if (payload && typeof payload === "object") {
            root.panelData = payload
            root.loading = false
          }
        } catch (error) {
          // A half-written data file must not blank the bar; keep the last
          // good payload and try again on the next tick.
        }
      }
    }
    onExited: function(exitCode) {
      if (exitCode !== 0) root.loading = false
    }
  }

  Process {
    id: actionProc
    onExited: function(exitCode) { Qt.callLater(root.refresh) }
  }

  Process {
    id: notifyProc
  }

  // FileView cannot watch a file whose directory does not exist yet, so the
  // data dir is created before the first read.
  Process {
    id: dataDirProc
    command: ["mkdir", "-p", (Quickshell.env("XDG_DATA_HOME") || Quickshell.env("HOME") + "/.local/share") + "/medkit"]
    onExited: refreshDebounce.restart()
  }

  FileView {
    path: (Quickshell.env("XDG_DATA_HOME") || Quickshell.env("HOME") + "/.local/share") + "/medkit/medicines.json"
    watchChanges: true
    printErrors: false
    onFileChanged: refreshDebounce.restart()
  }

  FileView {
    path: (Quickshell.env("XDG_DATA_HOME") || Quickshell.env("HOME") + "/.local/share") + "/medkit/state.json"
    watchChanges: true
    printErrors: false
    onFileChanged: refreshDebounce.restart()
  }

  FileView {
    path: (Quickshell.env("XDG_DATA_HOME") || Quickshell.env("HOME") + "/.local/share") + "/medkit/history.jsonl"
    watchChanges: true
    printErrors: false
    onFileChanged: refreshDebounce.restart()
  }

  // The three files move together when a dose is taken; debounce so one save
  // produces one read.
  Timer {
    id: refreshDebounce
    interval: 120
    onTriggered: root.refresh()
  }

  Timer {
    interval: 30000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  // ---- Panel. Shape contract for shell.summon/hide/toggle routing:
  //      Bar.findPanelWidget requires open/close/opened on the widget root.
  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false

  function open() { if (panelLoader.item) panelLoader.item.open() }
  function close() { if (panelLoader.item) panelLoader.item.close() }
  function togglePanel() { if (panelLoader.item) panelLoader.item.toggle() }

  function openTab(name) {
    if (panelLoader.item) panelLoader.item.tab = name
    open()
  }

  // How long the open-panel dot should run along the bar: the width of the
  // mark + label this widget actually paints, so it tracks the text instead
  // of a fraction of whatever slot the bar happens to give us.
  readonly property real openPanelIndicatorWidth: root.vertical
    ? 0
    : Math.max(barLabel.implicitWidth, Style.space(10))
  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false

  function closeForPopoutSwitch() {
    if (panelLoader.item) panelLoader.item.closeForPopoutSwitch()
  }

  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    if ("bar" in target) target.bar = root.bar
    if ("settings" in target) target.settings = root.settings
    if ("anchorItem" in target) target.anchorItem = content
    if ("hostWidget" in target) target.hostWidget = root
  }

  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()
  onPanelDataChanged: if (panelLoader.item) panelLoader.item.panelChanged()

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  Item {
    id: content
    anchors.fill: parent
    anchors.leftMargin: Style.space(8)
    anchors.rightMargin: Style.space(8)
    clip: true

    Text {
      id: barLabel
      anchors.verticalCenter: parent.verticalCenter
      anchors.left: parent.left
      width: root.vertical ? Style.space(12) : parent.width
      textFormat: Text.RichText
      text: "<span style='color:" + root.stateColorHex + ";'>" + root.pillGlyph + "</span>"
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
    onClicked: function(mouse) {
      if (mouse.button === Qt.RightButton) root.toggle()
      else root.togglePanel()
    }
    onEntered: if (root.bar) root.bar.showTooltip(root, root.tipText())
    onExited: if (root.bar) root.bar.hideTooltip(root)
  }
}
