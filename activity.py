# Copyright 2025 Sugar Labs
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""Sugar-AI Activity: An AI-powered coding assistant for Sugar Learning Platform."""

import gi
import os
import json
import threading
import requests
import time
from urllib.parse import quote

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from gettext import gettext as _

from sugar4.activity.activity import Activity
from sugar4.graphics.toolbarbox import ToolbarBox
from sugar4.activity.widgets import StopButton, ActivityToolbarButton
from sugar4.graphics.alert import Alert
from sugar4.graphics.icon import Icon


class SugarAIActivity(Activity):
    """Sugar-AI Activity class for integrating with Sugar-AI API."""

    def __init__(self, handle, application=None):
        """Set up the Sugar-AI activity."""
        Activity.__init__(self, handle, application=application)

        # Initialize API configuration
        self._api_key = ""
        self._api_base_url = "https://ai.sugarlabs.org"
        self._conversation_history = []
        self._is_requesting = False

        # Load saved API key if exists
        self._load_api_key()

        # We do not have collaboration features yet!
        # Make the share option insensitive
        self.max_participants = 1

        # UI
        self._setup_toolbar()
        self._setup_canvas()

        self.set_title("Sugar-AI Assistant")

    def _setup_toolbar(self):
        """Set up the activity toolbar."""
        toolbar_box = ToolbarBox()

        # Activity button
        activity_button = ActivityToolbarButton(self)
        toolbar_box.toolbar.append(activity_button)

        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        toolbar_box.toolbar.append(separator)

        # API Key button
        api_key_button = Gtk.Button()
        api_key_button.set_label(_("API Key"))
        api_key_button.set_tooltip_text(_("Configure Sugar-AI API Key"))
        api_key_button.connect("clicked", self._on_api_key_clicked)
        toolbar_box.toolbar.append(api_key_button)

        # Clear chat button
        clear_button = Gtk.Button()
        clear_button.set_label(_("Clear"))
        clear_button.set_tooltip_text(_("Clear conversation history"))
        clear_button.connect("clicked", self._on_clear_clicked)
        toolbar_box.toolbar.append(clear_button)

        # RAG toggle button
        self._rag_button = Gtk.ToggleButton()
        self._rag_button.set_label(_("RAG Mode"))
        self._rag_button.set_tooltip_text(_("Toggle Retrieval-Augmented Generation"))
        self._rag_button.set_active(True)  # Default to RAG mode
        toolbar_box.toolbar.append(self._rag_button)

        # Spacer to push stop button to the right
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        toolbar_box.toolbar.append(spacer)

        # Stop button
        stop_button = StopButton(self)
        toolbar_box.toolbar.append(stop_button)

        self.set_toolbar_box(toolbar_box)

    def _setup_canvas(self):
        """Set up the main canvas area."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(12)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)

        # Title and status
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        title_label = Gtk.Label()
        title_label.set_markup(
            "<span size='x-large' weight='bold'>Sugar-AI Assistant</span>"
        )
        title_label.set_halign(Gtk.Align.CENTER)
        title_box.append(title_label)

        self._status_label = Gtk.Label()
        self._update_status_label()
        self._status_label.set_halign(Gtk.Align.CENTER)
        title_box.append(self._status_label)

        main_box.append(title_box)

        # Chat area with scrolled window
        chat_frame = Gtk.Frame()
        chat_frame.set_label(_("Conversation"))
        chat_frame.set_vexpand(True)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(300)

        # Chat history view
        self._chat_view = Gtk.TextView()
        self._chat_view.set_editable(False)
        self._chat_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._chat_buffer = self._chat_view.get_buffer()

        # Set up text tags for formatting
        self._setup_text_tags()

        scrolled.set_child(self._chat_view)
        chat_frame.set_child(scrolled)
        main_box.append(chat_frame)

        # Input area
        input_frame = Gtk.Frame()
        input_frame.set_label(_("Ask Sugar-AI"))

        input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        input_box.set_margin_top(6)
        input_box.set_margin_bottom(6)
        input_box.set_margin_start(6)
        input_box.set_margin_end(6)

        self._question_entry = Gtk.Entry()
        self._question_entry.set_placeholder_text(
            _("Type your programming question here...")
        )
        self._question_entry.set_hexpand(True)
        self._question_entry.connect("activate", self._on_ask_clicked)
        input_box.append(self._question_entry)

        self._ask_button = Gtk.Button()
        self._ask_button.set_label(_("Ask"))
        self._ask_button.connect("clicked", self._on_ask_clicked)
        input_box.append(self._ask_button)

        input_frame.set_child(input_box)
        main_box.append(input_frame)

        # Add some example questions
        examples_frame = Gtk.Frame()
        examples_frame.set_label(_("Example Questions"))

        examples_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        examples_box.set_margin_top(6)
        examples_box.set_margin_bottom(6)
        examples_box.set_margin_start(6)
        examples_box.set_margin_end(6)

        example_questions = [
            "How do I create a Sugar activity with GTK4?",
            "What is the difference between lists and tuples in Python?",
            "How do I add a button to my Sugar activity?",
            "How do I use Pygame in a Sugar activity?",
        ]

        for question in example_questions:
            button = Gtk.Button()
            button.set_label(question)
            button.connect("clicked", lambda btn, q=question: self._set_question(q))
            examples_box.append(button)

        examples_frame.set_child(examples_box)
        main_box.append(examples_frame)

        self.set_canvas(main_box)

    def _setup_text_tags(self):
        """Set up text formatting tags for the chat buffer."""
        # User question tag
        user_tag = self._chat_buffer.create_tag("user")
        user_tag.set_property("weight", 700)  # Bold
        user_tag.set_property("foreground", "#0066cc")

        # AI response tag
        ai_tag = self._chat_buffer.create_tag("ai")
        ai_tag.set_property("foreground", "#006600")

        # Error tag
        error_tag = self._chat_buffer.create_tag("error")
        error_tag.set_property("foreground", "#cc0000")

        # System tag
        system_tag = self._chat_buffer.create_tag("system")
        system_tag.set_property("style", 2)  # Italic
        system_tag.set_property("foreground", "#666666")

    def _load_api_key(self):
        """Load API key from activity data."""
        try:
            data_dir = os.path.join(self.get_activity_root(), "data")
            if os.path.exists(data_dir):
                config_file = os.path.join(data_dir, "config.json")
                if os.path.exists(config_file):
                    with open(config_file, "r") as f:
                        config = json.load(f)
                        self._api_key = config.get("api_key", "")
        except Exception as e:
            print(f"Error loading API key: {e}")

    def _save_api_key(self):
        """Save API key to activity data."""
        try:
            data_dir = os.path.join(self.get_activity_root(), "data")
            os.makedirs(data_dir, exist_ok=True)
            config_file = os.path.join(data_dir, "config.json")

            config = {"api_key": self._api_key}
            with open(config_file, "w") as f:
                json.dump(config, f)
        except Exception as e:
            print(f"Error saving API key: {e}")

    def _update_status_label(self):
        """Update the status label based on API key state."""
        if self._api_key:
            self._status_label.set_markup(
                "<span color='green'>✓ API Key configured</span>"
            )
        else:
            self._status_label.set_markup(
                "<span color='red'>⚠ No API Key - Click 'API Key' to configure</span>"
            )

    def _on_api_key_clicked(self, button):
        """Handle API key configuration button click."""
        dialog = APIKeyDialog(self)
        dialog.present()

    def _on_clear_clicked(self, button):
        """Handle clear conversation button click."""
        self._conversation_history = []
        self._chat_buffer.set_text("")
        self._add_system_message("Conversation cleared.")

    def _on_ask_clicked(self, widget):
        """Handle ask button click or entry activation."""
        question = self._question_entry.get_text().strip()
        if not question:
            return

        if not self._api_key:
            self._show_error_alert("Please configure your API key first.")
            return

        if self._is_requesting:
            return

        # Clear input
        self._question_entry.set_text("")

        # Add question to chat
        self._add_user_message(question)

        # Show "thinking" message
        self._add_system_message(
            "Sugar-AI is thinking... This may take 2-5 minutes, please be patient."
        )

        # Disable input while processing
        self._set_input_sensitive(False)

        # Start API request in background thread
        threading.Thread(
            target=self._make_api_request, args=(question,), daemon=True
        ).start()

    def _set_question(self, question):
        """Set a question in the input field."""
        self._question_entry.set_text(question)

    def _add_user_message(self, message):
        """Add a user message to the chat."""
        end_iter = self._chat_buffer.get_end_iter()
        self._chat_buffer.insert_with_tags_by_name(
            end_iter, f"You: {message}\n\n", "user"
        )
        self._scroll_to_bottom()

    def _add_ai_message(self, message):
        """Add an AI response to the chat."""
        end_iter = self._chat_buffer.get_end_iter()
        self._chat_buffer.insert_with_tags_by_name(
            end_iter, f"Sugar-AI: {message}\n\n", "ai"
        )
        self._scroll_to_bottom()

    def _add_error_message(self, message):
        """Add an error message to the chat."""
        end_iter = self._chat_buffer.get_end_iter()
        self._chat_buffer.insert_with_tags_by_name(
            end_iter, f"Error: {message}\n\n", "error"
        )
        self._scroll_to_bottom()

    def _add_system_message(self, message):
        """Add a system message to the chat."""
        end_iter = self._chat_buffer.get_end_iter()
        self._chat_buffer.insert_with_tags_by_name(
            end_iter, f"[{message}]\n\n", "system"
        )
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        """Scroll chat view to bottom."""
        mark = self._chat_buffer.get_insert()
        self._chat_view.scroll_mark_onscreen(mark)

    def _set_input_sensitive(self, sensitive):
        """Enable/disable input controls."""
        self._question_entry.set_sensitive(sensitive)
        self._ask_button.set_sensitive(sensitive)
        self._is_requesting = not sensitive

        # Update button text to show status
        if sensitive:
            self._ask_button.set_label(_("Ask"))
        else:
            self._ask_button.set_label(_("Thinking..."))

    def _make_api_request(self, question):
        """Make API request in background thread with retry logic."""
        max_retries = 3
        retry_delays = [60, 120, 180]  # Wait 1, 2, then 3 minutes between retries

        try:
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        GLib.idle_add(
                            self._add_system_message,
                            f"Attempt {attempt + 1}/{max_retries} - retrying in {retry_delays[attempt - 1]} seconds...",
                        )
                        time.sleep(retry_delays[attempt - 1])
                        GLib.idle_add(
                            self._add_system_message, "Retrying request to Sugar-AI..."
                        )

                    # Choose endpoint based on RAG toggle
                    endpoint = "/ask" if self._rag_button.get_active() else "/ask-llm"
                    url = f"{self._api_base_url}{endpoint}"

                    params = {"question": quote(question)}
                    headers = {"X-API-Key": self._api_key}

                    # Make the request (Sugar-AI can take 2-5 minutes to respond)
                    response = requests.post(
                        url, params=params, headers=headers, timeout=300
                    )

                    if response.status_code == 200:
                        result = response.json()
                        answer = result.get("answer", "No answer received.")

                        # Update quota info if available
                        quota = result.get("quota", {})
                        if quota:
                            remaining = quota.get("remaining", "Unknown")
                            total = quota.get("total", "Unknown")
                            GLib.idle_add(
                                self._add_system_message, f"Quota: {remaining}/{total}"
                            )

                        # Add the response
                        GLib.idle_add(self._add_ai_message, answer)
                        return  # Success, exit the retry loop

                    elif response.status_code == 401:
                        GLib.idle_add(
                            self._add_error_message,
                            "Invalid API key. Please check your configuration.",
                        )
                        return  # Don't retry auth errors
                    elif response.status_code == 429:
                        GLib.idle_add(
                            self._add_error_message,
                            "Rate limit exceeded. Please try again later.",
                        )
                        return  # Don't retry rate limit errors
                    elif response.status_code == 504:
                        # Server timeout - this is worth retrying
                        if attempt == max_retries - 1:  # Last attempt
                            GLib.idle_add(
                                self._add_error_message,
                                f"Server timeout (504) after {max_retries} attempts. The Sugar-AI service is experiencing high load. Please try again later.",
                            )
                        else:
                            GLib.idle_add(
                                self._add_system_message,
                                f"Server timeout (504) on attempt {attempt + 1}. Will retry...",
                            )
                        continue  # Retry for server timeouts
                    elif response.status_code == 503:
                        GLib.idle_add(
                            self._add_error_message,
                            "Service unavailable (503). The Sugar-AI service may be down for maintenance. Please try again later.",
                        )
                        return  # Don't retry service unavailable
                    else:
                        GLib.idle_add(
                            self._add_error_message,
                            f"API error {response.status_code}: {response.text}",
                        )
                        return  # Don't retry other errors

                except requests.exceptions.Timeout:
                    if attempt == max_retries - 1:  # Last attempt
                        GLib.idle_add(
                            self._add_error_message,
                            f"Request timed out after 5 minutes on {max_retries} attempts. The Sugar-AI service may be experiencing high load. Please try again later.",
                        )
                    else:
                        GLib.idle_add(
                            self._add_system_message,
                            f"Request timed out on attempt {attempt + 1}. Will retry...",
                        )
                    continue  # Retry for timeouts
                except requests.exceptions.ConnectionError:
                    GLib.idle_add(
                        self._add_error_message,
                        "Connection error. Please check your internet connection.",
                    )
                    return  # Don't retry connection errors
                except Exception as e:
                    GLib.idle_add(
                        self._add_error_message, f"Unexpected error: {str(e)}"
                    )
                    return  # Don't retry unexpected errors

        finally:
            # Always re-enable input, regardless of success or failure
            GLib.idle_add(self._set_input_sensitive, True)

    def _show_error_alert(self, message):
        """Show an error alert dialog."""
        alert = Alert()
        alert.props.title = _("Error")
        alert.props.msg = message

        ok_icon = Icon(icon_name="dialog-ok")
        alert.add_button(Gtk.ResponseType.OK, _("OK"), ok_icon)
        alert.connect("response", self._alert_response_cb)

        self.add_alert(alert)

    def _alert_response_cb(self, alert, response_id):
        """Handle alert response."""
        self.remove_alert(alert)

    def read_file(self, file_path):
        """Read activity data from file."""
        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            self._api_key = data.get("api_key", "")
            self._conversation_history = data.get("conversation_history", [])

            # Restore conversation
            self._chat_buffer.set_text("")
            for entry in self._conversation_history:
                if entry["type"] == "user":
                    self._add_user_message(entry["message"])
                elif entry["type"] == "ai":
                    self._add_ai_message(entry["message"])

            self._update_status_label()

        except Exception as e:
            print(f"Error reading file: {e}")

    def write_file(self, file_path):
        """Write activity data to file."""
        try:
            # Extract conversation from buffer
            start_iter = self._chat_buffer.get_start_iter()
            end_iter = self._chat_buffer.get_end_iter()
            text = self._chat_buffer.get_text(start_iter, end_iter, False)

            # Parse conversation (simplified)
            conversation = []
            lines = text.split("\n")
            current_message = ""
            current_type = None

            for line in lines:
                if line.startswith("You: "):
                    if current_message and current_type:
                        conversation.append(
                            {"type": current_type, "message": current_message.strip()}
                        )
                    current_message = line[5:]
                    current_type = "user"
                elif line.startswith("Sugar-AI: "):
                    if current_message and current_type:
                        conversation.append(
                            {"type": current_type, "message": current_message.strip()}
                        )
                    current_message = line[10:]
                    current_type = "ai"
                elif current_message:
                    current_message += "\n" + line

            if current_message and current_type:
                conversation.append(
                    {"type": current_type, "message": current_message.strip()}
                )

            data = {"api_key": self._api_key, "conversation_history": conversation}

            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            print(f"Error writing file: {e}")


