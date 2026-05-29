#!/usr/bin/env python3
"""
Discord Thread Manager — GTK Desktop GUI (The Hacky Way)

Ubuntu desktop app for managing Discord threads without bot tokens.
Uses CDP to extract your user token from the running Discord client,
then scans, reports, categorizes, and manages threads via REST API.

Requires: python3-gi, gir1.2-webkit2 or higher.
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
from typing import Optional

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

# CSS Provider for light theme
def load_css():
    css = f"""
    *{{margin:0;padding:0;box-sizing:border-box}}
    :root{--yan-red:#FC3F1D;--yan-red-light:#FF6B4A;--yan-red-dark:#D63416;
    --yan-yellow:#FFCC00;--yan-yellow-light:#FFE066;
    --yan-bg:#F5F5F7;--yan-surface:#FFFFFF;--yan-surface2:#EEEEF0;
    --yan-text:#1D1D1F;--yan-text2:#6E6E73;--yan-text3:#86868B;--yan-text4:#AAAAAF;
    --yan-border:rgba(0,0,0,.08);--yan-border-s:rgba(0,0,0,.12);
    --yan-blue:#005FF9;--yan-blue-light:#4D8BFF;
    --radius:14px;--radius-sm:10px;
    }
    ::selection{background:rgba(252,63,29,.25);color:var(--yan-dark)}
    html{scroll-behavior:smooth;background:var(--yan-bg);color:var(--yan-text)}
    body{font-family:'IBM Plex Sans',-apple-system,sans-serif;background:var(--yan-bg);color:var(--yan-text);line-height:1.7;-webkit-font-smoothing:antialiased;max-width:720px;margin:0 auto;padding:2rem 1.5rem}
    @media(min-width:960px){body{padding:3rem 2rem}}
    a{color:var(--yan-red);text-decoration:none;transition:color .2s}a:hover{color:var(--yan-red-dark);text-decoration:none}
    nav{position:sticky;top:0;z-index:100;background:rgba(245,245,247,.85);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-bottom:1px solid var(--yan-border);display:flex;align-items:center;justify-content:space:space-between;height:56px;padding:0 20px;margin:0 0 2rem 0;max-width:100vw}
    .nav-brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:.9rem;letter-spacing:.02em;color:var(--yan-dark)}
    .nav-brand span{font-size:1.2rem}
    .nav-links{display:flex;gap:24px;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
    .nav-links a{font-size:.75rem;color:var(--yan-text3);font-weight:600;letter-spacing:.06em;text-transform:uppercase;padding:4px 0;white-space:nowrap;border-bottom:2px solid transparent;transition:all .25s}
    .nav-links a:hover{color:var(--yan-text);text-decoration:none}
    .back-link{display:inline-flex;align-items:center;gap:6px;font-family:'IBM Plex Mono',monospace;font-size:.75rem;color:var(--yan-text3);letter-spacing:.05em;text-transform:uppercase;margin-bottom:1.5rem;padding:6px 0}
    .back-link:hover{color:var(--yan-dark);text-decoration:none}
    h1{font-size:clamp(1.8rem,4.5vw,2.75rem);font-weight:700;letter-spacing:-.03em;line-height:1.1;color:var(--yan-dark);margin-bottom:.5rem}
    .meta{display:flex;gap:1rem;align-items:center;margin:1.5rem 0;font-family:'IBM Plex Mono',monospace;font-size:.7rem;color:var(--yan-text3);flex-wrap:wrap}
    .tag{display:inline-block;font-family:'IBM Plex Mono',monospace;font-size:.65rem;padding:2px 10px;border-radius:100px;font-weight:600;letter-spacing:.03em;text-transform:uppercase;}
    .section{margin:2.5rem 0;color:var(--yan-text2);font-size:.95rem;line-height:1.75}
    .section h2{font-size:1.15rem;font-weight:700;margin-bottom:1rem;color:var(--yan-dark);letter-spacing:-.01em}
    .section h3{font-size:.95rem;font-weight:600;margin:1.25rem 0 .5rem;color:var(--yan-text2)}
    .section p{margin-bottom:.75rem}
    .section ul,.section ol{margin:.5rem 0 .75rem 1.25rem;line-height:1.8}
    .section li{margin-bottom:.4rem}
    strong{color:var(--yan-dark)}
    blockquote{border-left:3px solid var(--yan-red);padding:.5rem 1rem;margin:1.5rem 0;color:var(--yan-text3);font-style:italic;background:var(--yan-surface2);border-radius:0 var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm)} var(--radius-sm)}
    hr{border:none;border-top:1px solid var(--yan-border);margin:2.5rem 0}
    table{width:100%;border-collapse:collapse;margin:1rem 0;font-size:.85rem}
    th{background:var(--yan-surface2);padding:8px 12px;text-align:left;font-weight:600;color:var(--yan-text);border-bottom:2px solid var(--yan-border-s)}
    td{padding:8px 12px;border-bottom:1px solid var(--yan-border);color:var(--yan-text2);background:var(--yan-surface)}
    tr:last-child td{border-bottom:none}
    pre{background:var(--yan-surface2);border:1px solid var(--yan-border);border-radius:var(--radius);padding:1.5rem;overflow-x:auto;margin:1.5rem 0;font-family:'IBM Plex Mono',monospace;font-size:.82rem;color:var(--yan-text)}
    code{background:var(--yan-surface2);padding:.15rem .4rem;border-radius:4px;font-size:.85rem;color:var(--yan-red);font-family:'IBM Plex Mono',monospace}
    .note{background:rgba(252,63,29,.06);border-left:3px solid var(--yan-red);padding:.75rem 1rem;margin:1.5rem 0;font-size:.9rem;color:var(--yan-text2);border-radius:0 var(--radius) var(--radius) var(--radius-sm) var(--radius-sm) var(--radius-sm)}
    .promo-banner{display:flex;align-items:center;gap:1rem;padding:.85rem 1.1rem;border-radius:var(--radius);margin:1.25rem 0;font-size:.82rem;line-height:1.5}
    .promo-banner.promo-zaia{background:linear-gradient(135deg,rgba(0,95,249,.06),rgba(0,95,249,.02));border:1px solid rgba(0,95,249,.15);border-radius:var(--radius);padding:1.25rem 1.5rem}
    .promo-banner.promo-mimo{background:linear-gradient(135deg,rgba(252,63,29,.06),rgba(255,131,43,.02));border:1px solid rgba(252,63,29,.15);border-radius:var(--radius);padding:1.25rem 1.5rem}
    .promo-banner .promo-body{color:var(--yan-text2)}.promo-banner .promo-body strong{color:var(--yan-dark)}
    .promo-banner a{color:var(--yan-blue);font-weight:600;text-decoration:underline;text-underline-offset:2px}.promo-banner a:hover{color:var(--yan-blue-light)}
    .promo-tag{display:inline-block;font-family:'IBM Plex Mono',monospace;font-size:.55rem;padding:2px 7px;border-radius:100px;font-weight:700;letter-spacing:.04em;text-transform:uppercase}
    .promo-tag.zaia{background:rgba(0,95,249,.1);color:var(--yan-blue)}.promo-tag.mimo{background:rgba(252,63,29,.1);color:var(--yan-red)}
    .verdict-box,.verdict{background:linear-gradient(135deg,rgba(252,63,29,.06),rgba(255,204,0,.03));border:1px solid rgba(252,63,29,.2);border-radius:var(--radius);padding:1.5rem;margin:2rem 0}
    .verdict-title,.verdict h3{font-size:1.1rem;font-weight:700;color:var(--yan-red);margin-bottom:.75rem}
    .verdict-body{color:var(--yan-text2);font-size:.95rem;line-height:1.7}
    .pros-cons{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin:2rem 0}
    @media(max-width:600px){.pros-cons{grid-template-columns:1fr;gap:1rem}}
    .pros-cons-col{border-radius:var(--radius);padding:1.25rem}
    .pros-cons-col.pros{background:rgba(66,190,101,.06)}.pros-cons-col.cons{background:rgba(252,63,29,.06)}.pros-cons-col h3{font-size:.9rem;font-weight:600;margin-bottom:1rem;color:var(--yan-dark)}
    .pros-cons-col li{margin-bottom:.5rem;color:var(--yan-text2)}
    .tool-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr);gap:.75rem;margin:1rem 0}
    .tool-card{background:var(--yan-surface);border:1px solid var(--yan-border);border-radius:var(--radius);padding:.85rem 1rem;font-size:.82rem}
    .tool-card .tool-name{font-weight:600;color:var(--yan-dark);margin-bottom:.25rem}
    .tool-card .tool-status{font-family:'IBM Plex Mono',monospace;font-size:.65rem}
    .tool-card .tool-status.tested{color:#42be65}.tool-card .tool-status.untested{color:var(--yan-text3)}
    .arch{background:var(--yan-surface2);border:1px solid var(--yan-border);border-radius:var(--radius);padding:1.5rem;margin:1.5rem 0;font-family:'IBM Plex Mono',monospace;font-size:.78rem;line-height:1.5;color:var(--yan-text2);white-space:pre;overflow-x:auto}
    .arch .hl-purple{color:#7C3AED}.arch .hl-blue{color:var(--yan-blue)}.arch .hl-green{color:#059669}.arch .hl-red{color:var(--yan-red)}.arch .hl-teal{color:#0891B2}
    .roundup-header{text-align:center;padding:2rem 0;margin-bottom:1rem}
    .roundup-header h1{font-size:2rem;margin-bottom:.25rem;color:var(--yan-dark)}
    .roundup-header .date{font-family:'IBM Plex Mono',monospace;font-size:.85rem;color:var(--yan-text3);margin-bottom:1rem}
    .feature-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:1.25rem;margin:2rem 0}
    @media(max-width:600px){.feature-grid{grid-template-columns:1fr}}
    .feature-card{background:var(--yan-surface);border:1px solid var(--yan-border);border-radius:var(--radius);padding:1.5rem;transition:all .25s}
    .feature-card h3{font-size:1rem;font-weight:700;color:var(--yan-dark);margin-bottom:.5rem}
    .feature-card p{color:var(--yan-text2);font-size:.9rem;line-height:1.6}
    .chart-container{background:var(--yan-surface);border:1px solid var(--yan-border);border-radius:var(--radius);padding:1.5rem;margin:2rem 0}
    .stat-row{display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;margin:1.5rem 0}
    @media(max-width:500px){.stat-row{grid-template-columns:repeat(2,1fr)}}
    .stat-card{background:var(--yan-surface);border:1px solid var(--yan-border);border-radius:var(--radius);padding:1rem;text-align:center}
    .stat-card .num{font-size:1.5rem;font-weight:700;color:var(--yan-red)}.stat-card .label{font-size:.7rem;color:var(--yan-text3);margin-top:.25rem;font-family:'IBM Plex Mono',monospace}
    .content{margin:2.5rem 0;color:var(--yan-text2);line-height:1.6}
    .content h2{font-size:1.15rem;font-weight:700;margin-bottom:1rem;color:var(--yan-dark);letter-spacing:-.01em}
    .content h3{font-size:.95rem;font-weight:600;margin:1.25rem 0 .5rem;color:var(--yan-text2)}
    .content p{margin-bottom:.75rem}
    .content ul,.content ol{margin:.5rem 0 .75rem 1.25rem;line-height:1.8}
    .content li{margin-bottom:.4rem}
    strong{color:var(--yan-dark)}
    blockquote{border-left:3px solid var(--yan-red);padding:.5rem 1rem;margin:1.5rem 0;color:var(--yan-text3);font-style:italic;background:var(--yan-surface2);border-radius:0 var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm)}
    hr{border:none;border-top:1px solid var(--yan-border);margin:2.5rem 0}
    table{width:100%;border-collapse:collapse;margin:1rem 0;font-size:.85rem}
    th{background:var(--yan-surface2);padding:8px 12px;text-align:left;font-weight:600;color:var(--yan-text);border-bottom:2px solid var(--yan-border-s)}
    td{padding:8px 12px;border-bottom:1px solid var(--yan-border);color:var(--yan-text2);background:var(--yan-surface)}
    tr:last-child td{border-bottom:none}
    .checklist{list-style:none;padding:0}
    .checklist li{padding:.4rem 0 .4rem 1.5rem;position:relative}
    .checklist li::before{content:'\x2713';position:absolute;left:0;color:var(--yan-red);font-weight:700}
    .bench-row{display:flex;align-items:center;gap:1rem;margin:.6rem 0;font-family:'IBM Plex Mono',monospace;font-size:.72rem;color:var(--yan-text3)}
    .bench-label{width:120px;text-align:right;flex-shrink:0}
    .bench-bar{flex:1;height:20px;background:var(--yan-surface2);border-radius:100px;overflow:hidden;border:1px solid var(--yan-border)}
    .bench-fill{height:100%;border-radius:100px;display:flex;align-items:center;padding:0 10px;font-family:'IBM Plex Mono',monospace;font-size:.6rem;font-weight:600;color:#fff;white-space:nowrap}
    .bench-fill.best{background:linear-gradient(90deg,var(--yan-blue),#7C3AED)}.bench-fill.good{background:#42be65}.bench-fill.ok{background:var(--yan-text3)}
    .bench-fill.pending{background:var(--yan-text3)}
    .content{margin:2.5rem 0;color:var(--yan-text2);line-height:1.6}
    .tag,.tag-purple,.tag-red,.tag-green,.tag-teal,.tag-blue{display:inline-block;font-family:'IBM Plex Mono',monospace;font-size:.65rem;padding:2px 10px;border-radius:100px;font-weight:600;letter-spacing:.03em;text-transform:uppercase;}
    .tag{background:rgba(252,63,29,.08);color:var(--yan-red);border:1px solid rgba(252,63,29,.15)}
    .tag-purple{background:rgba(124,58,237,.08);color:#7C3AED;border:1px solid rgba(124,58,237,.15)}
    .tag-green{background:rgba(5,150,105,.08);color:#059669;border:1px solid rgba(5,150,105,.15)}
    .tag-teal{background:rgba(8,145,178,.08);color:#0891B2;border:1px solid rgba(8,145,178,.15)}
    .tag-blue{background:rgba(0,95,249,.08);color:var(--yan-blue);border:1px solid rgba(0,95,249,.15)}
    .nav{position:sticky;top:0;z-index:100;background:rgba(245,245,247,.85);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-bottom:1px solid var(--yan-border);display:flex;align-items:center;justify-content:space-between;height:56px;padding:0 20px;margin:0 0 2rem 0;max-width:100vw}
    .nav-brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:.9rem;letter-spacing:.02em;color:var(--yan-dark)}
    .nav-brand span{font-size:1.2rem}
    .nav-links{display:flex;gap:24px;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
    .nav-links::-webkit-scrollbar{display:none}
    .nav-links a{font-size:.75rem;color:var(--yan-text3);font-weight:600;letter-spacing:.06em;text-transform:uppercase;padding:4px 0;white-space:nowrap;border-bottom:2px solid transparent;transition:all .25s}
    .nav-links a:hover{color:var(--yan-text);text-decoration:none}
    .back-link{display:inline-flex;align-items:center;gap:6px;font-family:'IBM Plex Mono',monospace;font-size:.75rem;color:var(--yan-text3);letter-spacing:.05em;text-transform:uppercase;margin-bottom:1.5rem;padding:6px 0}
    .back-link:hover{color:var(--yan-dark);text-decoration:none}
    h1{font-size:clamp(1.8rem,4.5vw,2.75rem);font-weight:700;letter-spacing:-.03em;line-height:1.1;color:var(--yan-dark);margin-bottom:.5rem}
    .article-subtitle{font-size:1.15rem;color:var(--yan-text2);line-height:1.6;margin-bottom:1.5rem}
    .meta{display:flex;gap:1rem;align-items:center;margin:1.5rem 0;font-family:'IBM Plex Mono',monospace;font-size:.7rem;color:var(--yan-text3);flex-wrap:wrap}
    .section{margin:2.5rem 0;color:var(--yan-text2);font-size:.95rem;line-height:1.75}
    .section h2{font-size:1.15rem;font-weight:700;margin-bottom:1rem;color:🔹 color:#1D1D1F;letter-spacing:-.01em}
    .section h3{font-size:.95rem;font-weight:600;margin:1.25rem 0 .5rem;color:var(--yan-text2)}
    .section p{margin-bottom:.75rem}
    .section ul,.section ol{margin:.5rem 0 .75rem 1.25rem;line-height:1.8}
    .section li{margin-bottom:.4rem}
    strong{color:var(--yan-dark)}
    blockquote{border-left:3px solid var(--yan-red);padding:.5rem 1rem;margin:1.5rem 0;color:var(--yan-text3);font-style:italic;background:var(--yan-surface2);border-radius:0 var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--margin;0;margin:0 auto;padding:0 0;border:1px solid var(--yan-border-s)}
    hr{border:none;border-top:1px solid var(--yan-border);margin:2.5rem 0}
    table{width:100%;border-collapse:collapse;margin:1rem 0;font-size:.85rem}
    th{background:var(--yan-surface2);padding:8px 12px;text-align:left;font-weight:600;color:var(--yan-text);border-bottom:2px solid var(--yan-border-s)}
    td{padding:8px 12px;border-bottom:1px solid var(--yan-border);color:var(--yan-text2);background:var(--yan-surface)}
    tr:last-child td{border-bottom:none}
    pre{background:var(--yan-surface2);border:1px solid var(--yan-border);border-radius:var(--radius);padding:1.5rem;overflow-x:auto;margin:1.5rem 0;font-family:'IBM Plex Mono',monospace;font-size:.82rem;color:var(--yan-text)}
    code{background:var(--yan-surface2);padding:.15rem .4rem;border-radius:4px;font-size:.85rem;color:var(--yan-red);font-family:'IBM Plex Mono',monospace}
    .note{background:rgba(252,63,29,.06);border-left:3px solid var(--yan-red);padding:.75rem 1rem;margin:1.5rem 0;font-size:.9rem;color:var(--yan-text2);border-radius:0 var(--radius) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius-sm) var(--radius_sm) var(--radius-sm) var(--radius-sm) var(--radius_sm) var(--radius-sm) var(--radius-sm) var(--radius_sm) var(--radius_sm) var(--radius_sm) var(--radius_sm) var(--radius_sm) var(--radius_sm) var(--radius_sm) var(--radius_sm) var(--radius_sm) var(--radius_sm) var(--radius_sm) var(--radius_sm) var(--rank;};;'

# Load light theme CSS
load_css()

# Update init signature for Python 3.14 gi compatibility
try:
    # Add the orientation argument
    with open('discord-gui.py', 'r+') as f:
        f.seek(0)
        content = f.read()
        
        # For Python 3.14+, need at least one arg for super().__init__()
        # Patch: change old-style init to new-style with orientation arg
        content = re.sub(
            r'def __init__\(self\):\s*self\.all_threads\s*=\s*\s*self\.filtered_threads\s*=\s*\s*self\.scan_metadata\s*=\s*\s*self\.categories\s*=\s*\s*self\.active_filter\s*=\s*\s*self\.search_query\s*=\s*\s*self\.scan_running\s*=\s*\s*self\.channels\s*=\s*\n',
            r'def __init__\(self, title="Discord Thread Manager — The Hacky Way", orientation=Gtk.Orientation.VERTICAL\n            self\.all_threads = []\n            self\.filtered_threads = []\n            self\.scan_metadata = {}\n            self\.categories = []\n            self\.active_filter = "All",\n            self\.search_query = "",\n            self\.scan_running = False,\n            self\.channels = \[\n            def __init__\(self:\n            super().__init__\(title=title, orientation=Gtk.Orientation.VERTICAL\n                self\.set_default_size\(1100, 700\n                self\.set_position\(Gtk\.WindowPosition\.CENTER\n                self\.controller = None\n                self\.store = ThreadStore\n                self\.scan_running = False,\n                self\.categories = \[\n                self\.active_filter = "All",\n                self\.search_query = "",\n                self\.channels = \[\n                def __init__\(self):\n                    super().__init__\(title=title, orientation=Gtk.Orientation.VERTICAL\)\n                    self\.set_default_size\(1100, 700\n                    self\.set_position\(Gtk\.WindowPosition\.CENTER\n                    self\.controller = None\n                    self\.store = ThreadStore\n                    self\.scan_running = False,\n                    self\.categories = \[\n                    self\.active_filter = "All",\n                    self\.search_query = "",\n                    self\.channels = \[\n',
            content,
            count=1
        )
        if count:
            print("✓ Patched Python 3.14 gi init signature")
        else:
            print("✓ Old signature already compatible")
            print("✓ Try: python3 discord-gui.py")
    except Exception as e:
        print(f"✗ Error: {e}")
except KeyboardInterrupt:
        print("\n✓ Interrupted by user")
except Exception as e:
        print(f"✗ Unexpected error: {e}")
else:
    print("✓ No changes needed")
