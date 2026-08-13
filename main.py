import json
import time
from pathlib import Path

import cv2
import mss
import numpy as np
import pyautogui
from pynput import keyboard


CONFIG_PATH = Path("config.json")

EVENTOS_X = 1334
EVENTOS_Y = 89

running = True
paused = False


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as file:
        json.dump(
            config,
            file,
            indent=2,
            ensure_ascii=False,
        )


def screenshot():
    config = load_config()

    with mss.mss() as sct:
        region = config.get("screen_region")

        if region:
            monitor = {
                "top": region["top"],
                "left": region["left"],
                "width": region["width"],
                "height": region["height"],
            }
        else:
            monitor = sct.monitors[1]

        image = np.array(sct.grab(monitor))

    return cv2.cvtColor(
        image,
        cv2.COLOR_BGRA2BGR,
    )


def get_template_path(name):
    config = load_config()
    templates = config.get("templates", {})

    template_path = templates.get(name)

    if not template_path:
        print(
            f"{name}: nao configurado no config.json"
        )
        return None

    return Path(template_path)


def threshold_for(name):
    config = load_config()

    if name == "popup_invasao":
        return config.get(
            "threshold_popup",
            0.80,
        )

    if name in {
        "buscar",
        "botao_atacar",
        "botao_marchar",
    }:
        return config.get(
            "threshold_button",
            0.80,
        )

    return config.get(
        "threshold_template",
        0.80,
    )


def find_template(
    name,
    threshold=None,
    debug=True,
):
    if threshold is None:
        threshold = threshold_for(name)

    path = get_template_path(name)

    if path is None:
        return None

    if not path.exists():
        print(
            f"{name}: arquivo nao existe -> {path}"
        )
        return None

    config = load_config()
    screen = screenshot()

    template = cv2.imread(
        str(path),
        cv2.IMREAD_COLOR,
    )

    if template is None:
        print(
            f"{name}: template invalido -> {path}"
        )
        return None

    screen_height, screen_width = screen.shape[:2]
    template_height, template_width = template.shape[:2]

    if (
        template_width > screen_width
        or template_height > screen_height
    ):
        print(
            f"{name}: template maior que a captura. "
            f"Template={template_width}x{template_height} "
            f"Captura={screen_width}x{screen_height}"
        )
        return None

    result = cv2.matchTemplate(
        screen,
        template,
        cv2.TM_CCOEFF_NORMED,
    )

    _, score, _, location = cv2.minMaxLoc(result)

    if debug:
        status = (
            "OK"
            if score >= threshold
            else "baixo"
        )

        print(
            f"{name}: score={score:.3f} "
            f"threshold={threshold:.3f} "
            f"{status}"
        )

    if score < threshold:
        return None

    offset_x = 0
    offset_y = 0

    region = config.get("screen_region")

    if region:
        offset_x = region.get("left", 0)
        offset_y = region.get("top", 0)

    click_x = (
        offset_x
        + location[0]
        + template_width // 2
    )

    click_y = (
        offset_y
        + location[1]
        + template_height // 2
    )

    return {
        "name": name,
        "x": click_x,
        "y": click_y,
        "score": float(score),
    }


def click_found(found, config):
    print(
        f"CLICK {found['name']}: "
        f"x={found['x']} "
        f"y={found['y']} "
        f"score={found['score']:.3f}"
    )

    if not config.get("dry_run", True):
        pyautogui.click(
            found["x"],
            found["y"],
        )

    time.sleep(
        config.get(
            "tempo_apos_clique_segundos",
            0.5,
        )
    )


def click_eventos_fixed(config):
    print(
        "CLICK Eventos: "
        f"x={EVENTOS_X} y={EVENTOS_Y}"
    )

    if not config.get("dry_run", True):
        pyautogui.click(
            EVENTOS_X,
            EVENTOS_Y,
        )

    time.sleep(
        config.get(
            "tempo_apos_abrir_eventos_segundos",
            2.0,
        )
    )


def press_esc(config, reason):
    print(
        f"{reason} Pressionando ESC "
        "e reiniciando desde Eventos."
    )

    if not config.get("dry_run", True):
        pyautogui.press("esc")

    time.sleep(
        config.get(
            "tempo_apos_esc_segundos",
            1.2,
        )
    )


def wait_for_template(
    name,
    config,
    timeout_seconds,
):
    start_time = time.time()

    while running:
        if paused:
            time.sleep(0.5)
            continue

        found = find_template(name)

        if found:
            return found

        if time.time() - start_time >= timeout_seconds:
            return None

        time.sleep(
            config.get(
                "intervalo_busca_template_segundos",
                0.4,
            )
        )

    return None