class APIKeyDialog(Gtk.Window):
    """Dialog for configuring API key."""

    def __init__(self, parent_activity):
        super().__init__()
        self.parent_activity = parent_activity

        self.set_title(_("Configure Sugar-AI API Key"))
        self.set_modal(True)
        self.set_transient_for(parent_activity)
        self.set_default_size(500, 300)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(12)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)

        # Instructions
        info_label = Gtk.Label()
        info_label.set_markup(
            "<b>Get your Sugar-AI API Key:</b>\n\n"
            "1. Visit https://ai.sugarlabs.org/request-key\n"
            "2. Fill out the form to request an API key\n"
            "3. Wait for approval and receive your key via email\n"
            "4. Enter your API key below:"
        )
        info_label.set_halign(Gtk.Align.START)
        info_label.set_wrap(True)
        main_box.append(info_label)

        # API Key entry
        key_frame = Gtk.Frame()
        key_frame.set_label(_("API Key"))

        self._key_entry = Gtk.Entry()
        self._key_entry.set_text(self.parent_activity._api_key)
        self._key_entry.set_placeholder_text(_("Enter your Sugar-AI API key here"))
        self._key_entry.set_visibility(False)  # Hide the key for security

        key_frame.set_child(self._key_entry)
        main_box.append(key_frame)

        # Show/Hide key checkbox
        self._show_key_check = Gtk.CheckButton()
        self._show_key_check.set_label(_("Show API key"))
        self._show_key_check.connect("toggled", self._on_show_key_toggled)
        main_box.append(self._show_key_check)

        # Buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.set_halign(Gtk.Align.END)

        cancel_button = Gtk.Button()
        cancel_button.set_label(_("Cancel"))
        cancel_button.connect("clicked", self._on_cancel_clicked)
        button_box.append(cancel_button)

        save_button = Gtk.Button()
        save_button.set_label(_("Save"))
        save_button.connect("clicked", self._on_save_clicked)
        button_box.append(save_button)

        main_box.append(button_box)

        self.set_child(main_box)

    def _on_show_key_toggled(self, checkbox):
        """Toggle API key visibility."""
        self._key_entry.set_visibility(checkbox.get_active())

    def _on_cancel_clicked(self, button):
        """Handle cancel button click."""
        self.close()

    def _on_save_clicked(self, button):
        """Handle save button click."""
        api_key = self._key_entry.get_text().strip()
        self.parent_activity._api_key = api_key
        self.parent_activity._save_api_key()
        self.parent_activity._update_status_label()
        self.close()
