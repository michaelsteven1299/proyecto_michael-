# Mis Finanzas: plantilla mes a mes conectada a Notion

App interactiva (`index.html`) para llevar ingresos y gastos mes a mes, **guardada en tu
base de Notion «Movimientos»**. Está basada en tu base «Registro de Finanzas Personales»
(mismos tipos, campos y métodos de pago).

## Qué hace

- **Mes a mes** con las flechas ‹ › (toca el nombre del mes para volver al actual).
- **Agregar**: tipo, monto, descripción, categoría y método de pago.
- **Solo una vez** o **Cada mes**: un ítem mensual se repite desde ese mes, en un día fijo
  y, si quieres, **hasta** un mes (por ejemplo, la última cuota de un crédito).
- Al editar un ítem mensual eliges: **solo este mes**, **este mes y los siguientes** o
  **todos los meses**. Lo mismo al eliminar.
- Casilla de **pagado / recibido** y total **pendiente por pagar**.
- **Resumen**, **Movimientos** (con filtros) y **Gráficos** (6 o 12 meses, balance, saldo
  acumulado, métodos de pago y tabla).
- Cada cambio se guarda en Notion: ves lo mismo en el celular y en el computador, y no se
  pierde al cerrar.

## Cómo funciona

```
Notion (tu página)  ──embed──▶  Cloudflare Worker  ──API──▶  base «Movimientos»
                                (sirve la app y guarda)
```

- `index.html`: la app. Si se abre sola (sin el servidor) funciona en modo "local" y guarda
  solo en el navegador.
- `worker/worker.js`: el servidor, **un solo archivo** que se pega en Cloudflare. Ya trae la
  app adentro. Se genera con `python3 worker/build.py` a partir de
  `worker/worker.template.js` + `index.html`.
- Cada mes de un ítem mensual es una fila propia en Notion. Las columnas **Serie** y
  **Omitido** las llena la app; no hace falta tocarlas.

## Configuración (una sola vez, unos 10 minutos)

### 1. Clave de Notion
1. Entra a <https://www.notion.so/profile/integrations> → **Nueva integración**.
2. Nombre: `Mis Finanzas`, tipo **Interna**, tu espacio de trabajo → **Guardar**.
3. Copia el **Secreto de integración interna** (empieza por `ntn_`).
4. Abre la página **💰 Mis Finanzas Mes a Mes** en Notion → **•••** (arriba a la derecha) →
   **Conexiones** → busca `Mis Finanzas` → **Confirmar**.

### 2. Servidor en Cloudflare (gratis)
1. Crea una cuenta en <https://dash.cloudflare.com/sign-up>.
2. **Workers & Pages** → **Create** → **Create Worker** → nombre `mis-finanzas` → **Deploy**.
3. **Edit code** → borra todo → pega el contenido completo de
   [`worker/worker.js`](worker/worker.js) → **Deploy**.
4. Vuelve al worker → **Settings** → **Variables and Secrets** → agrega:

   | Nombre | Tipo | Valor |
   |---|---|---|
   | `NOTION_TOKEN` | Secret | la clave `ntn_...` del paso 1 |
   | `APP_KEY` | Secret | una clave que inventes, ej. `mifinanza-7392-kq` (solo letras, números y guiones) |
   | `DATABASE_ID` | Text | `1a850b5350d54c9daa81a47a0806b362` |

   → **Deploy**.

### 3. Abrirla y ponerla en Notion
1. El enlace de tu app es: `https://mis-finanzas.<tu-subdominio>.workers.dev/?k=<tu APP_KEY>`
   (el subdominio aparece en la página del worker en Cloudflare).
2. Ábrelo en el navegador: arriba debe decir **«Guardado en Notion»**.
3. En tu página de Notion escribe `/embed`, pega el enlace y ajusta el alto.

> El enlace lleva tu clave: quien lo tenga puede ver y editar tus finanzas. Comparte la
> página de Notion solo con personas de confianza.

## Actualizar la app

Si cambia `index.html`: `python3 worker/build.py` y vuelve a pegar `worker/worker.js` en Cloudflare.
