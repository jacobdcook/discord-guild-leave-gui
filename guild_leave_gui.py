import asyncio
import io
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import aiohttp
from PIL import Image, ImageTk

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.txt")
API_BASE = "https://discord.com/api/v10"
CDN_BASE = "https://cdn.discordapp.com"
DEFAULT_DELAY_SEC = 3
ICON_SIZE = 32


async def fetch_guilds(session, token):
    async with session.get(
        f"{API_BASE}/users/@me/guilds",
        headers={"Authorization": token.strip()},
        params={"with_counts": "true"},
    ) as r:
        if r.status != 200:
            text = await r.text()
            raise RuntimeError(f"API {r.status}: {text[:200]}")
        data = await r.json()
    guilds = []
    for g in data:
        entry = {
            "id": g["id"],
            "name": g.get("name", "?"),
            "member_count": g.get("approximate_member_count", 0),
            "icon": g.get("icon"),
        }
        if entry["icon"]:
            ext = "gif" if entry["icon"].startswith("a_") else "png"
            url = f"{CDN_BASE}/icons/{entry['id']}/{entry['icon']}.{ext}?size={ICON_SIZE * 2}"
            try:
                async with session.get(url) as ir:
                    if ir.status == 200:
                        entry["icon_bytes"] = await ir.read()
            except Exception:
                pass
        guilds.append(entry)
    return guilds


async def leave_guild(session, token, guild_id):
    async with session.delete(
        f"{API_BASE}/users/@me/guilds/{guild_id}",
        headers={"Authorization": token.strip()},
    ) as r:
        if r.status not in (200, 204):
            text = await r.text()
            raise RuntimeError(f"Leave {guild_id}: {r.status} {text[:150]}")


def worker_fetch(token, on_done):
    async def run():
        async with aiohttp.ClientSession() as session:
            try:
                guilds = await fetch_guilds(session, token)
                on_done(guilds, None)
            except Exception as e:
                on_done(None, str(e))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run())
    finally:
        loop.close()


