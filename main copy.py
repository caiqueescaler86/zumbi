import time
import json
from pathlib import Path

import cv2
import mss
import numpy as np
import pyautogui
from pynput import keyboard


CONFIG_PATH = Path("config.json")
TEMPLATES_DIR = Path("templates")

running = True
paused = False


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def screenshot():
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        img = np.array(sct.grab(monitor))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def find_template(name, threshold=None):
    config = load_config()
    threshold = threshold or config.get("threshold", 0.82)

    path = TEMPLATES_DIR / f"{name}.png"
    if not path.exists():
        print(f"Template nao existe: {path}")
        return None

    screen = screenshot()
    template = cv2.imread(str(path), cv2.IMREAD_COLOR)

    if template is None:
        print(f"Template invalido: {path}")
        return None

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(result)

    if score < threshold:
        return None

    h, w = template.shape[:2]
    x = loc[0] + w // 2
    y = loc[1] + h // 2

    return {
        "name": name,
        "x": x,
        "y": y,
        "score": float(score),
    }


def click_template(name, threshold=None):
    config = load_config()
    found = find_template(name, threshold)

    if not found:
        return False

    print(
        f"CLICK {name}: x={found['x']} y={found['y']} "
        f"score={found['score']:.3f}"
    )

    if not config.get("dry_run", True):
        pyautogui.click(found["x"], found["y"])

    return True


def on_press(key):
    global running, paused

    try:
        if key == keyboard.Key.f8:
            paused = not paused
            print("PAUSADO" if paused else "RODANDO")

        if key == keyboard.Key.f12:
            running = False
            print("PARANDO...")

    except Exception:
        pass


def vigor_budget_ok(config):
    used = config.get("vigor_usado_hoje_bot", 0)
    limit = config.get("vigor_max_diario_bot", 999999)
    cost = config.get("custo_por_zumbi", 10)

    return used + cost <= limit


def add_vigor_spent():
    config = load_config()
    cost = config.get("custo_por_zumbi", 10)
    config["vigor_usado_hoje_bot"] = config.get("vigor_usado_hoje_bot", 0) + cost

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"Vigor usado hoje pelo bot: {config['vigor_usado_hoje_bot']}")


def main():
    global running

    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    config = load_config()
    print(
        "Bot iniciado. F8 pausa, F12 para. "
        f"dry_run={config.get('dry_run', True)}"
    )

    while running:
        config = load_config()

        if paused:
            time.sleep(1)
            continue

        if not vigor_budget_ok(config):
            print("Limite diario de vigor atingido. Parando.")
            break

        # 1. Se estou na tela do evento, Buscar e prioridade absoluta.
        if click_template("buscar", config.get("threshold_buscar", 0.80)):
            print("Cliquei em Buscar")
            time.sleep(config.get("delay_apos_buscar", 2.0))
            continue

        # 2. Se abriu popup correto, atacar.
        popup = find_template("popup_invasao_zumbis", config.get("threshold_popup", 0.85))
        if popup:
            print(f"Popup Invasao validado score={popup['score']:.3f}")

            if click_template("botao_ataque", config.get("threshold_ataque", 0.80)):
                print("Cliquei em Ataque")
                time.sleep(config.get("delay_apos_ataque", 1.2))
                continue

        # 3. Se estou na tela de marcha, marchar.
        if click_template("botao_marchar", config.get("threshold_botao_marchar", 0.80)):
            print("Cliquei em Marchar")
            if not config.get("dry_run", True):
                add_vigor_spent()
            time.sleep(config.get("delay_apos_marchar", 2.0))
            continue

        # 4. Se faltou vigor, tratar simples.
        if find_template("obter_vigor", config.get("threshold_obter_vigor", 0.80)):
            print("Apareceu Obter Vigor.")

            if not config.get("permitir_recarga", False):
                print("Recarga desativada no config. Parando.")
                break

            click_template("obter_vigor", config.get("threshold_obter_vigor", 0.80))
            time.sleep(1)

            if config.get("usar_item_10_vigor", True):
                if click_template("usar_item_10_vigor", config.get("threshold_usar_item_10_vigor", 0.80)):
                    print("Usei item 10 vigor")
                    time.sleep(1)
                    continue

            if config.get("usar_item_50_vigor", False):
                if click_template("item_50_vigor", config.get("threshold_item_vigor", 0.80)):
                    print("Usei item 50 vigor")
                    time.sleep(1)
                    continue

            print("Nao consegui recarregar vigor. Parando.")
            break

        # 5. So abre Eventos se nao achou nada mais importante.
        if click_template("eventos", config.get("threshold_eventos", 0.80)):
            print("Abri Eventos")
            time.sleep(config.get("delay_apos_eventos", 1.0))
            continue

        print("Nada encontrado. Aguardando...")
        time.sleep(config.get("delay_loop", 1.5))

    print("Bot finalizado.")


if __name__ == "__main__":
    main()