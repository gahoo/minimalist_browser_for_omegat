import org.omegat.core.Core
import org.omegat.core.CoreEvents
import org.omegat.core.events.IEditorEventListener
import org.omegat.gui.editor.IPopupMenuConstructor
import org.omegat.gui.editor.SegmentBuilder
import org.omegat.gui.main.MainWindow
import org.omegat.core.data.ProjectProperties
import org.omegat.core.data.SourceTextEntry
import org.omegat.core.events.IEntryEventListener

import javax.swing.AbstractAction
import javax.swing.Action
import javax.swing.JComponent
import javax.swing.JMenuItem
import javax.swing.JPopupMenu
import javax.swing.KeyStroke
import javax.swing.text.JTextComponent
import java.awt.event.ActionEvent
import java.awt.event.KeyEvent
def FILENAME = "wantwords.groovy"
def KEY = "wantwords"
def TITLE = "wantwords"
def DOMAIN = /^.*/
def URL = "http://10.147.20.16:5678/wantwords"

def pane = BrowserPane.get(KEY, TITLE, DOMAIN)
pane.getBrowser().loadURL(URL)

/* Record word at caret */
String caretWord = null
def editorEventListener = new IEditorEventListener() {
    @Override
    void onNewWord(String s) {
        caretWord = s
    }
}
CoreEvents.registerEditorEventListener(editorEventListener)

/* Main action that opens Google */
Action action = new AbstractAction() {
    @Override
    void actionPerformed(ActionEvent e) {
        q = ScriptHelpers.prepareText(Core.getEditor().getSelectedText(), caretWord)
        if (q == null) return
        url = "${URL}/?query="
        url += "${ScriptHelpers.encodeText(q)}"
        println(url)
        pane.getBrowser().loadURL(url)
    }
}

// FIXME: Remove menu items
/* Popup menu item */
Core.getEditor().registerPopupMenuConstructors(1000, new IPopupMenuConstructor() {
    @Override
    void addItems(JPopupMenu menu, JTextComponent comp, int mousepos, boolean isInActiveEntry,
                  boolean isInActiveTranslation, final SegmentBuilder sb) {
        if (isInActiveEntry) {
            menu.addSeparator()
            JMenuItem menuItem = menu.add("Search in Wantwords")
            menuItem.addActionListener(action)
        }
    }
})

/* Listen for events and update text */
def entryEventListener = new IEntryEventListener() {
    @Override
    void onNewFile(String s) {
    }

    @Override
    void onEntryActivated(SourceTextEntry sourceTextEntry) {
        url = "${URL}/?query="
        url += "${ScriptHelpers.encodeText(sourceTextEntry.srcText)}"
        println(url)
        pane.getBrowser().loadURL(url)
    }
}


/* Bind hotkey: Ctrl + ALT + G */
MainWindow mainWindow = (MainWindow) Core.getMainWindow()
int COMMAND_MASK = System.getProperty("os.name").contains("OS X") ? ActionEvent.META_MASK : ActionEvent.CTRL_MASK
KeyStroke keystroke = KeyStroke.getKeyStroke(KeyEvent.VK_SEMICOLON, COMMAND_MASK)
def actionMapKey = "searchInMerriamWebster"
mainWindow.getRootPane().getInputMap(JComponent.WHEN_IN_FOCUSED_WINDOW).put(keystroke, actionMapKey)
mainWindow.getRootPane().getActionMap().put(actionMapKey, action)

/* Remove all this when script is disabled */
def scriptsEventListener = [
        onAdd    : {},
        onEnable : {},
        onRemove : {},
        onDisable: { File file ->
            if (file.getName() == FILENAME) {
                pane.close()
                CoreEvents.unregisterEntryEventListener(entryEventListener)
                CoreEvents.unregisterEditorEventListener(editorEventListener)
                mainWindow.getRootPane().getInputMap(JComponent.WHEN_IN_FOCUSED_WINDOW).remove(keystroke)
                mainWindow.getRootPane().getActionMap().remove(actionMapKey)
                scriptsRunner.unregisterEventListener(scriptsEventListener)
            }
        }].asType(ScriptsEventListener)

scriptsRunner.registerEventListener(scriptsEventListener)
/*CoreEvents.registerEntryEventListener(entryEventListener)*/
