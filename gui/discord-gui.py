#!/usr/bin/env python3
"""
Discord Thread Manager — GTK Desktop GUI (The Hacky Way)

Ubuntu desktop app for managing Discord threads without bot tokens.
Uses CDP to extract your user token from the running Discord client,
then scans, reports, categorizes, and manages threads via REST API.

Requires: python3-gi, gir1.2-gtk-3.0, requests, websocket-client
Run: python3 discord-gui.py
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add parent scripts dir to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from discord_controller import (
    DiscordController, DiscordAPIClient, CDPClient,
    DISCORD_API_BASE, DISCORD_EPOCH_MS
)
from utils import (
    categorize_thread, age_bucket, parse_iso_timestamp,
    snowflake_to_datetime, get_thread_last_activity, save_json
)

# ---------------------------------------------------------------------------
# Color scheme
# ---------------------------------------------------------------------------
COLORS = {
    'bg_dark': '#1a1a2e',
    'bg_panel': '#16213e',
    'bg_card': '#1f2b47',
    'bg_card_hover': '#263352',
    'accent': '#FC3F1D',
    'accent_light': '#FF6B4A',
    'yellow': '#FFCC00',
    'green': '#42be65',
    'blue': '#4D8BFF',
    'text': '#f0f0f0',
    'text2': '#a0a0b0',
    'text3': '#6a6a7a',
    'border': 'rgba(255,255,255,0.08)',
    'red': '#fa4d56',
}


# ---------------------------------------------------------------------------
# CSS Provider
# ---------------------------------------------------------------------------
def load_css():
    css = """
    window { background-color: #1a1a2e; }
    .header-bar { background: #16213e; border-bottom: 1px solid rgba(255,255,255,0.08); padding: 12px 20px; }
    .header-title { color: #f0f0f0; font-size: 20px; font-weight: bold; }
    .header-subtitle { color: #6a6a7a; font-size: 11px; font-family: monospace; }
    .status-bar { background: #16213e; border-top: 1px solid rgba(255,255,255,0.08); padding: 8px 20px; }
    .status-label { color: #6a6a7a; font-size: 11px; font-family: monospace; }
    .accent-btn { background: #FC3F1D; color: white; border: none; border-radius: 6px; padding: 8px 20px; font-weight: bold; font-size: 12px; }
    .accent-btn:hover { background: #FF6B4A; }
    .secondary-btn { background: #1f2b47; color: #a0a0b0; border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; padding: 8px 16px; font-size: 12px; }
    .secondary-btn:hover { color: #f0f0f0; border-color: rgba(255,255,255,0.15); }
    .search-entry { background: #1f2b47; color: #f0f0f0; border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; padding: 8px 12px; font-size: 12px; }
    .search-entry:focus { border-color: #FC3F1D; }
    .channel-label { color: #f0f0f0; font-size: 12px; font-weight: bold; }
    .stat-value { color: #FC3F1D; font-size: 24px; font-weight: bold; }
    .stat-label { color: #6a6a7a; font-size: 10px; }
    .filter-btn { background: transparent; color: #6a6a7a; border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 4px 12px; font-size: 10px; }
    .filter-btn:hover { color: #f0f0f0; border-color: rgba(255,255,255,0.15); }
    .filter-btn.active { background: rgba(252,63,29,0.15); color: #FC3F1D; border-color: #FC3F1D; }
    .detail-title { color: #f0f0f0; font-size: 16px; font-weight: bold; }
    .detail-label { color: #6a6a7a; font-size: 10px; font-family: monospace; }
    .detail-value { color: #a0a0b0; font-size: 12px; }
    treeview { background: #1a1a2e; color: #a0a0b0; border: none; }
    treeview:selected { background: rgba(252,63,29,0.2); color: #f0f0f0; }
    treeview header button { background: #16213e; color: #6a6a7a; border: none; border-bottom: 1px solid rgba(255,255,255,0.08); padding: 6px; font-size: 10px; font-weight: bold; }
    scrolledwindow { background: transparent; }
    spinbutton { background: #1f2b47; color: #f0f0f0; border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; padding: 4px 8px; }
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode())
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


# ---------------------------------------------------------------------------
# Thread Store — holds scan results, handles filtering
# ---------------------------------------------------------------------------
class ThreadStore:
    def __init__(self):
        self.all_threads = []
        self.filtered_threads = []
        self.scan_metadata = {}
        self.categories = []
        self.active_filter = "All"
        self.search_query = ""

    def load_scan(self, result):
        self.all_threads = result.get("stale_threads", []) + result.get("all_threads", [])
        seen = set()
        unique = []
        for t in self.all_threads:
            if t["id"] not in seen:
                seen.add(t["id"])
                unique.append(t)
        self.all_threads = unique
        self.scan_metadata = result.get("scan_metadata", {})
        self.categories = sorted(set(t.get("category", "Other/Misc") for t in self.all_threads))
        self.apply_filters()

    def apply_filters(self):
        threads = self.all_threads
        if self.active_filter != "All":
            threads = [t for t in threads if t.get("category") == self.active_filter]
        if self.search_query:
            q = self.search_query.lower()
            threads = [t for t in threads if q in t.get("name", "").lower() or q in t.get("id", "")]
        self.filtered_threads = threads

    def set_filter(self, category):
        self.active_filter = category
        self.apply_filters()

    def set_search(self, query):
        self.search_query = query
        self.apply_filters()

    def get_stats(self):
        total = len(self.all_threads)
        archived = sum(1 for t in self.all_threads if t.get("is_archived"))
        locked = sum(1 for t in self.all_threads if t.get("is_locked"))
        stale = sum(1 for t in self.all_threads if t.get("days_inactive", 0) >= 30)
        return {"total": total, "archived": archived, "locked": locked, "stale": stale}


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------
class DiscordThreadManagerWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Discord Thread Manager")
        self.set_default_size(1100, 700)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.controller = None
        self.store = ThreadStore()
        self.detail_btn_thread_id = None

        load_css()
        self._build_ui()
        self._connect_signals()

    # ---- UI BUILDING ----

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(main_box)

        self._build_header(main_box)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.pack_start(content, True, True, 0)

        self._build_toolbar(content)
        self._build_stats_bar(content)
        self._build_filter_bar(content)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(650)
        content.pack_start(paned, True, True, 0)

        self._build_thread_list(paned)
        self._build_detail_panel(paned)
        self._build_status_bar(main_box)

    def _build_header(self, parent):
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header.get_style_context().add_class("header-bar")
        parent.pack_start(header, False, False, 0)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header.pack_start(title_box, True, True, 0)

        lbl = Gtk.Label(label="Discord Thread Manager")
        lbl.get_style_context().add_class("header-title")
        lbl.set_xalign(0)
        title_box.pack_start(lbl, False, False, 0)

        self.status_subtitle = Gtk.Label(label="No token extracted -- connect to Discord first")
        self.status_subtitle.get_style_context().add_class("header-subtitle")
        self.status_subtitle.set_xalign(0)
        title_box.pack_start(self.status_subtitle, False, False, 0)

        self.connect_btn = Gtk.Button(label="Connect")
        self.connect_btn.get_style_context().add_class("accent-btn")
        header.pack_end(self.connect_btn, False, False, 0)

    def _build_toolbar(self, parent):
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_top(8)
        toolbar.set_margin_bottom(4)
        toolbar.set_margin_start(16)
        toolbar.set_margin_end(16)
        parent.pack_start(toolbar, False, False, 0)

        ch_label = Gtk.Label(label="Channel ID:")
        ch_label.get_style_context().add_class("channel-label")
        toolbar.pack_start(ch_label, False, False, 0)

        self.channel_entry = Gtk.Entry()
        self.channel_entry.get_style_context().add_class("search-entry")
        self.channel_entry.set_width_chars(20)
        self.channel_entry.set_placeholder_text("e.g. 1234567890123456")
        toolbar.pack_start(self.channel_entry, False, False, 0)

        d_label = Gtk.Label(label="  Min days:")
        d_label.get_style_context().add_class("channel-label")
        toolbar.pack_start(d_label, False, False, 0)

        adj = Gtk.Adjustment(value=30, lower=1, upper=365, step_increment=1)
        self.days_spinner = Gtk.SpinButton()
        self.days_spinner.set_adjustment(adj)
        self.days_spinner.set_value(30)
        toolbar.pack_start(self.days_spinner, False, False, 0)

        self.scan_btn = Gtk.Button(label="Scan Threads")
        self.scan_btn.get_style_context().add_class("accent-btn")
        toolbar.pack_start(self.scan_btn, False, False, 4)

        sep = Gtk.Separator()
        toolbar.pack_start(sep, False, False, 8)

        self.report_btn = Gtk.Button(label="Report")
        self.report_btn.get_style_context().add_class("secondary-btn")
        self.report_btn.set_sensitive(False)
        toolbar.pack_start(self.report_btn, False, False, 4)

        self.archive_btn = Gtk.Button(label="Lock & Archive")
        self.archive_btn.get_style_context().add_class("secondary-btn")
        self.archive_btn.set_sensitive(False)
        toolbar.pack_start(self.archive_btn, False, False, 4)

        self.search_entry = Gtk.Entry()
        self.search_entry.get_style_context().add_class("search-entry")
        self.search_entry.set_width_chars(25)
        self.search_entry.set_placeholder_text("Search threads...")
        toolbar.pack_end(self.search_entry, False, False, 0)

    def _build_stats_bar(self, parent):
        stats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        stats_box.set_margin_start(16)
        stats_box.set_margin_end(16)
        stats_box.set_margin_top(4)
        stats_box.set_margin_bottom(4)
        parent.pack_start(stats_box, False, False, 0)

        self.stat_labels = {}
        for key, label_text in [("total", "Total"), ("stale", "Stale 30d+"),
                                ("archived", "Archived"), ("locked", "Locked")]:
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            val = Gtk.Label(label="0")
            val.get_style_context().add_class("stat-value")
            box.pack_start(val, False, False, 0)
            lbl = Gtk.Label(label=label_text)
            lbl.get_style_context().add_class("stat-label")
            box.pack_start(lbl, False, False, 0)
            stats_box.pack_start(box, False, False, 0)
            self.stat_labels[key] = val

    def _build_filter_bar(self, parent):
        self.filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.filter_box.set_margin_start(16)
        self.filter_box.set_margin_top(2)
        self.filter_box.set_margin_bottom(4)
        parent.pack_start(self.filter_box, False, False, 0)

        lbl = Gtk.Label(label="  Filter: ")
        lbl.get_style_context().add_class("detail-label")
        self.filter_box.pack_start(lbl, False, False, 0)

        self.filter_buttons = {}
        btn = Gtk.Button(label="All")
        btn.get_style_context().add_class("filter-btn")
        btn.get_style_context().add_class("active")
        self.filter_buttons["All"] = btn
        self.filter_box.pack_start(btn, False, False, 0)

    def _build_thread_list(self, parent):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        parent.pack1(scrolled, True, True)

        self.liststore = Gtk.ListStore(str, str, str, int, bool, bool, int)
        self.treeview = Gtk.TreeView(model=self.liststore)
        self.treeview.set_activate_on_single_click(True)

        for i, (title, col_type) in enumerate([
            ("Thread", 0), ("Category", 2), ("Days Inactive", 3),
            ("Messages", 6), ("Archived", 4), ("Locked", 5)
        ]):
            if col_type in (4, 5):
                renderer = Gtk.CellRendererToggle()
                col = Gtk.TreeViewColumn(title, renderer, active=col_type)
                renderer.set_activatable(False)
            else:
                renderer = Gtk.CellRendererText()
                col = Gtk.TreeViewColumn(title, renderer, text=col_type)
            col.set_resizable(True)
            col.set_min_width(80 if col_type != 0 else 250)
            self.treeview.append_column(col)

        self.treeview.set_headers_visible(True)
        self.treeview.set_enable_search(True)
        self.treeview.set_search_column(0)
        scrolled.add(self.treeview)

    def _build_detail_panel(self, parent):
        self.detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.detail_box.set_margin_top(16)
        self.detail_box.set_margin_bottom(16)
        self.detail_box.set_margin_start(16)
        self.detail_box.set_margin_end(16)
        parent.pack2(self.detail_box, True, True)

        self.detail_title = Gtk.Label(label="Select a thread")
        self.detail_title.get_style_context().add_class("detail-title")
        self.detail_title.set_xalign(0)
        self.detail_title.set_line_wrap(True)
        self.detail_box.pack_start(self.detail_title, False, False, 0)

        self.detail_grid = Gtk.Grid()
        self.detail_grid.set_column_spacing(12)
        self.detail_grid.set_row_spacing(8)
        self.detail_box.pack_start(self.detail_grid, False, False, 8)

        self.detail_fields = {}
        for i, (key, label) in enumerate([
            ("id", "Thread ID"), ("category", "Category"),
            ("days_inactive", "Days Inactive"), ("message_count", "Messages"),
            ("is_archived", "Archived"), ("is_locked", "Locked"),
            ("source", "Source"), ("parent_id", "Parent Channel"),
            ("owner_id", "Owner ID"), ("last_activity", "Last Activity"),
        ]):
            lbl = Gtk.Label(label=label + ":")
            lbl.get_style_context().add_class("detail-label")
            lbl.set_xalign(0)
            self.detail_grid.attach(lbl, 0, i, 1, 1)

            val = Gtk.Label(label="--")
            val.get_style_context().add_class("detail-value")
            val.set_xalign(0)
            val.set_selectable(True)
            self.detail_grid.attach(val, 1, i, 1, 1)
            self.detail_fields[key] = val

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_margin_top(12)
        self.detail_box.pack_start(btn_box, False, False, 0)

        self.detail_lock_btn = Gtk.Button(label="Lock")
        self.detail_lock_btn.get_style_context().add_class("secondary-btn")
        self.detail_lock_btn.set_sensitive(False)
        btn_box.pack_start(self.detail_lock_btn, False, False, 0)

        self.detail_archive_btn = Gtk.Button(label="Archive")
        self.detail_archive_btn.get_style_context().add_class("secondary-btn")
        self.detail_archive_btn.set_sensitive(False)
        btn_box.pack_start(self.detail_archive_btn, False, False, 0)

        self.detail_both_btn = Gtk.Button(label="Lock & Archive")
        self.detail_both_btn.get_style_context().add_class("accent-btn")
        self.detail_both_btn.set_sensitive(False)
        btn_box.pack_start(self.detail_both_btn, False, False, 0)

        self.detail_box.pack_start(Gtk.Label(), True, True, 0)

        self.report_view = Gtk.TextView()
        self.report_view.set_editable(False)
        self.report_view.get_style_context().add_class("search-entry")
        self.report_view.set_visible(False)
        report_scroll = Gtk.ScrolledWindow()
        report_scroll.add(self.report_view)
        self.detail_box.pack_start(report_scroll, True, True, 0)

    def _build_status_bar(self, parent):
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        bar.get_style_context().add_class("status-bar")
        parent.pack_end(bar, False, False, 0)

        self.status_label = Gtk.Label(label="Ready")
        self.status_label.get_style_context().add_class("status-label")
        self.status_label.set_xalign(0)
        bar.pack_start(self.status_label, True, True, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.set_fraction(0)
        self.progress.set_show_text(True)
        bar.pack_end(self.progress, False, False, 0)

    # ---- SIGNALS ----

    def _connect_signals(self):
        self.connect_btn.connect("clicked", self._on_connect)
        self.scan_btn.connect("clicked", self._on_scan)
        self.report_btn.connect("clicked", self._on_report)
        self.archive_btn.connect("clicked", self._on_bulk_archive)
        self.search_entry.connect("changed", self._on_search)
        self.treeview.connect("row-activated", self._on_thread_selected)
        self.detail_lock_btn.connect("clicked", self._on_detail_lock)
        self.detail_archive_btn.connect("clicked", self._on_detail_archive)
        self.detail_both_btn.connect("clicked", self._on_detail_both)

    # ---- ACTIONS ----

    def _set_status(self, msg):
        GLib.idle_add(self.status_label.set_text, msg)

    def _on_connect(self, btn):
        if self.controller:
            self._set_status("Already connected")
            return
        btn.set_sensitive(False)
        self._set_status("Connecting to Discord via CDP...")
        threading.Thread(target=self._do_connect, daemon=True).start()

    def _do_connect(self):
        try:
            self.controller = DiscordController()
            if not self.controller.full_startup():
                GLib.idle_add(self._on_connect_fail, "Failed to connect. Is Discord running?")
                return
            user = self.controller.api.user_info
            username = f"{user.get('username', '?')}#{user.get('discriminator', '?')}" if user else "?"
            GLib.idle_add(self._on_connect_success, username)
        except Exception as e:
            GLib.idle_add(self._on_connect_fail, str(e))

    def _on_connect_success(self, username):
        self.connect_btn.set_label(f"Connected: {username}")
        self.connect_btn.set_sensitive(False)
        self.status_subtitle.set_text(f"Authenticated as {username} -- token extracted via CDP")
        self._set_status(f"Connected as {username}")

    def _on_connect_fail(self, msg):
        self.connect_btn.set_sensitive(True)
        self.connect_btn.set_label("Connect")
        self._set_status(f"Connection failed: {msg}")

    def _on_scan(self, btn):
        if not self.controller:
            self._set_status("Connect to Discord first!")
            return
        channel_id = self.channel_entry.get_text().strip()
        if not channel_id:
            self._set_status("Enter a Channel ID")
            return
        min_days = int(self.days_spinner.get_value())
        self.scan_btn.set_sensitive(False)
        self._set_status(f"Scanning channel {channel_id}...")
        GLib.idle_add(self.progress.set_fraction, 0.1)
        threading.Thread(target=self._do_scan, args=(channel_id, min_days), daemon=True).start()

    def _do_scan(self, channel_id, min_days):
        try:
            GLib.idle_add(self.progress.set_fraction, 0.3)
            result = self.controller.scan_threads(channel_id, min_days)
            GLib.idle_add(self.progress.set_fraction, 0.8)
            GLib.idle_add(self._on_scan_complete, result)
        except Exception as e:
            GLib.idle_add(self._on_scan_fail, str(e))

    def _on_scan_complete(self, result):
        self.store.load_scan(result)
        self._refresh_list()
        self._refresh_stats()
        self._refresh_filters()
        self.scan_btn.set_sensitive(True)
        self.report_btn.set_sensitive(True)
        self.archive_btn.set_sensitive(True)
        self.progress.set_fraction(1.0)
        meta = self.store.scan_metadata
        self._set_status(
            f"Scan complete: {meta.get('total_threads_scanned', 0)} threads, "
            f"{meta.get('total_stale', 0)} stale")
        GLib.timeout_add(2000, lambda: (self.progress.set_fraction(0), False)[1])

    def _on_scan_fail(self, msg):
        self.scan_btn.set_sensitive(True)
        self.progress.set_fraction(0)
        self._set_status(f"Scan failed: {msg}")

    def _on_report(self, btn):
        if not self.store.all_threads:
            self._set_status("No threads to report")
            return
        threading.Thread(target=self._do_report, daemon=True).start()

    def _do_report(self):
        import tempfile
        report_path = os.path.join(tempfile.gettempdir(), "discord_thread_report.md")
        lines = [f"# Thread Report -- {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"]
        stats = self.store.get_stats()
        lines.append(f"Total: {stats['total']} | Stale: {stats['stale']} | Archived: {stats['archived']} | Locked: {stats['locked']}\n")

        cat_counts = {}
        for t in self.store.all_threads:
            cat = t.get("category", "Other")
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        lines.append("\n## Categories")
        for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- **{cat}**: {count}")

        lines.append("\n## Thread Details")
        for t in sorted(self.store.all_threads, key=lambda x: -x.get("days_inactive", 0)):
            status = []
            if t.get("is_archived"):
                status.append("archived")
            if t.get("is_locked"):
                status.append("locked")
            status_str = f" [{', '.join(status)}]" if status else ""
            lines.append(f"- **{t.get('name', 'Untitled')}** -- {t.get('days_inactive', '?')}d inactive, {t.get('message_count', 0)} msgs, {t.get('category', '?')}{status_str}")

        report = "\n".join(lines)
        with open(report_path, 'w') as f:
            f.write(report)
        GLib.idle_add(self._show_report, report, report_path)

    def _show_report(self, report, path):
        buf = self.report_view.get_buffer()
        buf.set_text(report)
        self.report_view.set_visible(True)
        self._set_status(f"Report saved to {path}")

    def _on_bulk_archive(self, btn):
        if not self.controller or not self.store.filtered_threads:
            return
        dialog = Gtk.MessageDialog(
            parent=self, flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Lock & archive {len(self.store.filtered_threads)} threads?")
        dialog.format_secondary_text("This will lock and archive all filtered threads.")
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return

        dialog2 = Gtk.MessageDialog(
            parent=self, flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Run LIVE? (No = dry run)")
        dialog2.format_secondary_text("YES = actually lock & archive. NO = dry run only.")
        live = dialog2.run() == Gtk.ResponseType.YES
        dialog2.destroy()

        thread_ids = [t["id"] for t in self.store.filtered_threads]
        self.archive_btn.set_sensitive(False)
        self._set_status(f"{'LIVE' if live else 'DRY RUN'}: Processing {len(thread_ids)} threads...")
        threading.Thread(target=self._do_archive, args=(thread_ids, not live), daemon=True).start()

    def _do_archive(self, thread_ids, dry_run):
        try:
            result = self.controller.lock_and_archive_threads(thread_ids, dry_run=dry_run)
            GLib.idle_add(self._on_archive_complete, result, dry_run)
        except Exception as e:
            GLib.idle_add(self._set_status, f"Archive failed: {e}")

    def _on_archive_complete(self, result, dry_run):
        self.archive_btn.set_sensitive(True)
        mode = "DRY RUN" if dry_run else "LIVE"
        locked = len(result.get("locked", []))
        failed = len(result.get("failed", []))
        self._set_status(f"{mode} complete: {locked} processed, {failed} failed")

    def _on_search(self, entry):
        self.store.set_search(entry.get_text())
        self._refresh_list()

    def _on_thread_selected(self, treeview, path, column):
        tree_iter = self.liststore.get_iter(path)
        thread_id = self.liststore.get_value(tree_iter, 0)
        for t in self.store.all_threads:
            if t["id"] == thread_id:
                self._show_detail(t)
                break

    def _show_detail(self, thread):
        self.detail_title.set_text(thread.get("name", "Untitled"))
        self.detail_fields["id"].set_text(thread.get("id", "--"))
        self.detail_fields["category"].set_text(thread.get("category", "--"))
        self.detail_fields["days_inactive"].set_text(str(thread.get("days_inactive", "--")))
        self.detail_fields["message_count"].set_text(str(thread.get("message_count", 0)))
        self.detail_fields["is_archived"].set_text("Yes" if thread.get("is_archived") else "No")
        self.detail_fields["is_locked"].set_text("Yes" if thread.get("is_locked") else "No")
        self.detail_fields["source"].set_text(thread.get("source", "--"))
        self.detail_fields["parent_id"].set_text(thread.get("parent_id", "--"))
        self.detail_fields["owner_id"].set_text(thread.get("owner_id", "--"))
        self.detail_fields["last_activity"].set_text(
            thread.get("last_activity", "--")[:19].replace("T", " "))
        self.detail_lock_btn.set_sensitive(True)
        self.detail_archive_btn.set_sensitive(True)
        self.detail_both_btn.set_sensitive(True)
        self.detail_btn_thread_id = thread["id"]

    def _on_detail_lock(self, btn):
        if self.detail_btn_thread_id and self.controller:
            ok = self.controller.api.lock_thread(self.detail_btn_thread_id)
            self._set_status(f"Lock {'OK' if ok else 'FAIL'}: {self.detail_btn_thread_id}")

    def _on_detail_archive(self, btn):
        if self.detail_btn_thread_id and self.controller:
            ok = self.controller.api.archive_thread(self.detail_btn_thread_id)
            self._set_status(f"Archive {'OK' if ok else 'FAIL'}: {self.detail_btn_thread_id}")

    def _on_detail_both(self, btn):
        if self.detail_btn_thread_id and self.controller:
            tid = self.detail_btn_thread_id
            lock_ok, archive_ok = self.controller.api.lock_and_archive(tid)
            self._set_status(f"Lock {'OK' if lock_ok else 'FAIL'} | Archive {'OK' if archive_ok else 'FAIL'}: {tid}")

    # ---- REFRESH UI ----

    def _refresh_list(self):
        self.liststore.clear()
        for t in self.store.filtered_threads:
            self.liststore.append([
                t.get("id", ""),
                t.get("name", "Untitled"),
                t.get("category", "Other"),
                t.get("days_inactive", 0),
                t.get("is_archived", False),
                t.get("is_locked", False),
                t.get("message_count", 0),
            ])

    def _refresh_stats(self):
        stats = self.store.get_stats()
        for key, label in self.stat_labels.items():
            label.set_text(str(stats.get(key, 0)))

    def _refresh_filters(self):
        for btn in list(self.filter_buttons.values()):
            if btn.get_parent():
                self.filter_box.remove(btn)
        self.filter_buttons.clear()

        all_btn = Gtk.Button(label="All")
        all_btn.get_style_context().add_class("filter-btn")
        if self.store.active_filter == "All":
            all_btn.get_style_context().add_class("active")
        all_btn.connect("clicked", self._on_filter_click, "All")
        self.filter_box.pack_start(all_btn, False, False, 0)
        self.filter_buttons["All"] = all_btn

        for cat in self.store.categories:
            btn = Gtk.Button(label=cat)
            btn.get_style_context().add_class("filter-btn")
            if self.store.active_filter == cat:
                btn.get_style_context().add_class("active")
            btn.connect("clicked", self._on_filter_click, cat)
            self.filter_box.pack_start(btn, False, False, 0)
            self.filter_buttons[cat] = btn

        self.filter_box.show_all()

    def _on_filter_click(self, btn, category):
        self.store.set_filter(category)
        self._refresh_list()
        for b in self.filter_buttons.values():
            if b.get_style_context().has_class("active"):
                b.get_style_context().remove_class("active")
        btn.get_style_context().add_class("active")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
def main():
    win = DiscordThreadManagerWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
