"""
Ejecuta un notebook con su directorio de trabajo fijado en el cwd del
proceso (la raiz del repo), no en la carpeta del notebook (src/), que es
el comportamiento por defecto de nbconvert. Así las rutas relativas que
usan los cuadernos (data/raw/, dashboard_data/, etc.) apuntan siempre al
mismo lugar sin importar desde donde se invoque.

Uso: python .github/scripts/run_notebook.py src/00_descargas.ipynb
"""
import sys

import nbformat
from nbclient import NotebookClient

path = sys.argv[1]
nb = nbformat.read(path, as_version=4)
client = NotebookClient(nb, timeout=900, kernel_name="python3", resources={"metadata": {"path": "."}})
client.execute()
nbformat.write(nb, path)
print("ejecutado:", path)
