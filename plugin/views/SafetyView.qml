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

  readonly property color dim: Qt.darker(root.foreground, 1.5)
  readonly property color dim2: Qt.darker(root.foreground, 2.0)
  readonly property var interactions: health.interactions || ({})
  readonly property var foodData: health.food || ({})
  readonly property var pregnancyData: health.pregnancy || ({})
  readonly property var missedData: health.missed || ({})

  function severityColor(severity) {
    if (severity === "severe") return Theme.danger
    if (severity === "moderate") return Theme.accentDim
    return Theme.mild
  }

  Block {
    width: parent.width
    title: "DRUG INTERACTIONS"
    glyph: Theme.glyphSafety
    meta: String(interactions.count || 0) + " FOUND · " + String(interactions.worst || "none").toUpperCase()
    tint: Number(interactions.count || 0) > 0 ? severityColor(String(interactions.worst || "mild")) : Theme.stateOk
    heavy: String(interactions.worst || "") === "severe"

    Text {
      width: parent.width
      visible: Number(interactions.count || 0) === 0
      textFormat: Text.PlainText
      text: "No interaction found between the medicines on your list."
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
    }

    Repeater {
      model: interactions.items || []

      delegate: Column {
        id: finding
        required property var modelData
        width: parent.width
        spacing: Style.space(4)

        Row {
          width: parent.width
          spacing: Style.space(7)

          Text {
            anchors.verticalCenter: parent.verticalCenter
            textFormat: Text.PlainText
            text: "[" + String(finding.modelData.severityLabel || "").toUpperCase() + "]"
            color: root.severityColor(String(finding.modelData.severity || "mild"))
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            font.bold: true
          }

          Text {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - implicitWidth - Style.space(7) - kindTag.width - Style.space(7)
            textFormat: Text.PlainText
            text: String(finding.modelData.a || "")
              + (finding.modelData.aGeneric ? " (" + finding.modelData.aGeneric + ")" : "")
              + "  +  "
              + String(finding.modelData.b || "")
              + (finding.modelData.bGeneric ? " (" + finding.modelData.bGeneric + ")" : "")
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            font.bold: true
            elide: Text.ElideRight
          }

          Text {
            id: kindTag
            anchors.verticalCenter: parent.verticalCenter
            textFormat: Text.PlainText
            text: finding.modelData.nsaidBp ? "NSAID + BP" : ""
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            font.bold: true
          }
        }

        Text {
          width: parent.width
          wrapMode: Text.WordWrap
          textFormat: Text.PlainText
          text: String(finding.modelData.effect || "")
          color: root.dim2
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
        }

        Text {
          width: parent.width
          wrapMode: Text.WordWrap
          textFormat: Text.PlainText
          text: "→ " + String(finding.modelData.advice || "")
          color: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
          font.bold: true
        }

        Item {
          width: parent.width
          height: index < (interactions.items || []).length - 1 ? Style.space(10) : 0
        }
      }
    }
  }

  Block {
    width: parent.width
    title: "FOOD AND MEAL TIMING"
    glyph: Theme.glyphPill
    meta: String((foodData.medicines || []).length) + " MEDICINES"
    tint: Theme.accentDim

    Text {
      width: parent.width
      visible: (foodData.medicines || []).length === 0
      textFormat: Text.PlainText
      text: "No food guidance matched your list."
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
    }

    Repeater {
      model: foodData.medicines || []

      delegate: Column {
        id: foodRow
        required property var modelData
        width: parent.width
        spacing: Style.space(3)

        Text {
          width: parent.width
          textFormat: Text.PlainText
          text: String(foodRow.modelData.name || "")
            + (foodRow.modelData.generic ? "  (" + foodRow.modelData.generic + ")" : "")
          color: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
          font.bold: true
        }

        Text {
          width: parent.width
          visible: String(foodRow.modelData.timing || "") !== ""
          wrapMode: Text.WordWrap
          textFormat: Text.PlainText
          text: "when · " + String(foodRow.modelData.timing || "")
          color: Theme.stateOk
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
        }

        Repeater {
          model: foodRow.modelData.rules || []

          delegate: Text {
            id: ruleText
            required property var modelData
            width: parent.width
            wrapMode: Text.WordWrap
            textFormat: Text.PlainText
            text: "[" + String(ruleText.modelData.severityLabel || "").toUpperCase() + "] "
              + String(ruleText.modelData.label || "")
              + " — " + String(ruleText.modelData.tip || "")
            color: root.severityColor(String(ruleText.modelData.severity || "mild"))
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
          }
        }
      }
    }
  }

  Block {
    width: parent.width
    visible: pregnancyData.active === true && (pregnancyData.findings || []).length > 0
    title: "PREGNANCY · " + String(pregnancyData.statusLabel || "").toUpperCase()
    glyph: Theme.glyphHealth
    meta: String(pregnancyData.countFlagged || 0) + " TO AVOID"
    tint: Number(pregnancyData.countFlagged || 0) > 0 ? Theme.danger : Theme.mild

    Repeater {
      model: pregnancyData.findings || []

      delegate: Column {
        id: finding2
        required property var modelData
        width: parent.width
        spacing: Style.space(4)

        Row {
          width: parent.width
          spacing: Style.space(7)

          Text {
            anchors.verticalCenter: parent.verticalCenter
            textFormat: Text.PlainText
            text: "[" + String(finding2.modelData.riskLabel || "").toUpperCase() + "]"
            color: String(finding2.modelData.riskColor || Theme.accentDim)
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            font.bold: true
          }

          Text {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - implicitWidth - Style.space(7)
            textFormat: Text.PlainText
            text: String(finding2.modelData.name || "")
              + (finding2.modelData.generic ? " (" + finding2.modelData.generic + ")" : "")
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            font.bold: true
            elide: Text.ElideRight
          }
        }

        Text {
          width: parent.width
          wrapMode: Text.WordWrap
          textFormat: Text.PlainText
          text: String(finding2.modelData.note || "")
          color: root.dim2
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
        }

        Text {
          width: parent.width
          wrapMode: Text.WordWrap
          textFormat: Text.PlainText
          text: "Safer: " + String(finding2.modelData.alternative || "")
          color: Theme.stateOk
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
          font.bold: true
        }
      }
    }

    Text {
      width: parent.width
      wrapMode: Text.WordWrap
      textFormat: Text.PlainText
      text: String(pregnancyData.consult || "")
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
      font.bold: true
    }
  }

  Block {
    width: parent.width
    title: "MISSED DOSE PROTOCOL"
    glyph: Theme.glyphWarn
    meta: Number(missedData.count || 0) + " MISSED TODAY"
    tint: Number(missedData.count || 0) > 0 ? Theme.danger : Theme.fg3

    Repeater {
      model: missedData.missed || []

      delegate: Text {
        id: missedText
        required property var modelData
        width: parent.width
        textFormat: Text.PlainText
        text: "✗ " + String(missedText.modelData.clock || "")
          + " " + String(missedText.modelData.name || "")
          + " — " + String(missedText.modelData.minutesLate || 0) + " min late"
        color: Theme.danger
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        font.bold: true
      }
    }

    Text {
      width: parent.width
      visible: (missedData.missed || []).length === 0
      textFormat: Text.PlainText
      text: "Nothing missed today."
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
    }

    Repeater {
      model: missedData.protocols || []

      delegate: Column {
        id: proto
        required property var modelData
        width: parent.width
        spacing: Style.space(2)

        Text {
          width: parent.width
          textFormat: Text.PlainText
          text: String(proto.modelData.name || "")
            + "  ·  " + String(proto.modelData.sourceLabel || "")
          color: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          font.bold: true
          font.letterSpacing: 0.8
        }

        Text {
          width: parent.width
          wrapMode: Text.WordWrap
          textFormat: Text.PlainText
          text: String(proto.modelData.text || "")
          color: root.dim2
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
        }
      }
    }
  }
}
