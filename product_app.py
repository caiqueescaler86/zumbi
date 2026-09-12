from __future__ import annotations

import json
import queue
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

import cv2
import mss
import numpy as np
import pyautogui
from pynput import keyboard

APP_DIR = Path(__file__).resolve().parent
PROFILE_PATH = APP_DIR / "profile.json"
TEMPLATE_DIR = APP_DIR / "templates" / "user"
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

STEPS = [
    ("eventos", "Eventos", "position"),
    ("buscar", "Buscar", "image"),
    ("popup_invasao", "Popup de invasao", "image"),
    ("botao_atacar", "Atacar", "image"),
    ("botao_marchar", "Marchar", "image"),
]

DEFAULT_PROFILE = {
    "threshold": 0.72,
    "click_delay": 0.30,
    "after_search": 0.50,
    "after_attack": 0.70,
    "after_march": 0.70,
    "timeout": 5.0,
    "actions": {},
}


def load_profile():
    if not PROFILE_PATH.exists():
        return json.loads(json.dumps(DEFAULT_PROFILE))
    try:
        data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        merged = json.loads(json.dumps(DEFAULT_PROFILE))
        merged.update(data)
        merged.setdefault("actions", {})
        return merged
    except Exception:
        return json.loads(json.dumps(DEFAULT_PROFILE))


def save_profile(profile):
    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def full_screenshot():
    with mss.mss() as sct:
        mon = sct.monitors[1]
        shot = np.array(sct.grab(mon))
    return cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR), mon


def best_match(template_path: str, threshold: float):
    path = Path(template_path)
    if not path.is_absolute():
        path = APP_DIR / path
    template = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if template is None:
        return None
    screen, mon = full_screenshot()
    th, tw = template.shape[:2]
    sh, sw = screen.shape[:2]
    if tw > sw or th > sh:
        return None
    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(result)
    if score < threshold:
        return None
    return {
        "x": int(mon["left"] + loc[0] + tw // 2),
        "y": int(mon["top"] + loc[1] + th // 2),
        "score": float(score),
    }


def find_action(action, threshold):
    best = None
    for path in action.get("templates", []):
        found = best_match(path, threshold)
        if found and (best is None or found["score"] > best["score"]):
            best = found
    return best


class CaptureOverlay(tk.Toplevel):
    def __init__(self, parent, title, callback):
        super().__init__(parent)
        self.callback = callback
        self.attributes("-fullscreen", True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.22)
        self.configure(bg="black", cursor="crosshair")
        self.label = tk.Label(self, text=f"{title}\nClique no centro do elemento | ESC cancela", bg="black", fg="white", font=("Segoe UI", 22, "bold"))
        self.label.pack(pady=35)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Button-1>", self._click)

    def _click(self, event):
        x, y = self.winfo_pointerxy()
        self.destroy()
        self.after(120, lambda: self.callback(x, y))


class CropOverlay(tk.Toplevel):
    def __init__(self, parent, name, center_x, center_y, callback):
        super().__init__(parent)
        self.name = name
        self.callback = callback
        self.screen, self.mon = full_screenshot()
        self.attributes("-fullscreen", True)
        self.attributes("-topmost", True)
        self.configure(cursor="crosshair")
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        rgb = cv2.cvtColor(self.screen, cv2.COLOR_BGR2RGB)
        try:
            from PIL import Image, ImageTk
            self.photo = ImageTk.PhotoImage(Image.fromarray(rgb))
            self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        except Exception:
            self.destroy()
            messagebox.showerror("Zumbi", "Pillow e necessario para o recorte visual. Rode: pip install Pillow")
            return
        self.start = None
        self.rect = None
        self.canvas.create_text(20, 25, anchor="nw", text="Arraste um retangulo ao redor do elemento. ENTER salva | ESC cancela", fill="white", font=("Segoe UI", 18, "bold"))
        local_x = center_x - self.mon["left"]
        local_y = center_y - self.mon["top"]
        self.canvas.create_line(local_x - 18, local_y, local_x + 18, local_y, fill="red", width=2)
        self.canvas.create_line(local_x, local_y - 18, local_x, local_y + 18, fill="red", width=2)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", self._save)
        self.canvas.bind("<ButtonPress-1>", self._start)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._end)

    def _start(self, event):
        self.start = (event.x, event.y)
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="red", width=3)

    def _drag(self, event):
        if self.start and self.rect:
            self.canvas.coords(self.rect, self.start[0], self.start[1], event.x, event.y)

    def _end(self, event):
        self.end = (event.x, event.y)

    def _save(self, _event=None):
        if not self.start or not hasattr(self, "end"):
            return
        x1, x2 = sorted((self.start[0], self.end[0]))
        y1, y2 = sorted((self.start[1], self.end[1]))
        if x2 - x1 < 8 or y2 - y1 < 8:
            return
        crop = self.screen[y1:y2, x1:x2]
        existing = list(TEMPLATE_DIR.glob(f"{self.name}_*.png"))
        path = TEMPLATE_DIR / f"{self.name}_{len(existing)+1:03d}.png"
        cv2.imwrite(str(path), crop)
        rel = str(path.relative_to(APP_DIR)).replace("\\", "/")
        self.destroy()
        self.callback(rel)


class ZumbiApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Zumbi")
        self.geometry("780x620")
        self.minsize(720, 560)
        self.profile = load_profile()
        self.running = False
        self.paused = False
        self.worker = None
        self.logs = queue.Queue()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._build()
        self.after(100, self._flush_logs)
        self.listener = keyboard.Listener(on_press=self._hotkey)
        self.listener.start()

    def _build(self):
        root = ttk.Frame(self, padding=18)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="ZUMBI", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        self.status = ttk.Label(root, text="Parado", font=("Segoe UI", 11))
        self.status.pack(anchor="w", pady=(0, 14))
        bar = ttk.Frame(root)
        bar.pack(fill="x", pady=(0, 12))
        ttk.Button(bar, text="Iniciar", command=self.start_bot).pack(side="left", padx=(0, 8))
        ttk.Button(bar, text="Pausar / Retomar", command=self.toggle_pause).pack(side="left", padx=(0, 8))
        ttk.Button(bar, text="Parar", command=self.stop_bot).pack(side="left", padx=(0, 8))
        ttk.Button(bar, text="Configurar", command=self.configure_wizard).pack(side="right")
        ttk.Separator(root).pack(fill="x", pady=8)
        ttk.Label(root, text="Configuracao", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(4, 8))
        self.actions_frame = ttk.Frame(root)
        self.actions_frame.pack(fill="x")
        self._refresh_actions()
        ttk.Label(root, text="Log", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(18, 6))
        self.logbox = tk.Text(root, height=14, state="disabled", font=("Consolas", 9))
        self.logbox.pack(fill="both", expand=True)
        ttk.Label(root, text="F8 pausa/retoma | F12 para", font=("Segoe UI", 9)).pack(anchor="e", pady=(6, 0))

    def _refresh_actions(self):
        for child in self.actions_frame.winfo_children():
            child.destroy()
        for name, label, mode in STEPS:
            action = self.profile["actions"].get(name, {})
            pos = action.get("position")
            templates = len(action.get("templates", []))
            status = "nao configurado"
            if pos:
                status = f"X {pos['x']} / Y {pos['y']}"
            if templates:
                status += f" | {templates} imagem(ns)"
            row = ttk.Frame(self.actions_frame)
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, width=20).pack(side="left")
            ttk.Label(row, text=status).pack(side="left")
            ttk.Button(row, text="Capturar", command=lambda n=name, l=label, m=mode: self.capture_step(n, l, m)).pack(side="right")

    def log(self, text):
        self.logs.put(text)

    def _flush_logs(self):
        while not self.logs.empty():
            text = self.logs.get_nowait()
            self.logbox.configure(state="normal")
            self.logbox.insert("end", text + "\n")
            self.logbox.see("end")
            self.logbox.configure(state="disabled")
        self.after(100, self._flush_logs)

    def configure_wizard(self):
        if self.running:
            messagebox.showwarning("Zumbi", "Pare o bot antes de configurar.")
            return
        self._wizard_index = 0
        self._wizard_next()

    def _wizard_next(self):
        if self._wizard_index >= len(STEPS):
            save_profile(self.profile)
            self._refresh_actions()
            messagebox.showinfo("Zumbi", "Configuracao concluida e salva.")
            return
        name, label, mode = STEPS[self._wizard_index]
        self.capture_step(name, label, mode, wizard=True)

    def capture_step(self, name, label, mode, wizard=False):
        self.withdraw()
        def got_position(x, y):
            self.deiconify()
            self.lift()
            action = self.profile["actions"].setdefault(name, {"mode": mode, "templates": []})
            action["mode"] = mode
            action["position"] = {"x": x, "y": y}
            save_profile(self.profile)
            if mode == "position":
                self._capture_done(wizard)
                return
            if messagebox.askyesno("Zumbi", f"Posicao de {label} salva.\nDeseja capturar/ajustar a imagem agora?"):
                self.withdraw()
                def got_template(path):
                    self.deiconify()
                    self.lift()
                    action["templates"] = action.get("templates", []) + [path]
                    save_profile(self.profile)
                    found = best_match(path, float(self.profile.get("threshold", 0.72)))
                    if found:
                        messagebox.showinfo("Teste", f"Imagem salva. Match atual: {found['score']:.1%}")
                    else:
                        messagebox.showwarning("Teste", "Imagem salva, mas nao atingiu o threshold no teste atual.")
                    self._capture_done(wizard)
                CropOverlay(self, name, x, y, got_template)
            else:
                self._capture_done(wizard)
        CaptureOverlay(self, f"Configure: {label}", got_position)

    def _capture_done(self, wizard):
        self._refresh_actions()
        if wizard:
            self._wizard_index += 1
            self.after(250, self._wizard_next)

    def _hotkey(self, key):
        if key == keyboard.Key.f8:
            self.after(0, self.toggle_pause)
        elif key == keyboard.Key.f12:
            self.after(0, self.stop_bot)

    def toggle_pause(self):
        if not self.running:
            return
        self.paused = not self.paused
        self.status.configure(text="Pausado" if self.paused else "Rodando")
        self.log("PAUSADO" if self.paused else "RETOMADO")

    def stop_bot(self):
        self.running = False
        self.paused = False
        self.status.configure(text="Parando...")

    def start_bot(self):
        required = ["eventos", "buscar", "popup_invasao", "botao_atacar", "botao_marchar"]
        missing = [x for x in required if x not in self.profile.get("actions", {})]
        if missing:
            messagebox.showwarning("Zumbi", "Configure primeiro: " + ", ".join(missing))
            return
        if self.running:
            return
        self.running = True
        self.paused = False
        self.status.configure(text="Rodando")
        self.worker = threading.Thread(target=self._bot_loop, daemon=True)
        self.worker.start()

    def _sleep(self, seconds):
        end = time.time() + seconds
        while self.running and time.time() < end:
            while self.paused and self.running:
                time.sleep(0.1)
            time.sleep(0.05)

    def _click(self, x, y, label):
        self.log(f"CLICK {label}: {x}, {y}")
        pyautogui.click(x, y)
        self._sleep(float(self.profile.get("click_delay", 0.30)))

    def _wait_image(self, name):
        action = self.profile["actions"][name]
        deadline = time.time() + float(self.profile.get("timeout", 5.0))
        while self.running and time.time() < deadline:
            if self.paused:
                time.sleep(0.1)
                continue
            found = find_action(action, float(self.profile.get("threshold", 0.72)))
            if found:
                self.log(f"{name}: match {found['score']:.3f}")
                return found
            time.sleep(0.25)
        return None

    def _bot_loop(self):
        attacks = 0
        try:
            while self.running:
                while self.paused and self.running:
                    time.sleep(0.1)
                eventos = self.profile["actions"]["eventos"]["position"]
                self._click(eventos["x"], eventos["y"], "Eventos")
                buscar = self._wait_image("buscar")
                if not buscar:
                    self.log("Buscar nao encontrado. Reiniciando ciclo.")
                    pyautogui.press("esc")
                    continue
                self._click(buscar["x"], buscar["y"], "Buscar")
                self._sleep(float(self.profile.get("after_search", 0.50)))
                popup = self._wait_image("popup_invasao")
                if not popup:
                    self.log("Popup nao encontrado. Reiniciando ciclo.")
                    pyautogui.press("esc")
                    continue
                atacar = self._wait_image("botao_atacar")
                if not atacar:
                    self.log("Atacar nao encontrado. Reiniciando ciclo.")
                    pyautogui.press("esc")
                    continue
                self._click(atacar["x"], atacar["y"], "Atacar")
                self._sleep(float(self.profile.get("after_attack", 0.70)))
                marchar = self._wait_image("botao_marchar")
                if not marchar:
                    self.log("Marchar nao encontrado. Possivel falta de vigor ou tela inesperada. Parando com seguranca.")
                    self.running = False
                    break
                self._click(marchar["x"], marchar["y"], "Marchar")
                attacks += 1
                self.log(f"Ciclo concluido. Marchas: {attacks}")
                self._sleep(float(self.profile.get("after_march", 0.70)))
        except pyautogui.FailSafeException:
            self.log("FAILSAFE acionado: mouse no canto da tela. Bot parado.")
        except Exception as exc:
            self.log(f"ERRO: {exc}")
        finally:
            self.running = False
            self.paused = False
            self.after(0, lambda: self.status.configure(text="Parado"))
            self.log(f"Finalizado. Marchas realizadas: {attacks}")

    def close(self):
        self.running = False
        try:
            self.listener.stop()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    pyautogui.FAILSAFE = True
    app = ZumbiApp()
    app.mainloop()