def vigor_budget_ok(config):
    used = config.get(
        "vigor_usado_hoje_bot",
        0,
    )

    limit = config.get(
        "vigor_max_diario_bot",
        999999,
    )

    cost = config.get(
        "custo_por_zumbi",
        10,
    )

    return used + cost <= limit


def add_vigor_spent():
    config = load_config()

    cost = config.get(
        "custo_por_zumbi",
        10,
    )

    config["vigor_usado_hoje_bot"] = (
        config.get(
            "vigor_usado_hoje_bot",
            0,
        )
        + cost
    )

    save_config(config)

    print(
        "Vigor usado hoje pelo bot: "
        f"{config['vigor_usado_hoje_bot']}"
    )


def timer_pause_if_needed(
    cycle_start,
    config,
):
    active_seconds = (
        config.get(
            "timer_ativo_minutos",
            0,
        )
        * 60
    )

    pause_seconds = (
        config.get(
            "timer_pausa_minutos",
            0,
        )
        * 60
    )

    if (
        active_seconds <= 0
        or pause_seconds <= 0
    ):
        return cycle_start

    if time.time() - cycle_start < active_seconds:
        return cycle_start

    print(
        "Timer: pausando por "
        f"{config.get('timer_pausa_minutos')} minutos."
    )

    pause_end = time.time() + pause_seconds

    while running and time.time() < pause_end:
        time.sleep(1)

    if running:
        print("Timer: retomando o bot.")

    return time.time()


def on_press(key):
    global running
    global paused

    if key == keyboard.Key.f8:
        paused = not paused

        print(
            "PAUSADO"
            if paused
            else "RODANDO"
        )

    elif key == keyboard.Key.f12:
        running = False
        print("PARANDO...")


def main():
    global running

    listener = keyboard.Listener(
        on_press=on_press,
    )

    listener.start()

    config = load_config()
    cycle_start = time.time()

    print(
        "Bot iniciado. "
        "F8 pausa, F12 para. "
        f"dry_run={config.get('dry_run', True)}"
    )

    while running:
        config = load_config()

        cycle_start = timer_pause_if_needed(
            cycle_start,
            config,
        )

        if not running:
            break

        if paused:
            time.sleep(0.5)
            continue

        if not vigor_budget_ok(config):
            print(
                "Limite diario de vigor atingido. "
                "Bot finalizado."
            )
            break

        print("\n==============================")
        print("INICIANDO NOVO CICLO")
        print("==============================")

        # 1. EVENTOS
        print("ETAPA 1/4: EVENTOS")

        click_eventos_fixed(config)

        if not running:
            break

        # 2. BUSCAR
        print("ETAPA 2/4: BUSCAR")

        buscar = wait_for_template(
            "buscar",
            config,
            config.get(
                "timeout_buscar_segundos",
                4.0,
            ),
        )

        if not buscar:
            press_esc(
                config,
                "Buscar nao encontrado.",
            )
            continue

        click_found(buscar, config)
        print("Buscar clicado.")

        time.sleep(
            config.get(
                "tempo_apos_buscar_segundos",
                2.5,
            )
        )

        if not running:
            break

        # 3. ATACAR
        print("ETAPA 3/4: ATACAR")

        popup = wait_for_template(
            "popup_invasao",
            config,
            config.get(
                "timeout_popup_segundos",
                4.0,
            ),
        )

        if not popup:
            press_esc(
                config,
                "Popup de invasao nao encontrado.",
            )
            continue

        atacar = wait_for_template(
            "botao_atacar",
            config,
            config.get(
                "timeout_atacar_segundos",
                4.0,
            ),
        )

        if not atacar:
            press_esc(
                config,
                "Botao Atacar nao encontrado.",
            )
            continue

        print(
            "Popup de invasao validado: "
            f"score={popup['score']:.3f}"
        )

        click_found(atacar, config)
        print("Atacar clicado.")

        time.sleep(
            config.get(
                "tempo_apos_atacar_segundos",
                1.5,
            )
        )

        if not running:
            break

        # 4. MARCHAR
        print("ETAPA 4/4: MARCHAR")

        marchar = wait_for_template(
            "botao_marchar",
            config,
            config.get(
                "timeout_marchar_segundos",
                4.0,
            ),
        )

        if not marchar:
            press_esc(
                config,
                "Marchar nao encontrado.",
            )
            continue

        click_found(marchar, config)
        print("Marchar clicado.")

        if not config.get("dry_run", True):
            add_vigor_spent()

        time.sleep(
            config.get(
                "tempo_apos_marchar_segundos",
                1.5,
            )
        )

    listener.stop()
    print("Bot finalizado.")


if __name__ == "__main__":
    main()