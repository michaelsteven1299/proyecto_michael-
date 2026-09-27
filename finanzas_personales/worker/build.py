"""Genera worker.js (un solo archivo para pegar en Cloudflare) con la app adentro."""
import json
import pathlib

aqui = pathlib.Path(__file__).parent
html = (aqui.parent / "index.html").read_text(encoding="utf-8")
plantilla = (aqui / "worker.template.js").read_text(encoding="utf-8")
salida = plantilla.replace("__APP_HTML__", json.dumps(html, ensure_ascii=False), 1)
(aqui / "worker.js").write_text(salida, encoding="utf-8")
print(f"worker.js generado ({len(salida.encode('utf-8')) // 1024} KB)")
