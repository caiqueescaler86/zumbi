# Last War Zombie Event Bot - prototipo seguro

Modo inicial: `dry_run=true`. Ele detecta e registra, mas nao clica em Marchar.

## Instalar

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Templates necessarios

Salve recortes PNG na pasta `templates/` com os nomes do `config.json`:

- eventos.png
- evento_invasao_zumbis.png
- buscar.png
- popup_invasao_zumbis.png
- botao_atacar.png
- botao_marchar.png
- obter_vigor.png
- reivindicar.png
- usar_10_vigor.png
- usar_50_vigor.png
- fechar.png
- fila_4_4.png

Use prints da sua propria tela, no mesmo zoom/resolucao do emulador.

## Hotkeys

- F8 pausa/continua
- F12 encerra
