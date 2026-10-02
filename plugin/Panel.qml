import QtQuick
import Quickshell
import qs.Commons
import qs.Ui

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

  readonly property var barIdentity: hostWidget || root
  readonly property var host: hostWidget
  readonly property var payload: host ? host.panelData : ({})

  readonly property color contentForeground: bar ? bar.foreground : Color.foreground
  readonly property string contentFontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property color dim: Qt.darker(contentForeground, 1.6)

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
    return { id: root.tab, label: root.tab, color: "#64748b", total: 0, taken: 0, due: 0, overdue: 0 }
  }
  readonly property color tabColor: String(currentTab.color || "#64748b")

  readonly property var tabDoses: filterTab(root.allDoses, root.tab)
  readonly property var lowMedicines: filterLow(root.allMedicines)

  // The colour the whole header speaks in: red if anything is late, amber if
  // something is due, green when today is finished, neutral otherwise.
  readonly property color statusColor: {
    if (overdueTotal() > 0) return "#ef4444"
    if (dueTotal() > 0) return "#f59e0b"
    if (root.payload.total > 0 && root.payload.taken === root.payload.total) return "#22c55e"
    return "#64748b"
  }
  readonly property string statusLabel: String(root.payload.colorLabel || "nothing due yet")
  readonly property real progress: root.payload.total > 0
    ? Number(root.payload.taken) / Number(root.payload.total)
    : 0

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

  function takeNext() {
    var dose = nextPendingInTab()
    if (dose && host) host.take(dose.name)
  }

  function cycleTab(step) {
    var ids = ["morning", "evening", "night", "emergency"]
    var index = ids.indexOf(root.tab)
    if (index < 0) index = 0
    root.tab = ids[(index + step + ids.length) % ids.length]
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
    cycleTab(direction)
    return false
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
  onTabChanged: if (host) host.notifyTab(tab)
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

      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.cycleTab(direction) }
      onActivateRequested: root.takeNext()
      onTextKey: function(t) {
        var key = t.toLowerCase()
        if (key === "1") root.tab = "morning"
        else if (key === "2") root.tab = "evening"
        else if (key === "3") root.tab = "night"
        else if (key === "4") root.tab = "emergency"
        else if (key === "t") root.takeNext()
        else if (key === "r") if (root.host) root.host.refresh()
        else if (key === "e") if (root.host) root.host.openDashboard()
        else if (key === "a") if (root.host) root.host.addMedicine()
        else if (key === "f") if (root.host) root.host.refill("")
      }

      Flickable {
        id: scroll
        anchors.fill: parent
        contentWidth: column.width
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height

        Column {
          id: column
          width: scroll.width
          spacing: Style.space(14)

          // ---- Header: the one number all four tabs feed. --------------
          Item {
            width: parent.width
            height: Math.max(hero.implicitHeight, headline.implicitHeight, share.implicitHeight)

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
                  text: String(root.payload.taken !== undefined ? root.payload.taken : 0)
                  color: root.contentForeground
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
              height: Style.space(12)

              Rectangle {
                id: track
                anchors.fill: parent
                radius: height / 2
                color: Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.12)
              }

              Rectangle {
                anchors.left: track.left
                anchors.verticalCenter: track.verticalCenter
                height: track.height
                radius: track.radius
                width: track.width * root.progress
                color: root.statusColor

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

          // ---- The four windows of the day. ----------------------------
          Row {
            id: tabRow
            width: parent.width
            spacing: Style.space(6)

            Repeater {
              model: root.tabList

              Item {
                id: tabItem
                required property var modelData

                readonly property bool selected: root.tab === tabItem.modelData.id
                readonly property color accent: String(tabItem.modelData.color || "#64748b")
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
                    color: Util.alpha(tabItem.accent, tabItem.selected ? 0.95 : 0.30)

                    Text {
                      id: countLabel
                      anchors.centerIn: parent
                      textFormat: Text.PlainText
                      text: tabItem.openCount > 0 ? String(tabItem.openCount) : String(tabItem.count)
                      color: tabItem.selected ? "#0d1016" : root.dim
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
                  height: Style.space(3)
                  radius: height / 2
                  color: tabItem.selected ? tabItem.accent : "transparent"

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
            text: tabHeading()
            foreground: root.contentForeground
            fontFamily: root.contentFontFamily
          }

          Text {
            visible: root.tab === "emergency" && root.tabDoses.length > 0
            width: parent.width
            textFormat: Text.PlainText
            text: "As-needed and every-N-days medicines live here, whatever the hour."
            color: root.dim
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.caption
          }

          Column {
            width: parent.width
            spacing: Style.space(9)

            Repeater {
              model: root.tabDoses

              DoseCard {
                required property var modelData
                width: parent.width
                dose: modelData
                host: root.host
                foreground: root.contentForeground
                fontFamily: root.contentFontFamily
              }
            }
          }

          Text {
            visible: root.tabDoses.length === 0
            width: parent.width
            wrapMode: Text.WordWrap
            textFormat: Text.PlainText
            text: root.payload.wizard === false
              ? "Setup is pending — enter your pill counts to switch reminders on."
              : "Nothing scheduled in this window."
            color: root.dim
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.body
          }

          // ---- Stock that is running out, wherever it lives. -----------
          Column {
            width: parent.width
            spacing: Style.space(9)
            visible: root.lowMedicines.length > 0

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
                color: Util.alpha("#ef4444", 0.10)
                borderSpec: Border.flat(Util.alpha("#ef4444", 0.55), Math.max(1, Style.normalBorderWidth))

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
                    tint: String(modelData.color || "#ef4444")
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
                      tint: "#ef4444"
                      filled: modelData.out
                      fontFamily: root.contentFontFamily
                      clickable: false
                    }

                    ChipButton {
                      text: "refill at " + modelData.refillAt
                      tint: "#64748b"
                      fontFamily: root.contentFontFamily
                      clickable: false
                    }

                    ChipButton {
                      text: "Refill"
                      tint: "#f59e0b"
                      filled: modelData.out
                      fontFamily: root.contentFontFamily
                      onClicked: if (root.host) root.host.refill(modelData.name)
                    }

                    ChipButton {
                      text: "Edit"
                      tint: "#3b82f6"
                      fontFamily: root.contentFontFamily
                      onClicked: if (root.host) root.host.editMedicine(modelData.name)
                    }

                    ChipButton {
                      text: "Delete"
                      tint: "#f87171"
                      fontFamily: root.contentFontFamily
                      onClicked: if (root.host) root.host.deleteMedicine(modelData.name)
                    }
                  }
                }
              }
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
                text: "＋ Add medicine"
                tint: "#7c3aed"
                filled: true
                fontFamily: root.contentFontFamily
                onClicked: if (root.host) root.host.addMedicine()
              }

              ChipButton {
                text: "↻ Refill"
                tint: "#f59e0b"
                fontFamily: root.contentFontFamily
                onClicked: if (root.host) root.host.refill("")
              }

              ChipButton {
                text: "Refresh"
                tint: "#38bdf8"
                fontFamily: root.contentFontFamily
                onClicked: if (root.host) root.host.refresh()
              }

              ChipButton {
                text: "Dashboard"
                tint: "#a78bfa"
                fontFamily: root.contentFontFamily
                onClicked: if (root.host) root.host.openDashboard()
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
    var a7 = root.payload.adherence7
    var a30 = root.payload.adherence30
    var text = "7d " + (a7 === null || a7 === undefined ? "—" : a7 + "%")
      + " · 30d " + (a30 === null || a30 === undefined ? "—" : a30 + "%")
    if (root.payload.taken === root.payload.total && root.payload.total > 0)
      text += " · all done"
    return text
  }
}
