import QtQuick
import qs.Commons
import qs.Ui
import ".."

Column {
  id: root

  property var health: ({})
  property var host: null
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family

  spacing: Style.space(10)

  readonly property var reviewData: health.review || ({})
  readonly property var reports: health.reports || ({})
  readonly property var duplicates: reviewData.duplicates || []

  readonly property color dim: Qt.darker(root.foreground, 1.5)
  readonly property color dim2: Qt.darker(root.foreground, 2.0)

  function severityColor(severity) {
    if (severity === "severe" || severity === "contraindicated") return "#ef4444"
    if (severity === "moderate" || severity === "avoid") return "#f59e0b"
    return "#38bdf8"
  }

  Block {
    width: parent.width
    title: "MEDICATION REVIEW"
    meta: reviewData.due ? "DUE NOW" : "SCHEDULED"
    tint: reviewData.due ? "#f59e0b" : "#22c55e"

    Row {
      width: parent.width
      spacing: Style.space(24)

      Column {
        spacing: Style.space(2)

        Text {
          textFormat: Text.PlainText
          text: String(reviewData.lastLabel || "never")
          color: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.title
          font.bold: true
        }

        Text {
          textFormat: Text.PlainText
          text: "LAST REVIEW"
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          font.bold: true
          font.letterSpacing: 1.1
        }
      }

      Column {
        spacing: Style.space(2)

        Text {
          textFormat: Text.PlainText
          text: String(reviewData.nextLabel || "never")
          color: reviewData.due ? "#f59e0b" : root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.title
          font.bold: true
        }

        Text {
          textFormat: Text.PlainText
          text: "NEXT REVIEW"
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          font.bold: true
          font.letterSpacing: 1.1
        }
      }

      Column {
        spacing: Style.space(2)

        Text {
          textFormat: Text.PlainText
          text: "every " + String(reviewData.intervalMonths || 3) + " months"
          color: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.subtitle
          font.bold: true
        }

        Text {
          textFormat: Text.PlainText
          text: "INTERVAL"
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          font.bold: true
          font.letterSpacing: 1.1
        }
      }
    }

    Repeater {
      model: duplicates

      delegate: Text {
        id: dup
        required property var modelData
        width: parent.width
        wrapMode: Text.WordWrap
        textFormat: Text.PlainText
        text: "[" + String(dup.modelData.severityLabel || "").toUpperCase() + "] "
          + String(dup.modelData.text || "")
        color: root.severityColor(String(dup.modelData.severity || "mild"))
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        font.bold: true
      }
    }

    Text {
      width: parent.width
      visible: duplicates.length === 0
      textFormat: Text.PlainText
      text: "No duplicate therapy found on the list."
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
    }

    Row {
      width: parent.width
      spacing: Style.space(8)

      ChipButton {
        text: "Export PDF"
        tint: "#7c3aed"
        filled: true
        fontFamily: root.fontFamily
        onClicked: if (root.host) root.host.reviewExport()
      }

      ChipButton {
        text: "Reviewed today"
        tint: "#22c55e"
        fontFamily: root.fontFamily
        onClicked: if (root.host) root.host.reviewDone()
      }
    }
  }

  Block {
    width: parent.width
    title: "WEEKLY REPORT"
    meta: "LAST 7 DAYS"
    tint: "#3b82f6"

    Repeater {
      model: reports.weekly ? reports.weekly.lines : []

      delegate: Text {
        id: line
        required property var modelData
        width: parent.width
        textFormat: Text.PlainText
        text: String(line.modelData || "")
        color: String(line.modelData || "").indexOf("##") === 0
          ? root.foreground
          : (String(line.modelData || "").indexOf("BELOW") >= 0
              || String(line.modelData || "").indexOf("OUT") >= 0 ? "#ef4444" : root.dim2)
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        font.bold: String(line.modelData || "").indexOf("##") === 0
      }
    }
  }

  Block {
    width: parent.width
    title: "MONTHLY REPORT"
    meta: "LAST 30 DAYS"
    tint: "#a78bfa"

    Repeater {
      model: reports.monthly ? reports.monthly.lines : []

      delegate: Text {
        id: mline
        required property var modelData
        width: parent.width
        textFormat: Text.PlainText
        text: String(mline.modelData || "")
        color: String(mline.modelData || "").indexOf("##") === 0
          ? root.foreground
          : (String(mline.modelData || "").indexOf("REPEAT") >= 0 ? "#ef4444" : root.dim2)
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        font.bold: String(mline.modelData || "").indexOf("##") === 0
      }
    }
  }

  Block {
    width: parent.width
    title: "SOURCES"
    meta: String(health.updated || "")
    tint: "#64748b"

    Text {
      width: parent.width
      wrapMode: Text.WordWrap
      textFormat: Text.PlainText
      text: (health.sources || []).map(function(source) { return "· " + source }).join("\n")
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      lineHeight: 1.35
    }

    Text {
      width: parent.width
      wrapMode: Text.WordWrap
      textFormat: Text.PlainText
      text: String(health.disclaimer || "This is not medical advice.")
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      font.bold: true
    }
  }
}
