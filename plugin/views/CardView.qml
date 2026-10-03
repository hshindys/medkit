import QtQuick
import qs.Commons
import qs.Ui
import ".."

Column {
  id: root

  property var card: ({})
  property var host: null
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family
  property bool hero: false

  readonly property var numbers: card.numbers || []
  readonly property var meds: card.medicines || []
  readonly property var allergies: card.allergies || []
  readonly property var conditions: card.conditions || []
  readonly property color dim: Qt.darker(root.foreground, 1.5)
  readonly property color dim2: Qt.darker(root.foreground, 2.0)
  readonly property color danger: "#ef4444"

  spacing: Style.space(10)

  Item {
    width: parent.width
    height: Math.max(bloodPill.height, identity.implicitHeight)

    BorderSurface {
      id: bloodPill
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      implicitWidth: bloodText.implicitWidth + Style.space(28)
      implicitHeight: bloodText.implicitHeight + Style.space(16)
      radius: Style.cornerRadius
      color: Util.alpha(root.danger, 0.18)
      borderSpec: Border.flat(root.danger, Math.max(2, Style.normalBorderWidth))

      Text {
        id: bloodText
        anchors.centerIn: parent
        textFormat: Text.PlainText
        text: String(card.bloodType || "unknown").toUpperCase()
        color: root.danger
        font.family: root.fontFamily
        font.pixelSize: root.hero ? Style.font.display : Style.font.heading
        font.bold: true
      }
    }

    Column {
      id: identity
      anchors.left: bloodPill.right
      anchors.leftMargin: Style.space(14)
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      spacing: Style.space(3)

      Text {
        width: parent.width
        textFormat: Text.PlainText
        text: String(card.name || "Name not recorded")
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: root.hero ? Style.font.title : Style.font.subtitle
        font.bold: true
        elide: Text.ElideRight
      }

      Text {
        width: parent.width
        textFormat: Text.PlainText
        text: [
          card.birthDate ? "born " + String(card.birthDate) : "",
          card.updatedDate ? "updated " + String(card.updatedDate) : "",
          "offline"
        ].filter(function(part) { return part !== "" }).join("  ·  ")
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        elide: Text.ElideRight
      }
    }
  }

  Block {
    width: parent.width
    title: "ALLERGIES"
    meta: String(allergies.length) + " RECORDED"
    tint: allergies.length > 0 ? root.danger : "#64748b"

    Text {
      width: parent.width
      wrapMode: Text.WordWrap
      textFormat: Text.PlainText
      text: allergies.length > 0
        ? allergies.join("  ·  ")
        : "None recorded — say so only if you have checked."
      color: allergies.length > 0 ? root.danger : root.dim2
      font.family: root.fontFamily
      font.pixelSize: root.hero ? Style.font.title : Style.font.body
      font.bold: allergies.length > 0
    }
  }

  Block {
    width: parent.width
    title: "CHRONIC CONDITIONS"
    visible: conditions.length > 0
    tint: "#f59e0b"

    Text {
      width: parent.width
      wrapMode: Text.WordWrap
      textFormat: Text.PlainText
      text: conditions.join("  ·  ")
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: root.hero ? Style.font.title : Style.font.body
      font.bold: true
    }
  }

  Block {
    width: parent.width
    title: "MEDICAL STATUS"
    visible: String(card.status || "none") !== "none"
    tint: "#a78bfa"

    Text {
      width: parent.width
      textFormat: Text.PlainText
      text: String(card.status || "")
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: root.hero ? Style.font.title : Style.font.body
      font.bold: true
    }
  }

  Block {
    width: parent.width
    title: "CURRENT MEDICATIONS"
    meta: String(meds.length) + " ACTIVE"
    tint: "#3b82f6"

    Repeater {
      model: meds

      delegate: Text {
        id: med
        required property var modelData
        width: parent.width
        wrapMode: Text.WordWrap
        textFormat: Text.PlainText
        text: (med.modelData.emergency ? "✦ " : "· ")
          + String(med.modelData.name || "")
          + (med.modelData.dose ? "  " + String(med.modelData.dose) : "")
          + (med.modelData.times ? "  @ " + String(med.modelData.times) : "")
        color: med.modelData.emergency ? root.danger : root.foreground
        font.family: root.fontFamily
        font.pixelSize: root.hero ? Style.font.body : Style.font.body
        font.bold: Boolean(med.modelData.emergency)
      }
    }

    Text {
      width: parent.width
      visible: meds.length === 0
      textFormat: Text.PlainText
      text: "Nothing on the list."
      color: root.dim2
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
    }
  }

  Block {
    width: parent.width
    title: "CONTACTS"
    meta: String(numbers.length) + " NUMBERS"
    tint: "#22c55e"

    Repeater {
      model: numbers

      delegate: Row {
        id: contact
        required property var modelData
        width: parent.width
        spacing: Style.space(8)

        Text {
          anchors.verticalCenter: parent.verticalCenter
          width: parent.width - callButton.width - Style.space(8)
          textFormat: Text.PlainText
          text: String(contact.modelData.label || "")
            + (contact.modelData.name ? " — " + String(contact.modelData.name) : "")
            + "  " + String(contact.modelData.phone || "")
          elide: Text.ElideRight
          color: String(contact.modelData.tint || root.foreground)
          font.family: root.fontFamily
          font.pixelSize: root.hero ? Style.font.body : Style.font.body
          font.bold: true
        }

        ChipButton {
          id: callButton
          anchors.verticalCenter: parent.verticalCenter
          text: "Call"
          tint: String(contact.modelData.tint || "#22c55e")
          fontFamily: root.fontFamily
          onClicked: if (root.host) root.host.callTarget(String(contact.modelData.label || ""))
        }
      }
    }
  }

  Row {
    width: parent.width
    spacing: Style.space(8)

    ChipButton {
      text: "Wallet card (.txt)"
      tint: "#22c55e"
      filled: true
      fontFamily: root.fontFamily
      onClicked: if (root.host) root.host.exportCard("txt")
    }

    ChipButton {
      text: "PDF"
      tint: "#22c55e"
      fontFamily: root.fontFamily
      onClicked: if (root.host) root.host.exportCard("pdf")
    }

    ChipButton {
      text: "Edit profile"
      tint: "#7c3aed"
      fontFamily: root.fontFamily
      onClicked: if (root.host) root.host.openDashboard()
    }

    ChipButton {
      text: "Refresh"
      tint: "#38bdf8"
      fontFamily: root.fontFamily
      onClicked: if (root.host) root.host.refresh()
    }
  }

  Text {
    width: parent.width
    wrapMode: Text.WordWrap
    textFormat: Text.PlainText
    text: String(card.disclaimer || "This is not medical advice.")
    color: root.dim
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
  }
}