def worker_leave(token, guild_ids, delay_sec, on_progress, on_done):
    async def run():
        async with aiohttp.ClientSession() as session:
            try:
                for i, gid in enumerate(guild_ids):
                    await leave_guild(session, token, gid)
                    on_progress(i + 1, len(guild_ids), gid)
                    if i < len(guild_ids) - 1:
                        await asyncio.sleep(delay_sec)
                on_done(None)
            except Exception as e:
                on_done(str(e))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run())
    finally:
        loop.close()


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Leave Discord servers (your account)")
        self.root.geometry("560x460")
        self.root.minsize(400, 320)

        f = ttk.Frame(self.root, padding=10)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text="User token (your account — see token.txt for how to get it):").pack(anchor=tk.W)
        self.token_var = tk.StringVar()
        if os.path.isfile(TOKEN_FILE):
            try:
                with open(TOKEN_FILE) as fp:
                    for line in fp:
                        t = line.strip()
                        if t and not t.startswith("#"):
                            self.token_var.set(t)
                            break
            except Exception:
                pass
        self.token_entry = ttk.Entry(f, textvariable=self.token_var, show="*", width=50)
        self.token_entry.pack(fill=tk.X, pady=(0, 8))

        btn_f = ttk.Frame(f)
        btn_f.pack(fill=tk.X, pady=(0, 8))
        self.load_btn = ttk.Button(btn_f, text="Load my servers", command=self.load_guilds)
        self.load_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.leave_btn = ttk.Button(btn_f, text="Leave selected", command=self.leave_selected, state=tk.DISABLED)
        self.leave_btn.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_f, text="Save token to file", command=self.save_token).pack(side=tk.LEFT)

        delay_f = ttk.Frame(f)
        delay_f.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(delay_f, text="Delay between each leave (seconds):").pack(side=tk.LEFT, padx=(0, 8))
        self.delay_var = tk.StringVar(value=str(DEFAULT_DELAY_SEC))
        self.delay_entry = ttk.Entry(delay_f, textvariable=self.delay_var, width=4)
        self.delay_entry.pack(side=tk.LEFT)

        ttk.Label(f, text="Servers (check to leave):").pack(anchor=tk.W, pady=(8, 0))
        sel_f = ttk.Frame(f)
        sel_f.pack(fill=tk.X, pady=(2, 4))
        ttk.Button(sel_f, text="Select all", command=self._select_all).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(sel_f, text="Deselect all", command=self._deselect_all).pack(side=tk.LEFT)
        list_f = ttk.Frame(f)
        list_f.pack(fill=tk.BOTH, expand=True, pady=4)
        self.canvas = tk.Canvas(list_f, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(list_f, orient=tk.VERTICAL, command=self.canvas.yview)
        self.listbox_frame = tk.Frame(self.canvas)
        self.listbox_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas_window = self.canvas.create_window((0, 0), window=self.listbox_frame, anchor=tk.NW)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        def _on_canvas_configure(ev):
            self.canvas.itemconfig(self.canvas_window, width=ev.width)
        self.canvas.bind("<Configure>", _on_canvas_configure)

        def _scroll(ev):
            if ev.num == 5 or (ev.delta and ev.delta < 0):
                self.canvas.yview_scroll(1, tk.UNITS)
            else:
                self.canvas.yview_scroll(-1, tk.UNITS)
        self.canvas.bind("<MouseWheel>", _scroll)
        self.canvas.bind("<Button-4>", _scroll)
        self.canvas.bind("<Button-5>", _scroll)

        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vars_by_id = {}
        self.photo_images = []
        self.log = scrolledtext.ScrolledText(f, height=6, state=tk.DISABLED)
        self.log.pack(fill=tk.X, pady=(8, 0))

        self.guilds = []
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def save_token(self):
        t = self.token_var.get().strip()
        if not t:
            messagebox.showwarning("Empty", "Enter a token first.")
            return
        try:
            with open(TOKEN_FILE, "w") as f:
                f.write(t + "\n")
            self.log_msg("Token saved to token.txt")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def log_msg(self, msg):
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)

    def _select_all(self):
        for var in self.vars_by_id.values():
            var.set(True)

    def _deselect_all(self):
        for var in self.vars_by_id.values():
            var.set(False)

    def _on_guilds_loaded(self, guilds, err=None):
        self.load_btn.config(state=tk.NORMAL)
        if err:
            messagebox.showerror("Error", err)
            self.log_msg(f"Error: {err}")
            return
        if guilds is None:
            return
        self.guilds = guilds
        self.vars_by_id.clear()
        self.photo_images.clear()
        for w in self.listbox_frame.winfo_children():
            w.destroy()
        for g in guilds:
            var = tk.BooleanVar(value=False)
            self.vars_by_id[g["id"]] = var
            row = ttk.Frame(self.listbox_frame)
            row.pack(anchor=tk.W, fill=tk.X, pady=1)
            cb = ttk.Checkbutton(row, variable=var)
            cb.pack(side=tk.LEFT, padx=(0, 6))
            if g.get("icon_bytes"):
                try:
                    img = Image.open(io.BytesIO(g["icon_bytes"])).resize((ICON_SIZE, ICON_SIZE))
                    photo = ImageTk.PhotoImage(img)
                    self.photo_images.append(photo)
                    ttk.Label(row, image=photo).pack(side=tk.LEFT, padx=(0, 8))
                except Exception:
                    pass
            ttk.Label(row, text=f"{g['name']} ({g['member_count']} members)").pack(side=tk.LEFT)
        self.listbox_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.leave_btn.config(state=tk.NORMAL if guilds else tk.DISABLED)
        self.log_msg(f"Loaded {len(guilds)} server(s). Order is as returned by Discord API (sidebar order is not exposed).")

    def load_guilds(self):
        token = self.token_var.get().strip()
        if not token:
            messagebox.showwarning("Missing token", "Enter your user token.")
            return
        self.load_btn.config(state=tk.DISABLED)
        self.log_msg("Loading your servers...")

        def on_done(guilds, err):
            self.root.after(0, lambda: self._on_guilds_loaded(guilds, err))

        threading.Thread(target=worker_fetch, args=(token, on_done), daemon=True).start()

    def leave_selected(self):
        to_leave = [gid for gid, var in self.vars_by_id.items() if var.get()]
        if not to_leave:
            messagebox.showinfo("Nothing selected", "Check the servers you want to leave.")
            return
        try:
            delay = max(1, min(60, int(self.delay_var.get().strip())))
        except ValueError:
            delay = DEFAULT_DELAY_SEC
        if not messagebox.askyesno("Confirm", f"Leave {len(to_leave)} server(s)? ({delay}s between each)"):
            return
        token = self.token_var.get().strip()
        self.leave_btn.config(state=tk.DISABLED)
        self.load_btn.config(state=tk.DISABLED)
        self.log_msg(f"Leaving {len(to_leave)} server(s), {delay}s between each...")

        def on_progress(current, total, gid):
            self.root.after(0, lambda: self.log_msg(f"Left {current}/{total}..."))

        def on_done(err):
            self.root.after(0, lambda: self._leave_done(err))

        threading.Thread(
            target=worker_leave,
            args=(token, to_leave, delay, on_progress, on_done),
            daemon=True,
        ).start()

    def _leave_done(self, err=None):
        self.leave_btn.config(state=tk.NORMAL)
        self.load_btn.config(state=tk.NORMAL)
        if err:
            messagebox.showerror("Error", err)
            self.log_msg(f"Error: {err}")
        else:
            left_ids = {gid for gid, var in self.vars_by_id.items() if var.get()}
            self.guilds = [g for g in self.guilds if g["id"] not in left_ids]
            self.vars_by_id.clear()
            self.photo_images.clear()
            for w in self.listbox_frame.winfo_children():
                w.destroy()
            for g in self.guilds:
                var = tk.BooleanVar(value=False)
                self.vars_by_id[g["id"]] = var
                row = ttk.Frame(self.listbox_frame)
                row.pack(anchor=tk.W, fill=tk.X, pady=1)
                cb = ttk.Checkbutton(row, variable=var)
                cb.pack(side=tk.LEFT, padx=(0, 6))
                if g.get("icon_bytes"):
                    try:
                        img = Image.open(io.BytesIO(g["icon_bytes"])).resize((ICON_SIZE, ICON_SIZE))
                        photo = ImageTk.PhotoImage(img)
                        self.photo_images.append(photo)
                        ttk.Label(row, image=photo).pack(side=tk.LEFT, padx=(0, 8))
                    except Exception:
                        pass
                ttk.Label(row, text=f"{g['name']} ({g['member_count']} members)").pack(side=tk.LEFT)
            self.listbox_frame.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            self.log_msg("Done.")

    def on_close(self):
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
