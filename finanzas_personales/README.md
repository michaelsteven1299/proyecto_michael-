# Mis Finanzas — plantilla mes a mes

App web interactiva (un solo archivo, `index.html`) para llevar ingresos y gastos
mes a mes. Está basada en la base de Notion **«Registro de Finanzas Personales»**:
usa los mismos campos (Descripción, Tipo, Gasto, Ingreso, Fecha, Método de Pago),
los mismos tipos (Gasto, Ingreso, Transferencia, Inversión, Reembolso) y tus métodos
de pago (Nequi, Bancolombia, Bancoomeva, Lulo, Efectivo, Pse, Transferencia, Nu).

## Qué hace

- **Navegas mes por mes** con las flechas ‹ › (toca el nombre del mes para volver al actual).
- **Tú creas los ítems** con el botón **Agregar**: tipo, monto, descripción, categoría y método de pago.
- Cada ítem puede ser **«Solo una vez»** (queda en su fecha) o **«Cada mes»** (se repite
  desde ese mes, con un día fijo y, si quieres, una fecha «Hasta», ej. la última cuota de un crédito).
- Al editar un ítem mensual eliges si el cambio aplica a **solo este mes**, **este mes y los
  siguientes** (ej. te subieron el arriendo) o **todos los meses**. Lo mismo al eliminar.
- Casilla para marcar cada movimiento como **pagado / recibido**, y un total de **pendiente por pagar**.
- **Resumen**: balance del mes, ingresos, gastos, inversión, tasa de ahorro y gráfico de dona por categoría.
- **Gráficos** (6 o 12 meses): ingresos vs. gastos, balance de cada mes, saldo acumulado,
  gastos por método de pago y tabla mensual.
- Modo claro/oscuro y diseño pensado primero para el celular.

## Dónde se guardan los datos

En el propio dispositivo/navegador (localStorage). Por eso, en la pestaña **Gráficos → Tus datos**:

- **Descargar / Copiar copia**: respaldo en JSON. Restáuralo en otro celular o computador.
- **CSV de este mes / del año**: exporta con las columnas de tu base de Notion para
  importarlo allá (••• → *Merge with CSV*).

Al abrirla por primera vez muestra **datos de ejemplo**; toca «Borrar ejemplos» para empezar con los tuyos.

## Cómo abrirla en Notion (celular)

La app se publica en GitHub Pages junto a la página del oro, en:

`https://michaelsteven1299.github.io/proyecto_michael-/finanzas/`

(se despliega cuando el workflow `prediccion_diaria.yml` corre en `main`; puedes
correrlo a mano desde **Actions → Prediccion diaria oro COP → Run workflow**).

En Notion:

1. Crea una página, por ejemplo «💰 Mis Finanzas».
2. Escribe `/embed`, pega el enlace de arriba y ajusta el alto del bloque.
3. En el celular, abre esa página; si prefieres pantalla completa, guarda el enlace
   como acceso directo en la pantalla de inicio (Compartir → *Añadir a pantalla de inicio*).

> Nota: Notion en el celular a veces limpia los datos de las páginas incrustadas.
> Para que tus datos no dependan de eso, usa siempre el mismo acceso (el embed **o** el
> acceso directo) y descarga una copia de seguridad de vez en cuando.
