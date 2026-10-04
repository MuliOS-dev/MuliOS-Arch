import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root
    width: 1920
    height: 1080
    color: "#0b0d0c"

    Image {
        anchors.fill: parent
        source: "file:///usr/share/backgrounds/mulios/wallpaper.jpg"
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        opacity: 0.38
    }

    Rectangle {
        anchors.fill: parent
        color: "#0b0d0c"
        opacity: 0.48
    }

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width * 0.34, 430)
        spacing: 14

        Text {
            Layout.alignment: Qt.AlignHCenter
            text: "MuliOS"
            color: "white"
            font.pixelSize: 42
            font.weight: Font.DemiBold
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            text: "Sign in"
            color: "#b8c0bc"
            font.pixelSize: 16
        }

        ComboBox {
            id: userBox
            Layout.fillWidth: true
            model: userModel
            textRole: "name"
            currentIndex: userModel.lastIndex >= 0 ? userModel.lastIndex : 0
            font.pixelSize: 15

            contentItem: Text {
                leftPadding: 12
                rightPadding: 12
                verticalAlignment: Text.AlignVCenter
                text: userBox.currentText
                color: "#f5f5f5"
                elide: Text.ElideRight
            }

            background: Rectangle {
                radius: 8
                color: "#151917"
                border.color: "#3b443f"
                border.width: 1
            }

            popup: Popup {
                y: userBox.height + 4
                width: userBox.width
                padding: 4

                contentItem: ListView {
                    implicitHeight: Math.min(contentHeight, 240)
                    clip: true
                    model: userBox.popup.visible ? userModel : null
                    currentIndex: userBox.currentIndex

                    delegate: ItemDelegate {
                        width: ListView.view.width
                        height: 38
                        highlighted: ListView.isCurrentItem
                        text: model.name
                        onClicked: {
                            userBox.currentIndex = index
                            userBox.popup.close()
                        }
                    }
                }

                background: Rectangle {
                    radius: 8
                    color: "#151917"
                    border.color: "#3b443f"
                    border.width: 1
                }
            }
        }

        TextField {
            id: password
            Layout.fillWidth: true
            placeholderText: "Password"
            echoMode: TextInput.Password
            selectByMouse: true
            font.pixelSize: 15
            onAccepted: login()

            background: Rectangle {
                radius: 8
                color: "#151917"
                border.color: "#3b443f"
                border.width: 1
            }
        }

        ComboBox {
            id: sessionBox
            Layout.fillWidth: true
            model: sessionModel
            textRole: "name"
            currentIndex: sessionModel.lastIndex >= 0 ? sessionModel.lastIndex : 0
            font.pixelSize: 15

            contentItem: Text {
                leftPadding: 12
                rightPadding: 12
                verticalAlignment: Text.AlignVCenter
                text: sessionBox.currentText
                color: "#f5f5f5"
                elide: Text.ElideRight
            }

            background: Rectangle {
                radius: 8
                color: "#151917"
                border.color: "#3b443f"
                border.width: 1
            }

            popup: Popup {
                y: sessionBox.height + 4
                width: sessionBox.width
                padding: 4

                contentItem: ListView {
                    implicitHeight: Math.min(contentHeight, 240)
                    clip: true
                    model: sessionBox.popup.visible ? sessionModel : null
                    currentIndex: sessionBox.currentIndex

                    delegate: ItemDelegate {
                        width: ListView.view.width
                        height: 38
                        highlighted: ListView.isCurrentItem
                        text: model.name
                        onClicked: {
                            sessionBox.currentIndex = index
                            sessionBox.popup.close()
                        }
                    }
                }

                background: Rectangle {
                    radius: 8
                    color: "#151917"
                    border.color: "#3b443f"
                    border.width: 1
                }
            }
        }

        Text {
            visible: userModel.count < 1 || sessionModel.count < 1
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            color: "#e58b8b"
            text: userModel.count < 1
                ? "No user account is available."
                : "No Plasma session is available."
        }

        Button {
            Layout.fillWidth: true
            text: "Sign in"
            font.pixelSize: 15
            onClicked: login()
        }

        Text {
            id: message
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            color: "#e58b8b"
            text: ""
            visible: text.length > 0
        }
    }

    Row {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 24
        spacing: 10

        Button {
            text: "Restart"
            visible: sddm.canReboot
            onClicked: sddm.reboot()
        }

        Button {
            text: "Shut down"
            visible: sddm.canPowerOff
            onClicked: sddm.powerOff()
        }
    }

    function login() {
        if (userModel.count < 1) {
            message.text = "No user account is available."
            return
        }
        if (sessionModel.count < 1) {
            message.text = "No desktop session is available."
            return
        }

        message.text = ""
        sddm.login(
            userBox.currentText,
            password.text,
            sessionBox.currentIndex
        )
    }

    Connections {
        target: sddm

        function onLoginFailed() {
            message.text = "Login failed."
            password.selectAll()
            password.forceActiveFocus()
        }
    }

    Component.onCompleted: {
        if (userModel.count > 0)
            userBox.currentIndex = userModel.lastIndex >= 0 ? userModel.lastIndex : 0

        if (sessionModel.count > 0)
            sessionBox.currentIndex = sessionModel.lastIndex >= 0 ? sessionModel.lastIndex : 0

        password.forceActiveFocus()
    }
}
