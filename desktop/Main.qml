import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

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
    property string currentLibraryLabel: "Playlisty"
    property string currentLibraryOrder: ""
    property string currentLikedOrder: ""
    property string currentSearchScope: "catalog"
    property string currentSearchMode: "all"
    property bool seekDragging: false
    property real seekPreview: 0
    property var playbackContext: null
    signal playingSourceRequested()

    onCurrentPageChanged: backend.clearTrackSelection()

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

    function libraryOrderLabels() {
        if (currentLibrarySection === "playlists")
            return ["Výchozí YTM", "A–Z", "Z–A"]
        return ["Nedávno přidané", "A–Z", "Z–A"]
    }

    function libraryOrderValues() {
        if (currentLibrarySection === "playlists")
            return ["", "a_to_z", "z_to_a"]
        return ["recently_added", "a_to_z", "z_to_a"]
    }

    function searchModeLabels() {
        if (currentSearchScope === "uploads")
            return ["Vše"]
        return [
            "Vše", "Skladby", "Videa", "Alba", "Interpreti",
            "Playlisty", "Profily", "Podcasty", "Epizody"
        ]
    }

    function searchModeValues() {
        if (currentSearchScope === "uploads")
            return ["all"]
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
        function onDetailTitleChanged() { backend.clearTrackSelection() }
        function onPlaybackSourceCaptured() { root.capturePlaybackContext() }
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
            if (returnToOverview) root.selectLibrarySection("playlists", "Playlisty")
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
            color: "#eeeeee"
            wrapMode: Text.WordWrap
            padding: 18
        }
    }

    component PlaylistPrivacyChoice: ComboBox {
        readonly property string privacyValue: ["PRIVATE", "UNLISTED", "PUBLIC"][currentIndex] || ""
        Layout.fillWidth: true
        model: ["Soukromý", "Neveřejný (přístup přes odkaz)", "Veřejný"]
        Accessible.name: "Viditelnost playlistu"
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
            text: "Smazat playlist?"
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
                text: "Smaže se celý playlist z YouTube Music. Tuto akci nelze vrátit. Samotné skladby tím neodstraníš."
                color: "#dddddd"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
            Label {
                text: "Přehrávací fronta zůstane zachovaná."
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
                text: "Smazat playlist"
                implicitWidth: 140
                enabled: !backend.busy && !backend.playlistDeleteState.pending
                         && !backend.playlistDeleteState.locked && !!backend.playlistDeleteState.playlistId
                onClicked: backend.confirmPlaylistDelete()
                background: Rectangle { color: parent.enabled ? "#743333" : "#3c3030"; border.color: "#985050"; radius: 4 }
            }
            PlayerTextButton {
                objectName: "playlistDeleteRecheck"
                text: "Ověřit znovu"
                implicitWidth: 125
                visible: !!backend.playlistDeleteState.canRecheck
                enabled: !backend.busy && !backend.playlistDeleteState.pending
                onClicked: backend.recheckPlaylistDelete()
            }
            PlayerTextButton {
                objectName: "playlistDeleteCancel"
                text: backend.playlistDeleteState.locked ? "Zavřít" : "Zrušit"
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
            text: "Upravit playlist"
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
                placeholderText: "Název playlistu"
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
                    placeholderText: "Popis (nepovinný)"
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
                model: ["Soukromý", "Neveřejný (přístup přes odkaz)", "Veřejný"]
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
                text: "Uložit"
                implicitWidth: 105
                enabled: !backend.busy && !backend.playlistEditState.locked && !backend.playlistEditState.pending
                         && !backend.playlistEditState.completed && playlistEditName.text.trim().length > 0
                onClicked: backend.savePlaylistEdit(playlistEditName.text, playlistEditDescription.text,
                                                   ["PRIVATE", "UNLISTED", "PUBLIC"][playlistEditPrivacy.currentIndex])
            }
            PlayerTextButton {
                objectName: "playlistEditClose"
                text: "Zavřít"
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
            text: "Nový prázdný playlist"
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
                placeholderText: "Název playlistu"
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
                text: "Playlist vznikne bez skladeb."
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
                text: "Vytvořit"
                implicitWidth: 105
                enabled: !backend.busy && !backend.emptyPlaylistState.pending
                         && !backend.emptyPlaylistState.completed && !backend.emptyPlaylistState.locked
                         && emptyPlaylistName.text.trim().length > 0
                onClicked: backend.createEmptyPlaylist(emptyPlaylistName.text, emptyPlaylistPrivacy.privacyValue)
            }
            PlayerTextButton {
                objectName: "emptyPlaylistClose"
                text: "Zavřít"
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
                  ? (backend.playlistSaveState.collection ? "Duplicitní skladby" : "Duplicitní skladba")
                  : "Přidat do playlistu"
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
                text: "Počet vybraných skladeb: " + (backend.playlistSaveState.selectionCount || 0)
                color: "#aaaaaa"
            }
            RowLayout {
                visible: !playlistSave.duplicateResult
                Button {
                    text: "Existující playlist"
                    checkable: true
                    checked: !playlistSave.newMode
                    enabled: playlistSave.canSave && playlistChoice.count > 0
                    onClicked: playlistSave.newMode = false
                }
                Button {
                    objectName: "playlistNewMode"
                    text: "Nový playlist"
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
                text: backend.playlistSaveState.collection ? "Povolit opakované výskyty skladeb" : "Povolit další výskyt stejné skladby"
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
                placeholderText: "Název nového playlistu"
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
                      ? "Vybrané skladby se uloží v zobrazeném pořadí, bez duplicit."
                      : "Playlist bude obsahovat vybranou skladbu."
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
                text: playlistSave.newMode ? "Vytvořit a přidat" : "Přidat"
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
                text: "Ověřit znovu"
                visible: !!backend.playlistSaveState.canRecheck
                enabled: !backend.busy && !backend.playlistSaveState.pending
                onClicked: backend.recheckPlaylistSave()
            }
            PlayerTextButton {
                objectName: "playlistSaveClose"
                implicitWidth: 85
                text: playlistSave.duplicateResult ? "OK" : "Zavřít"
                onClicked: playlistSave.close()
            }
        }
    }

    Dialog {
        id: trackInfo
        objectName: "trackInfoDialog"
        title: "Informace o skladbě"
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
                text: "Zavřít"
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
                width: infoScroll.availableWidth
                spacing: 12
                Image {
                    Layout.preferredWidth: 96
                    Layout.preferredHeight: 96
                    source: backend.playerThumbnail
                    visible: source.toString().length > 0
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                }
                Repeater {
                    model: [
                        {label: "Název", value: backend.playerTitle},
                        {label: "Interpret", value: backend.playerArtist},
                        {label: "Album", value: backend.playerAlbum},
                        {label: "Délka", value: backend.playerDuration > 0 ? root.formatTime(backend.playerDuration) : "Neznámá"},
                        {label: "Hodnocení", value: backend.playerLikeStatus === "LIKE" ? "Oblíbená"
                                                   : (backend.playerLikeStatus === "DISLIKE" ? "Neoblíbená"
                                                      : (backend.playerLikeStatus === "INDIFFERENT" ? "Bez hodnocení" : "Nezjištěno"))},
                        {label: "Pozice ve frontě", value: backend.playerHasTrack ? (backend.playerQueueIndex + 1) + " / " + backend.playerQueueCount : "Prázdná fronta"},
                        {label: "Název fronty", value: backend.playingListTitle}
                    ]
                    delegate: ColumnLayout {
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
                            text: modelData.value || "Neuvedeno"
                            color: "#f3f3f3"
                            wrapMode: Text.Wrap
                            font.pixelSize: 15
                        }
                    }
                }
            }
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
                      ? (active ? "Zrušit oblíbenou" : "Oblíbená")
                      : (active ? "Zrušit neoblíbenou" : "Neoblíbená")

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
        var i = sourceKey === "playing" ? backend.playerQueueIndex : backend.playerSourceIndex
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
        var index = backend.playerSourceIndex
        if (index < 0 || index >= view.count)
            return
        view.currentIndex = index
        view.forceLayout()
        view.positionViewAtIndex(index, ListView.Center)
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
        required property string setVideoId
        required property string kind
        required property string playlistId
        required property string browseId
        property string sourceKey: ""
        property bool partialLiked: sourceKey === "liked" && !backend.likedComplete
        property bool selectedTrack: backend.selectionSource === sourceKey && backend.selectedTrackIndices.indexOf(index) >= 0
        property bool multipleSelection: selectedTrack && backend.selectedTrackIndices.length > 1
        property bool actionable: videoId.length > 0 || browseId.length > 0 || playlistId.length > 0
        property bool currentTrack: backend.playerHasTrack
                                    && (sourceKey === "playing"
                                        ? backend.playerQueueIndex === index
                                        : (backend.playerQueueSource === sourceKey
                                           && backend.playerSourceIndex === index
                                           && backend.playerVideoId === videoId))

        function kindCaption(value) {
            var labels = {
                "song": "Skladba", "video": "Video",
                "album": "Album", "single": "Single", "ep": "EP",
                "artist": "Interpret", "playlist": "Playlist",
                "podcast": "Podcast", "channel": "Profil",
                "profile": "Profil", "upload_song": "Nahraná skladba",
                "upload_album": "Nahrané album", "upload_artist": "Nahraný interpret"
            }
            var label = labels[value] || value || "Položka"
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
                text: backend.playerState === "loading" ? "Připravuji…"
                      : (backend.playerState === "playing" ? "Hraje"
                         : (backend.playerState === "paused" ? "Pozastaveno" : "Zastaveno"))
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
                return videoId.length > 0 || (sourceKey === "detail" && kind === "album") ? Qt.PointingHandCursor : Qt.ArrowCursor
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
                else if (sourceKey === "detail" && kind === "album")
                    backend.openDetailItem(index)
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
            ToolTip.text: "Možnosti skladby"
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
            property bool libraryMatches: libraryRequest > 0 && backend.songLibraryMenuState.requestId === libraryRequest
            onAboutToShow: {
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
                text: "Přehrát jako další"
                enabled: backend.playerCanEditQueue
                onTriggered: trackDelegate.multipleSelection ? backend.enqueueSelection(true, root.navigationContext())
                           : backend.enqueueFrom(trackDelegate.sourceKey, trackDelegate.index, true, root.navigationContext())
            }
            MenuItem {
                text: "Přidat na konec fronty"
                enabled: backend.playerCanEditQueue
                onTriggered: trackDelegate.multipleSelection ? backend.enqueueSelection(false, root.navigationContext())
                           : backend.enqueueFrom(trackDelegate.sourceKey, trackDelegate.index, false, root.navigationContext())
            }
            MenuItem {
                text: "Přidat do playlistu…"
                visible: trackDelegate.multipleSelection ? backend.selectionCanSavePlaylist
                         : (kind === "song" || kind === "video" || kind === "upload_song")
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy
                onTriggered: trackDelegate.multipleSelection ? backend.openSelectedPlaylistSave()
                           : backend.openPlaylistSave(trackDelegate.sourceKey, trackDelegate.index)
            }
            MenuItem {
                text: "Spustit mix"
                visible: !trackDelegate.multipleSelection && (kind === "song" || kind === "video")
                height: visible ? implicitHeight : 0
                enabled: backend.playerCanEditQueue && !backend.busy && backend.connected
                onTriggered: backend.startRadioFrom(trackDelegate.sourceKey, trackDelegate.index)
            }
            MenuItem {
                objectName: "playlistMoveUpAction"
                text: "Posunout nahoru"
                visible: !trackDelegate.multipleSelection && trackDelegate.sourceKey === "detail"
                         && backend.detailCanEditPlaylist && videoId.length > 0 && setVideoId.length > 0
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy && trackDelegate.index > 0
                onTriggered: backend.moveDetailPlaylistItem(videoId, setVideoId, -1)
            }
            MenuItem {
                objectName: "playlistMoveDownAction"
                text: "Posunout dolů"
                visible: !trackDelegate.multipleSelection && trackDelegate.sourceKey === "detail"
                         && backend.detailCanEditPlaylist && videoId.length > 0 && setVideoId.length > 0
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy && trackDelegate.index + 1 < backend.detailTracksModel.count
                onTriggered: backend.moveDetailPlaylistItem(videoId, setVideoId, 1)
            }
            MenuItem {
                objectName: "playlistRemoveItemAction"
                text: "Odebrat z tohoto playlistu"
                visible: !trackDelegate.multipleSelection && trackDelegate.sourceKey === "detail" && backend.detailCanEditPlaylist
                         && videoId.length > 0 && setVideoId.length > 0
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy
                onTriggered: backend.removeDetailPlaylistItem(videoId, setVideoId)
            }
            // Append the delayed action so existing menu rows do not move.
            MenuItem {
                objectName: "songLibraryMenuAction"
                text: backend.songLibraryMenuState.inLibrary ? "Odebrat z knihovny" : "Přidat do knihovny"
                visible: !trackDelegate.multipleSelection && (kind === "song" || kind === "video") && trackMenu.libraryMatches
                         && backend.songLibraryMenuState.available && !backend.songLibraryMenuState.pending
                height: visible ? implicitHeight : 0
                enabled: visible && !backend.busy
                onTriggered: backend.changeSongLibrary(trackMenu.libraryRequest)
            }

        }
    }

    component CollectionHeader: RowLayout {
        property string backText: "← Zpět"
        signal goBack()
        Layout.fillWidth: true
        spacing: 10
        Button {
            text: parent.backText
            enabled: !backend.busy
            onClicked: parent.goBack()
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 2
            Label {
                objectName: "collectionTitle"
                text: backend.detailTitle
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                color: "white"
                font.pixelSize: 24
                font.bold: true
                elide: Text.ElideRight
            }
            Label {
                text: backend.detailTracksModel.count +
                      (backend.detailMeta.kind === "artist" && backend.detailMeta.section !== "songs"
                       ? " položek" : " skladeb")
                color: "#999999"
                font.pixelSize: 12
            }
        }
        Button {
            id: collectionMenuButton
            objectName: "collectionMenuButton"
            Layout.preferredWidth: 36
            Layout.preferredHeight: 36
            visible: backend.detailCanSavePlaylist || backend.detailCanEditPlaylist || backend.detailCanShuffle || backend.detailCanCollectionRadio
                     || backend.detailMeta.kind === "artist"
            enabled: !backend.busy && backend.connected
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.text: "Možnosti kolekce"
            onClicked: collectionMenu.popup(collectionMenuButton, width - collectionMenu.width, height)
            background: Rectangle {
                radius: 4
                color: collectionMenuButton.hovered ? "#3b3b3b" : "#222222"
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
            id: collectionMenu
            objectName: "collectionContextMenu"
            popupType: Popup.Item
            width: 260
            palette.text: "#eeeeee"
            palette.windowText: "#eeeeee"
            palette.highlight: "#6757b8"
            background: Rectangle { color: "#242424"; border.color: "#555555"; radius: 5 }
            MenuItem {
                objectName: "collectionShuffle"
                text: "Přehrát náhodně"
                visible: backend.detailMeta.kind === "playlist" || backend.detailMeta.kind === "album"
                height: visible ? implicitHeight : 0
                enabled: backend.detailCanShuffle && backend.connected && !backend.busy && backend.playerCanEditQueue
                onTriggered: backend.shuffleDetail()
            }
            MenuItem {
                objectName: "collectionRadio"
                text: "Spustit mix"
                visible: backend.detailMeta.kind === "playlist" || backend.detailMeta.kind === "album"
                height: visible ? implicitHeight : 0
                enabled: backend.detailCanCollectionRadio && backend.connected && !backend.busy && backend.playerCanEditQueue
                onTriggered: backend.startCollectionRadio()
            }
            MenuItem {
                objectName: "artistShuffle"
                text: "Přehrát náhodně"
                visible: backend.detailMeta.kind === "artist"
                height: visible ? implicitHeight : 0
                enabled: backend.detailCanArtistShuffle && backend.connected && !backend.busy && backend.playerCanEditQueue
                onTriggered: backend.startArtistPlayback("shuffle")
            }
            MenuItem {
                objectName: "artistRadio"
                text: "Spustit mix"
                visible: backend.detailMeta.kind === "artist"
                height: visible ? implicitHeight : 0
                enabled: backend.detailCanArtistRadio && backend.connected && !backend.busy && backend.playerCanEditQueue
                onTriggered: backend.startArtistPlayback("radio")
            }
            MenuItem {
                objectName: "collectionPlaylistSave"
                text: "Přidat seznam do playlistu…"
                visible: backend.detailCanSavePlaylist
                height: visible ? implicitHeight : 0
                enabled: backend.detailCanSavePlaylist && !backend.busy
                onTriggered: backend.openCollectionPlaylistSave()
            }
            MenuItem {
                objectName: "collectionPlaylistEdit"
                text: "Upravit playlist…"
                visible: backend.detailCanEditPlaylist
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy
                onTriggered: backend.openPlaylistEdit()
            }
            MenuItem {
                objectName: "collectionPlaylistDelete"
                text: "Smazat playlist…"
                visible: backend.detailCanDeletePlaylist
                height: visible ? implicitHeight : 0
                enabled: backend.connected && !backend.busy
                onTriggered: backend.openPlaylistDelete()
            }
        }
    }

    component ArtistNavigation: ColumnLayout {
        visible: backend.detailMeta.kind === "artist"
        spacing: 6
        Flow {
            objectName: "artistNavigationFlow"
            Layout.fillWidth: true
            Layout.preferredHeight: childrenRect.height
            spacing: 8
            Row {
                spacing: 6
                height: artistOrder.implicitHeight
                Repeater {
                    model: [{key: "songs", label: "Skladby"},
                            {key: "albums", label: "Alba"},
                            {key: "singles", label: "Singly a EP"}]
                    Button {
                        required property var modelData
                        text: modelData.label
                        objectName: "artistSection-" + modelData.key
                        checkable: true
                        checked: backend.detailMeta.section === modelData.key
                        enabled: !backend.busy
                        onClicked: backend.selectArtistSection(modelData.key)
                    }
                }
            }
            ComboBox {
                id: artistOrder
                objectName: "artistOrder"
                width: Math.min(240, parent.width)
                enabled: !backend.busy
                textRole: "label"
                valueRole: "key"
                model: backend.detailMeta.section === "songs"
                       ? [{key: "a_to_z", label: "A–Z"}, {key: "z_to_a", label: "Z–A"},
                          {key: "default", label: "Původní pořadí YTM"}]
                       : [{key: "a_to_z", label: "A–Z"}, {key: "z_to_a", label: "Z–A"},
                          {key: "default", label: "Původní pořadí YTM"},
                          {key: "newest", label: "Od nejnovějších"},
                          {key: "oldest", label: "Od nejstarších"}]
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
        Label {
            visible: backend.detailTracksModel.count === 0
            text: "V této části nejsou dostupné žádné položky."
            color: "#aaaaaa"
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
    }

    component LibraryNavigation: ColumnLayout {
        spacing: 12

        Flow {
            Layout.fillWidth: true
            Layout.preferredHeight: childrenRect.height
            spacing: 8

            Label {
                text: "Knihovna"
                color: "white"
                font.pixelSize: 28
                font.bold: true
                width: implicitWidth + 10
                height: libraryOrder.height
                verticalAlignment: Text.AlignVCenter
            }

            Button {
                text: "Playlisty"
                checkable: true
                checked: root.currentPage === 1 && root.currentLibrarySection === "playlists"
                onClicked: root.selectLibrarySection("playlists", "Playlisty")
            }
            Button {
                text: "Skladby"
                checkable: true
                checked: root.currentPage === 1 && root.currentLibrarySection === "songs"
                onClicked: root.selectLibrarySection("songs", "Skladby")
            }
            Button {
                text: "Alba"
                checkable: true
                checked: root.currentPage === 1 && root.currentLibrarySection === "albums"
                onClicked: root.selectLibrarySection("albums", "Alba")
            }
            Button {
                text: "Interpreti"
                checkable: true
                checked: root.currentPage === 1 && root.currentLibrarySection === "artists"
                onClicked: root.selectLibrarySection("artists", "Interpreti")
            }
            Button {
                text: "Profily"
                checkable: true
                checked: root.currentPage === 1 && root.currentLibrarySection === "channels"
                onClicked: root.selectLibrarySection("channels", "Profily")
            }
            Button {
                text: "Podcasty"
                checkable: true
                checked: root.currentPage === 1 && root.currentLibrarySection === "podcasts"
                onClicked: root.selectLibrarySection("podcasts", "Podcasty")
            }
            Button {
                text: "Nahrané"
                checkable: true
                checked: root.currentPage === 1 && root.currentLibrarySection.indexOf("upload_") === 0
                onClicked: root.selectLibrarySection("upload_songs", "Nahrané skladby")
            }

            ComboBox {
                id: libraryOrder
                visible: root.currentPage === 1
                width: 170
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

        RowLayout {
            visible: root.currentPage === 1 && root.currentLibrarySection.indexOf("upload_") === 0
            spacing: 8
            Label {
                text: "Nahrané soubory:"
                color: "#999999"
            }
            Button {
                text: "Skladby"
                checkable: true
                checked: root.currentPage === 1 && root.currentLibrarySection === "upload_songs"
                onClicked: root.selectLibrarySection("upload_songs", "Nahrané skladby")
            }
            Button {
                text: "Alba"
                checkable: true
                checked: root.currentPage === 1 && root.currentLibrarySection === "upload_albums"
                onClicked: root.selectLibrarySection("upload_albums", "Nahraná alba")
            }
            Button {
                text: "Interpreti"
                checkable: true
                checked: root.currentPage === 1 && root.currentLibrarySection === "upload_artists"
                onClicked: root.selectLibrarySection("upload_artists", "Nahraní interpreti")
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

            Label {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: heading
                color: "white"
                font.pixelSize: 28
                font.bold: true
                elide: Text.ElideRight
            }
            Label {
                text: tracks.count + " položek"
                color: "#999999"
                font.pixelSize: 13
            }
            ListView {
                id: trackList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: tracks
                delegate: TrackDelegate { sourceKey: trackPage.sourceKey }
                Keys.onPressed: function(event) { root.trackKeys(event, trackPage.sourceKey) }
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
                Item { Layout.fillWidth: true }
                Button {
                    id: libraryMenuButton
                    objectName: "libraryPlaylistMenuButton"
                    Layout.preferredWidth: 36
                    Layout.preferredHeight: 36
                    visible: !isMix && root.currentPage === 1 && root.currentLibrarySection === "playlists"
                    enabled: backend.connected && !backend.busy
                    hoverEnabled: true
                    ToolTip.visible: hovered
                    ToolTip.text: "Možnosti playlistů"
                    onClicked: libraryMenu.popup(libraryMenuButton, width - libraryMenu.width, height)
                    background: Rectangle {
                        radius: 4
                        color: libraryMenuButton.hovered ? "#3b3b3b" : "#222222"
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
                            text: "Nový playlist…"
                            enabled: backend.connected && !backend.busy
                            onTriggered: backend.beginEmptyPlaylist()
                        }
                    }
                }
                Label {
                    text: items.count + " položek"
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

                NavButton { pageIndex: 0; pageText: "Hledat" }
                NavButton { pageIndex: 1; pageText: "Knihovna" }
                NavButton { pageIndex: 2; pageText: "Oblíbená hudba" }
                NavButton { pageIndex: 3; pageText: "Historie" }
                NavButton { pageIndex: 4; pageText: "Mixy pro vás" }
                NavButton { pageIndex: 5; pageText: "Fronta" + (backend.playerQueueCount > 0 ? " (" + backend.playerQueueCount + ")" : ""); objectName: "queueButton" }

                Item { Layout.fillHeight: true }

                Label {
                    text: "Desktop GUI · " + fcmVersion
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
                            text: backend.busy
                                  ? backend.status
                                  : (backend.connected
                                     ? "Připojeno · " + backend.accountName
                                     : backend.status)
                            color: backend.status.indexOf("Chyba") >= 0 ? "#ff8a80" : "#999999"
                            font.pixelSize: 13
                        }
                        PlayerTextButton {
                            objectName: "infoButton"
                            text: "Info"
                            enabled: backend.playerHasTrack
                            onClicked: trackInfo.open()
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
                                text: "Hledat"
                                color: "white"
                                font.pixelSize: 28
                                font.bold: true
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Button {
                                    text: "YT Music"
                                    checkable: true
                                    checked: root.currentSearchScope === "catalog"
                                    onClicked: root.selectSearchScope("catalog")
                                }
                                Button {
                                    text: "Knihovna"
                                    checkable: true
                                    checked: root.currentSearchScope === "library"
                                    onClicked: root.selectSearchScope("library")
                                }
                                Button {
                                    text: "Nahrané soubory"
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
                                    Layout.fillWidth: true
                                    placeholderText: root.currentSearchScope === "uploads"
                                                     ? "Hledat v nahraných souborech…"
                                                     : (root.currentSearchScope === "library"
                                                        ? "Hledat v knihovně…"
                                                        : "Hledat v YT Music…")
                                    onAccepted: backend.search(
                                        text, root.currentSearchMode, root.currentSearchScope
                                    )
                                }
                                Button {
                                    text: "Hledat"
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
                            ListView {
                                id: searchResultsList
                                clip: true
                                model: backend.searchResultsModel
                                delegate: TrackDelegate { sourceKey: "search" }
                                Keys.onPressed: function(event) { root.trackKeys(event, "search") }
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
                                    ArtistNavigation { Layout.fillWidth: true }
                                    ListView {
                                        id: searchDetailList
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        clip: true
                                        model: backend.detailTracksModel
                                        delegate: TrackDelegate { sourceKey: "detail" }
                                        Keys.onPressed: function(event) { root.trackKeys(event, "detail") }
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
                                    ArtistNavigation { Layout.fillWidth: true }
                                    ListView {
                                        id: libraryDetailList
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        clip: true
                                        model: backend.detailTracksModel
                                        delegate: TrackDelegate { sourceKey: "detail" }
                                        Keys.onPressed: function(event) { root.trackKeys(event, "detail") }
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

                            RowLayout {
                                Layout.fillWidth: true
                                Label {
                                    text: "Oblíbená hudba"
                                    color: "white"
                                    font.pixelSize: 28
                                    font.bold: true
                                }
                                Item { Layout.fillWidth: true }
                                ToolButton {
                                    id: likedMenuButton
                                    objectName: "likedMenuButton"
                                    text: "⋮"
                                    enabled: backend.connected && !backend.busy
                                    onClicked: likedMenu.popup(likedMenuButton, 0, height)
                                    Menu {
                                        id: likedMenu
                                        objectName: "likedContextMenu"
                                        popupType: Popup.Item
                                        MenuItem {
                                            objectName: "likedShuffle"
                                            text: "Přehrát náhodně"
                                            enabled: backend.likedComplete && backend.likedModel.count > 0 && backend.connected && !backend.busy && backend.playerCanEditQueue
                                            onTriggered: backend.startLikedPlayback("shuffle")
                                        }
                                        MenuItem {
                                            objectName: "likedRadio"
                                            text: "Spustit mix"
                                            enabled: backend.likedComplete && backend.likedModel.count > 0 && backend.connected && !backend.busy && backend.playerCanEditQueue
                                            onTriggered: backend.startLikedPlayback("radio")
                                        }
                                    }
                                }
                                ComboBox {
                                    id: likedOrder
                                    enabled: backend.likedComplete
                                    Layout.preferredWidth: 170
                                    model: ["Výchozí YTM", "A–Z", "Z–A"]
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

                            Label {
                                text: backend.likedModel.count + " položek"
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
                                            text: backend.likedLoading ? "Načítám další skladby…"
                                                : backend.likedComplete ? "Vše načteno · " + backend.likedModel.count + " skladeb"
                                                : "Načítání se nepodařilo dokončit"
                                            font.pixelSize: 16
                                            font.bold: true
                                            color: "#eeeeee"
                                        }
                                        Label {
                                            Layout.fillWidth: true
                                            visible: !backend.likedComplete
                                            wrapMode: Text.Wrap
                                            text: backend.likedLoading
                                                ? "Skladby už můžeš přehrávat dvojklikem. Další se doplní i do fronty; řazení a ostatní akce až po dokončení."
                                                : "Seznam není úplný. Otevři Oblíbenou hudbu znovu."
                                            color: "#bbbbbb"
                                            font.pixelSize: 13
                                        }
                                    }
                                }
                            }

                            ListView {
                                id: likedList
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                clip: true
                                model: backend.likedModel
                                delegate: TrackDelegate { sourceKey: "liked"; enabled: backend.likedComplete || backend.likedLoading }
                                Keys.onPressed: function(event) { root.trackKeys(event, "liked") }
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

                    TrackPage { heading: "Historie"; tracks: backend.historyModel; sourceKey: "history" }

                    Item {
                        Loader {
                            anchors.fill: parent
                            sourceComponent: backend.detailTracksModel.count > 0 ? mixDetailComponent : mixGridComponent
                        }
                        Component {
                            id: mixGridComponent
                            CardGrid { heading: "Mixy pro vás"; items: backend.mixesModel; isMix: true }
                        }
                        Component {
                            id: mixDetailComponent
                            Item {
                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 22
                                    CollectionHeader {
                                        backText: "← Mixy"
                                        onGoBack: backend.clearDetail()
                                    }
                                    ListView {
                                        id: mixDetailList
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        clip: true
                                        model: backend.detailTracksModel
                                        delegate: TrackDelegate { sourceKey: "detail" }
                                        Keys.onPressed: function(event) { root.trackKeys(event, "detail") }
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
                                    text: "Fronta"
                                    color: "white"
                                    font.pixelSize: 28
                                    font.bold: true
                                }
                                Label {
                                    objectName: "queuePosition"
                                    Layout.fillWidth: true
                                    text: (backend.playerHasTrack ? (backend.playerQueueIndex + 1) + " / " + backend.playerQueueCount : "0 / 0")
                                          + (backend.playerQueueLoading ? (backend.playerWaitingForTracks ? " · Čekám na další skladby…" : " · Načítám další skladby…")
                                             : backend.playerQueueIncomplete ? " · Seznam není úplný" : "")
                                    wrapMode: Text.Wrap
                                    color: "#b9b0ff"
                                    font.pixelSize: 16
                                }
                                Button {
                                    objectName: "queueShuffleButton"
                                    text: "Zamíchat"
                                    enabled: backend.connected && !backend.busy && backend.playerCanShuffle
                                    hoverEnabled: true
                                    ToolTip.visible: hovered
                                    ToolTip.text: backend.playerCanShuffle
                                                  ? "Zamíchat frontu; aktuální skladba pokračuje"
                                                  : "Tuto frontu nyní nelze zamíchat"
                                    onClicked: backend.shuffleQueue()
                                }
                                Button {
                                    text: "Na aktuální"
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
                                text: "Fronta je prázdná. Vyber skladbu v knihovně nebo hledání."
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                color: "#aaaaaa"
                            }
                            ListView {
                                id: queueList
                                objectName: "queueList"
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.minimumWidth: 0
                                clip: true
                                model: backend.playingTracksModel
                                delegate: TrackDelegate { sourceKey: "playing" }
                                Keys.onPressed: function(event) { root.trackKeys(event, "playing") }
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
                    objectName: "selectionActions"
                    visible: backend.selectedTrackIndices.length > 1
                    Layout.fillWidth: true
                    Layout.leftMargin: 22
                    Layout.rightMargin: 22
                    spacing: 12
                    Label {
                        objectName: "selectedTrackCount"
                        text: "Vybráno: " + backend.selectedTrackIndices.length
                        color: "#dddddd"
                    }
                    Button {
                        id: selectedActionsButton
                        objectName: "selectedActionsButton"
                        text: "Akce ⋮"
                        onClicked: selectedActions.popup(selectedActionsButton, 0, -selectedActions.height)
                    }
                    Button {
                        objectName: "clearTrackSelection"
                        text: "Zrušit výběr"
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
                            text: "Přehrát jako další"
                            enabled: backend.playerCanEditQueue && backend.selectedTrackIndices.length > 1
                            onTriggered: backend.enqueueSelection(true, root.navigationContext())
                        }
                        MenuItem {
                            text: "Přidat na konec fronty"
                            enabled: backend.playerCanEditQueue && backend.selectedTrackIndices.length > 1
                            onTriggered: backend.enqueueSelection(false, root.navigationContext())
                        }
                        MenuItem {
                            text: "Přidat do playlistu…"
                            enabled: backend.connected && !backend.busy && backend.selectionCanSavePlaylist
                                     && backend.selectedTrackIndices.length > 1
                            onTriggered: backend.openSelectedPlaylistSave()
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
                                ToolTip.text: "Zobrazit přehrávaný seznam"
                            }
                        }

                        ColumnLayout {
                            Layout.preferredWidth: 210
                            spacing: 3

                            Label {
                                text: backend.playerHasTrack ? backend.playerTitle : "Nic se nepřehrává"
                                color: "white"
                                font.pixelSize: 15
                                font.bold: true
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Label {
                                text: backend.playerHasTrack
                                      ? (backend.playerState === "loading"
                                         ? "Připravuji lokální audio…"
                                         : backend.playerSubtitle)
                                      : (backend.localPlaybackAvailable
                                         ? "Klikni na skladbu"
                                         : "GStreamer není dostupný v tomto virtualenv")
                                color: "#999999"
                                font.pixelSize: 13
                                elide: Text.ElideRight
                                Layout.fillWidth: true
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

                        Item { Layout.fillWidth: true }

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
                                    text: "Připravuji skladbu…"
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
                                    enabled: backend.playerHasTrack
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
                                    ToolTip.text: "Zastavit; Play spustí skladbu od začátku"
                                }
                                PlayerTextButton {
                                    objectName: "repeatButton"
                                    implicitWidth: 110
                                    implicitHeight: 32
                                    hoverEnabled: true
                                    active: backend.playerRepeatMode !== "off"
                                    text: backend.playerRepeatMode === "all" ? "Opakovat: vše"
                                          : (backend.playerRepeatMode === "one" ? "Opakovat: 1" : "Opakovat: vyp.")
                                    enabled: backend.playerHasTrack
                                    onClicked: backend.cycleRepeat()
                                    ToolTip.visible: hovered
                                    ToolTip.text: backend.playerRepeatMode === "all" ? "Opakovat celý seznam"
                                                  : (backend.playerRepeatMode === "one" ? "Opakovat jednu skladbu"
                                                     : "Opakování je vypnuté")
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
                                    text: backend.playerMuted ? "Zapnout" : "Ztlumit"
                                    enabled: backend.localPlaybackAvailable
                                    implicitWidth: 58
                                    onClicked: backend.toggleMute()
                                }
                                PlayerTextButton {
                                    text: "-"
                                    enabled: backend.localPlaybackAvailable
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
                                    enabled: backend.localPlaybackAvailable
                                    onMoved: backend.setVolume(Math.round(value))
                                }
                                PlayerTextButton {
                                    text: "+"
                                    enabled: backend.localPlaybackAvailable
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
                                text: "Výstup: Toto zařízení"
                                color: backend.localPlaybackAvailable ? "#aaaaaa" : "#ff8a80"
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
