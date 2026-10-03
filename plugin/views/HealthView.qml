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

  readonly property var adherence: health.adherence || ({})
  readonly property var effects: health.sideEffects || ({})
  readonly property var vitals: health.vitals || ({})
  readonly property var refills: health.refills || ({})

  readonly property color dim: Qt.darker(root.foreground, 1.5)
  readonly property color dim2: Qt.darker(root.foreground, 2.0)

  function effectColor(severity) {
    if (severity === "severe") return "#ef4444"
    if (severity === "moderate") return "#f59e0b"
    return "#38bdf8"
  }

  function healthNumber(value, suffix) {
    if (value === null || value === undefined || value === "") return "—"
    return String(value) + (suffix || "")
  }

  Block {
    width: parent.width
    title: "ADHERENCE"
    meta: String(adherence.threshold || 80) + "% TARGET"
    tint: Number(adherence.weekly && adherence.weekly.below ? 1 : 0) ? "#ef4444" : "#22c55e"

    Row {
      width: parent.width
      spacing: Style.space(18)

      Column {
        spacing: Style.space(2)

        Text {
          textFormat: Text.PlainText
          text: String(adherence.weekly ? adherence.weekly.label : "—")
          color: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.display
          font.bold: true
        }

        Text {
          textFormat: Text.PlainText
          text: "LAST 7 DAYS"
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
          text: adherence.streak ? String(adherence.streak.label) : "—"
          color: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.title
          font.bold: true
        }

        Text {
          textFormat: Text.PlainText
          text: "STREAK"
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
          text: adherence.monthly ? String(adherence.monthly.label) : "—"
          color: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.title
          font.bold: true
        }

        Text {
          textFormat: Text.PlainText
          text: "LAST 30 DAYS"
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          font.bold: true
          font.letterSpacing: 1.1
        }
      }
    }

    Row {
      width: parent.width
      height: Style.space(72)
      spacing: Style.space(6)

      Repeater {
        model: adherence.weekly ? adherence.weekly.days : []

        delegate: Item {
          id: dayBar
          required property var modelData
          width: (parent.width - Style.space(6) * 6) / 7
          height: parent.height

          Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: parent.height
            radius: Style.cornerRadius
            color: Util.alpha(root.foreground, 0.08)
          }

          Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: parent.height * Math.max(0, Math.min(1, Number(dayBar.modelData.pct || 0) / 100))
            radius: Style.cornerRadius
            color: String(dayBar.modelData.color || "#64748b")
          }

          Text {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: Style.space(4)
            textFormat: Text.PlainText
            text: String(dayBar.modelData.weekday || "")
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            font.bold: true
          }
        }
      }
    }

    Text {
      width: parent.width
      wrapMode: Text.WordWrap
      textFormat: Text.PlainText
      text: adherence.weekly && adherence.weekly.below
        ? "Below target — a nudge fires each morning until it recovers."
        : (adherence.monthly
            ? String(adherence.monthly.missed || 0) + " dose(s) missed in 30 days · "
              + String(adherence.monthly.belowDays || 0) + " day(s) under target"
            : "")
      color: adherence.weekly && adherence.weekly.below ? "#ef4444" : root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
      font.bold: adherence.weekly && adherence.weekly.below
    }
  }

  Block {
    width: parent.width
    title: "VITALS"
    meta: String((vitals.chart && vitals.chart.count) || 0) + " READINGS · 14 DAYS"
    tint: "#38bdf8"

    Text {
      width: parent.width
      visible: !vitals.chart || Number(vitals.chart.count || 0) === 0
      textFormat: Text.PlainText
      text: "No readings yet — medkit --vital add bp 120/80"
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
    }

    Repeater {
      model: vitals.summary ? vitals.summary.types : []

      delegate: Text {
        id: vitalRow
        required property var modelData
        width: parent.width
        textFormat: Text.PlainText
        text: String(vitalRow.modelData.label || "")
          + "   latest " + root.healthNumber(vitalRow.modelData.latest)
          + (vitalRow.modelData.latest2 !== undefined && vitalRow.modelData.latest2 !== null
              ? "/" + root.healthNumber(vitalRow.modelData.latest2) : "")
          + " " + String(vitalRow.modelData.unit || "")
          + "   ·  avg " + root.healthNumber(vitalRow.modelData.avg)
          + (vitalRow.modelData.avg2 !== undefined && vitalRow.modelData.avg2 !== null
              ? "/" + root.healthNumber(vitalRow.modelData.avg2) : "")
          + "  ·  " + String(vitalRow.modelData.count || 0) + "x"
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        font.bold: true
      }
    }

    Text {
      width: parent.width
      visible: vitals.correlation !== undefined && Number(vitals.correlation.readings || []).length > 0
      wrapMode: Text.WordWrap
      textFormat: Text.PlainText
      text: vitals.correlation
        ? String(vitals.correlation.linked || 0) + " reading(s) matched to a dose within "
          + String(vitals.correlation.windowHours || 4) + "h, "
          + String(vitals.correlation.unlinked || 0) + " not matched"
        : ""
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
    }

    Repeater {
      model: vitals.correlation ? vitals.correlation.readings : []

      delegate: Column {
        id: reading
        required property var modelData
        visible: index < 6
        width: parent.width
        spacing: Style.space(2)

        Text {
          width: parent.width
          textFormat: Text.PlainText
          text: String(reading.modelData.clock || "") + "  "
            + String(reading.modelData.label || reading.modelData.kind || "")
            + "  " + String(reading.modelData.value || "")
            + (reading.modelData.value2 !== undefined && reading.modelData.value2 !== null
                ? "/" + String(reading.modelData.value2) : "")
            + " " + String(reading.modelData.unit || "")
          color: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
          font.bold: true
        }

        Text {
          width: parent.width
          wrapMode: Text.WordWrap
          textFormat: Text.PlainText
          text: reading.modelData.doses && reading.modelData.doses.length > 0
            ? "→ " + (function() {
                var parts = []
                for (var i = 0; i < reading.modelData.doses.length; i++) {
                  var dose = reading.modelData.doses[i]
                  var gap = Number(dose.minutes || 0)
                  parts.push(String(dose.medicine) + " " + (gap >= 0 ? "+" : "") + gap + "m")
                }
                return parts.join("  ·  ")
              })()
            : "→ no dose within the window"
          color: (reading.modelData.doses && reading.modelData.doses.length > 0) ? "#22c55e" : root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
        }
      }
    }
  }

  Block {
    width: parent.width
    title: "SIDE EFFECTS"
    meta: String(effects.count || 0) + " IN 30 DAYS"
    tint: Number((effects.repeats || []).length) > 0 ? "#ef4444" : "#a78bfa"

    Repeater {
      model: effects.repeats || []

      delegate: Column {
        id: repeat
        required property var modelData
        width: parent.width
        spacing: Style.space(2)

        Text {
          width: parent.width
          wrapMode: Text.WordWrap
          textFormat: Text.PlainText
          text: "REPEAT ×" + String(repeat.modelData.count || 0) + "  "
            + String(repeat.modelData.effect || "") + " with " + String(repeat.modelData.medicine || "")
          color: root.effectColor(String(repeat.modelData.worst || "mild"))
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
          font.bold: true
        }

        Text {
          width: parent.width
          wrapMode: Text.WordWrap
          textFormat: Text.PlainText
          text: String(repeat.modelData.dose || "") + "  ·  first "
            + String(repeat.modelData.first || "") + "  ·  worst "
            + String(repeat.modelData.worst || "")
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
        }
      }
    }

    Repeater {
      model: effects.recent || []

      delegate: Text {
        id: effectRow
        required property var modelData
        width: parent.width
        wrapMode: Text.WordWrap
        textFormat: Text.PlainText
        text: "[" + String(effectRow.modelData.severity || "").toUpperCase() + "] "
          + String(effectRow.modelData.date || "") + "  "
          + String(effectRow.modelData.medicine || "")
          + " — " + String(effectRow.modelData.effect || "")
        color: root.effectColor(String(effectRow.modelData.severity || "mild"))
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
      }
    }

    Text {
      width: parent.width
      visible: Number(effects.count || 0) === 0
      textFormat: Text.PlainText
      text: "Nothing logged in the last 30 days."
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
    }

    Text {
      width: parent.width
      wrapMode: Text.WordWrap
      textFormat: Text.PlainText
      text: "Log one: medkit --side-effect \"Medicine\" \"effect\" mild|moderate|severe"
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      font.bold: true
    }
  }

  Block {
    width: parent.width
    title: "SUPPLY"
    meta: String(refills.countWarn || 0) + " NEED A REFILL"
    tint: Number(refills.countWarn || 0) > 0 ? "#f59e0b" : "#22c55e"

    Repeater {
      model: refills.medicines || []

      delegate: Row {
        id: stock
        required property var modelData
        width: parent.width
        spacing: Style.space(8)

        Text {
          anchors.verticalCenter: parent.verticalCenter
          width: parent.width - chips.width - Style.space(8)
          textFormat: Text.PlainText
          text: String(stock.modelData.name || "")
            + "  " + String(stock.modelData.stock || 0) + " left"
            + (stock.modelData.daysLeft !== null && stock.modelData.daysLeft !== undefined
                ? " · " + String(stock.modelData.daysLeft) + "d @ " + String(stock.modelData.perDay) + "/day"
                : "")
          elide: Text.ElideRight
          color: stock.modelData.out ? "#ef4444" : root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
          font.bold: true
        }

        Row {
          id: chips
          anchors.verticalCenter: parent.verticalCenter
          spacing: Style.space(6)

          ChipButton {
            visible: stock.modelData.out === true
            text: "OUT"
            tint: "#ef4444"
            filled: true
            fontFamily: root.fontFamily
            clickable: false
          }

          ChipButton {
            visible: stock.modelData.warn === true && stock.modelData.out !== true
            text: "runs out " + String(stock.modelData.runOut || "")
            tint: "#f59e0b"
            fontFamily: root.fontFamily
            clickable: false
          }

          ChipButton {
            text: "Refill"
            tint: "#f59e0b"
            fontFamily: root.fontFamily
            onClicked: if (root.host) root.host.refill(stock.modelData.name)
          }
        }
      }
    }

    Text {
      width: parent.width
      visible: (refills.medicines || []).length === 0
      textFormat: Text.PlainText
      text: "No pill counts recorded yet."
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
    }

    Row {
      width: parent.width
      spacing: Style.space(8)

      Text {
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width - pharmacyChip.width - Style.space(8)
        textFormat: Text.PlainText
        text: refills.pharmacy && refills.pharmacy.phone
          ? "Pharmacy: " + String(refills.pharmacy.name || "") + " " + String(refills.pharmacy.phone)
          : "No pharmacy saved on the emergency card."
        elide: Text.ElideRight
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
      }

      ChipButton {
        id: pharmacyChip
        visible: refills.pharmacy !== undefined && Boolean(refills.pharmacy.phone)
        text: "Call pharmacy"
        tint: "#38bdf8"
        fontFamily: root.fontFamily
        onClicked: if (root.host) root.host.callPharmacy()
      }
    }
  }
}
