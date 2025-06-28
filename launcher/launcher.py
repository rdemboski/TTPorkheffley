import tkinter as tk
from tkinter import ttk, messagebox
import requests, hashlib, os, subprocess

# === CONFIGURATION ===
MANIFEST_URL = 'https://yourblobstorage.blob.core.windows.net/game/manifest.json'
NEWS_URL = 'https://yourblobstorage.blob.core.windows.net/game/news.txt'
INSTALL_DIR = "C:\\Users\\ryand\\Documents\\GitHub\\TTPorkheffley\\build\\win_amd64"
GAME_EXECUTABLE = "TTPHEngine.exe"

# === LAUNCHER APP ===
class GameLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Toontown Porkheffley Launcher")
        self.geometry("500x400")
        self.resizable(False, False)

        self.create_widgets()

    def create_widgets(self):
        # Tabs
        self.notebook = ttk.Notebook(self)
        self.frame_main = tk.Frame(self.notebook)
        self.frame_news = tk.Frame(self.notebook)
        self.notebook.add(self.frame_main, text="Launcher")
        self.notebook.add(self.frame_news, text="News")
        self.notebook.pack(fill='both', expand=True)

        # --- Launcher Tab ---
        self.status_label = tk.Label(self.frame_main, text="Ready", anchor="w")
        self.status_label.pack(pady=(15, 5))

        self.progress_bar = ttk.Progressbar(self.frame_main, length=400, mode='determinate')
        self.progress_bar.pack(pady=(0, 10))

        self.play_button = tk.Button(self.frame_main, text="Update + Launch", command=self.launch_game) # update_game
        self.play_button.pack(pady=10)

        # --- News Tab ---
        self.news_text = tk.Text(self.frame_news, wrap="word", state='normal', height=20)
        self.news_text.pack(fill='both', expand=True, padx=10, pady=10)
        self.load_news()

    def load_news(self):
        try:
            response = requests.get(NEWS_URL, timeout=5)
            self.news_text.insert('1.0', response.text)
        except Exception as e:
            self.news_text.insert('1.0', f"Failed to load news.\n\n{str(e)}")

    def update_game(self):
        self.play_button.config(state='disabled')
        self.status_label.config(text="Checking for updates...")
        self.progress_bar['value'] = 0
        self.update_idletasks()

        try:
            manifest = requests.get(MANIFEST_URL, timeout=10).json()
            files = manifest.get("files", {})
        except Exception as e:
            messagebox.showerror("Error", f"Could not fetch manifest:\n{str(e)}")
            self.play_button.config(state='normal')
            return

        for filename, meta in files.items():
            url = meta["url"]
            expected_hash = meta["hash"]

            local_path = os.path.join(INSTALL_DIR, filename)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            needs_download = True
            if os.path.exists(local_path):
                if self.compute_hash(local_path) == expected_hash:
                    needs_download = False

            if needs_download:
                self.status_label.config(text=f"Downloading: {filename}")
                self.download_file(url, local_path)
                self.update_idletasks()

        self.status_label.config(text="Update complete. Launching game...")
        self.progress_bar['value'] = 0
        self.play_button.config(state='normal')
        self.launch_game()

    def compute_hash(self, path):
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            while chunk := f.read(4096):
                sha256.update(chunk)
        return sha256.hexdigest()

    def download_file(self, url, dest):
        try:
            r = requests.get(url, stream=True)
            total = int(r.headers.get('content-length', 0))
            self.progress_bar['maximum'] = total
            self.progress_bar['value'] = 0

            with open(dest, 'wb') as f:
                for chunk in r.iter_content(1024):
                    if chunk:
                        f.write(chunk)
                        self.progress_bar['value'] += len(chunk)
                        self.update_idletasks()
        except Exception as e:
            messagebox.showerror("Download Error", f"Failed to download {os.path.basename(dest)}:\n{str(e)}")

    def launch_game(self):
        try:
            exe_path = os.path.join(INSTALL_DIR, GAME_EXECUTABLE)
            subprocess.Popen([exe_path], cwd=INSTALL_DIR)
            self.quit()
        except Exception as e:
            messagebox.showerror("Launch Failed", f"Could not start game:\n{str(e)}")

if __name__ == "__main__":
    app = GameLauncher()
    app.mainloop()