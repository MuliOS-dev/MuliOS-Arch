import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Effects

Rectangle {
    id: root
    width: 1920
    height: 1080
    color: "#070908"

    Image {
        id: wallpaper
        anchors.fill: parent
        source: "file:///usr/share/backgrounds/mulios/wallpaper.png"
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        visible: false
    }

    MultiEffect {
        anchors.fill: parent
        source: wallpaper
        blurEnabled: true
        blur: 1.0
        blurMax: 32
        brightness: -0.18
        saturation: 0.82
        opacity: 0.72
    }

    Rectangle {
        anchors.fill: parent
        color: "#070908"
        opacity: 0.42
    }

    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.color: "#18ffffff"
        border.width: 1
    }

    Rectangle {
        id: loginCard
        anchors.centerIn: parent
        width: Math.min(parent.width * 0.38, 520)
        height: 620
        radius: 34
        color: "#b9141816"
        border.color: "#35ffffff"
        border.width: 1

        layer.enabled: true
        layer.smooth: true

        ColumnLayout {
            anchors.fill: parent
            anchors.leftMargin: 52
            anchors.rightMargin: 52
            anchors.topMargin: 42
            anchors.bottomMargin: 42
            spacing: 18

            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                width: 86
                height: 86
                radius: width / 2
                color: "#d91a211d"
                border.color: "#55ffffff"
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: userBox.currentText.length > 0
                        ? userBox.currentText.charAt(0).toUpperCase()
                        : "M"
                    color: "#ffffff"
                    font.pixelSize: 34
                    font.weight: Font.DemiBold
                }
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "MuliOS"
                color: "#ffffff"
                font.pixelSize: 32
                font.weight: Font.DemiBold
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "Welcome back"
                color: "#b9c2bd"
                font.pixelSize: 15
            }

            Item { Layout.preferredHeight: 2 }

            Text {
                Layout.fillWidth: true
                text: "Account"
                color: "#d7ddd9"
                font.pixelSize: 13
                font.weight: Font.Medium
            }

            ComboBox {
                id: userBox
                Layout.fillWidth: true
                Layout.preferredHeight: 54
                model: userModel
                textRole: "name"
                currentIndex: userModel.lastIndex >= 0 ? userModel.lastIndex : 0
                font.pixelSize: 15

                contentItem: Text {
                    leftPadding: 18
                    rightPadding: 48
                    verticalAlignment: Text.AlignVCenter
                    text: userBox.currentText
                    color: "#ffffff"
                    elide: Text.ElideRight
                }

                indicator: Text {
                    x: userBox.width - width - 18
                    y: (userBox.height - height) / 2
                    text: "⌄"
                    color: "#aeb8b2"
                    font.pixelSize: 18
                }

                background: Rectangle {
                    radius: 18
                    color: "#80171c19"
                    border.color: userBox.activeFocus ? "#63c98d" : "#38ffffff"
                    border.width: 1
                }

                popup: Popup {
                    y: userBox.height + 8
                    width: userBox.width
                    padding: 6

                    contentItem: ListView {
                        implicitHeight: Math.min(contentHeight, 260)
                        clip: true
                        model: userBox.popup.visible ? userModel : null
                        currentIndex: userBox.currentIndex

                        delegate: ItemDelegate {
                            width: ListView.view.width
                            height: 44
                            highlighted: ListView.isCurrentItem
                            text: model.name

                            contentItem: Text {
                                text: model.name
                                color: "#ffffff"
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: 12
                            }

                            background: Rectangle {
                                radius: 13
                                color: parent.highlighted ? "#3347a86d" : "transparent"
                            }

                            onClicked: {
                                userBox.currentIndex = index
                                userBox.popup.close()
                            }
                        }
                    }

                    background: Rectangle {
                        radius: 20
                        color: "#e0131715"
                        border.color: "#40ffffff"
                        border.width: 1
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                text: "Password"
                color: "#d7ddd9"
                font.pixelSize: 13
                font.weight: Font.Medium
            }

            TextField {
                id: password
                Layout.fillWidth: true
                Layout.preferredHeight: 54
                placeholderText: "Enter your password"
                echoMode: TextInput.Password
                selectByMouse: true
                font.pixelSize: 15
                color: "#ffffff"
                placeholderTextColor: "#82908a"
                leftPadding: 18
                rightPadding: 18
                onAccepted: login()

                background: Rectangle {
                    radius: 18
                    color: "#80171c19"
                    border.color: password.activeFocus ? "#63c98d" : "#38ffffff"
                    border.width: 1
                }
            }

            ComboBox {
                id: sessionBox
                Layout.fillWidth: true
                Layout.preferredHeight: 50
                model: sessionModel
                textRole: "name"
                currentIndex: sessionModel.lastIndex >= 0 ? sessionModel.lastIndex : 0
                font.pixelSize: 14

                contentItem: Text {
                    leftPadding: 18
                    rightPadding: 42
                    verticalAlignment: Text.AlignVCenter
                    text: sessionBox.currentText
                    color: "#cbd3ce"
                    elide: Text.ElideRight
                }

                background: Rectangle {
                    radius: 17
                    color: "#5e171c19"
                    border.color: "#30ffffff"
                    border.width: 1
                }
            }

            Button {
                id: signInButton
                Layout.fillWidth: true
                Layout.preferredHeight: 56
                text: "Sign in"
                font.pixelSize: 16
                font.weight: Font.DemiBold
                onClicked: login()

                contentItem: Text {
                    text: signInButton.text
                    color: "#061009"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font: signInButton.font
                }

                background: Rectangle {
                    radius: 19
                    color: signInButton.down
                        ? "#4fbd78"
                        : signInButton.hovered
                            ? "#72d99b"
                            : "#63c98d"
                    border.color: "#8ae6ae"
                    border.width: 1
                }
            }

            Text {
                id: message
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                color: "#ff9a9a"
                text: ""
                visible: text.length > 0
            }
        }
    }

    Row {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 28
        spacing: 10

        Button {
            id: restartButton
            text: "Restart"
            visible: sddm.canReboot
            onClicked: sddm.reboot()

            contentItem: Text {
                text: restartButton.text
                color: "#f0f4f1"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            background: Rectangle {
                radius: 16
                color: "#7a111512"
                border.color: "#35ffffff"
                border.width: 1
            }
        }

        Button {
            id: shutdownButton
            text: "Shut down"
            visible: sddm.canPowerOff
            onClicked: sddm.powerOff()

            contentItem: Text {
                text: shutdownButton.text
                color: "#f0f4f1"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            background: Rectangle {
                radius: 16
                color: "#7a111512"
                border.color: "#35ffffff"
                border.width: 1
            }
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

        if (password.text.length === 0) {
            message.text = "Enter your password."
            password.forceActiveFocus()
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
            message.text = "Login failed. Check your password."
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
