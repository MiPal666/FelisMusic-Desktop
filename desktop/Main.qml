import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQml.Models

ApplicationWindow {
    id: root
    width: 1280
    height: 800
    minimumWidth: 900
    minimumHeight: 600
    visible: true
    title: "FelisMusic " + fcmVersion
    color: "#0c0c0c"

    property int currentPage: 1
    property string errorText: ""
    property string currentLibrarySection: "playlists"
    property string currentLibraryLabel: qsTr("Playlisty")
    property string currentLibraryOrder: ""
    property string lastUploadSection: "upload_albums"
    property string currentLikedOrder: ""
    property string currentSearchScope: "catalog"
    property string currentSearchMode: "all"
    property bool seekDragging: false
    property real seekPreview: 0
    property var playbackContext: null
    signal playingSourceRequested()

    onCurrentPageChanged: backend.clearTrackSelection()
    onCurrentLibrarySectionChanged: {
        if (["upload_albums", "upload_artists", "upload_songs"].indexOf(currentLibrarySection) >= 0)
            lastUploadSection = currentLibrarySection
    }

    function trackKeys(event, source) {
        if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                && backend.selectionSource === source) {
            backend.playSelectedTrack()
            event.accepted = true
        } else if (event.key === Qt.Key_A && (event.modifiers & Qt.ControlModifier)) {
            backend.selectAllTracks(source)
            event.accepted = true
        } else if (event.key === Qt.Key_Escape) {
            backend.clearTrackSelection()
            event.accepted = true
        }
    }

    function navigationContext() {
        return {
            page: currentPage,
            librarySection: currentLibrarySection,
            libraryLabel: currentLibraryLabel,
            libraryOrder: currentLibraryOrder,
            likedOrder: currentLikedOrder,
            searchScope: currentSearchScope,
            searchMode: currentSearchMode,
            searchText: searchField.text
        }
    }

    function capturePlaybackContext() {
        playbackContext = navigationContext()
        backend.setPlaybackSourceContext(playbackContext)
    }

    function restoreTrackNavigation(context) {
        if (context.librarySection !== undefined) {
            currentLibrarySection = context.librarySection || currentLibrarySection
            currentLibraryLabel = context.libraryLabel || currentLibraryLabel
            currentLibraryOrder = context.libraryOrder || ""
        }
        if (context.page === 0) {
            currentSearchScope = context.searchScope || currentSearchScope
            currentSearchMode = context.searchMode || currentSearchMode
            searchField.text = context.searchText || ""
        }
        if (context.page === 2) currentLikedOrder = context.likedOrder || ""
        if (context.page !== undefined) currentPage = context.page
    }

    function pageSelected(index) {
        currentPage = index
        if (index === 5) {
            Qt.callLater(root.revealQueueRow)
            return
        }
        backend.clearDetail()
        if (index === 1 && backend.libraryItemsModel.count === 0)
            backend.loadLibrarySection(currentLibrarySection, currentLibraryOrder)
        // Oblíbená hudba je živý seznam. Po like/unlike ji při každém
        // vstupu obnovíme z YTM, aby nově označené/odebrané skladby seděly.
        if (index === 2) backend.loadLiked()
        if (index === 3 && backend.historyModel.count === 0) backend.loadHistory()
        if (index === 4 && backend.mixesModel.count === 0) backend.loadMixes()
    }

    function selectLibrarySection(section, label) {
        currentPage = 1
        currentLibrarySection = section
        currentLibraryLabel = label

        // Playlisty mají skutečné výchozí pořadí YTM. U ostatních
        // kategorií používáme jen explicitní pořadí podporované API;
        // order="" se po předchozím sortu nechoval jako spolehlivý reset.
        if (section === "playlists" && currentLibraryOrder === "recently_added")
            currentLibraryOrder = ""
        else if (section !== "playlists" && currentLibraryOrder === "")
            currentLibraryOrder = "recently_added"

        backend.clearDetail()
        backend.loadLibrarySection(section, currentLibraryOrder)
    }

    function openUploads() {
        var labels = {upload_albums: qsTr("Nahraná alba"), upload_artists: qsTr("Nahraní interpreti"),
                      upload_songs: qsTr("Nahrané skladby")}
        selectLibrarySection(lastUploadSection, labels[lastUploadSection])
    }

    function libraryOrderLabels() {
        if (currentLibrarySection === "playlists")
            return [qsTr("Výchozí YTM"), qsTr("A–Z"), qsTr("Z–A")]
        return [qsTr("Nedávno přidané"), qsTr("A–Z"), qsTr("Z–A")]
    }

    function libraryOrderValues() {
        if (currentLibrarySection === "playlists")
            return ["", "a_to_z", "z_to_a"]
        return ["recently_added", "a_to_z", "z_to_a"]
    }

    function searchModeLabels() {
        if (currentSearchScope === "uploads")
            return [qsTr("Vše")]
        if (currentSearchScope === "library")
            return [qsTr("Vše"), qsTr("Skladby"), qsTr("Alba"), qsTr("Interpreti")]
        return [
            qsTr("Vše"), qsTr("Skladby"), qsTr("Videa"), qsTr("Alba"), qsTr("Interpreti"),
            qsTr("Playlisty"), qsTr("Profily"), qsTr("Podcasty"), qsTr("Epizody")
        ]
    }

    function searchModeValues() {
        if (currentSearchScope === "uploads")
            return ["all"]
        if (currentSearchScope === "library")
            return ["all", "songs", "albums", "artists"]
        return [
            "all", "songs", "videos", "albums", "artists",
            "playlists", "profiles", "podcasts", "episodes"
        ]
    }

    function selectSearchScope(scope) {
        currentSearchScope = scope
        if (scope === "uploads")
            currentSearchMode = "all"
        else if (searchModeValues().indexOf(currentSearchMode) < 0)
            currentSearchMode = "all"
        backend.clearDetail()
        if (searchField.text.trim().length > 0)
            backend.search(searchField.text, currentSearchMode, currentSearchScope)
    }

    // A missing catalog returns the Czech singular source with %n replaced.
    function songCountText(count) {
        const translated = qsTr("%n skladba", "", count)
        if (translated !== count + " skladba" || count === 1)
            return translated
        return count + (count >= 2 && count <= 4 ? " skladby" : " skladeb")
    }

    function itemCountText(count) {
        const translated = qsTr("%n položka", "", count)
        if (translated !== count + " položka" || count === 1)
            return translated
        return count + (count >= 2 && count <= 4 ? " položky" : " položek")
    }

    function loadedSongCountText(count) {
        const translated = qsTr("Vše načteno · %n skladba", "", count)
        if (translated !== "Vše načteno · " + count + " skladba" || count === 1)
            return translated
        return "Vše načteno · " + count + (count >= 2 && count <= 4 ? " skladby" : " skladeb")
    }

    function formatTime(value) {
        var total = Math.max(0, Math.floor(value || 0))
        var hours = Math.floor(total / 3600)
        var minutes = Math.floor((total % 3600) / 60)
        var seconds = total % 60
        if (hours > 0)
            return hours + ":" + (minutes < 10 ? "0" : "") + minutes + ":" + (seconds < 10 ? "0" : "") + seconds
        return minutes + ":" + (seconds < 10 ? "0" : "") + seconds
    }

    Connections {
        target: backend
        function onOutputChanged() { castDialog.close() }
        function onLoginRequested() { loginDialog.open() }
        function onLoginChanged() {
            if (backend.loginState.phase === "closed" || backend.loginState.phase === "success")
                loginDialog.close()
            if (backend.loginState.phase === "success") {
                root.playbackContext = null
                root.currentPage = 1
            }
            if (backend.loginState.phase === "closed" && !backend.connected) {
                root.playbackContext = null
                root.currentPage = 1
            }
        }
        function onDetailTitleChanged() { backend.clearTrackSelection() }
        function onPlaybackSourceCaptured() {
            root.capturePlaybackContext()
            if (backend.playerQueueSource === "detail" && backend.detailMeta.kind === "playlist") {
                root.currentPage = 5
                Qt.callLater(root.revealQueueRow)
            }
        }
        function onPlaylistBatchRemoveRequested(count, title) {
            playlistBatchRemove.itemCount = count
            playlistBatchRemove.playlistTitle = title
            playlistBatchRemove.open()
        }
        function onUploadNavigationOpened(context) { root.restoreTrackNavigation(context) }
        function onSourceNavigationRestored(context) { root.restoreTrackNavigation(context) }
        function onQueueShuffled() {
            if (root.currentPage === 5) Qt.callLater(root.revealQueueRow)
        }
        function onSongLibraryChanged() {
            if (root.currentPage === 1 && root.currentLibrarySection === "songs"
                    && backend.detailTitle.length === 0)
                backend.loadLibrarySection("songs", root.currentLibraryOrder)
        }
        function onPlaylistDeleteRequested() { playlistDeleteDialog.open() }
        function onPlaylistDeleteChanged() {
            if (backend.playlistDeleteState.completed && !backend.playlistDeleteState.pending)
                playlistDeleteDialog.close()
        }
        function onPlaylistDeleted(playlistId, returnToOverview) {
            if (returnToOverview) root.selectLibrarySection("playlists", qsTr("Playlisty"))
        }
        function onPlaylistEditRequested() {
            playlistEditName.text = backend.playlistEditState.title || ""
            playlistEditDescription.text = backend.playlistEditState.description || ""
            playlistEditPrivacy.currentIndex = ["PRIVATE", "UNLISTED", "PUBLIC"].indexOf(backend.playlistEditState.privacy)
            playlistEditDialog.open()
            playlistEditName.forceActiveFocus()
        }
        function onPlaylistEditChanged() {
            if (backend.playlistEditState.completed && !backend.playlistEditState.pending)
                playlistEditDialog.close()
        }
        function onEmptyPlaylistRequested() {
            emptyPlaylistName.text = ""
            emptyPlaylistPrivacy.currentIndex = 0
            emptyPlaylistDialog.open()
            emptyPlaylistName.forceActiveFocus()
        }
        function onEmptyPlaylistChanged() {
            if (backend.emptyPlaylistState.completed && !backend.emptyPlaylistState.pending)
                emptyPlaylistDialog.close()
        }
        function onPlaylistSaveChanged() {
            var state = backend.playlistSaveState
            if (state.completed && state.verified && !state.pending)
                playlistSave.close()
        }
        function onPlaylistSaveRequested() {
            playlistSave.newMode = (backend.playlistSaveState.targets || []).length === 0
            playlistName.text = ""
            playlistNewPrivacy.currentIndex = 0
            playlistDuplicates.checked = false
            playlistChoice.currentIndex = playlistChoice.count > 0 ? 0 : -1
            playlistSave.open()
        }
        function onPlaylistsChanged(playlistId) {
            if (root.currentPage === 1 && root.currentLibrarySection === "playlists"
                    && backend.detailTitle.length === 0)
                backend.loadLibrarySection("playlists", root.currentLibraryOrder)
        }
        function onRadioStarted() {
            root.currentPage = 5
            Qt.callLater(root.revealQueueRow)
        }
        function onArtistPlaybackStarted() {
            root.currentPage = 5
            Qt.callLater(root.revealQueueRow)
        }
        function onCollectionShuffleStarted() {
            root.currentPage = 5
            Qt.callLater(root.revealQueueRow)
        }
        function onErrorOccurred(message) {
            root.errorText = message
            errorDialog.open()
        }
    }

    Dialog {
        id: errorDialog
        title: "FelisMusic"
        modal: true
        standardButtons: Dialog.Ok
        anchors.centerIn: parent
        width: Math.min(root.width * 0.65, 720)

        contentItem: Label {
            text: root.errorText
            color: errorDialog.palette.windowText
            wrapMode: Text.WordWrap
            padding: 18
        }
    }

    Dialog {
        id: castDialog
        objectName: "castDevicesDialog"
        title: qsTr("Zvukové výstupy")
        modal: true
        anchors.centerIn: parent
        width: Math.min(520, root.width - 40)
        background: Rectangle { color: "#202020"; border.color: "#555555"; radius: 6 }
        header: Label { text: castDialog.title; color: "#eeeeee"; font.bold: true; padding: 14 }
        contentItem: ColumnLayout {
            spacing: 12
            Label {
                Layout.fillWidth: true
                text: backend.castState.switching ? backend.status : backend.castState.message
                color: "#bbbbbb"
                wrapMode: Text.WordWrap
            }
            ListView {
                objectName: "castDevicesList"
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(240, count * 48)
                clip: true
                model: backend.castState.devices
                delegate: Rectangle {
                    required property var modelData
                    width: ListView.view.width
                    height: 48
                    color: modelData.id === backend.castState.currentId ? "#303438" : "#262626"
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        Label {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            text: modelData.name
                            color: "#eeeeee"
                            elide: Text.ElideRight
                        }
                        Label {
                            text: modelData.id === backend.castState.currentId
                                  ? (backend.castState.disconnected ? qsTr("Odpojeno") : qsTr("Aktuální výstup"))
                                  : modelData.kind === "group" ? qsTr("Skupina") : qsTr("Cast audio")
                            visible: modelData.kind !== "local" || modelData.id === backend.castState.currentId
                            color: modelData.id === backend.castState.currentId
                                   ? (backend.castState.disconnected ? "#ff8a80" : "#a6d3a6") : "#aaaaaa"
                            font.pixelSize: 12
                        }
                        Button {
                            objectName: "castSelectButton"
                            text: modelData.id === backend.castState.currentId ? qsTr("Znovu připojit") : qsTr("Přepnout")
                            visible: modelData.id !== backend.castState.currentId || backend.castState.canReconnect
                            enabled: modelData.kind === "local" ? backend.castState.canReturn : backend.castState.canSelect
                            onClicked: modelData.kind === "local" ? backend.selectLocalOutput() : backend.selectCastOutput(modelData.id)
                        }
                    }
                }
                ScrollBar.vertical: ScrollBar { }
            }
            BusyIndicator { Layout.alignment: Qt.AlignHCenter; running: backend.castState.scanning || backend.castState.switching; visible: running }
            Button {
                objectName: "castDiscoverButton"
                Layout.fillWidth: true
                text: qsTr("Vyhledat zařízení")
                enabled: !backend.castState.scanning
                onClicked: backend.discoverCastDevices()
            }
            Button {
                objectName: "castCloseButton"
                Layout.fillWidth: true
                text: qsTr("Zavřít")
                onClicked: castDialog.close()
            }
        }
    }

    Dialog {
        id: logoutDialog
        objectName: "logoutDialog"
        title: qsTr("Odhlásit FelisMusic?")
        modal: true
        anchors.centerIn: parent
        width: Math.min(500, root.width - 40)
        background: Rectangle { color: "#202020"; border.color: "#555555"; radius: 6 }
        header: Label { text: logoutDialog.title; color: "#eeeeee"; font.bold: true; padding: 14 }
        contentItem: ColumnLayout {
            spacing: 14
            Label {
                Layout.fillWidth: true
                text: qsTr("Poslech se zastaví a fronta se vyprázdní. Odstraní se uložené přihlášení i samostatné přihlašovací profily FelisMusic. Odhlásí se také CLI.")
                color: "#eeeeee"
                wrapMode: Text.WordWrap
            }
            Button {
                objectName: "logoutConfirmButton"
                Layout.fillWidth: true
                text: qsTr("Odhlásit")
                onClicked: { logoutDialog.close(); backend.logout() }
            }
            Button {
                objectName: "logoutCancelButton"
                Layout.fillWidth: true
                text: qsTr("Zrušit")
                onClicked: logoutDialog.close()
            }
        }
    }

    Dialog {
        id: loginDialog
        objectName: "loginDialog"
        title: qsTr("Přihlášení k YouTube Music")
        background: Rectangle { color: "#202020"; border.color: "#555555"; radius: 6 }
        header: Label {
            text: loginDialog.title
            color: "#eeeeee"
            font.bold: true
            padding: 14
        }
        modal: true
        anchors.centerIn: parent
        width: Math.min(520, root.width - 40)
        closePolicy: Popup.NoAutoClose
        contentItem: ColumnLayout {
            spacing: 14
            Label {
                Layout.fillWidth: true
                text: backend.loginState.message || ""
                color: "#eeeeee"
                wrapMode: Text.WordWrap
            }
            Label {
                Layout.fillWidth: true
                text: qsTr("Přihlášení proběhne v samostatném profilu prohlížeče.")
                color: "#aaaaaa"
                wrapMode: Text.WordWrap
            }
            ComboBox {
                id: loginBrowserChoice
                objectName: "loginBrowserChoice"
                Layout.fillWidth: true
                model: backend.loginState.browsers || []
                textRole: "name"
                valueRole: "id"
                visible: backend.loginState.phase === "choose" || backend.loginState.phase === "error"
            }
            BusyIndicator {
                Layout.alignment: Qt.AlignHCenter
                running: backend.loginState.phase === "detecting" || backend.loginState.phase === "verifying"
                visible: running
            }
            Button {
                objectName: "loginStartButton"
                Layout.fillWidth: true
                text: qsTr("Otevřít přihlašovací okno")
                visible: backend.loginState.phase === "choose" || backend.loginState.phase === "error"
                enabled: loginBrowserChoice.currentIndex >= 0
                onClicked: backend.startLogin(loginBrowserChoice.currentValue)
            }
            Button {
                objectName: "loginFinishButton"
                Layout.fillWidth: true
                text: qsTr("Převzít přihlášení")
                visible: backend.loginState.phase === "browser"
                enabled: backend.loginState.canFinish || false
                onClicked: backend.finishLogin()
            }
            Button {
                objectName: "loginCancelButton"
                Layout.fillWidth: true
                text: qsTr("Zrušit")
                onClicked: backend.cancelLogin()
            }
        }
    }

    component PlaylistPrivacyChoice: ComboBox {
        readonly property string privacyValue: ["PRIVATE", "UNLISTED", "PUBLIC"][currentIndex] || ""
        Layout.fillWidth: true
        model: [qsTr("Soukromý"), qsTr("Neveřejný (přístup přes odkaz)"), qsTr("Veřejný")]
        Accessible.name: qsTr("Viditelnost playlistu")
    }

    Dialog {
        id: playlistDeleteDialog
        objectName: "playlistDeleteDialog"
        modal: true
        anchors.centerIn: parent
        width: Math.min(root.width - 48, 540)
        padding: 18
        closePolicy: backend.playlistDeleteState.pending ? Popup.NoAutoClose : Popup.CloseOnEscape
        onClosed: backend.cancelPlaylistDelete()
        background: Rectangle { color: "#181818"; border.color: "#494949"; radius: 8 }
        header: Label {
            text: qsTr("Smazat playlist?")
            color: "white"
            font.pixelSize: 19
            font.bold: true
            padding: 18
        }
        contentItem: ColumnLayout {
            spacing: 14
            Label {
                objectName: "playlistDeleteTitle"
                text: backend.playlistDeleteState.title || ""
                font.bold: true
                font.pixelSize: 18
                color: "white"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
            Label {
                text: qsTr("Smaže se celý playlist z YouTube Music. Tuto akci nelze vrátit. Samotné skladby tím neodstraníš.")
                color: "#dddddd"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
            Label {
                text: qsTr("Přehrávací fronta zůstane zachovaná.")
                color: "#aaaaaa"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
            Label {
                objectName: "playlistDeleteMessage"
                text: backend.playlistDeleteState.message || ""
                visible: text.length > 0
                color: backend.playlistDeleteState.error ? "#ffaaaa" : "#cccccc"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
            BusyIndicator {
                running: !!backend.playlistDeleteState.pending
                visible: running
                Layout.alignment: Qt.AlignHCenter
            }
        }
        footer: DialogButtonBox {
            background: Item { }
            PlayerTextButton {
                objectName: "playlistDeleteSubmit"
                text: qsTr("Smazat playlist")
                implicitWidth: 140
                enabled: !backend.busy && !backend.playlistDeleteState.pending
                         && !backend.playlistDeleteState.locked && !!backend.playlistDeleteState.playlistId
                onClicked: backend.confirmPlaylistDelete()
                background: Rectangle { color: parent.enabled ? "#743333" : "#3c3030"; border.color: "#985050"; radius: 4 }
            }
            PlayerTextButton {
                objectName: "playlistDeleteRecheck"
                text: qsTr("Ověřit znovu")
                implicitWidth: 125
                visible: !!backend.playlistDeleteState.canRecheck
                enabled: !backend.busy && !backend.playlistDeleteState.pending
                onClicked: backend.recheckPlaylistDelete()
            }
            PlayerTextButton {
                objectName: "playlistDeleteCancel"
                text: backend.playlistDeleteState.locked ? qsTr("Zavřít") : qsTr("Zrušit")
                implicitWidth: 85
                enabled: !backend.playlistDeleteState.pending
                onClicked: playlistDeleteDialog.close()
            }
        }
    }

    Dialog {
        id: playlistEditDialog
        objectName: "playlistEditDialog"
        modal: true
        anchors.centerIn: parent
        width: Math.min(root.width - 48, 540)
        padding: 18
        background: Rectangle { color: "#181818"; border.color: "#494949"; radius: 8 }
        header: Label {
            text: qsTr("Upravit playlist")
            color: "white"
            font.pixelSize: 19
            font.bold: true
            padding: 18
        }
        contentItem: ColumnLayout {
            spacing: 12
            enabled: !backend.busy && !backend.playlistEditState.locked
            TextField {
                id: playlistEditName
                objectName: "playlistEditName"
                Layout.fillWidth: true
                placeholderText: qsTr("Název playlistu")
                color: "white"
                placeholderTextColor: "#999999"
                background: Rectangle { color: "#292929"; border.color: "#666666"; radius: 4 }
            }
            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: 110
                TextArea {
                    id: playlistEditDescription
                    objectName: "playlistEditDescription"
                    placeholderText: qsTr("Popis (nepovinný)")
                    placeholderTextColor: "#999999"
                    color: "white"
                    wrapMode: TextEdit.Wrap
                    background: Rectangle { color: "#292929"; border.color: "#666666"; radius: 4 }
                }
            }
            ComboBox {
                id: playlistEditPrivacy
                objectName: "playlistEditPrivacy"
                Layout.fillWidth: true
                model: [qsTr("Soukromý"), qsTr("Neveřejný (přístup přes odkaz)"), qsTr("Veřejný")]
            }
            Label {
                objectName: "playlistEditMessage"
                text: backend.playlistEditState.message || ""
                visible: text.length > 0
                color: backend.playlistEditState.error ? "#ffaaaa" : "#cccccc"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
        }
        footer: DialogButtonBox {
            background: Item { }
            PlayerTextButton {
                objectName: "playlistEditSubmit"
                text: qsTr("Uložit")
                implicitWidth: 105
                enabled: !backend.busy && !backend.playlistEditState.locked && !backend.playlistEditState.pending
                         && !backend.playlistEditState.completed && playlistEditName.text.trim().length > 0
                onClicked: backend.savePlaylistEdit(playlistEditName.text, playlistEditDescription.text,
                                                   ["PRIVATE", "UNLISTED", "PUBLIC"][playlistEditPrivacy.currentIndex])
            }
            PlayerTextButton {
                objectName: "playlistEditClose"
                text: qsTr("Zavřít")
                implicitWidth: 85
                onClicked: playlistEditDialog.close()
            }
        }
    }

    Dialog {
        id: emptyPlaylistDialog
        objectName: "emptyPlaylistDialog"
        modal: true
        anchors.centerIn: parent
        width: Math.min(root.width - 48, 520)
        padding: 18
        background: Rectangle { color: "#181818"; border.color: "#494949"; radius: 8 }
        header: Label {
            text: qsTr("Nový prázdný playlist")
            color: "white"
            font.pixelSize: 19
            font.bold: true
            padding: 18
        }
        contentItem: ColumnLayout {
            spacing: 12
            TextField {
                id: emptyPlaylistName
                objectName: "emptyPlaylistName"
                Layout.fillWidth: true
                placeholderText: qsTr("Název playlistu")
                color: "white"
                placeholderTextColor: "#999999"
                enabled: !backend.busy && !backend.emptyPlaylistState.locked
                background: Rectangle { color: "#292929"; border.color: "#666666"; radius: 4 }
                onAccepted: if (emptyPlaylistSubmit.enabled) backend.createEmptyPlaylist(text, emptyPlaylistPrivacy.privacyValue)
            }
            PlaylistPrivacyChoice {
                id: emptyPlaylistPrivacy
                objectName: "emptyPlaylistPrivacy"
                enabled: !backend.busy && !backend.emptyPlaylistState.locked
            }
            Label {
                text: qsTr("Playlist vznikne bez skladeb.")
                color: "#aaaaaa"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
            Label {
                objectName: "emptyPlaylistMessage"
                text: backend.emptyPlaylistState.message || ""
                color: backend.emptyPlaylistState.error ? "#ffaaaa" : "#cccccc"
                visible: text.length > 0
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
            BusyIndicator {
                running: !!backend.emptyPlaylistState.pending
                visible: running
                Layout.alignment: Qt.AlignHCenter
            }
        }
        footer: DialogButtonBox {
            background: Item { }
            PlayerTextButton {
                id: emptyPlaylistSubmit
                objectName: "emptyPlaylistSubmit"
                text: qsTr("Vytvořit")
                implicitWidth: 105
                enabled: !backend.busy && !backend.emptyPlaylistState.pending
                         && !backend.emptyPlaylistState.completed && !backend.emptyPlaylistState.locked
                         && emptyPlaylistName.text.trim().length > 0
                onClicked: backend.createEmptyPlaylist(emptyPlaylistName.text, emptyPlaylistPrivacy.privacyValue)
            }
            PlayerTextButton {
                objectName: "emptyPlaylistClose"
                text: qsTr("Zavřít")
                implicitWidth: 85
                onClicked: emptyPlaylistDialog.close()
            }
        }
    }

    Dialog {
        id: playlistSave
        objectName: "playlistSaveDialog"
        property bool newMode: false
        property bool duplicateResult: !!backend.playlistSaveState.duplicate
        property bool canSave: !backend.busy && !backend.playlistSaveState.pending
                               && !backend.playlistSaveState.completed && !backend.playlistSaveState.locked
        modal: true
        anchors.centerIn: parent
        width: Math.min(root.width - 48, 580)
        padding: 18
        background: Rectangle { color: "#181818"; border.color: "#494949"; radius: 8 }
        header: Label {
            text: playlistSave.duplicateResult
                  ? (backend.playlistSaveState.collection ? qsTr("Duplicitní skladby") : qsTr("Duplicitní skladba"))
                  : qsTr("Přidat do playlistu")
            color: "white"
            font.pixelSize: 19
            font.bold: true
            padding: 18
        }
        contentItem: ColumnLayout {
            spacing: 12
            Label {
                text: backend.playlistSaveState.title || ""
                color: "white"
                font.bold: true
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Label {
                visible: !!backend.playlistSaveState.collection
                text: qsTr("Počet vybraných skladeb: %1").arg(backend.playlistSaveState.selectionCount || 0)
                color: "#aaaaaa"
            }
            RowLayout {
                visible: !playlistSave.duplicateResult
                Button {
                    text: qsTr("Existující playlist")
                    checkable: true
                    checked: !playlistSave.newMode
                    enabled: playlistSave.canSave && playlistChoice.count > 0
                    onClicked: playlistSave.newMode = false
                }
                Button {
                    objectName: "playlistNewMode"
                    text: qsTr("Nový playlist")
                    checkable: true
                    checked: playlistSave.newMode
                    enabled: playlistSave.canSave
                    onClicked: playlistSave.newMode = true
                }
            }
            ComboBox {
                id: playlistChoice
                objectName: "playlistChoice"
                Layout.fillWidth: true
                visible: !playlistSave.duplicateResult && !playlistSave.newMode
                enabled: playlistSave.canSave
                model: backend.playlistSaveState.targets || []
                textRole: "title"
                valueRole: "playlistId"
            }
            CheckBox {
                id: playlistDuplicates
                objectName: "playlistDuplicates"
                text: backend.playlistSaveState.collection ? qsTr("Povolit opakované výskyty skladeb") : qsTr("Povolit další výskyt stejné skladby")
                visible: !playlistSave.duplicateResult && !playlistSave.newMode
                enabled: playlistSave.canSave
                contentItem: Text {
                    text: playlistDuplicates.text
                    color: "#dddddd"
                    leftPadding: playlistDuplicates.indicator.width + playlistDuplicates.spacing
                    verticalAlignment: Text.AlignVCenter
                }
            }
            TextField {
                id: playlistName
                objectName: "playlistNewName"
                Layout.fillWidth: true
                visible: !playlistSave.duplicateResult && playlistSave.newMode
                enabled: playlistSave.canSave
                placeholderText: qsTr("Název nového playlistu")
                color: "white"
                placeholderTextColor: "#999999"
                background: Rectangle { color: "#292929"; border.color: "#666666"; radius: 4 }
            }
            PlaylistPrivacyChoice {
                id: playlistNewPrivacy
                objectName: "playlistNewPrivacy"
                visible: !playlistSave.duplicateResult && playlistSave.newMode
                enabled: playlistSave.canSave
            }
            Label {
                text: backend.playlistSaveState.collection
                      ? qsTr("Vybrané skladby se uloží v zobrazeném pořadí, bez duplicit.")
                      : qsTr("Playlist bude obsahovat vybranou skladbu.")
                visible: !playlistSave.duplicateResult && playlistSave.newMode && !backend.playlistSaveState.completed
                color: "#aaaaaa"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Label {
                objectName: "playlistSaveMessage"
                text: backend.playlistSaveState.message || ""
                color: backend.playlistSaveState.error ? "#ffaaaa" : "#eeeeee"
                font.pixelSize: playlistSave.duplicateResult ? 20 : 13
                font.bold: playlistSave.duplicateResult
                visible: text.length > 0
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            BusyIndicator {
                running: !!backend.playlistSaveState.pending
                visible: running
                Layout.alignment: Qt.AlignHCenter
            }
        }
        footer: DialogButtonBox {
            background: Item { }
            PlayerTextButton {
                objectName: "playlistSaveSubmit"
                visible: !backend.playlistSaveState.completed && !backend.playlistSaveState.locked
                implicitWidth: 155
                text: playlistSave.newMode ? qsTr("Vytvořit a přidat") : qsTr("Přidat")
                enabled: playlistSave.canSave && (playlistSave.newMode
                         ? playlistName.text.trim().length > 0 : playlistChoice.currentIndex >= 0)
                onClicked: {
                    if (playlistSave.newMode) backend.createPlaylistWithSong(playlistName.text, playlistNewPrivacy.privacyValue)
                    else backend.saveSongToPlaylist(playlistChoice.currentValue, playlistDuplicates.checked)
                }
            }
            PlayerTextButton {
                objectName: "playlistSaveRecheck"
                implicitWidth: 130
                text: qsTr("Ověřit znovu")
                visible: !!backend.playlistSaveState.canRecheck
                enabled: !backend.busy && !backend.playlistSaveState.pending
                onClicked: backend.recheckPlaylistSave()
            }
            PlayerTextButton {
                objectName: "playlistSaveClose"
                implicitWidth: 85
                text: playlistSave.duplicateResult ? qsTr("OK") : qsTr("Zavřít")
                onClicked: playlistSave.close()
            }
        }
    }

    Dialog {
        id: playlistBatchRemove
        objectName: "playlistBatchRemoveDialog"
        property int itemCount: 0
        property string playlistTitle: ""
        title: qsTr("Odebrat vybrané skladby?")
        modal: true
        anchors.centerIn: parent
        width: Math.min(root.width - 48, 540)
        standardButtons: Dialog.Ok | Dialog.Cancel
        background: Rectangle { color: "#181818"; border.color: "#494949"; radius: 8 }
        header: Label { text: playlistBatchRemove.title; color: "white"; font.pixelSize: 19; padding: 18 }
        contentItem: Label {
            text: qsTr("Odebrat vybrané skladby z playlistu „%2“? Počet: %1.")
                  .arg(playlistBatchRemove.itemCount).arg(playlistBatchRemove.playlistTitle)
            color: "#eeeeee"
            wrapMode: Text.Wrap
        }
        onAccepted: backend.removeSelectedPlaylistItems()
        onRejected: backend.cancelSelectedPlaylistRemove()
    }

    Dialog {
        id: aboutDialog
        objectName: "aboutDialog"
        title: qsTr("O aplikaci")
        modal: true
        anchors.centerIn: parent
        width: Math.min(root.width - 48, 520)
        height: Math.min(root.height - 48, 350)
        padding: 18
        background: Rectangle { color: "#181818"; border.color: "#494949"; radius: 8 }
        header: Label {
            text: aboutDialog.title
            color: "white"
            font.pixelSize: 19
            font.bold: true
            padding: 18
        }
        footer: DialogButtonBox {
            background: Item {}
            PlayerTextButton {
                text: qsTr("Zavřít")
                implicitWidth: 85
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
            }
            onRejected: aboutDialog.close()
        }
        contentItem: ScrollView {
            id: aboutScroll
            clip: true
            contentWidth: availableWidth
            ColumnLayout {
                width: aboutScroll.availableWidth
                spacing: 14
                RowLayout {
                    spacing: 16
                    Image {
                        source: "felismusic.svg"
                        sourceSize.width: 64
                        sourceSize.height: 64
                        Layout.preferredWidth: 64
                        Layout.preferredHeight: 64
                        fillMode: Image.PreserveAspectFit
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Label {
                            text: "FelisMusic Desktop"
                            color: "white"
                            font.pixelSize: 23
                            font.bold: true
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }
                        Label {
                            objectName: "aboutVersionLabel"
                            text: qsTr("Verze %1").arg(fcmVersion)
                            color: "#bbbbbb"
                        }
                    }
                }
                Label {
                    text: qsTr("Přehrávač YouTube Music pro Linux s podporou Chromecast Audio a skupin reproduktorů Google Cast.")
                    color: "#eeeeee"
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                Label {
                    text: qsTr("Licence GPL verze 3 nebo novější (GPL-3.0-or-later).")
                    color: "#bbbbbb"
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: 8
                    PlayerTextButton {
                        text: qsTr("Projekt na GitHubu")
                        implicitWidth: contentItem.implicitWidth + 24
                        onClicked: Qt.openUrlExternally("https://github.com/MiPal666/FelisMusic-Desktop")
                    }
                    PlayerTextButton {
                        text: qsTr("Nahlásit chybu")
                        implicitWidth: contentItem.implicitWidth + 24
                        onClicked: Qt.openUrlExternally("https://github.com/MiPal666/FelisMusic-Desktop/issues")
                    }
                }
            }
        }
    }

    Dialog {
        id: trackInfo
        objectName: "trackInfoDialog"
        property var selectedInfo: null
        property var information: selectedInfo || ({
            title: backend.playerTitle, artist: backend.playerArtist, album: backend.playerAlbum,
            thumbnail: backend.playerThumbnail, duration: backend.playerDuration,
            likeStatus: backend.playerLikeStatus, inQueue: true,
            queueIndex: backend.playerQueueIndex, queueCount: backend.playerQueueCount,
            queueTitle: backend.playingListTitle
        })
        title: qsTr("Informace o skladbě")
        modal: true
        padding: 18
        anchors.centerIn: parent
        width: Math.min(root.width - 48, 620)
        height: Math.min(root.height - 48, 590)
        background: Rectangle {
            color: "#181818"
            border.color: "#494949"
            radius: 8
        }
        header: Label {
            text: trackInfo.title
            color: "white"
            font.pixelSize: 19
            font.bold: true
            padding: 18
        }
        footer: DialogButtonBox {
            background: Item { }
            PlayerTextButton {
                text: qsTr("Zavřít")
                implicitWidth: 85
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
            }
            onRejected: trackInfo.close()
        }

        ScrollView {
            id: infoScroll
            anchors.fill: parent
            clip: true
            contentWidth: availableWidth

            ColumnLayout {
                objectName: "trackInfoFields"
                width: infoScroll.availableWidth
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 14
                    Image {
                        Layout.alignment: Qt.AlignTop
                        Layout.preferredWidth: 96
                        Layout.preferredHeight: 96
                        source: trackInfo.information.thumbnail
                        visible: source.toString().length > 0 && status !== Image.Error
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 8
                        Repeater {
                            model: [
                                {label: qsTr("Název"), value: trackInfo.information.title},
                                {label: qsTr("Interpret"), value: trackInfo.information.artist},
                                {label: qsTr("Album"), value: trackInfo.information.album}
                            ]
                            delegate: InfoField {}
                        }
                    }
                }
                Repeater {
                    model: [
                        {label: qsTr("Délka"), value: trackInfo.information.duration > 0 ? root.formatTime(trackInfo.information.duration) : qsTr("Neznámá")},
                        {label: qsTr("Hodnocení"), value: trackInfo.information.likeStatus === "LIKE" ? qsTr("Oblíbená")
                                                   : (trackInfo.information.likeStatus === "DISLIKE" ? qsTr("Neoblíbená")
                                                      : (trackInfo.information.likeStatus === "INDIFFERENT" ? qsTr("Bez hodnocení") : qsTr("Nezjištěno")))}
                    ].concat(trackInfo.information.inQueue ? [
                        {label: qsTr("Pozice ve frontě"), value: trackInfo.information.queueIndex >= 0 ? (trackInfo.information.queueIndex + 1) + " / " + trackInfo.information.queueCount : qsTr("Prázdná fronta")},
                        {label: qsTr("Název fronty"), value: trackInfo.information.queueTitle}
                    ] : [])
                    delegate: InfoField {}
                }
            }
        }
    }

    component InfoField: ColumnLayout {
        required property var modelData
        Layout.fillWidth: true
        spacing: 3
        Label {
            text: modelData.label
            color: "#aaaaaa"
            font.pixelSize: 12
        }
        Label {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            text: modelData.value || qsTr("Neuvedeno")
            color: "#f3f3f3"
            wrapMode: Text.Wrap
            font.pixelSize: 15
        }
    }

    component NavButton: Button {
        required property int pageIndex
        required property string pageText
        Layout.fillWidth: true
        implicitHeight: 48
        text: pageText
        checkable: true
        checked: root.currentPage === pageIndex
        onClicked: root.pageSelected(pageIndex)

        background: Rectangle {
            radius: 7
            color: parent.checked ? "#2c2c2c" : (parent.hovered ? "#202020" : "transparent")
        }

        contentItem: Text {
            text: parent.text
            color: "#f2f2f2"
            font.pixelSize: 16
            verticalAlignment: Text.AlignVCenter
            leftPadding: 14
        }
    }

    component PlayerTextButton: Button {
        property bool active: false
        implicitHeight: 36
        implicitWidth: 52

        background: Rectangle {
            radius: 5
            color: parent.down ? "#62636c"
                   : (parent.active ? "#6757b8" : (parent.hovered ? "#55565f" : "#464750"))
            border.color: "#62636c"
            opacity: parent.enabled ? 1.0 : 0.55
        }

        contentItem: Text {
            text: parent.text
            color: parent.enabled ? "#f3f3f3" : "#9a9a9a"
            font.pixelSize: 12
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    component RatingButton: Button {
        id: ratingButton
        property bool active: false
        property string iconKind: "like"
        implicitHeight: 32
        implicitWidth: 40
        hoverEnabled: true

        ToolTip.visible: hovered
        ToolTip.delay: 450
        ToolTip.text: iconKind === "like"
                      ? (active ? qsTr("Zrušit oblíbenou") : qsTr("Oblíbená"))
                      : (active ? qsTr("Zrušit neoblíbenou") : qsTr("Neoblíbená"))

        onActiveChanged: ratingCanvas.requestPaint()
        onIconKindChanged: ratingCanvas.requestPaint()
        onEnabledChanged: ratingCanvas.requestPaint()

        background: Rectangle {
            radius: 5
            color: parent.active
                   ? (parent.down ? "#51476f" : "#40385a")
                   : (parent.down ? "#55565f" : (parent.hovered ? "#404149" : "#303138"))
            border.color: parent.active ? "#9f91d8" : "#55565f"
            opacity: parent.enabled ? 1.0 : 0.5
        }

        contentItem: Canvas {
            id: ratingCanvas
            opacity: ratingButton.enabled ? 1.0 : 0.45
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
            Component.onCompleted: requestPaint()

            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                var sx = width / 36.0
                var sy = height / 36.0
                function px(x) { return x * sx }
                function py(y) {
                    var value = ratingButton.iconKind === "dislike" ? 36 - y : y
                    return value * sy
                }

                ctx.lineWidth = Math.max(1.6, 1.8 * Math.min(sx, sy))
                ctx.lineJoin = "round"
                ctx.lineCap = "round"
                ctx.strokeStyle = ratingButton.active ? "#ffffff" : "#dddddd"
                ctx.fillStyle = ratingButton.active ? "#8f80cf" : "#00000000"

                var points = [
                    [11, 17], [16, 17], [19, 9], [21, 7], [23, 8],
                    [24, 10], [23, 16], [29, 16], [31, 18], [29, 27],
                    [27, 29], [16, 29], [11, 27]
                ]
                ctx.beginPath()
                ctx.moveTo(px(points[0][0]), py(points[0][1]))
                for (var i = 1; i < points.length; ++i)
                    ctx.lineTo(px(points[i][0]), py(points[i][1]))
                ctx.closePath()
                ctx.fill()
                ctx.stroke()

                var y1 = ratingButton.iconKind === "dislike" ? 8 : 17
                var y2 = ratingButton.iconKind === "dislike" ? 19 : 28
                ctx.beginPath()
                ctx.rect(px(5), y1 * sy, px(5), (y2 - y1) * sy)
                ctx.fill()
                ctx.stroke()
            }
        }
    }

    component TransportButton: Button {
        id: transportButton
        property string iconKind: "play"
        implicitWidth: 64
        implicitHeight: 38
        onIconKindChanged: iconCanvas.requestPaint()

        background: Rectangle {
            radius: 5
            color: parent.down ? "#62636c" : (parent.hovered ? "#55565f" : "#464750")
            border.color: "#62636c"
            opacity: parent.enabled ? 1.0 : 0.55
        }

        contentItem: Canvas {
            id: iconCanvas
            opacity: transportButton.enabled ? 1.0 : 0.38
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
            Component.onCompleted: requestPaint()

            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                ctx.fillStyle = "#f4f4f4"

                var cx = width / 2
                var cy = height / 2
                var h = 15
                var w = 12

                function triangle(left, top, right, middle, left2, bottom) {
                    ctx.beginPath()
                    ctx.moveTo(left, top)
                    ctx.lineTo(right, middle)
                    ctx.lineTo(left2, bottom)
                    ctx.closePath()
                    ctx.fill()
                }

                if (transportButton.iconKind === "play") {
                    triangle(cx - 6, cy - h / 2, cx + 8, cy, cx - 6, cy + h / 2)
                } else if (transportButton.iconKind === "pause") {
                    ctx.fillRect(cx - 7, cy - h / 2, 5, h)
                    ctx.fillRect(cx + 2, cy - h / 2, 5, h)
                } else if (transportButton.iconKind === "stop") {
                    ctx.fillRect(cx - 7, cy - 7, 14, 14)
                } else if (transportButton.iconKind === "previous") {
                    ctx.fillRect(cx - 10, cy - h / 2, 3, h)
                    triangle(cx + 7, cy - h / 2, cx - 6, cy, cx + 7, cy + h / 2)
                } else if (transportButton.iconKind === "next") {
                    ctx.fillRect(cx + 7, cy - h / 2, 3, h)
                    ctx.beginPath()
                    ctx.moveTo(cx - 7, cy - h / 2)
                    ctx.lineTo(cx + 6, cy)
                    ctx.lineTo(cx - 7, cy + h / 2)
                    ctx.closePath()
                    ctx.fill()
                }
            }
        }
    }

    component BusyOverlay: Rectangle {
        visible: backend.busy
        color: "#99000000"
        z: 100
        anchors.fill: parent

        Column {
            anchors.centerIn: parent
            spacing: 16

            BusyIndicator {
                anchors.horizontalCenter: parent.horizontalCenter
                running: visible
            }

            Label {
                anchors.horizontalCenter: parent.horizontalCenter
                text: backend.status
                color: "#dddddd"
            }
        }
    }

    function followPlayingRow(view, sourceKey) {
        if (!view || (sourceKey !== "playing" && backend.playerQueueSource !== sourceKey))
            return
        var i = sourceKey === "playing" ? backend.playerQueueIndex : backend.playerVisibleSourceIndex
        if (i >= 0 && i < view.count)
            view.positionViewAtIndex(i, ListView.Contain)
    }

    function revealQueueRow() {
        if (currentPage !== 5 || !backend.playerHasTrack)
            return
        queueList.currentIndex = backend.playerQueueIndex
        queueList.forceLayout()
        queueList.positionViewAtIndex(backend.playerQueueIndex, ListView.Center)
    }

    function showPlayingList() {
        if (backend.playerQueueSource === "playing") {
            currentPage = 5
            Qt.callLater(root.revealQueueRow)
            return
        }
        var context = backend.playerSourceContext
        if (context.page === undefined)
            context = playbackContext
        if (!context || !backend.restorePlayingSource(context.page))
            return
        if (context.page === 1) {
            currentLibrarySection = context.librarySection
            currentLibraryLabel = context.libraryLabel
            currentLibraryOrder = context.libraryOrder
        } else if (context.page === 2) {
            currentLikedOrder = context.likedOrder
        } else if (context.page === 0) {
            currentSearchScope = context.searchScope
            currentSearchMode = context.searchMode
            searchField.text = context.searchText
        }
        // Set the page directly: pageSelected() clears detail and reloads data.
        currentPage = context.page
        Qt.callLater(function() { root.playingSourceRequested() })
    }

    function revealPlayingSource(view, sourceKey) {
        if (!view.visible || backend.playerQueueSource !== sourceKey)
            return
        var index = backend.playerVisibleSourceIndex
        if (index < 0 || index >= view.count)
            return
        view.currentIndex = index
        view.forceLayout()
        view.positionViewAtIndex(index, ListView.Center)
    }

    component TrackListView: ListView {
        id: selectionView
        required property string selectionKey
        objectName: "trackList_" + selectionKey
        Keys.onPressed: function(event) { root.trackKeys(event, selectionKey) }

        // Passive tap recognition leaves row clicks, double clicks and drags
        // with their existing handlers. indexAt uses content coordinates.
        TapHandler {
            acceptedButtons: Qt.LeftButton
            onTapped: function(eventPoint, button) {
                var point = eventPoint.position
                var scrollBar = selectionView.ScrollBar.vertical
                if (scrollBar && scrollBar.visible && point.x >= selectionView.width - scrollBar.width)
                    return
                if (selectionView.indexAt(point.x + selectionView.contentX,
                                          point.y + selectionView.contentY) < 0) {
                    backend.clearTrackSelection()
                    selectionView.forceActiveFocus()
                }
            }
        }
    }

    component TrackDelegate: Rectangle {
        id: trackDelegate
        // Qt 6 QAbstractListModel roles are injected directly into the delegate.
        // Declaring matching required properties makes that binding explicit and
        // avoids relying on the non-portable `model.<role>` object.
        required property int index
        required property string title
        required property string subtitle
        required property string duration
        required property string thumbnail
        required property string videoId
        required property string likeStatus
        required property string setVideoId
        required property string albumId
        required property var artistLinks
        required property string kind
        required property string playlistId
        required property string browseId
        property string sourceKey: ""
        property bool partialLiked: (sourceKey === "liked" && !backend.likedComplete)
                                    || (sourceKey === "detail" && !backend.detailComplete)
                                    || (sourceKey === "library" && (root.currentLibrarySection === "songs" || root.currentLibrarySection === "upload_songs") && !backend.librarySongsComplete)
        property bool selectedTrack: backend.selectionSource === sourceKey && backend.selectedTrackIndices.indexOf(index) >= 0
        property bool multipleSelection: selectedTrack && backend.selectedTrackIndices.length > 1
        property var navigationArtists: Array.from(artistLinks || []).filter(function(artist) {
            var currentKind = kind === "upload_song" ? "upload_artist" : "artist"
            return sourceKey !== "detail" || backend.detailMeta.kind !== currentKind
                || String(artist.id).replace(/^MPLA/, "") !== String(backend.detailMeta.browseId || "").replace(/^MPLA/, "")
        })
        property bool actionable: videoId.length > 0 || browseId.length > 0 || playlistId.length > 0
        property bool currentTrack: backend.playerHasTrack
                                    && (sourceKey === "playing"
                                        ? backend.playerQueueIndex === index
                                        : (backend.playerQueueSource === sourceKey
                                           && backend.playerVisibleSourceIndex === index
                                           && backend.playerVideoId === videoId))

        function kindCaption(value) {
            var labels = {
                "song": qsTr("Skladba"), "video": qsTr("Video"),
                "album": qsTr("Album"), "single": qsTr("Single"), "ep": qsTr("EP"),
                "artist": qsTr("Interpret"), "playlist": qsTr("Playlist"),
                "podcast": qsTr("Podcast"), "channel": qsTr("Profil"),
                "profile": qsTr("Profil"), "upload_song": qsTr("Nahraná skladba"),
                "upload_album": qsTr("Nahrané album"), "upload_artist": qsTr("Nahraný interpret")
            }
            var label = labels[value] || value || qsTr("Položka")
            return label
        }

        width: ListView.view ? ListView.view.width : 600
        height: 68
        opacity: 1.0
        color: selectedTrack ? "#30394d" : (currentTrack ? "#27223a" : (mouse.containsMouse ? "#1c1c1c" : "transparent"))
        border.color: selectedTrack ? "#91a9df" : (currentTrack ? "#6757d9" : "transparent")
        border.width: selectedTrack || currentTrack ? 1 : 0

        Rectangle {
            width: 4
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            color: "#7566e8"
            visible: currentTrack
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: videoId.length > 0 ? 56 : 14
            spacing: 12

            Rectangle {
                Layout.preferredWidth: 48
                Layout.preferredHeight: 48
                radius: 4
                color: "#292929"
                clip: true

                Image {
                    anchors.fill: parent
                    source: thumbnail
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: true
                    visible: status === Image.Ready
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3

                Label {
                    Layout.fillWidth: true
                    text: title
                    color: "white"
                    font.pixelSize: 15
                    font.bold: true
                    elide: Text.ElideRight
                }
                Label {
                    Layout.fillWidth: true
                    text: subtitle
                    color: "#aaaaaa"
                    font.pixelSize: 13
                    elide: Text.ElideRight
                }
            }

            Label {
                visible: currentTrack
                text: backend.playerState === "loading" ? qsTr("Připravuji…")
                      : (backend.playerState === "playing" ? qsTr("Hraje")
                         : (backend.playerState === "paused" ? qsTr("Pozastaveno") : qsTr("Zastaveno")))
                color: "#b9b0ff"
                font.pixelSize: 12
                font.bold: true
            }

            Label {
                visible: sourceKey === "search"
                text: kindCaption(kind)
                color: "#8f8f8f"
                font.pixelSize: 11
            }

            Label {
                text: duration
                color: "#aaaaaa"
                font.pixelSize: 13
            }
        }

        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            cursorShape: {
                if (sourceKey === "search")
                    return actionable ? Qt.PointingHandCursor : Qt.ArrowCursor
                return videoId.length > 0 || (sourceKey === "detail" && (kind === "album" ||
                       (backend.detailMeta.kind === "profile" && kind === "playlist"))) ? Qt.PointingHandCursor : Qt.ArrowCursor
            }
            onClicked: function(event) {
                if (videoId.length > 0) {
                    if (trackDelegate.ListView.view) trackDelegate.ListView.view.forceActiveFocus()
                    if (event.button !== Qt.RightButton || !trackDelegate.selectedTrack)
                        backend.selectTrack(sourceKey, index,
                                            event.button !== Qt.RightButton && !!(event.modifiers & Qt.ControlModifier),
                                            event.button !== Qt.RightButton && !!(event.modifiers & Qt.ShiftModifier))
                    if (event.button === Qt.RightButton && !trackDelegate.partialLiked)
                        trackMenu.popup(trackDelegate, event.x, event.y)
                    return
                }
                if (event.button === Qt.RightButton) return
                backend.clearTrackSelection()
                if (sourceKey === "search" && actionable)
                    backend.openSearchResult(index)
                else if (sourceKey === "detail" && (kind === "album" ||
                         (backend.detailMeta.kind === "profile" && kind === "playlist")))
                    backend.openDetailItem(index, root.navigationContext())
            }
            onDoubleClicked: function(event) {
                if (event.button === Qt.LeftButton && videoId.length > 0
                        && !(event.modifiers & (Qt.ControlModifier | Qt.ShiftModifier)))
                    backend.playFrom(sourceKey, index)
            }
        }

        Button {
            id: menuButton
            objectName: "trackMenuButton"
            enabled: !trackDelegate.partialLiked
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            width: 34
            height: 34
            visible: videoId.length > 0
            hoverEnabled: true
            onClicked: {
                if (!trackDelegate.selectedTrack) backend.selectTrack(sourceKey, index, false, false)
                trackMenu.popup(menuButton, menuButton.width - trackMenu.width, menuButton.height)
            }
            ToolTip.visible: hovered
            ToolTip.text: qsTr("Možnosti skladby")
            background: Rectangle {
                radius: 4
                color: menuButton.hovered ? "#3b3b3b" : "transparent"
            }
            contentItem: Canvas {
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.fillStyle = "#dddddd"
                    for (var i = 0; i < 3; ++i) {
                        ctx.beginPath()
                        ctx.arc(width / 2, height / 2 + (i - 1) * 6, 2, 0, Math.PI * 2)
                        ctx.fill()
                    }
                }
            }
        }

        Menu {
            id: trackMenu
            objectName: "trackContextMenu"
            property int libraryRequest: 0
            property string publicLink: ""
            property bool libraryMatches: libraryRequest > 0 && backend.songLibraryMenuState.requestId === libraryRequest
            onAboutToShow: {
                publicLink = trackDelegate.multipleSelection ? "" : backend.publicLinkFrom(trackDelegate.sourceKey, trackDelegate.index)
                if (!trackDelegate.multipleSelection && (kind === "song" || kind === "video"))
                    libraryRequest = backend.prepareSongLibrary(trackDelegate.sourceKey, trackDelegate.index)
            }
            onClosed: {
                if (libraryRequest > 0) backend.cancelSongLibraryProbe(libraryRequest)
                libraryRequest = 0
            }
            Component.onDestruction: {
                if (libraryRequest > 0) backend.cancelSongLibraryProbe(libraryRequest)
            }
            popupType: Popup.Item
            width: 240
            palette.text: "#eeeeee"
            palette.windowText: "#eeeeee"
            palette.highlight: "#6757b8"
            background: Rectangle {
                color: "#242424"
                border.color: "#555555"
                radius: 5
            }
            MenuItem {
                text: qsTr("Přehrát jako další")
                enabled: backend.playerCanEditQueue
                onTriggered: trackDelegate.multipleSelection ? backend.enqueueSelection(true, root.navigationContext())
                           : backend.enqueueFrom(trackDelegate.sourceKey, trackDelegate.index, true, root.navigationContext())
            }
            MenuItem {
                text: qsTr("Přidat na konec fronty")
                enabled: backend.playerCanEditQueue
                onTriggered: trackDelegate.multipleSelection ? backend.enqueueSelection(false, root.navigationContext())
                           : backend.enqueueFrom(trackDelegate.sourceKey, trackDelegate.index, false, root.navigationContext())
            }
            MenuItem {
                text: qsTr("Přidat do playlistu…")
                visible: trackDelegate.multipleSelection ? backend.selectionCanSavePlaylist
                         : (kind === "song" || kind === "video" || kind === "upload_song")
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy
                onTriggered: trackDelegate.multipleSelection ? backend.openSelectedPlaylistSave()
                           : backend.openPlaylistSave(trackDelegate.sourceKey, trackDelegate.index)
            }
            MenuItem {
                text: qsTr("Spustit mix")
                visible: !trackDelegate.multipleSelection && (kind === "song" || kind === "video")
                height: visible ? implicitHeight : 0
                enabled: backend.playerCanEditQueue && !backend.busy && backend.connected
                onTriggered: backend.startRadioFrom(trackDelegate.sourceKey, trackDelegate.index)
            }
            MenuItem {
                objectName: "uploadTrackAlbum"
                text: qsTr("Otevřít nahrané album")
                visible: !trackDelegate.multipleSelection && kind === "upload_song"
                         && !(sourceKey === "detail" && backend.detailMeta.kind === "upload_album"
                              && albumId === backend.detailMeta.browseId)
                         && albumId.indexOf("FEmusic_library_privately_owned_release") === 0
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy
                onTriggered: backend.openUploadTrackTarget(sourceKey, trackDelegate.index, "album", "", root.navigationContext())
            }
            MenuItem {
                objectName: "onlineTrackAlbum"
                text: qsTr("Otevřít album")
                visible: !trackDelegate.multipleSelection && (kind === "song" || kind === "video")
                         && !(sourceKey === "detail" && backend.detailMeta.kind === "album"
                              && albumId === backend.detailMeta.browseId)
                         && albumId.indexOf("MPRE") === 0
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy
                onTriggered: backend.openTrackTarget(sourceKey, trackDelegate.index, "album", "", root.navigationContext())
            }
            MenuItem {
                objectName: "onlineTrackArtist"
                text: qsTr("Otevřít interpreta") + (trackDelegate.navigationArtists.length > 1 ? "…" : "")
                visible: !trackDelegate.multipleSelection && (kind === "song" || kind === "video") && trackDelegate.navigationArtists.length > 0
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy
                onTriggered: {
                    if (trackDelegate.navigationArtists.length === 1)
                        backend.openTrackTarget(sourceKey, trackDelegate.index, "artist", trackDelegate.navigationArtists[0].id, root.navigationContext())
                    else
                        uploadArtistMenu.popup(menuButton, menuButton.width - uploadArtistMenu.width, menuButton.height)
                }
            }
            MenuItem {
                objectName: "uploadTrackArtist"
                text: qsTr("Otevřít nahraného interpreta") + (trackDelegate.navigationArtists.length > 1 ? "…" : "")
                visible: !trackDelegate.multipleSelection && kind === "upload_song" && trackDelegate.navigationArtists.length > 0
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy
                onTriggered: {
                    if (trackDelegate.navigationArtists.length === 1)
                        backend.openUploadTrackTarget(sourceKey, trackDelegate.index, "artist", trackDelegate.navigationArtists[0].id, root.navigationContext())
                    else
                        uploadArtistMenu.popup(menuButton, menuButton.width - uploadArtistMenu.width, menuButton.height)
                }
            }
            MenuItem {
                objectName: "trackInfoAction"
                text: qsTr("Informace")
                visible: !trackDelegate.multipleSelection && videoId.length > 0
                         && (kind === "song" || kind === "video" || kind === "upload_song")
                height: visible ? implicitHeight : 0
                onTriggered: {
                    var info = backend.trackInfoFrom(trackDelegate.sourceKey, trackDelegate.index)
                    if (info.title !== undefined) {
                        trackInfo.selectedInfo = info
                        trackInfo.open()
                    }
                }
            }
            MenuItem {
                objectName: "itemCopyLinkAction"
                text: qsTr("Kopírovat odkaz")
                visible: !trackDelegate.multipleSelection && trackMenu.publicLink.length > 0
                height: visible ? implicitHeight : 0
                onTriggered: backend.copyPublicLink(trackMenu.publicLink)
            }
            MenuItem {
                objectName: "itemOpenLinkAction"
                text: qsTr("Otevřít v prohlížeči")
                visible: !trackDelegate.multipleSelection && trackMenu.publicLink.length > 0
                height: visible ? implicitHeight : 0
                onTriggered: backend.openPublicLink(trackMenu.publicLink)
            }
            MenuItem {
                objectName: "trackRatingAction"
                text: qsTr("Hodnocení…")
                visible: !trackDelegate.multipleSelection && videoId.length > 0
                         && (kind === "song" || kind === "video" || kind === "upload_song")
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.trackRatingBusy
                onTriggered: trackRatingMenu.popup(menuButton, menuButton.width - trackRatingMenu.width, menuButton.height)
            }
            MenuItem {
                objectName: "queueMoveUpAction"
                text: qsTr("Posunout nahoru")
                visible: trackDelegate.sourceKey === "playing" && !trackDelegate.multipleSelection
                height: visible ? implicitHeight : 0
                enabled: backend.playerCanMoveQueue && trackDelegate.index > 0
                onTriggered: backend.moveQueueItem(trackDelegate.index, -1)
            }
            MenuItem {
                objectName: "queueMoveDownAction"
                text: qsTr("Posunout dolů")
                visible: trackDelegate.sourceKey === "playing" && !trackDelegate.multipleSelection
                height: visible ? implicitHeight : 0
                enabled: backend.playerCanMoveQueue && trackDelegate.index + 1 < backend.playerQueueCount
                onTriggered: backend.moveQueueItem(trackDelegate.index, 1)
            }
            MenuItem {
                objectName: "queueRemoveItemAction"
                text: trackDelegate.currentTrack && backend.playerRemovalPending ? qsTr("Odebere se po dohrání")
                      : trackDelegate.currentTrack && (backend.playerState === "playing" || backend.playerState === "paused")
                        ? qsTr("Odebrat z fronty po dohrání") : qsTr("Odebrat z fronty")
                visible: trackDelegate.sourceKey === "playing" && !trackDelegate.multipleSelection
                height: visible ? implicitHeight : 0
                enabled: backend.playerCanEditQueue && !(trackDelegate.currentTrack && backend.playerRemovalPending)
                onTriggered: backend.removeQueueItem(trackDelegate.index)
            }
            MenuItem {
                objectName: "playlistMoveUpAction"
                text: qsTr("Posunout nahoru")
                visible: !trackDelegate.multipleSelection && trackDelegate.sourceKey === "detail"
                         && backend.detailCanEditPlaylist && videoId.length > 0 && setVideoId.length > 0
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy && trackDelegate.index > 0
                onTriggered: backend.moveDetailPlaylistItem(videoId, setVideoId, -1)
            }
            MenuItem {
                objectName: "playlistMoveDownAction"
                text: qsTr("Posunout dolů")
                visible: !trackDelegate.multipleSelection && trackDelegate.sourceKey === "detail"
                         && backend.detailCanEditPlaylist && videoId.length > 0 && setVideoId.length > 0
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy && trackDelegate.index + 1 < backend.detailTracksModel.count
                onTriggered: backend.moveDetailPlaylistItem(videoId, setVideoId, 1)
            }
            MenuItem {
                objectName: "playlistRemoveItemAction"
                text: trackDelegate.multipleSelection ? qsTr("Odebrat vybrané z playlistu…") : qsTr("Odebrat z tohoto playlistu")
                visible: trackDelegate.multipleSelection ? backend.selectionCanRemovePlaylist
                         : (trackDelegate.sourceKey === "detail" && backend.detailCanEditPlaylist
                            && videoId.length > 0 && setVideoId.length > 0)
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy
                onTriggered: trackDelegate.multipleSelection ? backend.openSelectedPlaylistRemove()
                           : backend.removeDetailPlaylistItem(videoId, setVideoId)
            }
            // Append the delayed action so existing menu rows do not move.
            MenuItem {
                objectName: "songLibraryMenuAction"
                text: backend.songLibraryMenuState.inLibrary ? qsTr("Odebrat z knihovny") : qsTr("Přidat do knihovny")
                visible: !trackDelegate.multipleSelection && (kind === "song" || kind === "video") && trackMenu.libraryMatches
                         && backend.songLibraryMenuState.available && !backend.songLibraryMenuState.pending
                height: visible ? implicitHeight : 0
                enabled: visible && !backend.busy
                onTriggered: backend.changeSongLibrary(trackMenu.libraryRequest)
            }

        }

        Menu {
            id: trackRatingMenu
            objectName: "trackRatingMenu"
            popupType: Popup.Item
            width: 240
            palette.text: "#eeeeee"
            palette.windowText: "#eeeeee"
            palette.highlight: "#6757b8"
            background: Rectangle { color: "#242424"; border.color: "#555555"; radius: 5 }
            MenuItem {
                objectName: "trackRateLike"
                text: qsTr("Oblíbená") + (trackDelegate.likeStatus === "LIKE" ? " ✓" : "")
                enabled: backend.connected && !backend.trackRatingBusy
                onTriggered: backend.rateTrackFrom(trackDelegate.sourceKey, trackDelegate.index, "LIKE")
            }
            MenuItem {
                objectName: "trackRateDislike"
                text: qsTr("Neoblíbená") + (trackDelegate.likeStatus === "DISLIKE" ? " ✓" : "")
                enabled: backend.connected && !backend.trackRatingBusy
                onTriggered: backend.rateTrackFrom(trackDelegate.sourceKey, trackDelegate.index, "DISLIKE")
            }
            MenuItem {
                objectName: "trackRateClear"
                text: qsTr("Zrušit hodnocení")
                enabled: backend.connected && !backend.trackRatingBusy
                onTriggered: backend.rateTrackFrom(trackDelegate.sourceKey, trackDelegate.index, "INDIFFERENT")
            }
        }

        Menu {
            id: uploadArtistMenu
            objectName: "uploadArtistChoiceMenu"
            popupType: Popup.Item
            width: 260
            palette.text: "#eeeeee"
            palette.windowText: "#eeeeee"
            background: Rectangle { color: "#242424"; border.color: "#555555"; radius: 5 }
            Instantiator {
                model: trackDelegate.navigationArtists
                delegate: MenuItem {
                    required property var modelData
                    text: modelData.name
                    enabled: backend.connected && !backend.busy
                    onTriggered: trackDelegate.kind === "upload_song"
                        ? backend.openUploadTrackTarget(trackDelegate.sourceKey, trackDelegate.index,
                            "artist", modelData.id, root.navigationContext())
                        : backend.openTrackTarget(trackDelegate.sourceKey, trackDelegate.index,
                            "artist", modelData.id, root.navigationContext())
                }
                onObjectAdded: function(index, object) { uploadArtistMenu.insertItem(index, object) }
                onObjectRemoved: function(index, object) { uploadArtistMenu.removeItem(object) }
            }
        }
    }

    component HeaderActionsButton: Button {
        text: qsTr("Akce ▾")
        font.pixelSize: 11
        Layout.preferredHeight: 28
        readonly property int inlineMargin: 10
        Layout.leftMargin: inlineMargin
    }

    component CollectionHeader: ColumnLayout {
        id: collectionHeader
        property string backText: qsTr("← Zpět")
        signal goBack()
        Layout.fillWidth: true
        spacing: 4
        Button {
            objectName: "collectionBackButton"
            text: collectionHeader.backText
            flat: true
            font.pixelSize: 12
            padding: 5
            enabled: !backend.busy
            onClicked: collectionHeader.goBack()
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Image {
                objectName: "collectionHeaderCover"
                source: backend.detailMeta.header ? backend.detailMeta.header.thumbnail || "" : ""
                visible: source.toString().length > 0 && status !== Image.Error
                Layout.preferredWidth: 44
                Layout.preferredHeight: 44
                fillMode: Image.PreserveAspectFit
                asynchronous: true
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 2
                GridLayout {
                    id: collectionTitleRow
                    Layout.fillWidth: true
                    columns: 3
                    columnSpacing: 8
                    rowSpacing: 4

                    readonly property bool actionsOnOwnRow: collectionMenuButton.visible
                        && width < collectionTitle.naturalWidth + collectionMenuButton.implicitWidth
                            + collectionMenuButton.inlineMargin + columnSpacing

                    Label {
                        id: collectionTitle
                        Layout.row: 0
                        Layout.column: 0
                        Layout.columnSpan: collectionTitleRow.actionsOnOwnRow ? 2 : 1
                        readonly property real naturalWidth: Math.ceil(titleMetrics.advanceWidth)
                            + leftPadding + rightPadding + 2
                        Layout.preferredWidth: naturalWidth
                        Layout.maximumWidth: naturalWidth
                        objectName: "collectionTitle"
                        text: backend.detailTitle
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        color: "white"
                        font.pixelSize: 24
                        font.bold: true
                        elide: Text.ElideRight
                        TextMetrics {
                            id: titleMetrics
                            text: collectionTitle.text
                            font: collectionTitle.font
                        }
                        HoverHandler { id: collectionTitleHover }
                        ToolTip.visible: collectionTitle.truncated && collectionTitleHover.hovered
                        ToolTip.text: collectionTitle.text
                    }
                    HeaderActionsButton {
                        id: collectionMenuButton
                        objectName: "collectionMenuButton"
                        Layout.row: collectionTitleRow.actionsOnOwnRow ? 1 : 0
                        Layout.column: collectionTitleRow.actionsOnOwnRow ? 0 : 1
                        Layout.alignment: Qt.AlignLeft | Qt.AlignVCenter
                        Layout.leftMargin: collectionTitleRow.actionsOnOwnRow ? 0 : inlineMargin
                        visible: backend.detailCanSavePlaylist || backend.detailCanEditPlaylist || backend.detailCanShuffle || backend.detailCanCollectionRadio
                                 || backend.detailCanAlbumLibrary
                                 || backend.detailCanPlaylistLibrary
                                 || backend.detailPublicLink.length > 0
                                 || backend.detailMeta.kind === "artist" || backend.detailCanUploadArtistMix
                        enabled: backend.detailPublicLink.length > 0 || (!backend.busy && backend.connected)
                        hoverEnabled: true
                        ToolTip.visible: hovered
                        ToolTip.text: qsTr("Možnosti kolekce")
                        onClicked: collectionMenu.popup(collectionMenuButton, 0, height)
                    }
                    Item {
                        Layout.row: 0
                        Layout.column: 2
                        Layout.fillWidth: true
                    }
                }
                Label {
                    objectName: "collectionHeaderSummary"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    text: backend.detailHeaderSummary ||
                          ((backend.detailMeta.kind === "artist" && backend.detailMeta.section !== "songs")
                           || backend.detailMeta.kind === "profile"
                           ? root.itemCountText(backend.detailTracksModel.count)
                           : root.songCountText(backend.detailTracksModel.count))
                    elide: Text.ElideRight
                    HoverHandler { id: headerSummaryHover }
                    ToolTip.visible: headerSummaryHover.hovered
                    ToolTip.text: text
                    color: "#999999"
                    font.pixelSize: 12
                }
            }
        }
        Menu {
            id: collectionMenu
            objectName: "collectionContextMenu"
            property string publicLink: ""
            onAboutToShow: publicLink = backend.detailPublicLink
            popupType: Popup.Item
            width: 260
            palette.text: "#eeeeee"
            palette.windowText: "#eeeeee"
            palette.highlight: "#6757b8"
            background: Rectangle { color: "#242424"; border.color: "#555555"; radius: 5 }
            MenuItem {
                objectName: "collectionCopyLinkAction"
                text: qsTr("Kopírovat odkaz")
                visible: collectionMenu.publicLink.length > 0
                height: visible ? implicitHeight : 0
                onTriggered: backend.copyPublicLink(collectionMenu.publicLink)
            }
            MenuItem {
                objectName: "collectionOpenLinkAction"
                text: qsTr("Otevřít v prohlížeči")
                visible: collectionMenu.publicLink.length > 0
                height: visible ? implicitHeight : 0
                onTriggered: backend.openPublicLink(collectionMenu.publicLink)
            }
            MenuItem {
                objectName: "collectionShuffle"
                text: qsTr("Přehrát náhodně")
                visible: backend.detailMeta.kind === "playlist" || backend.detailMeta.kind === "album"
                         || backend.detailMeta.kind === "upload_album" || backend.detailMeta.kind === "upload_artist"
                height: visible ? implicitHeight : 0
                enabled: backend.detailCanShuffle && backend.connected && !backend.busy && backend.playerCanEditQueue
                onTriggered: backend.shuffleDetail()
            }
            MenuItem {
                objectName: "collectionRadio"
                text: qsTr("Spustit mix")
                visible: backend.detailMeta.kind === "playlist" || backend.detailMeta.kind === "album"
                height: visible ? implicitHeight : 0
                enabled: backend.detailCanCollectionRadio && backend.connected && !backend.busy && backend.playerCanEditQueue
                onTriggered: backend.startCollectionRadio()
            }
            MenuItem {
                objectName: "artistShuffle"
                text: qsTr("Přehrát náhodně")
                visible: backend.detailMeta.kind === "artist"
                height: visible ? implicitHeight : 0
                enabled: backend.detailCanArtistShuffle && backend.connected && !backend.busy && backend.playerCanEditQueue
                onTriggered: backend.startArtistPlayback("shuffle")
            }
            MenuItem {
                objectName: "artistRadio"
                text: qsTr("Spustit mix")
                visible: backend.detailMeta.kind === "artist"
                height: visible ? implicitHeight : 0
                enabled: backend.detailCanArtistRadio && backend.connected && !backend.busy && backend.playerCanEditQueue
                onTriggered: backend.startArtistPlayback("radio")
            }
            MenuItem {
                objectName: "uploadArtistMix"
                text: qsTr("Spustit mix")
                visible: backend.detailMeta.kind === "upload_artist"
                height: visible ? implicitHeight : 0
                enabled: backend.detailCanUploadArtistMix && backend.connected && !backend.busy && backend.playerCanEditQueue
                onTriggered: backend.startUploadArtistMix()
            }
            MenuItem {
                objectName: "albumLibraryAction"
                text: backend.detailMeta.albumLibrary && backend.detailMeta.albumLibrary.inLibrary
                      ? qsTr("Odebrat album z knihovny") : qsTr("Přidat album do knihovny")
                visible: backend.detailCanAlbumLibrary
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy
                onTriggered: backend.changeAlbumLibrary()
            }
            MenuItem {
                objectName: "playlistLibraryAction"
                text: backend.detailMeta.playlistLibrary && backend.detailMeta.playlistLibrary.inLibrary
                      ? qsTr("Odebrat playlist z knihovny") : qsTr("Přidat playlist do knihovny")
                visible: backend.detailCanPlaylistLibrary
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy
                onTriggered: backend.changePlaylistLibrary()
            }
            MenuItem {
                objectName: "artistSubscriptionAction"
                text: backend.detailMeta.artistSubscription && backend.detailMeta.artistSubscription.subscribed
                      ? qsTr("Zrušit odběr") : qsTr("Odebírat")
                visible: backend.detailCanArtistSubscription
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy
                onTriggered: backend.changeArtistSubscription()
            }
            MenuItem {
                objectName: "collectionPlaylistSave"
                text: qsTr("Přidat seznam do playlistu…")
                visible: backend.detailCanSavePlaylist
                height: visible ? implicitHeight : 0
                enabled: backend.connected && backend.detailCanSavePlaylist && !backend.busy
                onTriggered: backend.openCollectionPlaylistSave()
            }
            MenuItem {
                objectName: "albumCollectionNext"
                text: qsTr("Přehrát jako další")
                visible: backend.detailMeta.kind === "album"
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy && backend.playerCanEditQueue && backend.detailCanEnqueueAlbum
                onTriggered: backend.enqueueAlbumCollection(true, root.navigationContext())
            }
            MenuItem {
                objectName: "albumCollectionAppend"
                text: qsTr("Přidat na konec fronty")
                visible: backend.detailMeta.kind === "album"
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy && backend.playerCanEditQueue && backend.detailCanEnqueueAlbum
                onTriggered: backend.enqueueAlbumCollection(false, root.navigationContext())
            }
            MenuItem {
                objectName: "playlistCollectionNext"
                text: qsTr("Přehrát jako další")
                visible: backend.detailMeta.kind === "playlist" && !backend.detailMeta.dynamicMix
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy && backend.playerCanEditQueue && backend.detailCanEnqueuePlaylist
                onTriggered: backend.enqueuePlaylistCollection(true, root.navigationContext())
            }
            MenuItem {
                objectName: "playlistCollectionAppend"
                text: qsTr("Přidat na konec fronty")
                visible: backend.detailMeta.kind === "playlist" && !backend.detailMeta.dynamicMix
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy && backend.playerCanEditQueue && backend.detailCanEnqueuePlaylist
                onTriggered: backend.enqueuePlaylistCollection(false, root.navigationContext())
            }
            MenuItem {
                objectName: "uploadCollectionNext"
                text: qsTr("Přehrát jako další")
                visible: backend.detailMeta.kind === "upload_album" || backend.detailMeta.kind === "upload_artist"
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy && backend.playerCanEditQueue && backend.detailCanSavePlaylist
                onTriggered: backend.enqueueUploadCollection("detail", true, root.navigationContext())
            }
            MenuItem {
                objectName: "uploadCollectionAppend"
                text: qsTr("Přidat na konec fronty")
                visible: backend.detailMeta.kind === "upload_album" || backend.detailMeta.kind === "upload_artist"
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy && backend.playerCanEditQueue && backend.detailCanSavePlaylist
                onTriggered: backend.enqueueUploadCollection("detail", false, root.navigationContext())
            }
            MenuItem {
                objectName: "collectionPlaylistEdit"
                text: qsTr("Upravit playlist…")
                visible: backend.detailCanEditPlaylist
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy
                onTriggered: backend.openPlaylistEdit()
            }
            MenuItem {
                objectName: "collectionPlaylistDelete"
                text: qsTr("Smazat playlist…")
                visible: backend.detailCanDeletePlaylist
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy
                onTriggered: backend.openPlaylistDelete()
            }
        }
    }

    component PlaylistLoadBanner: Rectangle {
        objectName: "playlistLoadBanner"
        property bool sawLoading: backend.detailLoading
        visible: backend.detailMeta.dynamicMix === true || backend.detailLoading || !backend.detailComplete || doneTimer.running
        implicitHeight: pageLoadRow.implicitHeight + 20
        radius: 6
        color: backend.detailMeta.playlistLoadState === "error" ? "#3b2920"
             : backend.detailLoading || backend.detailMeta.dynamicMix === true ? "#23243b"
             : backend.detailComplete ? "#173328" : "#3b2920"
        Timer { id: doneTimer; interval: 4000 }
        Connections {
            target: backend
            function onDetailTitleChanged() {
                if (backend.detailLoading) { sawLoading = true; doneTimer.stop() }
                else if (sawLoading && backend.detailComplete && backend.detailMeta.kind === "playlist") {
                    sawLoading = false; doneTimer.restart()
                } else if (backend.detailMeta.kind !== "playlist") { sawLoading = false; doneTimer.stop() }
            }
        }
        RowLayout {
            id: pageLoadRow
            anchors.fill: parent
            anchors.margins: 10
            BusyIndicator {
                objectName: "playlistLoadSpinner"
                Layout.preferredWidth: 28
                Layout.preferredHeight: 28
                running: backend.detailLoading
                visible: running
            }
            ColumnLayout {
                Layout.fillWidth: true
                Label {
                    objectName: "playlistLoadTitle"
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: backend.detailMeta.dynamicMix === true
                        ? (backend.detailMeta.playlistLoadState === "error" ? qsTr("Další část mixu se nepodařila načíst")
                           : backend.detailLoading ? qsTr("Načítám další doporučení…")
                           : backend.detailMeta.playlistLoadState === "complete" ? qsTr("Mix už nenabízí další pokračování")
                           : qsTr("Dynamický mix · Počet načtených skladeb: %1").arg(backend.detailTracksModel.count))
                        : backend.detailLoading ? qsTr("Načítám další skladby…")
                        : backend.detailComplete ? root.loadedSongCountText(backend.detailTracksModel.count)
                        : qsTr("Načítání se nepodařilo dokončit")
                    color: "#eeeeee"
                    font.bold: true
                }
                Label {
                    Layout.fillWidth: true
                    visible: backend.detailMeta.dynamicMix === true || !backend.detailComplete
                    wrapMode: Text.Wrap
                    text: backend.detailMeta.dynamicMix === true
                        ? (backend.detailMeta.playlistLoadState === "error"
                           ? qsTr("Načtené skladby můžeš přehrát. Pro nové načtení otevři mix znovu.")
                           : qsTr("Další skladby se načtou podle postupu přehrávání."))
                        : backend.detailLoading
                        ? qsTr("Skladby už můžeš přehrávat dvojklikem. Další se doplní i do fronty; ostatní akce až po dokončení.")
                        : qsTr("Seznam není úplný. Otevři playlist znovu.")
                    color: "#bbbbbb"
                }
            }
        }
    }

    component ProfileNavigation: ColumnLayout {
        visible: backend.detailMeta.kind === "profile"
        spacing: 6
        RowLayout {
            Repeater {
                model: [{key: "videos", label: qsTr("Videa")}, {key: "playlists", label: qsTr("Playlisty")}]
                Button {
                    required property var modelData
                    objectName: "profileSection-" + modelData.key
                    text: modelData.label
                    checkable: true
                    checked: backend.detailMeta.section === modelData.key
                    enabled: !backend.busy
                    onClicked: backend.selectProfileSection(modelData.key)
                }
            }
            Button {
                objectName: "profileLoadMore"
                text: qsTr("Načíst další")
                visible: {
                    var meta = backend.detailMeta
                    var state = meta.profilePages && meta.profilePages[meta.section]
                    return !!state && !state.complete
                }
                enabled: !backend.busy
                onClicked: backend.loadMoreProfile()
            }
        }
        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: "#aaaaaa"
            text: backend.detailTracksModel.count === 0 ? qsTr("V této části nejsou dostupné žádné položky.")
                  : qsTr("Počet načtených položek: %1. Přehrávání používá načtená videa.").arg(backend.detailTracksModel.count)
        }
    }

    component ArtistNavigation: ColumnLayout {
        visible: backend.detailMeta.kind === "artist" || backend.detailMeta.kind === "upload_artist"
        spacing: 6
        Flow {
            objectName: "artistNavigationFlow"
            Layout.fillWidth: true
            Layout.preferredHeight: childrenRect.height
            spacing: 8
            Row {
                visible: backend.detailMeta.kind === "artist"
                spacing: 6
                height: artistOrder.implicitHeight
                ComboBox {
                    objectName: "artistSongScope"
                    visible: !!backend.detailMeta.songScopes
                    enabled: !backend.busy
                    width: 200
                    textRole: "label"
                    valueRole: "key"
                    model: [{key: "library", label: qsTr("Skladby")},
                            {key: "all", label: qsTr("Všechny skladby")}]
                    currentIndex: backend.detailMeta.songScope === "all" ? 1 : 0
                    onActivated: backend.selectArtistSongScope(currentValue)
                }
                Repeater {
                    model: [{key: "songs", label: qsTr("Skladby")},
                            {key: "albums", label: qsTr("Alba")},
                            {key: "singles", label: qsTr("Singly a EP")}]
                    Button {
                        required property var modelData
                        visible: modelData.key !== "songs" || !backend.detailMeta.songScopes
                        text: modelData.label
                        objectName: "artistSection-" + modelData.key
                        checkable: true
                        checked: backend.detailMeta.section === modelData.key
                        enabled: !backend.busy
                        onClicked: backend.selectArtistSection(modelData.key)
                    }
                }
            }
            Row {
                spacing: 8
                Label {
                    id: artistOrderLabel
                    height: artistOrder.height
                    verticalAlignment: Text.AlignVCenter
                    text: qsTr("Řadit podle")
                    color: "#aaaaaa"
                }
                ComboBox {
                    id: artistOrder
                    objectName: "artistOrder"
                    width: 170
                    Accessible.name: artistOrderLabel.text
                    enabled: !backend.busy
                    textRole: "label"
                    valueRole: "key"
                    model: backend.detailMeta.section === "songs"
                           ? [{key: "a_to_z", label: qsTr("A–Z")}, {key: "z_to_a", label: qsTr("Z–A")},
                              {key: "default", label: backend.detailMeta.kind === "upload_artist" ? qsTr("Původní pořadí") : qsTr("Původní pořadí YTM")}]
                           : [{key: "a_to_z", label: qsTr("A–Z")}, {key: "z_to_a", label: qsTr("Z–A")},
                              {key: "default", label: qsTr("Původní pořadí YTM")},
                              {key: "newest", label: qsTr("Od nejnovějších")},
                              {key: "oldest", label: qsTr("Od nejstarších")}]
                    currentIndex: {
                        var meta = backend.detailMeta
                        var order = (meta.orders && meta.orders[meta.section]) || "a_to_z"
                        for (var i = 0; i < model.length; ++i)
                            if (model[i].key === order) return i
                        return 0
                    }
                    onActivated: backend.setArtistOrder(currentValue)
                }
            }
        }
        Label {
            visible: backend.detailTracksModel.count === 0
            text: qsTr("V této části nejsou dostupné žádné položky.")
            color: "#aaaaaa"
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
    }

    component LibraryNavigation: ColumnLayout {
        spacing: 12

        GridLayout {
            id: libraryToolbar
            Layout.fillWidth: true
            columns: 2
            columnSpacing: 12
            rowSpacing: 8

            readonly property bool sortOnOwnRow: width < libraryTabs.singleRowWidth
                + librarySort.implicitWidth + columnSpacing

            Flow {
                id: libraryTabs
                objectName: "libraryTabs"
                Layout.row: 0
                Layout.column: 0
                Layout.columnSpan: !librarySort.visible || libraryToolbar.sortOnOwnRow ? 2 : 1
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredHeight: childrenRect.height
                spacing: 8

                readonly property real singleRowWidth: children.reduce(
                    (total, item) => total + item.width, 0) + (children.length - 1) * spacing

                Label {
                    text: qsTr("Knihovna")
                    color: "white"
                    font.pixelSize: 28
                    font.bold: true
                    width: implicitWidth + 10
                    height: libraryOrder.height
                    verticalAlignment: Text.AlignVCenter
                }

                Button {
                    text: qsTr("Playlisty")
                    checkable: true
                    checked: root.currentPage === 1 && root.currentLibrarySection === "playlists"
                    onClicked: root.selectLibrarySection("playlists", qsTr("Playlisty"))
                }
                Button {
                    text: qsTr("Skladby")
                    checkable: true
                    checked: root.currentPage === 1 && root.currentLibrarySection === "songs"
                    onClicked: root.selectLibrarySection("songs", qsTr("Skladby"))
                }
                Button {
                    text: qsTr("Alba")
                    checkable: true
                    checked: root.currentPage === 1 && root.currentLibrarySection === "albums"
                    onClicked: root.selectLibrarySection("albums", qsTr("Alba"))
                }
                Button {
                    text: qsTr("Interpreti")
                    checkable: true
                    checked: root.currentPage === 1 && root.currentLibrarySection === "artists"
                    onClicked: root.selectLibrarySection("artists", qsTr("Interpreti"))
                }
                Button {
                    text: qsTr("Profily")
                    checkable: true
                    checked: root.currentPage === 1 && root.currentLibrarySection === "channels"
                    onClicked: root.selectLibrarySection("channels", qsTr("Profily"))
                }
                Button {
                    text: qsTr("Podcasty")
                    checkable: true
                    checked: root.currentPage === 1 && root.currentLibrarySection === "podcasts"
                    onClicked: root.selectLibrarySection("podcasts", qsTr("Podcasty"))
                }
                Button {
                    objectName: "uploadsNavigationButton"
                    text: qsTr("Nahrané")
                    checkable: true
                    checked: root.currentPage === 1 && root.currentLibrarySection.indexOf("upload_") === 0
                    onClicked: root.openUploads()
                }

            }

            RowLayout {
                id: librarySort
                objectName: "librarySort"
                Layout.row: libraryToolbar.sortOnOwnRow ? 1 : 0
                Layout.column: libraryToolbar.sortOnOwnRow ? 0 : 1
                Layout.columnSpan: libraryToolbar.sortOnOwnRow ? 2 : 1
                Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                visible: root.currentPage === 1 && backend.detailTitle.length === 0
                spacing: 8

                Label {
                    id: libraryOrderLabel
                    text: qsTr("Řadit podle")
                    color: "#aaaaaa"
                }
                ComboBox {
                    id: libraryOrder
                    objectName: "libraryOrder"
                    Accessible.name: libraryOrderLabel.text
                    Layout.preferredWidth: 170
                    model: root.libraryOrderLabels()
                    currentIndex: {
                        var values = root.libraryOrderValues()
                        var index = values.indexOf(root.currentLibraryOrder)
                        return index >= 0 ? index : 0
                    }
                    onActivated: {
                        var values = root.libraryOrderValues()
                        root.currentLibraryOrder = values[currentIndex]
                        backend.loadLibrarySection(
                            root.currentLibrarySection,
                            root.currentLibraryOrder
                        )
                    }
                }
            }
        }

        RowLayout {
            visible: root.currentPage === 1 && root.currentLibrarySection.indexOf("upload_") === 0
            spacing: 8
            Label {
                text: qsTr("Nahrané soubory:")
                color: "#999999"
            }
            Button {
                objectName: "uploadAlbumsTab"
                text: qsTr("Alba")
                checkable: true
                checked: root.currentPage === 1 && root.currentLibrarySection === "upload_albums"
                onClicked: root.selectLibrarySection("upload_albums", qsTr("Nahraná alba"))
            }
            Button {
                objectName: "uploadArtistsTab"
                text: qsTr("Interpreti")
                checkable: true
                checked: root.currentPage === 1 && root.currentLibrarySection === "upload_artists"
                onClicked: root.selectLibrarySection("upload_artists", qsTr("Nahraní interpreti"))
            }
            Button {
                objectName: "uploadSongsTab"
                text: qsTr("Skladby")
                checkable: true
                checked: root.currentPage === 1 && root.currentLibrarySection === "upload_songs"
                onClicked: root.selectLibrarySection("upload_songs", qsTr("Nahrané skladby"))
            }
            Item { Layout.fillWidth: true }
        }
    }

    component TrackPage: Item {
        id: trackPage
        required property string heading
        required property var tracks
        required property string sourceKey

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 12

            RowLayout {
                Layout.fillWidth: true
                Label {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.maximumWidth: implicitWidth + 2
                    text: heading
                    color: "white"
                    font.pixelSize: 28
                    font.bold: true
                    elide: Text.ElideRight
                }
                HeaderActionsButton {
                    id: uploadMenuButton
                    objectName: root.currentLibrarySection === "songs" ? "librarySongsMenuButton" : "uploadSongsMenuButton"
                    visible: trackPage.sourceKey === "library" && (root.currentLibrarySection === "songs" || root.currentLibrarySection === "upload_songs")
                    enabled: backend.connected && !backend.busy
                    hoverEnabled: true
                    ToolTip.visible: hovered
                    ToolTip.text: root.currentLibrarySection === "songs" ? qsTr("Možnosti skladeb") : qsTr("Možnosti nahraných skladeb")
                    onClicked: uploadMenu.popup(uploadMenuButton, 0, height)
                    Menu {
                        id: uploadMenu
                        objectName: "uploadSongsMenu"
                        popupType: Popup.Item
                        width: 260
                        palette.text: "#eeeeee"
                        palette.windowText: "#eeeeee"
                        palette.highlight: "#6757b8"
                        background: Rectangle { color: "#242424"; border.color: "#555555"; radius: 5 }
                        MenuItem {
                            objectName: root.currentLibrarySection === "songs" ? "librarySongsShuffle" : "uploadSongsShuffle"
                            text: qsTr("Přehrát náhodně")
                            enabled: backend.connected && !backend.busy && backend.playerCanEditQueue && trackPage.tracks.count > 0 && backend.uploadSongsComplete
                            onTriggered: root.currentLibrarySection === "songs" ? backend.shuffleLibrarySongs() : backend.shuffleUploadSongs()
                        }
                        MenuItem {
                            objectName: "uploadSongsNext"
                            visible: root.currentLibrarySection === "upload_songs"
                            height: visible ? implicitHeight : 0
                            text: qsTr("Přehrát jako další")
                            enabled: backend.connected && !backend.busy && backend.playerCanEditQueue && trackPage.tracks.count > 0 && backend.uploadSongsComplete
                            onTriggered: backend.enqueueUploadCollection("library", true, root.navigationContext())
                        }
                        MenuItem {
                            objectName: "uploadSongsAppend"
                            visible: root.currentLibrarySection === "upload_songs"
                            height: visible ? implicitHeight : 0
                            text: qsTr("Přidat na konec fronty")
                            enabled: backend.connected && !backend.busy && backend.playerCanEditQueue && trackPage.tracks.count > 0 && backend.uploadSongsComplete
                            onTriggered: backend.enqueueUploadCollection("library", false, root.navigationContext())
                        }
                        MenuItem {
                            objectName: "uploadSongsPlaylistSave"
                            visible: root.currentLibrarySection === "upload_songs"
                            height: visible ? implicitHeight : 0
                            text: qsTr("Přidat seznam do playlistu…")
                            enabled: backend.connected && !backend.busy && trackPage.tracks.count > 0 && backend.uploadSongsComplete
                            onTriggered: backend.openUploadSongsPlaylistSave()
                        }
                    }
                }
                Item { Layout.fillWidth: true }
            }
            Label {
                text: root.itemCountText(tracks.count)
                color: "#999999"
                font.pixelSize: 13
            }
            Rectangle {
                objectName: "uploadSongsLoadBanner"
                Layout.fillWidth: true
                implicitHeight: uploadLoadRow.implicitHeight + 20
                visible: trackPage.sourceKey === "library" && (root.currentLibrarySection === "songs" || root.currentLibrarySection === "upload_songs")
                         && (!backend.librarySongsComplete || uploadDoneTimer.running)
                radius: 6
                color: backend.librarySongsLoading ? "#23243b" : backend.librarySongsComplete ? "#173328" : "#3b2920"
                Timer { id: uploadDoneTimer; interval: 4000 }
                Connections {
                    target: backend
                    function onUploadSongsLoadChanged() {
                        if (backend.librarySongsComplete) uploadDoneTimer.restart()
                        else uploadDoneTimer.stop()
                    }
                }
                RowLayout {
                    id: uploadLoadRow
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 12
                    BusyIndicator {
                        objectName: "uploadSongsLoadSpinner"
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        visible: running
                        running: backend.librarySongsLoading
                    }
                    Label {
                        objectName: "uploadSongsLoadTitle"
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        color: "#eeeeee"
                        text: backend.librarySongsLoading
                            ? qsTr("Načítám další skladby… · %1 načteno\nSkladby už můžeš přehrávat dvojklikem. Další se doplní i do fronty. Akce nad celým seznamem budou dostupné po dokončení.").arg(trackPage.tracks.count)
                            : backend.librarySongsComplete ? root.loadedSongCountText(trackPage.tracks.count)
                            : (root.currentLibrarySection === "songs"
                               ? qsTr("Načítání se nepodařilo dokončit. Seznam není úplný. Otevři Skladby znovu.")
                               : qsTr("Načítání se nepodařilo dokončit. Seznam není úplný. Otevři Nahrané skladby znovu."))
                    }
                }
            }
            TrackListView {
                id: trackList
                selectionKey: trackPage.sourceKey
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: tracks
                delegate: TrackDelegate {
                    sourceKey: trackPage.sourceKey
                    enabled: trackPage.sourceKey !== "library" || (root.currentLibrarySection !== "songs" && root.currentLibrarySection !== "upload_songs")
                             || backend.librarySongsComplete || backend.librarySongsLoading
                }
                ScrollBar.vertical: ScrollBar { }
 Connections {
     target: root
     function onPlayingSourceRequested() {
         root.revealPlayingSource(trackList, trackPage.sourceKey)
     }
 }
 Connections {
                    target: backend
                    function onPlayerTrackChanged() {
                        root.followPlayingRow(trackList, trackPage.sourceKey)
                    }
                }
            }
        }
    }

    component CardGrid: Item {
        required property string heading
        required property var items
        required property bool isMix

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 16

            RowLayout {
                Layout.fillWidth: true
                Label {
                    text: heading
                    color: "white"
                    font.pixelSize: 28
                    font.bold: true
                }
                HeaderActionsButton {
                    id: libraryMenuButton
                    objectName: "libraryPlaylistMenuButton"
                    visible: !isMix && root.currentPage === 1 && root.currentLibrarySection === "playlists"
                    enabled: backend.connected && !backend.busy
                    hoverEnabled: true
                    ToolTip.visible: hovered
                    ToolTip.text: qsTr("Možnosti playlistů")
                    onClicked: libraryMenu.popup(libraryMenuButton, 0, height)
                    Menu {
                        id: libraryMenu
                        objectName: "libraryPlaylistMenu"
                        popupType: Popup.Item
                        width: 220
                        palette.text: "#eeeeee"
                        palette.windowText: "#eeeeee"
                        palette.highlight: "#6757b8"
                        background: Rectangle { color: "#242424"; border.color: "#555555"; radius: 5 }
                        MenuItem {
                            objectName: "newEmptyPlaylistAction"
                            text: qsTr("Nový playlist…")
                            enabled: backend.connected && !backend.busy
                            onTriggered: backend.beginEmptyPlaylist()
                        }
                    }
                }
                Item { Layout.fillWidth: true }
                Label {
                    text: root.itemCountText(items.count)
                    color: "#888888"
                }
            }

            GridView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                cellWidth: 230
                cellHeight: 285
                model: items
                ScrollBar.vertical: ScrollBar { }

                delegate: Item {
                    required property string kind
                    required property string title
                    required property string subtitle
                    required property string playlistId
                    required property string browseId
                    required property string thumbnail

                    width: 218
                    height: 272
                    property string cardKind: kind
                    property string cardTitle: title
                    property string cardSubtitle: subtitle
                    property string cardPlaylistId: playlistId
                    property string cardBrowseId: browseId
                    property string cardThumbnail: thumbnail

                    Rectangle {
                        anchors.fill: parent
                        radius: 9
                        color: cardMouse.containsMouse ? "#202020" : "#151515"

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 9

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: width
                                radius: 7
                                color: "#292929"
                                clip: true

                                Image {
                                    anchors.fill: parent
                                    source: cardThumbnail
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                    cache: true
                                }
                            }

                            Label {
                                Layout.fillWidth: true
                                text: cardTitle
                                color: "white"
                                font.pixelSize: 15
                                font.bold: true
                                maximumLineCount: 2
                                wrapMode: Text.Wrap
                                elide: Text.ElideRight
                            }
                            Label {
                                Layout.fillWidth: true
                                text: cardSubtitle
                                color: "#999999"
                                font.pixelSize: 12
                                maximumLineCount: 2
                                wrapMode: Text.Wrap
                                elide: Text.ElideRight
                            }
                            Item { Layout.fillHeight: true }
                        }

                        MouseArea {
                            id: cardMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (isMix)
                                    backend.loadMixTracks(cardPlaylistId, cardTitle)
                                else
                                    backend.openLibraryItem(
                                        cardKind,
                                        cardBrowseId,
                                        cardPlaylistId,
                                        cardTitle
                                    )
                            }
                        }
                    }
                }
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0
        Keys.priority: Keys.AfterItem
        Keys.onPressed: function(event) {
            if (event.key === Qt.Key_Escape && backend.selectedTrackIndices.length > 0) {
                backend.clearTrackSelection()
                event.accepted = true
            }
        }

        Rectangle {
            Layout.preferredWidth: 245
            Layout.fillHeight: true
            color: "#090909"
            border.color: "#292929"
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 7

                Label {
                    text: "♫  FelisMusic"
                    color: "white"
                    font.pixelSize: 25
                    font.bold: true
                    Layout.leftMargin: 10
                    Layout.topMargin: 6
                    Layout.bottomMargin: 22
                }

                NavButton { pageIndex: 0; pageText: qsTr("Hledat") }
                NavButton { pageIndex: 1; pageText: qsTr("Knihovna") }
                NavButton { pageIndex: 2; pageText: qsTr("Oblíbená hudba") }
                NavButton { pageIndex: 3; pageText: qsTr("Historie") }
                NavButton { pageIndex: 4; pageText: qsTr("Mixy pro vás") }
                NavButton { pageIndex: 5; pageText: qsTr("Fronta") + (backend.playerQueueCount > 0 ? " (" + backend.playerQueueCount + ")" : ""); objectName: "queueButton" }

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    Image {
                        objectName: "sidebarAppIcon"
                        anchors.centerIn: parent
                        width: Math.max(0, Math.min(192, parent.width, parent.height - 12))
                        height: width
                        visible: width >= 36
                        source: "felismusic.svg"
                        fillMode: Image.PreserveAspectFit
                        sourceSize.width: 192
                        sourceSize.height: 192
                    }
                }

                Label {
                    text: qsTr("Desktop GUI · %1").arg(fcmVersion)
                    color: "#777777"
                    font.pixelSize: 12
                    Layout.leftMargin: 10
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 70
                    color: "#111111"
                    border.color: "#292929"
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 24
                        anchors.rightMargin: 24
                        spacing: 16

                        Label {
                            text: "FelisMusic"
                            color: "white"
                            font.pixelSize: 20
                            font.bold: true
                        }

                        Label {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            elide: Text.ElideRight
                            horizontalAlignment: Text.AlignRight
                            objectName: "connectionStatusLabel"
                            text: backend.busy
                                  ? backend.status
                                  : (backend.connected
                                     ? qsTr("Připojeno · %1").arg(backend.accountName)
                                     : backend.status)
                            color: backend.statusIsError ? "#ff8a80" : "#999999"
                            font.pixelSize: 13
                        }
                        PlayerTextButton {
                            objectName: "outputDevicesButton"
                            text: qsTr("Výstupy")
                            implicitWidth: 78
                            onClicked: castDialog.open()
                        }
                        PlayerTextButton {
                            objectName: "accountButton"
                            text: qsTr("Účet")
                            enabled: !backend.busy
                            onClicked: accountMenu.popup(this, width - accountMenu.width, height)
                            Menu {
                                id: accountMenu
                                objectName: "accountMenu"
                                popupType: Popup.Item
                                MenuItem {
                                    objectName: "accountLoginAction"
                                    text: qsTr("Přihlásit / obnovit přihlášení")
                                    enabled: !backend.busy
                                    onTriggered: backend.openLogin()
                                }
                                MenuItem {
                                    objectName: "accountLogoutAction"
                                    text: qsTr("Odhlásit…")
                                    enabled: !backend.busy
                                    onTriggered: logoutDialog.open()
                                }
                            }
                        }
                        PlayerTextButton {
                            objectName: "infoButton"
                            text: qsTr("Info")
                            onClicked: infoMenu.popup(this, width - infoMenu.width, height)
                            Menu {
                                id: infoMenu
                                objectName: "infoMenu"
                                popupType: Popup.Item
                                MenuItem {
                                    text: qsTr("Informace o skladbě")
                                    enabled: backend.playerHasTrack
                                    onTriggered: { trackInfo.selectedInfo = null; trackInfo.open() }
                                }
                                MenuItem {
                                    objectName: "aboutAction"
                                    text: qsTr("O aplikaci")
                                    onTriggered: aboutDialog.open()
                                }
                            }
                        }
                    }
                }

                StackLayout {
                    id: stack
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    currentIndex: root.currentPage

                    Item {
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 22
                            spacing: 14

                            Label {
                                text: qsTr("Hledat")
                                color: "white"
                                font.pixelSize: 28
                                font.bold: true
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Button {
                                    objectName: "searchCatalogScope"
                                    text: "YT Music"
                                    checkable: true
                                    checked: root.currentSearchScope === "catalog"
                                    onClicked: root.selectSearchScope("catalog")
                                }
                                Button {
                                    objectName: "searchLibraryScope"
                                    text: qsTr("Knihovna")
                                    checkable: true
                                    checked: root.currentSearchScope === "library"
                                    onClicked: root.selectSearchScope("library")
                                }
                                Button {
                                    objectName: "searchUploadsScope"
                                    text: qsTr("Nahrané soubory")
                                    checkable: true
                                    checked: root.currentSearchScope === "uploads"
                                    onClicked: root.selectSearchScope("uploads")
                                }
                                Item { Layout.fillWidth: true }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                ComboBox {
                                    id: searchMode
                                    objectName: "searchTypeCombo"
                                    visible: root.currentSearchScope !== "uploads"
                                    enabled: visible
                                    Layout.preferredWidth: visible ? 175 : 0
                                    model: root.searchModeLabels()
                                    currentIndex: {
                                        var values = root.searchModeValues()
                                        var index = values.indexOf(root.currentSearchMode)
                                        return index >= 0 ? index : 0
                                    }
                                    onActivated: {
                                        var values = root.searchModeValues()
                                        root.currentSearchMode = values[currentIndex]
                                        if (searchField.text.trim().length > 0)
                                            backend.search(
                                                searchField.text,
                                                root.currentSearchMode,
                                                root.currentSearchScope
                                            )
                                    }
                                }

                                TextField {
                                    id: searchField
                                    objectName: "searchInput"
                                    Layout.fillWidth: true
                                    placeholderText: root.currentSearchScope === "uploads"
                                                     ? qsTr("Hledat v nahraných souborech…")
                                                     : (root.currentSearchScope === "library"
                                                        ? qsTr("Hledat v knihovně…")
                                                        : qsTr("Hledat v YT Music…"))
                                    onAccepted: backend.search(
                                        text, root.currentSearchMode, root.currentSearchScope
                                    )
                                }
                                Button {
                                    text: qsTr("Hledat")
                                    onClicked: backend.search(
                                        searchField.text,
                                        root.currentSearchMode,
                                        root.currentSearchScope
                                    )
                                }
                            }

                            Loader {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                sourceComponent: backend.detailTitle.length > 0
                                                 ? searchDetailComponent
                                                 : searchResultsComponent
                            }
                        }

                        Component {
                            id: searchResultsComponent
                            TrackListView {
                                id: searchResultsList
                                selectionKey: "search"
                                clip: true
                                model: backend.searchResultsModel
                                delegate: TrackDelegate { sourceKey: "search" }
                                ScrollBar.vertical: ScrollBar { }
 Connections {
     target: root
     function onPlayingSourceRequested() {
         root.revealPlayingSource(searchResultsList, "search")
     }
 }
 Connections {
                                    target: backend
                                    function onPlayerTrackChanged() { root.followPlayingRow(searchResultsList, "search") }
                                }
                            }
                        }

                        Component {
                            id: searchDetailComponent
                            Item {
                                ColumnLayout {
                                    anchors.fill: parent
                                    spacing: 12
                                    CollectionHeader {
                                        onGoBack: backend.backDetail()
                                    }
                                    PlaylistLoadBanner { Layout.fillWidth: true }
                                    ArtistNavigation { Layout.fillWidth: true }
                                    ProfileNavigation { Layout.fillWidth: true }
                                    TrackListView {
                                        id: searchDetailList
                                        selectionKey: "detail"
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        clip: true
                                        model: backend.detailTracksModel
                                        delegate: TrackDelegate { sourceKey: "detail"; enabled: backend.detailComplete || backend.detailLoading }
                                        ScrollBar.vertical: ScrollBar { }
 Connections {
     target: root
     function onPlayingSourceRequested() {
         root.revealPlayingSource(searchDetailList, "detail")
     }
 }
 Connections {
                                            target: backend
                                            function onPlayerTrackChanged() { root.followPlayingRow(searchDetailList, "detail") }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Item {
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 22
                            spacing: 12

                            LibraryNavigation {
                                Layout.fillWidth: true
                            }

                            Loader {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                Layout.fillHeight: true
                                sourceComponent: backend.detailTitle.length > 0
                                                 ? libraryDetailComponent
                                                 : ((root.currentLibrarySection === "songs"
                                                     || root.currentLibrarySection === "upload_songs")
                                                    ? libraryTracksComponent
                                                    : libraryCardsComponent)
                            }
                        }

                        Component {
                            id: libraryCardsComponent
                            CardGrid {
                                heading: root.currentLibraryLabel
                                items: backend.libraryItemsModel
                                isMix: false
                            }
                        }

                        Component {
                            id: libraryTracksComponent
                            TrackPage {
                                heading: root.currentLibraryLabel
                                tracks: backend.libraryItemsModel
                                sourceKey: "library"
                            }
                        }

                        Component {
                            id: libraryDetailComponent
                            Item {
                                ColumnLayout {
                                    anchors.fill: parent
                                    spacing: 12
                                    CollectionHeader {
                                        onGoBack: backend.backDetail()
                                    }
                                    PlaylistLoadBanner { Layout.fillWidth: true }
                                    ArtistNavigation { Layout.fillWidth: true }
                                    ProfileNavigation { Layout.fillWidth: true }
                                    TrackListView {
                                        id: libraryDetailList
                                        selectionKey: "detail"
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        clip: true
                                        model: backend.detailTracksModel
                                        delegate: TrackDelegate { sourceKey: "detail"; enabled: backend.detailComplete || backend.detailLoading }
                                        ScrollBar.vertical: ScrollBar { }
 Connections {
     target: root
     function onPlayingSourceRequested() {
         root.revealPlayingSource(libraryDetailList, "detail")
     }
 }
 Connections {
                                            target: backend
                                            function onPlayerTrackChanged() { root.followPlayingRow(libraryDetailList, "detail") }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Item {
                        id: likedPage
                        property bool sawLoading: false
                        Timer {
                            id: likedCompletionTimer
                            objectName: "likedCompletionTimer"
                            interval: 4000
                        }
                        Connections {
                            target: backend
                            function onLikedLoadChanged() {
                                if (backend.likedLoading) {
                                    likedPage.sawLoading = true
                                    likedCompletionTimer.stop()
                                } else {
                                    if (likedPage.sawLoading && backend.likedComplete)
                                        likedCompletionTimer.restart()
                                    likedPage.sawLoading = false
                                }
                            }
                        }
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 22
                            spacing: 12

                            GridLayout {
                                id: likedHeader
                                Layout.fillWidth: true
                                columns: 2
                                columnSpacing: 12
                                rowSpacing: 8

                                readonly property bool controlsOnOwnRow: width < likedHeading.implicitWidth
                                    + likedControls.implicitWidth + columnSpacing

                                Label {
                                    id: likedHeading
                                    Layout.row: 0
                                    Layout.column: 0
                                    Layout.columnSpan: likedHeader.controlsOnOwnRow ? 2 : 1
                                    Layout.fillWidth: true
                                    text: qsTr("Oblíbená hudba")
                                    color: "white"
                                    font.pixelSize: 28
                                    font.bold: true
                                }
                                RowLayout {
                                    id: likedControls
                                    objectName: "likedControls"
                                    Layout.row: likedHeader.controlsOnOwnRow ? 1 : 0
                                    Layout.column: likedHeader.controlsOnOwnRow ? 0 : 1
                                    Layout.columnSpan: likedHeader.controlsOnOwnRow ? 2 : 1
                                    Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                                    spacing: 8

                                    readonly property bool canStartPlayback: backend.likedComplete
                                        && backend.likedModel.count > 0 && backend.connected
                                        && !backend.busy && backend.playerCanEditQueue

                                    Button {
                                        objectName: "likedShuffle"
                                        text: qsTr("Přehrát náhodně")
                                        enabled: likedControls.canStartPlayback
                                        onClicked: backend.startLikedPlayback("shuffle")
                                    }
                                    Button {
                                        objectName: "likedRadio"
                                        text: qsTr("Spustit mix")
                                        enabled: likedControls.canStartPlayback
                                        onClicked: backend.startLikedPlayback("radio")
                                    }
                                    Label {
                                        id: likedOrderLabel
                                        text: qsTr("Řadit podle")
                                        color: "#aaaaaa"
                                    }
                                    ComboBox {
                                        id: likedOrder
                                        Accessible.name: likedOrderLabel.text
                                        enabled: backend.likedComplete
                                        Layout.preferredWidth: 170
                                        model: [qsTr("Výchozí YTM"), qsTr("A–Z"), qsTr("Z–A")]
                                        currentIndex: {
                                            var values = ["", "a_to_z", "z_to_a"]
                                            var index = values.indexOf(root.currentLikedOrder)
                                            return index >= 0 ? index : 0
                                        }
                                        onActivated: {
                                            var values = ["", "a_to_z", "z_to_a"]
                                            root.currentLikedOrder = values[currentIndex]
                                            backend.sortLiked(root.currentLikedOrder)
                                        }
                                    }
                                }
                            }

                            Label {
                                text: root.itemCountText(backend.likedModel.count)
                                color: "#999999"
                                font.pixelSize: 13
                            }

                            Rectangle {
                                objectName: "likedLoadBanner"
                                Layout.fillWidth: true
                                implicitHeight: likedLoadRow.implicitHeight + 24
                                visible: backend.likedLoading || !backend.likedComplete || likedCompletionTimer.running
                                color: backend.likedComplete ? "#173328" : backend.likedLoading ? "#23243b" : "#3b2920"
                                radius: 6
                                RowLayout {
                                    id: likedLoadRow
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 12
                                    BusyIndicator {
                                        objectName: "likedLoadSpinner"
                                        Layout.preferredWidth: 28
                                        Layout.preferredHeight: 28
                                        running: backend.likedLoading
                                        visible: running
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 4
                                        Label {
                                            objectName: "likedLoadTitle"
                                            Layout.fillWidth: true
                                            wrapMode: Text.Wrap
                                            text: backend.likedLoading ? qsTr("Načítám další skladby…")
                                                : backend.likedComplete ? root.loadedSongCountText(backend.likedModel.count)
                                                : qsTr("Načítání se nepodařilo dokončit")
                                            font.pixelSize: 16
                                            font.bold: true
                                            color: "#eeeeee"
                                        }
                                        Label {
                                            Layout.fillWidth: true
                                            visible: !backend.likedComplete
                                            wrapMode: Text.Wrap
                                            text: backend.likedLoading
                                                ? qsTr("Skladby už můžeš přehrávat dvojklikem. Další se doplní i do fronty; řazení a ostatní akce až po dokončení.")
                                                : qsTr("Seznam není úplný. Otevři Oblíbenou hudbu znovu.")
                                            color: "#bbbbbb"
                                            font.pixelSize: 13
                                        }
                                    }
                                }
                            }

                            TrackListView {
                                id: likedList
                                selectionKey: "liked"
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                clip: true
                                model: backend.likedModel
                                delegate: TrackDelegate { sourceKey: "liked"; enabled: backend.likedComplete || backend.likedLoading }
                                ScrollBar.vertical: ScrollBar { }
 Connections {
     target: root
     function onPlayingSourceRequested() {
         root.revealPlayingSource(likedList, "liked")
     }
 }
 Connections {
                                    target: backend
                                    function onPlayerTrackChanged() { root.followPlayingRow(likedList, "liked") }
                                }
                            }
                        }
                    }

                    TrackPage { heading: qsTr("Historie"); tracks: backend.historyModel; sourceKey: "history" }

                    Item {
                        Loader {
                            anchors.fill: parent
                            sourceComponent: backend.detailTracksModel.count > 0 ? mixDetailComponent : mixGridComponent
                        }
                        Component {
                            id: mixGridComponent
                            CardGrid { heading: qsTr("Mixy pro vás"); items: backend.mixesModel; isMix: true }
                        }
                        Component {
                            id: mixDetailComponent
                            Item {
                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 22
                                    CollectionHeader {
                                        backText: qsTr("← Mixy")
                                        onGoBack: backend.clearDetail()
                                    }
                                    PlaylistLoadBanner { Layout.fillWidth: true }
                                    TrackListView {
                                        id: mixDetailList
                                        selectionKey: "detail"
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        clip: true
                                        model: backend.detailTracksModel
                                        delegate: TrackDelegate { sourceKey: "detail"; enabled: backend.detailComplete || backend.detailLoading }
                                        ScrollBar.vertical: ScrollBar { }
 Connections {
     target: root
     function onPlayingSourceRequested() {
         root.revealPlayingSource(mixDetailList, "detail")
     }
 }
 Connections {
                                            target: backend
                                            function onPlayerTrackChanged() { root.followPlayingRow(mixDetailList, "detail") }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Item {
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 22
                            spacing: 12

                            RowLayout {
                                Layout.fillWidth: true
                                Label {
                                    text: qsTr("Fronta")
                                    color: "white"
                                    font.pixelSize: 28
                                    font.bold: true
                                }
                                Label {
                                    objectName: "queuePosition"
                                    Layout.fillWidth: true
                                    text: (backend.playerHasTrack ? (backend.playerQueueIndex + 1) + " / " + backend.playerQueueCount : "0 / 0")
                                          + (backend.playerWaitingForTracks ? qsTr(" · Čekám na další skladby…")
                                             : backend.playerQueueLoading ? qsTr(" · Načítám další skladby…")
                                             : backend.playerQueueIncomplete ? qsTr(" · Seznam není úplný")
                                             : backend.playerQueueDynamic ? qsTr(" · Dynamický mix") : "")
                                    wrapMode: Text.Wrap
                                    color: "#b9b0ff"
                                    font.pixelSize: 16
                                }
                                Button {
                                    objectName: "queueShuffleButton"
                                    text: qsTr("Zamíchat")
                                    enabled: backend.connected && !backend.busy && backend.playerCanShuffle
                                    hoverEnabled: true
                                    ToolTip.visible: hovered
                                    ToolTip.text: backend.playerCanShuffle
                                                  ? qsTr("Zamíchat frontu; aktuální skladba pokračuje")
                                                  : qsTr("Tuto frontu nyní nelze zamíchat")
                                    onClicked: backend.shuffleQueue()
                                }
                                Button {
                                    text: qsTr("Na aktuální")
                                    enabled: backend.playerHasTrack
                                    onClicked: root.revealQueueRow()
                                }
                            }
                            Label {
                                Layout.fillWidth: true
                                text: backend.playingListTitle
                                color: "#aaaaaa"
                                elide: Text.ElideRight
                            }
                            Label {
                                visible: !backend.playerHasTrack
                                text: qsTr("Fronta je prázdná. Vyber skladbu v knihovně nebo hledání.")
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                color: "#aaaaaa"
                            }
                            TrackListView {
                                id: queueList
                                selectionKey: "playing"
                                objectName: "queueList"
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.minimumWidth: 0
                                clip: true
                                model: backend.playingTracksModel
                                delegate: TrackDelegate { sourceKey: "playing" }
                                ScrollBar.vertical: ScrollBar { }
                                Connections {
                                    target: backend
                                    function onPlayerTrackChanged() { Qt.callLater(root.revealQueueRow) }
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    objectName: "singleSelectionActions"
                    visible: backend.selectedTrackIndices.length === 1
                    Layout.fillWidth: true
                    Layout.leftMargin: 22
                    Layout.rightMargin: 22
                    Button {
                        objectName: "clearSingleTrackSelection"
                        text: qsTr("Zrušit výběr ×")
                        flat: true
                        palette.buttonText: "#dddddd"
                        onClicked: backend.clearTrackSelection()
                    }
                    Item { Layout.fillWidth: true }
                }

                RowLayout {
                    objectName: "selectionActions"
                    visible: backend.selectedTrackIndices.length > 1
                    Layout.fillWidth: true
                    Layout.leftMargin: 22
                    Layout.rightMargin: 22
                    spacing: 12
                    Label {
                        objectName: "selectedTrackCount"
                        text: qsTr("Vybráno: %1").arg(backend.selectedTrackIndices.length)
                        color: "#dddddd"
                    }
                    Button {
                        id: selectedActionsButton
                        objectName: "selectedActionsButton"
                        text: qsTr("Akce ⋮")
                        onClicked: selectedActions.popup(selectedActionsButton, 0, -selectedActions.height)
                    }
                    Button {
                        objectName: "clearTrackSelection"
                        text: qsTr("Zrušit výběr ×")
                        onClicked: backend.clearTrackSelection()
                    }
                    Item { Layout.fillWidth: true }
                    Menu {
                        id: selectedActions
                        objectName: "selectedActionsMenu"
                        popupType: Popup.Item
                        width: 240
                        palette.text: "#eeeeee"
                        palette.windowText: "#eeeeee"
                        palette.highlight: "#6757b8"
                        background: Rectangle { color: "#242424"; border.color: "#555555"; radius: 5 }
                        MenuItem {
                            text: qsTr("Přehrát jako další")
                            enabled: backend.playerCanEditQueue && backend.selectedTrackIndices.length > 1
                            onTriggered: backend.enqueueSelection(true, root.navigationContext())
                        }
                        MenuItem {
                            text: qsTr("Přidat na konec fronty")
                            enabled: backend.playerCanEditQueue && backend.selectedTrackIndices.length > 1
                            onTriggered: backend.enqueueSelection(false, root.navigationContext())
                        }
                        MenuItem {
                            text: qsTr("Přidat do playlistu…")
                            enabled: backend.connected && !backend.busy && backend.selectionCanSavePlaylist
                                     && backend.selectedTrackIndices.length > 1
                            onTriggered: backend.openSelectedPlaylistSave()
                        }
                        MenuItem {
                            objectName: "selectedPlaylistRemoveAction"
                            text: qsTr("Odebrat z playlistu…")
                            visible: backend.selectionCanRemovePlaylist
                            height: visible ? implicitHeight : 0
                            enabled: backend.connected && !backend.busy && backend.selectionCanRemovePlaylist
                            onTriggered: backend.openSelectedPlaylistRemove()
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 108
                    color: "#181818"
                    border.color: "#303030"
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 18
                        anchors.rightMargin: 18
                        spacing: 14

                        Rectangle {
                            Layout.preferredWidth: 64
                            Layout.preferredHeight: 64
                            radius: 5
                            color: "#292929"
                            clip: true

                            Image {
                                anchors.fill: parent
                                source: backend.playerThumbnail
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: true
                                visible: backend.playerHasTrack && status === Image.Ready
                            }

                            MouseArea {
                                anchors.fill: parent
                                enabled: backend.playerHasTrack
                                hoverEnabled: true
                                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: root.showPlayingList()
                                ToolTip.visible: containsMouse && enabled
                                ToolTip.text: qsTr("Zobrazit přehrávaný seznam")
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.preferredWidth: 300
                            Layout.maximumWidth: 420
                            id: nowPlayingMetadata
                            spacing: 3

                            readonly property bool showTrackDetails: backend.playerHasTrack
                                && (nowPlayingTitle.truncated || nowPlayingSubtitle.truncated)
                            readonly property string trackDetails: backend.playerSubtitle
                                ? backend.playerTitle + " — " + backend.playerSubtitle : backend.playerTitle

                            Label {
                                id: nowPlayingTitle
                                objectName: "nowPlayingTitle"
                                text: backend.playerHasTrack ? backend.playerTitle : qsTr("Nic se nepřehrává")
                                color: "white"
                                font.pixelSize: 15
                                font.bold: true
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                HoverHandler { id: nowPlayingTitleHover }
                                ToolTip.visible: nowPlayingMetadata.showTrackDetails && nowPlayingTitleHover.hovered
                                ToolTip.text: nowPlayingMetadata.trackDetails
                            }
                            Label {
                                id: nowPlayingSubtitle
                                objectName: "nowPlayingSubtitle"
                                text: backend.castState.disconnected ? qsTr("Cast odpojený · vyber jiný výstup")
                                      : backend.playerHasTrack
                                      ? (backend.playerState === "loading"
                                         ? qsTr("Připravuji lokální audio…")
                                         : backend.playerSubtitle)
                                      : (backend.playbackOutputAvailable
                                         ? qsTr("Klikni na skladbu")
                                         : qsTr("GStreamer není dostupný v tomto virtualenv"))
                                color: "#999999"
                                font.pixelSize: 13
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                HoverHandler { id: nowPlayingSubtitleHover }
                                ToolTip.visible: nowPlayingMetadata.showTrackDetails && nowPlayingSubtitleHover.hovered
                                ToolTip.text: nowPlayingMetadata.trackDetails
                            }

                            RowLayout {
                                visible: backend.playerHasTrack
                                spacing: 5

                                RatingButton {
                                    iconKind: "like"
                                    active: backend.playerLikeStatus === "LIKE"
                                    enabled: backend.playerCanRate
                                    onClicked: backend.toggleRating("LIKE")
                                }
                                RatingButton {
                                    iconKind: "dislike"
                                    active: backend.playerLikeStatus === "DISLIKE"
                                    enabled: backend.playerCanRate
                                    onClicked: backend.toggleRating("DISLIKE")
                                }

                                BusyIndicator {
                                    visible: backend.playerRatingBusy
                                    running: visible
                                    Layout.preferredWidth: 18
                                    Layout.preferredHeight: 18
                                }
                            }
                        }

                        ColumnLayout {
                            Layout.preferredWidth: 500
                            spacing: 5

                            RowLayout {
                                Layout.alignment: Qt.AlignHCenter
                                spacing: 12

                                BusyIndicator {
                                    visible: backend.playerState === "loading"
                                    running: visible
                                    Layout.preferredWidth: 28
                                    Layout.preferredHeight: 28
                                }
                                Label {
                                    visible: backend.playerState === "loading"
                                    text: qsTr("Připravuji skladbu…")
                                    color: "#dddddd"
                                    font.pixelSize: 13
                                }

                                TransportButton {
                                    visible: backend.playerState !== "loading"
                                    iconKind: "previous"
                                    enabled: backend.playerCanPrevious
                                    onClicked: backend.previousTrack()
                                }
                                TransportButton {
                                    visible: backend.playerState !== "loading"
                                    iconKind: backend.playerState === "playing" ? "pause" : "play"
                                    enabled: backend.playerHasTrack && backend.playbackOutputAvailable
                                    onClicked: backend.togglePlayPause()
                                }
                                TransportButton {
                                    visible: backend.playerState !== "loading"
                                    iconKind: "next"
                                    enabled: backend.playerCanNext
                                    onClicked: backend.nextTrack()
                                }
                                TransportButton {
                                    objectName: "stopButton"
                                    iconKind: "stop"
                                    implicitWidth: 42
                                    enabled: backend.playerHasTrack && (backend.playerState !== "idle" || backend.playerWaitingForTracks)
                                    hoverEnabled: true
                                    onClicked: backend.stopPlayback()
                                    ToolTip.visible: hovered
                                    ToolTip.text: qsTr("Zastavit; Play spustí skladbu od začátku")
                                }
                                PlayerTextButton {
                                    objectName: "repeatButton"
                                    implicitWidth: 110
                                    implicitHeight: 32
                                    hoverEnabled: true
                                    active: backend.playerRepeatMode !== "off"
                                    text: backend.playerRepeatMode === "all" ? qsTr("Opakovat: vše")
                                          : (backend.playerRepeatMode === "one" ? qsTr("Opakovat: 1") : qsTr("Opakovat: vyp."))
                                    enabled: backend.playerHasTrack
                                    onClicked: backend.cycleRepeat()
                                    ToolTip.visible: hovered
                                    ToolTip.text: backend.playerRepeatMode === "all" ? qsTr("Opakovat celý seznam")
                                                  : (backend.playerRepeatMode === "one" ? qsTr("Opakovat jednu skladbu")
                                                     : qsTr("Opakování je vypnuté"))
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 6

                                PlayerTextButton {
                                    text: "-30 s"
                                    enabled: backend.playerCanSeek
                                    onClicked: backend.seekRelative(-30)
                                }
                                PlayerTextButton {
                                    text: "-10 s"
                                    enabled: backend.playerCanSeek
                                    onClicked: backend.seekRelative(-10)
                                }
                                Label {
                                    text: root.formatTime(root.seekDragging ? root.seekPreview : backend.playerPosition)
                                    color: "#aaaaaa"
                                    font.pixelSize: 11
                                    Layout.preferredWidth: 42
                                }
                                Slider {
                                    id: seekSlider
                                    Layout.fillWidth: true
                                    from: 0
                                    to: Math.max(1, backend.playerDuration)
                                    value: root.seekDragging
                                           ? root.seekPreview
                                           : Math.min(backend.playerPosition, to)
                                    enabled: backend.playerCanSeek

                                    // Qt/KDE styly umí během dragování přepisovat value
                                    // bindingem z backendu. Interakci proto obsloužíme
                                    // explicitně a seek pošleme až při puštění myši.
                                    MouseArea {
                                        anchors.fill: parent
                                        enabled: seekSlider.enabled
                                        hoverEnabled: true
                                        preventStealing: true
                                        cursorShape: Qt.PointingHandCursor

                                        function updatePreview(mouseX) {
                                            var ratio = Math.max(0, Math.min(1, mouseX / Math.max(1, width)))
                                            root.seekPreview = seekSlider.from
                                                               + ratio * (seekSlider.to - seekSlider.from)
                                        }

                                        onPressed: function(mouse) {
                                            root.seekDragging = true
                                            updatePreview(mouse.x)
                                        }
                                        onPositionChanged: function(mouse) {
                                            if (pressed)
                                                updatePreview(mouse.x)
                                        }
                                        onReleased: function(mouse) {
                                            updatePreview(mouse.x)
                                            var target = root.seekPreview
                                            backend.seekTo(target)
                                            root.seekDragging = false
                                        }
                                        onCanceled: root.seekDragging = false
                                    }
                                }
                                Label {
                                    text: backend.playerDuration > 0
                                          ? root.formatTime(backend.playerDuration)
                                          : "--:--"
                                    color: "#aaaaaa"
                                    font.pixelSize: 11
                                    Layout.preferredWidth: 42
                                }
                                PlayerTextButton {
                                    text: "+10 s"
                                    enabled: backend.playerCanSeek
                                    onClicked: backend.seekRelative(10)
                                }
                                PlayerTextButton {
                                    text: "+30 s"
                                    enabled: backend.playerCanSeek
                                    onClicked: backend.seekRelative(30)
                                }
                            }
                        }

                        Item { Layout.fillWidth: true }

                        ColumnLayout {
                            Layout.preferredWidth: 300
                            spacing: 4

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 6

                                PlayerTextButton {
                                    text: backend.playerMuted ? qsTr("Zapnout") : qsTr("Ztlumit")
                                    enabled: backend.playbackOutputAvailable
                                    implicitWidth: 58
                                    onClicked: backend.toggleMute()
                                }
                                PlayerTextButton {
                                    text: "-"
                                    enabled: backend.playbackOutputAvailable
                                    implicitWidth: 30
                                    onClicked: backend.changeVolume(-5)
                                }
                                Slider {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 150
                                    from: 0
                                    to: 100
                                    stepSize: 1
                                    value: backend.playerVolume
                                    enabled: backend.playbackOutputAvailable
                                    onMoved: backend.setVolume(Math.round(value))
                                }
                                PlayerTextButton {
                                    text: "+"
                                    enabled: backend.playbackOutputAvailable
                                    implicitWidth: 30
                                    onClicked: backend.changeVolume(5)
                                }
                                Label {
                                    text: backend.playerVolume + "%"
                                    color: "#aaaaaa"
                                    font.pixelSize: 11
                                    Layout.preferredWidth: 34
                                    horizontalAlignment: Text.AlignRight
                                }
                            }

                            Label {
                                objectName: "outputStatusLabel"
                                text: qsTr("Výstup: %1").arg(backend.outputName)
                                color: backend.playbackOutputAvailable ? "#aaaaaa" : "#ff8a80"
                                font.pixelSize: 13
                                Layout.alignment: Qt.AlignRight
                            }
                        }
                    }
                }
            }

            BusyOverlay { }
        }
    }

    Connections {
        target: backend

        function onInitialized() {
            // Start on Knihovna and load it as soon as authentication is ready.
            root.pageSelected(root.currentPage)
        }
    }
}
