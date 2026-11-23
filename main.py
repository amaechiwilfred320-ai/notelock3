
import os
import sqlite3
import threading
from datetime import datetime
from xml.sax.saxutils import escape

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer


BLUE = (0.05, 0.27, 0.67, 1)
DARK_BLUE = (0.025, 0.15, 0.40, 1)
WHITE = (1, 1, 1, 1)
PALE_BLUE = (0.92, 0.95, 1, 1)


class NoteLockApp(App):

    def build(self):
        self.title = "NoteLock"

        Window.clearcolor = PALE_BLUE

        self.db = os.path.join(
            self.user_data_dir, "notelock.db"
        )

        self.pdf_dir = os.path.join(
            self.user_data_dir, "PDFs"
        )

        os.makedirs(self.pdf_dir, exist_ok=True)

        self.current_id = None
        self.stop_event = threading.Event()
        self.is_listening = False

        self.android_recognizer = None
        self.android_listener = None

        self.init_db()

        root = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(9)
        )

        header = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(66),
            padding=dp(6)
        )

        with header.canvas.before:
            Color(*BLUE)
            header.bg = RoundedRectangle(
                pos=header.pos,
                size=header.size,
                radius=[dp(14)]
            )

        header.bind(
            pos=lambda w, v: setattr(w.bg, "pos", v),
            size=lambda w, v: setattr(w.bg, "size", v)
        )

        header.add_widget(Label(
            text="[b]NoteLock[/b]",
            markup=True,
            color=WHITE,
            font_size="25sp"
        ))

        header.add_widget(Label(
            text="Audio to text document converter",
            color=(0.9, 0.94, 1, 1),
            font_size="12sp"
        ))

        root.add_widget(header)

        self.title_input = TextInput(
            hint_text="Document title",
            multiline=False,
            size_hint_y=None,
            height=dp(46),
            padding=dp(10),
            background_color=WHITE,
            foreground_color=DARK_BLUE
        )

        root.add_widget(self.title_input)

        self.text_input = TextInput(
            hint_text="Converted speech appears here.",
            multiline=True,
            padding=dp(12),
            background_color=WHITE,
            foreground_color=(0.1, 0.13, 0.2, 1)
        )

        root.add_widget(self.text_input)

        self.status = Label(
            text="Ready. Tap Start Listening and speak.",
            color=DARK_BLUE,
            size_hint_y=None,
            height=dp(28),
            font_size="12sp"
        )

        root.add_widget(self.status)

        row = BoxLayout(
            size_hint_y=None,
            height=dp(48),
            spacing=dp(8)
        )

        row.add_widget(
            self.button("Start Listening", self.start_listening)
        )

        row.add_widget(
            self.button("Stop Listening", self.stop_listening, True)
        )

        root.add_widget(row)

        row = BoxLayout(
            size_hint_y=None,
            height=dp(48),
            spacing=dp(8)
        )

        row.add_widget(
            self.button("Save Document", self.save_document)
        )

        row.add_widget(
            self.button("Export PDF", self.export_pdf, True)
        )

        root.add_widget(row)

        row = BoxLayout(
            size_hint_y=None,
            height=dp(44),
            spacing=dp(8)
        )

        row.add_widget(
            self.button("New", self.new_document, light=True)
        )

        row.add_widget(
            self.button("Saved Documents", self.show_documents, light=True)
        )

        root.add_widget(row)

        self.root = root
        return root

    def button(self, text, callback, dark=False, light=False):

        if light:
            bg, fg = WHITE, DARK_BLUE
        elif dark:
            bg, fg = DARK_BLUE, WHITE
        else:
            bg, fg = BLUE, WHITE

        b = Button(
            text=text,
            background_normal="",
            background_color=bg,
            color=fg,
            bold=True,
            font_size="13sp"
        )

        b.bind(on_release=lambda *_: callback())

        return b

    # DATABASE

    def init_db(self):

        with sqlite3.connect(self.db) as con:

            con.execute("""
                CREATE TABLE IF NOT EXISTS docs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    updated TEXT NOT NULL
                )
            """)

    # PLATFORM CHECK

    def is_android(self):

        from kivy.utils import platform

        return platform == "android"

    # SPEECH TO TEXT

    def start_listening(self):

        if self.is_listening:
            return

        self.is_listening = True
        self.status.text = "Starting speech recognition..."

        if self.is_android():
            self.start_android_speech()
        else:
            self.start_windows_speech()

    # WINDOWS SPEECH RECOGNITION

    def start_windows_speech(self):

        try:
            import speech_recognition as sr

        except ImportError:

            self.is_listening = False

            self.message(
                "Missing module",
                "Install:\n"
                "py -m pip install SpeechRecognition pyaudio"
            )

            return

        self.stop_event.clear()

        threading.Thread(
            target=self.windows_worker,
            daemon=True
        ).start()

    def windows_worker(self):

        import speech_recognition as sr

        recognizer = sr.Recognizer()

        try:

            with sr.Microphone() as source:

                recognizer.adjust_for_ambient_noise(
                    source,
                    duration=0.5
                )

                Clock.schedule_once(
                    lambda dt: self.set_status("Listening. Speak now.")
                )

                while not self.stop_event.is_set():

                    try:

                        audio = recognizer.listen(
                            source,
                            timeout=1,
                            phrase_time_limit=12
                        )

                    except sr.WaitTimeoutError:
                        continue

                    if self.stop_event.is_set():
                        break

                    Clock.schedule_once(
                        lambda dt: self.set_status("Converting speech...")
                    )

                    try:

                        words = recognizer.recognize_google(
                            audio,
                            language="en-US"
                        )

                        Clock.schedule_once(
                            lambda dt, value=words:
                            self.append_text(value)
                        )

                    except sr.UnknownValueError:

                        Clock.schedule_once(
                            lambda dt: self.set_status(
                                "Could not understand. Please repeat."
                            )
                        )

                    except sr.RequestError as err:

                        Clock.schedule_once(
                            lambda dt, value=str(err):
                            self.set_status("Speech service error: " + value)
                        )

        except Exception as err:

            Clock.schedule_once(
                lambda dt, value=str(err):
                self.audio_error(value)
            )

        finally:

            self.is_listening = False

            Clock.schedule_once(
                lambda dt: self.set_status("Listening stopped.")
            )

    def audio_error(self, error):

        self.is_listening = False

        self.message(
            "Microphone error",
            "Check that your microphone is connected and allowed in Windows.\n\n"
            + error
        )

    # ANDROID SPEECH RECOGNITION

    def start_android_speech(self):

        try:

            from jnius import autoclass, PythonJavaClass, java_method

            from android.permissions import (
                request_permissions,
                Permission
            )

            self._autoclass = autoclass
            self._PythonJavaClass = PythonJavaClass
            self._java_method = java_method

            def permission_callback(permissions, grants):

                if not all(grants):

                    self.is_listening = False

                    Clock.schedule_once(
                        lambda dt: self.message(
                            "Permission required",
                            "Allow microphone permission and try again."
                        )
                    )

                else:

                    Clock.schedule_once(
                        lambda dt: self.create_android_recognizer()
                    )

            request_permissions(
                [Permission.RECORD_AUDIO, Permission.INTERNET],
                permission_callback
            )

        except Exception as err:

            self.is_listening = False

            self.message("Android setup error", str(err))

    def create_android_recognizer(self):

        try:

            autoclass = self._autoclass
            PythonJavaClass = self._PythonJavaClass
            java_method = self._java_method

            SpeechRecognizer = autoclass(
                "android.speech.SpeechRecognizer"
            )

            RecognizerIntent = autoclass(
                "android.speech.RecognizerIntent"
            )

            Intent = autoclass(
                "android.content.Intent"
            )

            PythonActivity = autoclass(
                "org.kivy.android.PythonActivity"
            )

            Locale = autoclass("java.util.Locale")

            activity = PythonActivity.mActivity

            if not SpeechRecognizer.isRecognitionAvailable(activity):

                raise RuntimeError(
                    "No speech recognition service is available."
                )

            app = self

            class RecognitionListener(PythonJavaClass):

                __javainterfaces__ = [
                    "android/speech/RecognitionListener"
                ]

                __javacontext__ = "app"

                @java_method("(Landroid/os/Bundle;)V")
                def onReadyForSpeech(self, params):

                    Clock.schedule_once(
                        lambda dt: app.set_status("Listening. Speak now.")
                    )

                @java_method("()V")
                def onBeginningOfSpeech(self):
                    pass

                @java_method("(F)V")
                def onRmsChanged(self, rmsdB):
                    pass

                @java_method("([B)V")
                def onBufferReceived(self, buffer):
                    pass

                @java_method("()V")
                def onEndOfSpeech(self):

                    Clock.schedule_once(
                        lambda dt: app.set_status("Converting speech...")
                    )

                @java_method("(I)V")
                def onError(self, error):

                    app.is_listening = False

                    Clock.schedule_once(
                        lambda dt: app.set_status(
                            "Recognition stopped. Try again."
                        )
                    )

                @java_method("(Landroid/os/Bundle;)V")
                def onResults(self, bundle):

                    results = bundle.getStringArrayList(
                        SpeechRecognizer.RESULTS_RECOGNITION
                    )

                    if results is not None and results.size() > 0:

                        words = str(results.get(0))

                        Clock.schedule_once(
                            lambda dt, value=words:
                            app.append_text(value)
                        )

                    app.is_listening = False

                @java_method("(Landroid/os/Bundle;)V")
                def onPartialResults(self, bundle):
                    pass

                @java_method("(ILandroid/os/Bundle;)V")
                def onEvent(self, eventType, params):
                    pass

            self.android_recognizer = (
                SpeechRecognizer.createSpeechRecognizer(activity)
            )

            self.android_listener = RecognitionListener()

            self.android_recognizer.setRecognitionListener(
                self.android_listener
            )

            intent = Intent(
                RecognizerIntent.ACTION_RECOGNIZE_SPEECH
            )

            intent.putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
            )

            intent.putExtra(
                RecognizerIntent.EXTRA_LANGUAGE,
                Locale.getDefault().toString()
            )

            intent.putExtra(
                RecognizerIntent.EXTRA_PARTIAL_RESULTS,
                True
            )

            intent.putExtra(
                RecognizerIntent.EXTRA_PROMPT,
                "Speak to convert your voice into text"
            )

            self.android_recognizer.startListening(intent)

            self.status.text = "Listening. Speak now."

        except Exception as err:

            self.is_listening = False

            self.message("Speech recognition error", str(err))

    def stop_listening(self):

        if not self.is_listening:

            self.status.text = "Not currently listening."
            return

        self.is_listening = False

        if self.is_android():

            try:

                if self.android_recognizer:
                    self.android_recognizer.stopListening()

            except Exception:
                pass

        else:

            self.stop_event.set()

        self.status.text = "Stopping..."

    def append_text(self, words):

        words = words.strip()

        if words:

            old = self.text_input.text.rstrip()

            self.text_input.text = (old + " " + words).strip()

            self.status.text = (
                "Speech converted. Tap Start Listening to dictate more."
            )

    def set_status(self, text):

        self.status.text = text

    # SAVE DOCUMENT

    def save_document(self):

        title = self.title_input.text.strip()
        body = self.text_input.text.strip()

        if not title or not body:

            self.message(
                "Missing information",
                "Enter a title and some text first."
            )

            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        with sqlite3.connect(self.db) as con:

            if self.current_id is None:

                cur = con.execute(
                    "INSERT INTO docs(title,body,updated) VALUES(?,?,?)",
                    (title, body, now)
                )

                self.current_id = cur.lastrowid

            else:

                con.execute(
                    "UPDATE docs SET title=?,body=?,updated=? WHERE id=?",
                    (title, body, now, self.current_id)
                )

        self.status.text = "Document saved."

        self.message(
            "Saved",
            "Your document is saved on this device."
        )

    def new_document(self):

        self.current_id = None
        self.title_input.text = ""
        self.text_input.text = ""

        self.status.text = "New document. Ready to listen."

    # VIEW SAVED DOCUMENTS

    def show_documents(self):

        with sqlite3.connect(self.db) as con:

            rows = con.execute(
                "SELECT id,title,updated FROM docs ORDER BY id DESC"
            ).fetchall()

        popup = Popup(
            title="Saved Documents",
            size_hint=(0.92, 0.82)
        )

        layout = BoxLayout(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(8)
        )

        if rows:

            scroll = ScrollView()

            items = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                spacing=dp(5)
            )

            items.bind(
                minimum_height=items.setter("height")
            )

            for rid, title, updated in rows:

                b = Button(
                    text=f"{title} • {updated}",
                    size_hint_y=None,
                    height=dp(46),
                    background_normal="",
                    background_color=BLUE,
                    color=WHITE
                )

                b.bind(
                    on_release=lambda _, doc_id=rid:
                    self.load_document(doc_id, popup)
                )

                items.add_widget(b)

            scroll.add_widget(items)
            layout.add_widget(scroll)

        else:

            layout.add_widget(
                Label(
                    text="No saved documents.",
                    color=DARK_BLUE
                )
            )

        close = self.button(
            "Close",
            popup.dismiss,
            dark=True
        )

        close.size_hint_y = None
        close.height = dp(44)

        layout.add_widget(close)

        popup.content = layout
        popup.open()

    def load_document(self, rid, popup):

        with sqlite3.connect(self.db) as con:

            row = con.execute(
                "SELECT title,body FROM docs WHERE id=?",
                (rid,)
            ).fetchone()

        if row:

            self.current_id = rid
            self.title_input.text = row[0]
            self.text_input.text = row[1]

            self.status.text = "Document opened."

            popup.dismiss()

    # EXPORT PDF

    def export_pdf(self):

        title = self.title_input.text.strip()
        body = self.text_input.text.strip()

        if not title or not body:

            self.message(
                "Nothing to export",
                "Convert speech or type text first."
            )

            return

        safe = "".join(
            c for c in title
            if c.isalnum() or c in " -_"
        ).strip()

        safe = safe.replace(" ", "_") or "NoteLock_Document"

        filename = (
            safe + "_" +
            datetime.now().strftime("%Y%m%d_%H%M%S") +
            ".pdf"
        )

        path = os.path.join(self.pdf_dir, filename)

        styles = getSampleStyleSheet()

        heading = ParagraphStyle(
            "NLHeading",
            parent=styles["Title"],
            textColor=colors.HexColor("#164A9C"),
            fontSize=19,
            leading=24,
            spaceAfter=8 * mm
        )

        body_style = ParagraphStyle(
            "NLBody",
            parent=styles["BodyText"],
            fontSize=11,
            leading=17,
            textColor=colors.HexColor("#202938"),
            spaceAfter=4 * mm
        )

        story = [
            Paragraph(escape(title), heading),
            Paragraph("Created with NoteLock", styles["Italic"]),
            Spacer(1, 5 * mm)
        ]

        for line in body.splitlines():

            if line.strip():

                story.append(
                    Paragraph(escape(line), body_style)
                )

            else:

                story.append(Spacer(1, 3 * mm))

        pdf = SimpleDocTemplate(
            path,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm
        )

        pdf.build(story)

        self.status.text = "PDF exported."

        self.message(
            "PDF created",
            "Saved in the app's private PDF folder:\n" + path
        )

    # POPUP MESSAGE

    def message(self, title, message):

        layout = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(10)
        )

        layout.add_widget(
            Label(
                text=message,
                color=DARK_BLUE,
                halign="center"
            )
        )

        popup = Popup(
            title=title,
            content=layout,
            size_hint=(0.88, 0.45)
        )

        close = self.button(
            "OK",
            popup.dismiss,
            dark=True
        )

        close.size_hint_y = None
        close.height = dp(42)

        layout.add_widget(close)

        popup.open()

    def on_stop(self):

        self.stop_event.set()

        if self.android_recognizer:

            try:
                self.android_recognizer.destroy()
            except Exception:
                pass


if __name__ == "__main__":

    NoteLockApp().run()
