import org.omegat.core.Core
import org.omegat.core.CoreEvents
import org.omegat.core.events.IEditorEventListener
import org.omegat.gui.editor.IPopupMenuConstructor
import org.omegat.gui.editor.SegmentBuilder
import org.omegat.gui.main.MainWindow
import org.omegat.core.data.ProjectProperties
import org.omegat.core.data.SourceTextEntry
import org.omegat.core.events.IEntryEventListener
import org.omegat.core.events.IProjectEventListener

import javax.swing.AbstractAction
import javax.swing.Action
import javax.swing.JComponent
import javax.swing.JMenuItem
import javax.swing.JPopupMenu
import javax.swing.KeyStroke
import javax.swing.text.JTextComponent
import java.awt.event.ActionEvent
import java.awt.event.KeyEvent
def FILENAME = "deepl_free.groovy"
def KEY = "DEEPL_FREE"
def TITLE = "DeepL Free"
def DOMAIN = /^.*/
def BASE_URL = "http://192.168.1.100:5678/deepl"

String sourceCode = 'EN'
String targetCode = 'ZH'

ProjectProperties pp = Core.getProject().getProjectProperties()
if (pp) {
    sourceCode = pp.getSourceLanguage().getLanguageCode().toUpperCase()
    targetCode = pp.getTargetLanguage().getLanguageCode().toUpperCase()
}

def URL = "${BASE_URL}/?params.lang.target_lang=${targetCode}&params.jobs[0].sentences[0].text="

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
        url = "${URL}${ScriptHelpers.encodeText(q)}"
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
            JMenuItem menuItem = menu.add("Search in DeepL Free")
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
        url = "${URL}${ScriptHelpers.encodeText(q)}"
        println(url)
        pane.getBrowser().loadURL(url)
    }
}


/* Bind hotkey: Ctrl + ALT + G */
MainWindow mainWindow = (MainWindow) Core.getMainWindow()
int COMMAND_MASK = System.getProperty("os.name").contains("OS X") ? ActionEvent.META_MASK : ActionEvent.CTRL_MASK
KeyStroke keystroke = KeyStroke.getKeyStroke(KeyEvent.VK_PERIOD, COMMAND_MASK)
def actionMapKey = "searchInDeepLFree"
/*
mainWindow.getRootPane().getInputMap(JComponent.WHEN_IN_FOCUSED_WINDOW).put(keystroke, actionMapKey)
mainWindow.getRootPane().getActionMap().put(actionMapKey, action)
*/

/* Also change language */
def projectEventListener = new IProjectEventListener() {
    @Override
    void onProjectChanged(IProjectEventListener.PROJECT_CHANGE_TYPE project_change_type) {
        if (project_change_type == IProjectEventListener.PROJECT_CHANGE_TYPE.LOAD ||
            project_change_type == IProjectEventListener.PROJECT_CHANGE_TYPE.CREATE ||
            project_change_type == IProjectEventListener.PROJECT_CHANGE_TYPE.MODIFIED
        ) {
            pp = Core.getProject().getProjectProperties()
            sourceCode = pp.getSourceLanguage().getLanguageCode().toUpperCase()
            targetCode = pp.getTargetLanguage().getLanguageCode().toUpperCase()
            URL = "${BASE_URL}/?params.lang.target_lang=${targetCode}&params.jobs[0].sentences[0].text="
            println("DeepL Free URL change to ${URL}")
        }
    }
}

/* Remove all this when script is disabled */
def scriptsEventListener = [
        onAdd    : {},
        onEnable : {},
        onRemove : {},
        onDisable: { File file ->
            if (file.getName() == FILENAME) {
                pane.close()
                CoreEvents.unregisterEntryEventListener(entryEventListener)
                CoreEvents.unregisterProjectChangeListener(projectEventListener)
                CoreEvents.unregisterEditorEventListener(editorEventListener)
                mainWindow.getRootPane().getInputMap(JComponent.WHEN_IN_FOCUSED_WINDOW).remove(keystroke)
                mainWindow.getRootPane().getActionMap().remove(actionMapKey)
                scriptsRunner.unregisterEventListener(scriptsEventListener)
            }
        }].asType(ScriptsEventListener)

scriptsRunner.registerEventListener(scriptsEventListener)
CoreEvents.registerProjectChangeListener(projectEventListener)
/* CoreEvents.registerEntryEventListener(entryEventListener) */
