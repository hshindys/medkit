import QtQuick
import Quickshell
import qs.Commons
import qs.Ui
import "views"

// The MedKit panel: what is due, in the window of the day it belongs to.
//
// The header and the progress bar sit outside the tabs because "how much of
// today is done" is one number no matter which window you are looking at;
// the tabs only decide which doses are in front of you. Four of them —
// morning, evening, night, and the as-needed shelf (emergency or medicines
// taken every N days rather than daily).
//
// Everything is tinted: each tab has its own accent, each dose card its own
// medicine colour, each badge the state it describes. The panel borrows the
// coffee tracker's shape — a bar icon that opens a card, one-tap buttons
// inside it — because that gesture is already in the user's hands.
Panel {
  id: root
  moduleName: "hshindys.medkit"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null

  // "morning" | "evening" | "night" | "emergency". Session-local: the panel
  // opens on whichever window the day is actually in.
  property string tab: {
    var hour = new Date().getHours()
    if (hour >= 18 || hour < 5) return "night"
    if (hour >= 12) return "evening"
    if (hour >= 5 && hour < 12) return "morning"
    return "morning"
  }

  // Which half of the panel is in front of you: the doses of the day, or the
  // safety / health / report / emergency-card views fed by payload.health.
  property string view: "doses"

  // Filter over the dose list: all / due / taken / skipped.
  property string doseFilter: "all"
  // Keyboard cursor over the dose list (j/k, arrows).
  property int selectedDose: 0
  // The `?` shortcut sheet.
  property bool cheatsheet: false
  // True while `--plugin-panel` is still running: the shimmering skeleton.
  readonly property bool skeleton: host ? host.loading === true && root.payload.total === undefined : false

  // The taken/total number counts up to its new value instead of jumping.
  property real displayTaken: 0

  readonly property var viewList: [
    { id: "doses", label: "Doses", color: Theme.accent, badge: 0 },
    { id: "safety", label: "Safety", color: Theme.accent, badge: root.safetyCount() },
    { id: "health", label: "Health", color: Theme.accent, badge: 0 },
    { id: "reports", label: "Reports", color: Theme.accent, badge: 0 },
    { id: "card", label: "Card", color: Theme.accent, badge: root.cardBadge() }
  ]

  readonly property var health: root.payload.health || ({})

  readonly property var barIdentity: hostWidget || root
  readonly property var host: hostWidget
  readonly property var payload: host ? host.panelData : ({})

  readonly property color contentForeground: bar ? bar.foreground : Color.foreground
  readonly property string contentFontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property color dim: Theme.fg2

  // Header mark when no medicine is next: the medication bottle, so the
  // panel still says what it is about at a glance.
  readonly property string medicationGlyph: ""

  readonly property var tabList: payload.tabs ? payload.tabs : []
  readonly property var allDoses: payload.doses ? payload.doses : []
  readonly property var allMedicines: payload.medicines ? payload.medicines : []
  readonly property var currentTab: {
    var list = root.tabList
    for (var i = 0; i < list.length; i++)
      if (list[i].id === root.tab) return list[i]
    return { id: root.tab, label: root.tab, color: Theme.fg3, total: 0, taken: 0, due: 0, overdue: 0 }
  }
  readonly property color tabColor: String(currentTab.color || Theme.fg3)

  readonly property var tabDoses: filterTab(root.allDoses, root.tab)
  readonly property var lowMedicines: filterLow(root.allMedicines)

  // The colour the whole header speaks in: brightest when anything is late,
  // near-white when something is due, mid-grey when today is finished,
  // dim otherwise. No hue — the glyph beside it carries the meaning.
  readonly property color statusColor: {
    if (overdueTotal() > 0) return Theme.stateLate
    if (dueTotal() > 0) return Theme.stateDue
    if (root.payload.total > 0 && root.payload.taken === root.payload.total) return Theme.stateOk
    return Theme.stateIdle
  }
  readonly property string statusLabel: String(root.payload.colorLabel || "nothing due yet")
  readonly property real progress: root.payload.total > 0
    ? Number(root.payload.taken) / Number(root.payload.total)
    : 0

  // Count-up: the header's taken number eases to its new value over 300ms.
  readonly property real targetTaken: Number(root.payload.taken || 0)
  onTargetTakenChanged: {
    if (Math.abs(root.displayTaken - root.targetTaken) < 0.5) return
    takenAnim.from = root.displayTaken
    takenAnim.to = root.targetTaken
    takenAnim.start()
  }
  onPayloadChanged: if (root.displayTaken === 0) root.displayTaken = root.targetTaken

  NumberAnimation {
    id: takenAnim
    target: root
    property: "displayTaken"
    duration: Theme.countUp
    easing.type: Easing.OutCubic
  }

  onViewChanged: root.selectedDose = 0
  onDoseFilterChanged: root.selectedDose = 0
  onProgressChanged: if (progressRing) progressRing.requestPaint()

  function filterTab(list, tab) {
    var out = []
    for (var i = 0; i < list.length; i++)
      if (list[i].tab === tab) out.push(list[i])
    return out
  }

  function filterLow(list) {
    var out = []
    for (var i = 0; i < list.length; i++)
      if (list[i].low && list[i].active) out.push(list[i])
    return out
  }

  function overdueTotal() {
    var n = 0
    var list = root.tabList
    for (var i = 0; i < list.length; i++) n += Number(list[i].overdue || 0)
    return n
  }

  function dueTotal() {
    var n = 0
    var list = root.tabList
    for (var i = 0; i < list.length; i++) n += Number(list[i].due || 0)
    return n
  }

  function percent(value) {
    return Math.round(Number(value || 0) * 100) + " %"
  }

  function nextPendingInTab() {
    var list = root.tabDoses
    for (var i = 0; i < list.length; i++)
      if (list[i].state !== "taken") return list[i]
    return null
  }

  function isSelected(dose) {
    var list = root.visibleDoses()
    if (root.selectedDose < 0 || root.selectedDose >= list.length) return false
    return list[root.selectedDose] === dose
  }

  function takeNext() {
    var dose = nextPendingInTab()
    if (dose && host) host.take(dose.name)
  }

  // ---- Filter over the dose list -------------------------------------
  function visibleDoses() {
    var list = root.tabDoses
    if (root.doseFilter === "all") return list
    var out = []
    for (var i = 0; i < list.length; i++) {
      var state = list[i].state
      if (root.doseFilter === "due" && (state === "due" || state === "overdue")) out.push(list[i])
      else if (root.doseFilter === "taken" && state === "taken") out.push(list[i])
      else if (root.doseFilter === "skipped" && state === "skipped") out.push(list[i])
    }
    return out
  }

  // ---- Keyboard cursor over the dose list ----------------------------
  function moveSelection(delta) {
    var list = root.visibleDoses()
    if (list.length === 0) return
    var index = root.selectedDose + delta
    if (index < 0) index = list.length - 1
    if (index >= list.length) index = 0
    root.selectedDose = index
  }

  function selectedDoseEntry() {
    var list = root.visibleDoses()
    if (list.length === 0) return null
    var index = Math.min(Math.max(root.selectedDose, 0), list.length - 1)
    return list[index]
  }

  function takeSelected() {
    var dose = selectedDoseEntry()
    if (!dose) { takeNext(); return }
    if (dose.state === "taken" || dose.state === "skipped") { takeNext(); return }
    if (host) host.take(dose.name)
  }

  function skipSelected() {
    var dose = selectedDoseEntry()
    if (dose && host) host.skip(dose.name)
  }

  function editSelected() {
    var dose = selectedDoseEntry()
    if (dose && host) host.editMedicine(dose.name)
  }

  function deleteSelected() {
    var dose = selectedDoseEntry()
    if (dose && host) host.deleteMedicine(dose.name)
  }

  function cycleTab(step) {
    var ids = ["morning", "evening", "night", "emergency"]
    var index = ids.indexOf(root.tab)
    if (index < 0) index = 0
    root.tab = ids[(index + step + ids.length) % ids.length]
  }

  function cycleView(step) {
    var ids = []
    for (var i = 0; i < root.viewList.length; i++) ids.push(root.viewList[i].id)
    var index = ids.indexOf(root.view)
    if (index < 0) index = 0
    root.view = ids[(index + step + ids.length) % ids.length]
  }

  function safetyCount() {
    var found = root.health.interactions
    var count = found ? Number(found.count || 0) : 0
    var pregnancy = root.health.pregnancy
    if (pregnancy && pregnancy.active) count += Number(pregnancy.countFlagged || 0)
    var repeats = root.health.sideEffects
    if (repeats) count += (repeats.repeats || []).length
    return count
  }

  function cardBadge() {
    var card = root.health.emergency
    if (!card || !card.incomplete) return 0
    return 1
  }

  function open() {
    root.controller.show()
    Qt.callLater(function() {
      if (root.opened) setCenterHoverRevealSuppressed(true)
    })
  }

  function close() {
    setCenterHoverRevealSuppressed(false)
    root.controller.hide()
  }

  function toggle() {
    if (root.opened) root.close()
    else root.open()
  }

  // Kept so the bar's panel routing matches every other plugin's contract.
  function switchPanel(direction) {
    if (root.view !== "doses") {
      cycleView(direction)
      return false
    }
    cycleTab(direction)
    return false
  }

  function openView(name) {
    root.view = name
    open()
  }

  function setCenterHoverRevealSuppressed(value) {
    if (root.bar && typeof root.bar.setCenterHoverRevealSuppressed === "function")
      root.bar.setCenterHoverRevealSuppressed(value)
    else if (root.bar && "centerHoverRevealSuppressed" in root.bar)
      root.bar.centerHoverRevealSuppressed = value
  }

  function panelChanged() { /* bindings track host.panelData directly */ }

  // Opening a window, or jumping to another one, tells you what that window
  // still owes you — one notice per dose per day, deduplicated by medkit.
  onTabChanged: {
    root.selectedDose = 0
    if (host) host.notifyTab(tab)
  }
  onOpenedChanged: if (opened && host) host.notifyTab(tab)

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(780))
    contentHeight: panel.fittedContentHeight(column.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent

      onCloseRequested: {
        if (root.cheatsheet) { root.cheatsheet = false; return }
        root.close()
      }
      onTabRequested: function(direction) { root.cycleTab(direction) }
      onMoveRequested: function(dx, dy) {
        if (dy !== 0) root.moveSelection(dy)
        else root.cycleTab(dx)
      }
      onActivateRequested: root.takeSelected()
      onDeleteRequested: root.deleteSelected()
      onTextKey: function(t) {
        var key = t.toLowerCase()
        if (key === "1" || key === "2" || key === "3" || key === "4") {
          root.view = "doses"
          if (key === "1") root.tab = "morning"
          else if (key === "2") root.tab = "evening"
          else if (key === "3") root.tab = "night"
          else if (key === "4") root.tab = "emergency"
        }
        else if (key === "5") root.view = "safety"
        else if (key === "6") root.view = "health"
        else if (key === "7") root.view = "reports"
        else if (key === "8") root.view = "card"
        else if (key === "s") root.skipSelected()
        else if (key === "d") root.deleteSelected()
        else if (key === "t") root.takeNext()
        else if (key === "r") if (root.host) root.host.refresh()
        else if (key === "e") root.editSelected()
        else if (key === "g") if (root.host) root.host.openDashboard()
        else if (key === "a") if (root.host) root.host.addMedicine()
        else if (key === "f") if (root.host) root.host.refill("")
        else if (key === "c") if (root.host) root.host.showEmergency()
        else if (key === "?" || key === "/") root.cheatsheet = !root.cheatsheet
      }

      // The panel fades in and lifts 8px on open — the only motion the
      // shell's own panel animation does not already cover.
      Item {
        id: panelBody
        anchors.fill: parent
        opacity: root.opened ? 1 : 0
        transform: Translate {
          id: bodyShift
          y: root.opened ? 0 : Style.space(8)
          Behavior on y { NumberAnimation { duration: Theme.fadePanel; easing.type: Easing.OutCubic } }
        }
        Behavior on opacity { NumberAnimation { duration: Theme.fadePanel; easing.type: Easing.OutCubic } }

      Flickable {
        id: scroll
        anchors.fill: parent
        contentWidth: column.width
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height

        // 4px scrollbar: `line` track, `fg3` thumb.
        Rectangle {
          anchors.right: parent.right
          anchors.rightMargin: 1
          width: Style.space(4)
          radius: width / 2
          color: Theme.line
          visible: scroll.contentHeight > scroll.height
          height: Math.max(Style.space(36), scroll.height * scroll.height / scroll.contentHeight)
          y: Math.max(0, (scroll.height - height) * (scroll.contentY / Math.max(1, scroll.contentHeight - scroll.height)))

          Behavior on y { NumberAnimation { duration: 90 } }
        }

        Column {
          id: column
          width: scroll.width
          spacing: Style.space(14)

          // ---- Skeleton while `--plugin-panel` is still running. -------
          Column {
            visible: root.skeleton
            width: parent.width
            spacing: Style.space(9)

            Repeater {
              model: 3

              delegate: Item {
                id: skel
                width: parent.width
                height: Style.space(72)

                Rectangle {
                  anchors.fill: parent
                  radius: Style.cornerRadius
                  color: Theme.bg2
                  border.width: 1
                  border.color: Theme.line
                }

                Rectangle {
                  id: band
                  width: skel.width * 0.34
                  height: skel.height
                  radius: Style.cornerRadius
                  color: Theme.alpha(Theme.fg3, 0.14)
                  x: -band.width

                  SequentialAnimation on x {
                    running: skel.visible
                    loops: Animation.Infinite
                    NumberAnimation { to: skel.width; duration: Theme.shimmer; easing.type: Easing.InOutSine }
                    NumberAnimation { to: -band.width; duration: 0 }
                  }
                }
              }
            }
          }

          // ---- Header: the one number all four tabs feed. --------------
            Item {
              width: parent.width
              height: Math.max(hero.implicitHeight, headline.implicitHeight, share.implicitHeight)

              HoverHandler { id: headerHover }

              PillIcon {
              id: hero
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
              size: Style.space(52)
              path: nextHeroIcon()
              glyph: root.medicationGlyph
              tint: root.statusColor
              fontFamily: root.contentFontFamily
            }

            Column {
              id: headline
              anchors.left: hero.right
              anchors.leftMargin: Style.space(14)
              anchors.right: share.left
              anchors.rightMargin: Style.space(18)
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(3)

              Row {
                spacing: Style.space(6)

                Text {
                  id: heroNumber
                  textFormat: Text.PlainText
                  text: String(Math.round(root.displayTaken))
                  color: Theme.fg0
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.display
                  font.bold: true
                }

                Text {
                  anchors.baseline: heroNumber.baseline
                  textFormat: Text.PlainText
                  text: "/" + String(root.payload.total !== undefined ? root.payload.total : 0)
                  color: root.dim
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.heading
                  font.bold: true
                }
              }

              Text {
                width: parent.width
                textFormat: Text.PlainText
                text: headerLine()
                color: root.dim
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
                font.letterSpacing: 1.1
                elide: Text.ElideRight
              }
            }

            Row {
              id: share
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(16)

              // Taken/total as an arc — only while you are pointing at it.
              Canvas {
                id: progressRing
                anchors.verticalCenter: parent.verticalCenter
                visible: headerHover.hovered
                opacity: headerHover.hovered ? 1 : 0
                width: Style.space(46)
                height: width
                onPaint: {
                  var ctx = getContext("2d")
                  ctx.reset()
                  ctx.lineWidth = Style.space(4)
                  ctx.lineCap = "round"
                  ctx.strokeStyle = Theme.line.toString()
                  ctx.beginPath()
                  ctx.arc(width / 2, height / 2, width / 2 - ctx.lineWidth, 0, Math.PI * 2)
                  ctx.stroke()
                  ctx.strokeStyle = Theme.accent.toString()
                  ctx.beginPath()
                  ctx.arc(width / 2, height / 2, width / 2 - ctx.lineWidth,
                          -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * root.progress)
                  ctx.stroke()
                  ctx.fillStyle = Theme.fg1.toString()
                  ctx.font = Style.font.caption + "px monospace"
                  ctx.textAlign = "center"
                  ctx.textBaseline = "middle"
                  ctx.fillText(String(Math.round(root.progress * 100)) + "%", width / 2, height / 2)
                }
                onVisibleChanged: requestPaint()
                Behavior on opacity { NumberAnimation { duration: Theme.fadeView } }
              }

              Column {
                anchors.verticalCenter: parent.verticalCenter
                spacing: Style.space(2)

                Text {
                  textFormat: Text.PlainText
                  text: "ADHERENCE 7D"
                  color: root.dim
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.caption
                  font.bold: true
                  font.letterSpacing: 1.1
                }

                Text {
                  textFormat: Text.PlainText
                  text: root.payload.adherence7 === null || root.payload.adherence7 === undefined
                    ? "—" : String(root.payload.adherence7) + " %"
                  color: root.contentForeground
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.title
                  font.bold: true
                }
              }

              BorderSurface {
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: shareText.implicitWidth + Style.space(16)
                implicitHeight: shareText.implicitHeight + Style.space(10)
                color: Util.alpha(root.statusColor, 0.18)
                radius: Style.cornerRadius
                borderSpec: Border.flat(root.statusColor, Math.max(1, Style.normalBorderWidth))

                Text {
                  id: shareText
                  anchors.centerIn: parent
                  textFormat: Text.PlainText
                  text: root.percent(root.progress)
                  color: root.statusColor
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.subtitle
                  font.bold: true
                }
              }
            }
          }

          // ---- Progress toward "today, done". --------------------------
          Column {
            width: parent.width
            spacing: Style.space(7)

            Item {
              width: parent.width
              height: Style.space(3)

              Rectangle {
                id: track
                anchors.fill: parent
                radius: height / 2
                color: Theme.line
              }

              Rectangle {
                anchors.left: track.left
                anchors.verticalCenter: track.verticalCenter
                height: track.height
                radius: track.radius
                width: track.width * root.progress
                color: Theme.accent

                Behavior on width { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
                Behavior on color { ColorAnimation { duration: 200 } }
              }
            }

            Item {
              width: parent.width
              height: progressLeft.implicitHeight

              Text {
                id: progressLeft
                anchors.left: parent.left
                textFormat: Text.PlainText
                text: String(root.payload.next
                  ? "NEXT " + root.payload.next + " · " + root.payload.nextName
                  : (root.payload.pending > 0 ? root.payload.pending + " LEFT TODAY" : "NOTHING LEFT TODAY"))
                color: root.dim
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
              }

              Text {
                anchors.right: parent.right
                textFormat: Text.PlainText
                text: root.statusLabel.toUpperCase()
                color: root.statusColor
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
              }
            }
          }

          PanelSeparator { foreground: root.contentForeground }

          // ---- Which half of the panel. -------------------------------
          ViewSwitcher {
            width: parent.width
            model: root.viewList
            current: root.view
            foreground: root.contentForeground
            fontFamily: root.contentFontFamily
            onChosen: function(id) { root.view = id }
          }

          PanelSeparator { foreground: root.contentForeground }

          // ---- The four windows of the day. ----------------------------
          Row {
            id: tabRow
            width: parent.width
            visible: root.view === "doses"
            opacity: root.view === "doses" ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.fadeView; easing.type: Easing.OutCubic } }
            spacing: Style.space(6)

            Repeater {
              model: root.tabList

              Item {
                id: tabItem
                required property var modelData

                readonly property bool selected: root.tab === tabItem.modelData.id
                readonly property color accent: Theme.accent
                readonly property int count: Number(tabItem.modelData.total || 0)
                readonly property int openCount: count - Number(tabItem.modelData.taken || 0)

                width: tabContent.implicitWidth + Style.space(26)
                height: Style.space(36)

                Rectangle {
                  anchors.fill: parent
                  radius: Style.cornerRadius
                  color: tabItem.selected
                    ? Util.alpha(tabItem.accent, 0.18)
                    : (tabMouse.containsMouse ? Util.alpha(tabItem.accent, 0.10) : "transparent")

                  Behavior on color { ColorAnimation { duration: 120 } }
                }

                Row {
                  id: tabContent
                  anchors.centerIn: parent
                  spacing: Style.space(7)

                  Text {
                    anchors.verticalCenter: parent.verticalCenter
                    textFormat: Text.PlainText
                    text: tabItem.modelData.icon
                    color: tabItem.selected ? tabItem.accent : root.dim
                    font.family: root.contentFontFamily
                    font.pixelSize: Style.font.icon
                  }

                  Text {
                    anchors.verticalCenter: parent.verticalCenter
                    textFormat: Text.PlainText
                    text: tabItem.modelData.label
                    color: tabItem.selected ? root.contentForeground : root.dim
                    font.family: root.contentFontFamily
                    font.pixelSize: Style.font.subtitle
                    font.bold: tabItem.selected
                  }

                  Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: countLabel.implicitWidth + Style.space(12)
                    height: Style.space(18)
                    radius: height / 2
                    color: tabItem.selected ? Theme.accent : Theme.alpha(Theme.fg2, 0.35)

                    Text {
                      id: countLabel
                      anchors.centerIn: parent
                      textFormat: Text.PlainText
                      text: tabItem.openCount > 0 ? String(tabItem.openCount) : String(tabItem.count)
                      color: tabItem.selected ? Theme.bg0 : root.dim
                      font.family: root.contentFontFamily
                      font.pixelSize: Style.font.caption
                      font.bold: true
                    }
                  }
                }

                Rectangle {
                  anchors.left: parent.left
                  anchors.right: parent.right
                  anchors.bottom: parent.bottom
                  height: Style.space(2)
                  radius: height / 2
                  color: tabItem.selected ? Theme.accent : "transparent"

                  Behavior on color { ColorAnimation { duration: 140 } }
                }

                MouseArea {
                  id: tabMouse
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.tab = tabItem.modelData.id
                }
              }
            }
          }

          // ---- What this window holds. ---------------------------------
          PanelSectionHeader {
            visible: root.view === "doses"
            opacity: root.view === "doses" ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.fadeView; easing.type: Easing.OutCubic } }
            text: tabHeading()
            foreground: root.contentForeground
            fontFamily: root.contentFontFamily
          }

          // ---- Filter over the dose list. ------------------------------
          Row {
            visible: root.view === "doses"
            opacity: root.view === "doses" ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.fadeView; easing.type: Easing.OutCubic } }
            spacing: Style.space(6)

            Repeater {
              model: [
                { id: "all", label: "All" },
                { id: "due", label: "Due" },
                { id: "taken", label: "Taken" },
                { id: "skipped", label: "Skipped" }
              ]

              ChipButton {
                required property var modelData
                text: String(modelData.label)
                filled: root.doseFilter === String(modelData.id)
                fontFamily: root.contentFontFamily
                tooltip: "Show " + String(modelData.label).toLowerCase() + " doses only"
                onClicked: root.doseFilter = String(modelData.id)
              }
            }
          }

          Text {
            visible: root.view === "doses" && root.tab === "emergency" && root.tabDoses.length > 0
            width: parent.width
            textFormat: Text.PlainText
            text: "As-needed and every-N-days medicines live here, whatever the hour."
            color: root.dim
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.caption
          }

          Column {
            width: parent.width
            visible: root.view === "doses"
            opacity: root.view === "doses" ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.fadeView; easing.type: Easing.OutCubic } }
            spacing: Style.space(9)

            Repeater {
              model: root.visibleDoses()

              DoseCard {
                required property var modelData
                width: parent.width
                dose: modelData
                host: root.host
                foreground: root.contentForeground
                fontFamily: root.contentFontFamily
                selected: root.isSelected(modelData)
              }
            }
          }

          Column {
            visible: root.view === "doses" && root.visibleDoses().length === 0
            width: parent.width
            spacing: Style.space(8)

            Text {
              width: parent.width
              horizontalAlignment: Text.AlignHCenter
              textFormat: Text.PlainText
              text: Theme.glyphPill
              color: Theme.fg3
              font.family: root.contentFontFamily
              font.pixelSize: Style.space(34)
            }

            Text {
              width: parent.width
              horizontalAlignment: Text.AlignHCenter
              wrapMode: Text.WordWrap
              textFormat: Text.PlainText
              text: root.payload.wizard === false
                ? "Setup is pending — enter your pill counts to switch reminders on."
                : (root.tabDoses.length > 0
                    ? "No doses match this filter."
                    : "Nothing scheduled in this window.")
              color: Theme.fg2
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.body
            }
          }

          // ---- Stock that is running out, wherever it lives. -----------
          Column {
            width: parent.width
            spacing: Style.space(9)
            visible: root.view === "doses" && root.lowMedicines.length > 0

            PanelSeparator { foreground: root.contentForeground }

            PanelSectionHeader {
              text: "LOW ON STOCK · " + root.lowMedicines.length
              foreground: root.contentForeground
              fontFamily: root.contentFontFamily
            }

            Repeater {
              model: root.lowMedicines

              BorderSurface {
                required property var modelData
                width: parent.width
                implicitHeight: stockRow.implicitHeight + Style.space(16)
                height: implicitHeight
                radius: Style.cornerRadius
                color: Util.alpha(Theme.danger, 0.10)
                borderSpec: Border.flat(Util.alpha(Theme.danger, 0.55), Math.max(1, Style.normalBorderWidth))

                Row {
                  id: stockRow
                  anchors.left: parent.left
                  anchors.right: parent.right
                  anchors.verticalCenter: parent.verticalCenter
                  anchors.leftMargin: Style.space(14)
                  anchors.rightMargin: Style.space(14)
                  spacing: Style.space(10)

                  PillIcon {
                    anchors.verticalCenter: parent.verticalCenter
                    size: Style.space(30)
                    path: modelData.icon
                    tint: String(modelData.color || Theme.danger)
                    fontFamily: root.contentFontFamily
                  }

                  Text {
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - implicitWidth - chipRow.width - Style.space(20)
                    textFormat: Text.PlainText
                    text: modelData.name
                    elide: Text.ElideRight
                    color: root.contentForeground
                    font.family: root.contentFontFamily
                    font.pixelSize: Style.font.body
                    font.bold: true
                  }

                  Row {
                    id: chipRow
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Style.space(6)

                    ChipButton {
                      text: modelData.out ? "OUT" : (modelData.stock + " left")
                      tint: Theme.danger
                      filled: modelData.out
                      fontFamily: root.contentFontFamily
                      clickable: false
                    }

                    ChipButton {
                      text: "refill at " + modelData.refillAt
                      tint: Theme.fg3
                      fontFamily: root.contentFontFamily
                      clickable: false
                    }

                    ChipButton {
                      text: "Refill"
                      tint: Theme.accentDim
                      filled: modelData.out
                      fontFamily: root.contentFontFamily
                      onClicked: if (root.host) root.host.refill(modelData.name)
                    }

                    ChipButton {
                      text: "Edit"
                      tint: Theme.accentDim
                      fontFamily: root.contentFontFamily
                      onClicked: if (root.host) root.host.editMedicine(modelData.name)
                    }

                    ChipButton {
                      text: "Delete"
                      tint: Theme.danger
                      fontFamily: root.contentFontFamily
                      onClicked: if (root.host) root.host.deleteMedicine(modelData.name)
                    }
                  }
                }
              }
            }
          }

          // ---- The safety, health, report and card views. --------------
          SafetyView {
            width: parent.width
            visible: root.view === "safety"
            opacity: root.view === "safety" ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.fadeView; easing.type: Easing.OutCubic } }
            health: root.health
            host: root.host
            foreground: root.contentForeground
            fontFamily: root.contentFontFamily
          }

          HealthView {
            width: parent.width
            visible: root.view === "health"
            opacity: root.view === "health" ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.fadeView; easing.type: Easing.OutCubic } }
            health: root.health
            host: root.host
            foreground: root.contentForeground
            fontFamily: root.contentFontFamily
          }

          ReportsView {
            width: parent.width
            visible: root.view === "reports"
            opacity: root.view === "reports" ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.fadeView; easing.type: Easing.OutCubic } }
            health: root.health
            host: root.host
            foreground: root.contentForeground
            fontFamily: root.contentFontFamily
          }

          Column {
            width: parent.width
            visible: root.view === "card"
            opacity: root.view === "card" ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.fadeView; easing.type: Easing.OutCubic } }
            spacing: Style.space(9)

            CardView {
              width: parent.width
              card: root.health.emergency || ({})
              host: root.host
              foreground: root.contentForeground
              fontFamily: root.contentFontFamily
            }

            ChipButton {
              text: Theme.glyphCard + " Open fullscreen card"
              tint: Theme.accentDim
              filled: true
              fontFamily: root.contentFontFamily
              onClicked: if (root.host) root.host.showEmergency()
            }
          }

          // ---- Footer: the doors out of here. --------------------------
          PanelSeparator { foreground: root.contentForeground }

          Row {
            width: parent.width
            spacing: Style.space(8)

            Text {
              anchors.verticalCenter: parent.verticalCenter
              width: parent.width - buttons.width - Style.space(12)
              textFormat: Text.PlainText
              text: footerLine()
              color: root.dim
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.caption
              elide: Text.ElideRight
            }

            Row {
              id: buttons
              spacing: Style.space(8)

              ChipButton {
                text: Theme.glyphAdd + " Add medicine"
                tint: Theme.accentDim
                filled: true
                fontFamily: root.contentFontFamily
                onClicked: if (root.host) root.host.addMedicine()
              }

              ChipButton {
                text: Theme.glyphRefill + " Refill"
                tint: Theme.accentDim
                fontFamily: root.contentFontFamily
                onClicked: if (root.host) root.host.refill("")
              }

              ChipButton {
                text: "Refresh"
                tint: Theme.mild
                fontFamily: root.contentFontFamily
                onClicked: if (root.host) root.host.refresh()
              }

              ChipButton {
                text: Theme.glyphDashboard + " Dashboard"
                tint: Theme.accentDim
                fontFamily: root.contentFontFamily
                onClicked: if (root.host) root.host.openDashboard()
              }

              ChipButton {
                text: Theme.glyphEmergency + " Emergency card"
                tint: Theme.danger
                filled: true
                fontFamily: root.contentFontFamily
                tooltip: "Fullscreen medical card, offline"
                onClicked: if (root.host) root.host.showEmergency()
              }
            }
          }

          // ---- The line that has to be on every answer. ---------------
          Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            textFormat: Text.PlainText
            text: "This is not medical advice."
            color: Theme.fg3
            font.family: root.contentFontFamily
            font.pixelSize: Style.space(11)
          }

          // ---- Shortcut sheet (`?`). -----------------------------------
          BorderSurface {
            visible: root.cheatsheet
            width: parent.width
            implicitHeight: cheatsheetBody.implicitHeight + Style.space(24)
            height: implicitHeight
            radius: Style.cornerRadius
            color: Theme.bg2
            borderSpec: Border.flat(Theme.line, Math.max(1, Style.normalBorderWidth))

            Column {
              id: cheatsheetBody
              x: Style.space(12)
              y: Style.space(12)
              width: parent.width - Style.space(24)
              spacing: Style.space(4)

              Text {
                textFormat: Text.PlainText
                text: "KEYBOARD"
                color: Theme.fg2
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
                font.letterSpacing: 1.1
              }

              Text {
                width: parent.width
                textFormat: Text.PlainText
                text: "j / k  move · enter take · s skip · e edit · d delete\n"
                  + "1–4 dose window · 5–8 view · g dashboard · a add · f refill\n"
                  + "t take next · r refresh · c emergency card · esc close"
                color: Theme.fg1
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.caption
              }
            }
          }
        }
      }
      }
    }
  }

  function nextHeroIcon() {
    var list = root.tabDoses
    for (var i = 0; i < list.length; i++)
      if (list[i].state !== "taken" && list[i].iconLarge) return list[i].iconLarge
    if (root.payload.nextName) {
      var all = root.allMedicines
      for (var j = 0; j < all.length; j++)
        if (all[j].name === root.payload.nextName) return all[j].iconLarge
    }
    return ""
  }

  function headerLine() {
    var parts = ["TODAY"]
    if (root.payload.next) parts.push("NEXT " + root.payload.next)
    if (root.lowMedicines.length > 0) parts.push(root.lowMedicines.length + " LOW")
    if (Number(root.payload.emergency || 0) > 0) parts.push(root.payload.emergency + " EMERGENCY")
    return parts.join(" · ")
  }

  function tabHeading() {
    var label = String(root.currentTab.label || root.tab).toUpperCase()
    var windows = {
      morning: "05:00 – 11:59",
      evening: "12:00 – 17:59",
      night: "18:00 – 04:59",
      emergency: "AS NEEDED"
    }
    var window = windows[root.tab] || ""
    return label + " · " + window + " · " + root.tabDoses.length + " DOSES"
  }

  function footerLine() {
    if (root.host && String(root.host.actionMessage || "") !== "")
      return String(root.host.actionMessage)
    var a7 = root.payload.adherence7
    var a30 = root.payload.adherence30
    var text = "7d " + (a7 === null || a7 === undefined ? "—" : a7 + "%")
      + " · 30d " + (a30 === null || a30 === undefined ? "—" : a30 + "%")
    if (root.payload.taken === root.payload.total && root.payload.total > 0)
      text += " · all done"
    return text
  }
}
