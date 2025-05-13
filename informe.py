import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime
import random

st.set_page_config(page_title="Informe Económico Semanal", layout="wide")

# ✅ Título y subtítulo de presentación
st.title("📊 Informe Económico Semanal Automatizado")
st.caption("Trabajo práctico realizado por Sol Silvestrini")

@st.cache_data
def cargar_dolar_csv():
    df = pd.read_csv("valores_limpio.csv", parse_dates=["fecha"])
    df = df.sort_values("fecha").fillna(method="ffill")
    df["Brecha"] = (df["USD CCL"] / df["OFICIAL"] - 1) * 100
    return df

def obtener_datos_yahoo(ticker, periodo):
    return yf.Ticker(ticker).history(period=periodo)

def seccion_evolucion():
    st.subheader("📈 Evolución de activos")
    activos = {
        "Bitcoin": "BTC-USD", "Ethereum": "ETH-USD", "Gold": "GC=F", "Silver": "SI=F",
        "Microsoft": "MSFT", "Apple": "AAPL", "Nvidia": "NVDA", "Amazon": "AMZN",
        "Google": "GOOGL", "Meta": "META", "Tesla": "TSLA", "S&P 500": "^GSPC",
        "JP Morgan": "JPM", "Visa": "V", "Eli Lilly": "LLY", "Tenaris": "TS"
    }

    seleccion = st.multiselect("Seleccionar activos", list(activos.keys()), default=["Google", "Apple", "Tesla"])
    periodo = st.selectbox("Elegir periodo", ["7d", "30d", "90d", "180d", "365d", "max"], index=4)

    df_merged = None
    precios_actuales = {}
    rendimientos = {}

    for nombre in seleccion:
        ticker = activos[nombre]
        data = obtener_datos_yahoo(ticker, periodo)
        if data is not None and not data.empty:
            data = data[["Close"]].dropna().rename(columns={"Close": nombre})
            data = data.reset_index()
            data["Fecha"] = pd.to_datetime(data["Date"])
            data = data.drop(columns=["Date"])

            precio = data[nombre].iloc[-1]
            precios_actuales[nombre] = precio
            rendimiento = (data[nombre].iloc[-1] / data[nombre].iloc[0] - 1) * 100
            rendimientos[nombre] = rendimiento

            data = data[["Fecha", nombre]]
            df_merged = data if df_merged is None else pd.merge(df_merged, data, on="Fecha", how="outer")

    if df_merged is not None:
        df_merged = df_merged.sort_values("Fecha").fillna(method="ffill")
        df_melted = df_merged.melt(id_vars="Fecha", var_name="Activo", value_name="Valor")
        fig = px.line(df_melted, x="Fecha", y="Valor", color="Activo")
        fig.update_layout(title="", yaxis_title="", xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    if seleccion:
        cols = st.columns(len(seleccion))
        for idx, nombre in enumerate(seleccion):
            precio = precios_actuales.get(nombre, "-")
            delta = rendimientos.get(nombre, None)
            if isinstance(precio, (int, float)) and delta is not None:
                cols[idx].metric(nombre, f"${precio:,.2f}", f"{delta:+.2f}%")
            elif isinstance(precio, (int, float)):
                cols[idx].metric(nombre, f"${precio:,.2f}", "-")
            else:
                cols[idx].metric(nombre, "-", "-")

def seccion_dolar():
    df = cargar_dolar_csv()

    st.markdown("#### Cotización por fecha")
    fecha = st.date_input("Seleccionar fecha:", value=df["fecha"].max(), min_value=df["fecha"].min(), max_value=df["fecha"].max())
    fila = df[df["fecha"] <= pd.to_datetime(fecha)].iloc[-1]
    for col in ["USD CCL", "USD MEP", "OFICIAL", "EUR", "UYU"]:
        st.metric(col, f"${fila[col]:,.2f}")

    st.markdown("#### Gráfico de cotizaciones")
    monedas_disp = ["USD CCL", "USD MEP", "OFICIAL", "EUR", "UYU"]
    monedas_selec = st.multiselect("Seleccionar monedas a comparar:", monedas_disp, default=monedas_disp)
    periodo_comp = st.selectbox("Periodo para cotizaciones:", ["7 días", "30 días", "90 días", "180 días", "365 días", "Histórico"])
    periodos = {"7 días": 7, "30 días": 30, "90 días": 90, "180 días": 180, "365 días": 365, "Histórico": len(df)}
    df_periodo = df.tail(periodos[periodo_comp])

    fig1 = px.line(df_periodo, x="fecha", y=monedas_selec)
    fig1.update_layout(xaxis_title="", yaxis_title="")
    st.plotly_chart(fig1, use_container_width=True)

    st.markdown("#### Brecha USD CCL vs Oficial")
    df_brecha = df.tail(periodos[periodo_comp])
    fig2 = px.line(df_brecha, x="fecha", y="Brecha", title="Brecha USD CCL vs Oficial")
    fig2.update_layout(xaxis_title="", yaxis_title="Brecha (%)")
    st.plotly_chart(fig2, use_container_width=True)

import feedparser
from collections import defaultdict

def seccion_titulares():
    st.subheader("📰 Titulares económicos")

    # Fuente fija: El Cronista
    fuente_seleccionada = "El Cronista"
    url_feed = "https://www.cronista.com/files/rss/finanzas.xml"
    st.caption("🗞️ Fuente: El Cronista")

    try:
        feed = feedparser.parse(url_feed)

        # Validación de resultados
        if not feed.entries or len(feed.entries) == 0:
            st.warning("No se pudieron cargar titulares desde El Cronista.")
            return

        # Clasificación por tema
        temas = {
            "📈 Inflación": ["inflación", "ipc", "precios"],
            "💵 Tipo de cambio": ["dólar", "blue", "cambiario"],
            "🌾 Commodities": ["soja", "petróleo", "commodities"],
            "🏦 Política monetaria": ["bcra", "tasa", "interviene", "liquidez"],
            "⚠️ Alerta": ["crisis", "default", "caída", "récord"]
        }

        noticias = []
        agrupadas = defaultdict(list)
        resumen_temas = defaultdict(int)

        for entry in feed.entries[:20]:
            titulo = entry.title
            enlace = entry.link
            fecha_raw = entry.get("published", "")
            try:
                fecha_obj = datetime(*entry.published_parsed[:6])
                fecha_formateada = fecha_obj.strftime("%d/%m/%Y %H:%M hs")
            except:
                fecha_formateada = fecha_raw

            etiquetas = []
            titulo_lower = titulo.lower()
            for categoria, palabras in temas.items():
                if any(p in titulo_lower for p in palabras):
                    etiquetas.append(categoria)
                    resumen_temas[categoria] += 1

            if not etiquetas:
                etiquetas.append("📄 General")

            for et in etiquetas:
                agrupadas[et].append({
                    "titulo": titulo,
                    "link": enlace,
                    "fecha": fecha_formateada
                })

            noticias.append({
                "Título": titulo,
                "Fecha": fecha_formateada,
                "Fuente": fuente_seleccionada,
                "Enlace": enlace,
                "Temas": ", ".join(etiquetas)
            })

        # RESUMEN automático del día
        st.markdown("### 🧠 Síntesis del día")
        temas_ordenados = sorted(resumen_temas.items(), key=lambda x: x[1], reverse=True)
        if temas_ordenados:
            st.markdown("Hoy se destacaron:\n")
            for tema, cantidad in temas_ordenados:
                st.markdown(f"- {tema}: {cantidad} titulares")
        else:
            st.markdown("*No se detectaron temas destacados.*")

        # FILTRO por tema
        todos_los_temas = list(agrupadas.keys())
        seleccionados = st.multiselect("📌 Filtrar por tema", todos_los_temas, default=todos_los_temas)

        # MOSTRAR NOTICIAS agrupadas por tema
        for categoria in seleccionados:
            st.markdown(f"## {categoria}")
            for noticia in agrupadas[categoria]:
                st.markdown(f"""
                    <div style='padding: 1rem; border-radius: 12px; background-color: #1e1e1e; margin-bottom: 1rem;'>
                        <a href="{noticia['link']}" target="_blank" style="text-decoration: none;">
                            <h4 style='margin-bottom: 0.3rem; color: #4FC3F7;'>{noticia['titulo']}</h4>
                        </a>
                        <p style='color: gray; font-size: 0.9rem;'>🗓️ {noticia['fecha']}</p>
                    </div>
                """, unsafe_allow_html=True)

        # EXPORTACIÓN
        df_noticias = pd.DataFrame(noticias)
        st.download_button("📤 Descargar titulares como CSV", df_noticias.to_csv(index=False), "titulares.csv", "text/csv")

        # FECHA de última actualización
        st.caption(f"🕒 Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    except Exception as e:
        st.error(f"Error al cargar noticias: {str(e)}")


def seccion_precios_actuales():
    st.subheader("📊 Precios actuales de activos")

    try:
        df = pd.read_csv("assets_yahoo_top100.csv")
    except FileNotFoundError:
        st.error("No se encontró el archivo assets_yahoo_top100.csv.")
        return

    df = df.sort_values("Nombre")
    opciones = [f"{row['Ticker']} - {row['Nombre']}" for _, row in df.iterrows()]

    if "activos" not in st.session_state:
        st.session_state["activos"] = opciones[:10]

    seleccionados = st.multiselect("⭐ Elegí tus activos favoritos", options=opciones, default=st.session_state["activos"])
    st.session_state["activos"] = seleccionados

    tickers = [s.split(" - ")[0] for s in seleccionados]
    nombres = {row['Ticker']: row['Nombre'] for _, row in df.iterrows()}
    num_cols = 3
    cols = st.columns(num_cols)

    datos_variacion = []

    for idx, ticker in enumerate(tickers):
        with cols[idx % num_cols]:
            try:
                info = yf.Ticker(ticker).info
                precio = info.get("regularMarketPrice", None)
                cierre = info.get("previousClose", None)
                if precio and cierre:
                    variacion = ((precio - cierre) / cierre) * 100
                    st.metric(f"{ticker} - {nombres[ticker]}", f"${precio:,.2f}", f"{variacion:+.2f}%")
                    datos_variacion.append((ticker, nombres[ticker], precio, cierre, variacion))
                elif precio:
                    st.metric(f"{ticker} - {nombres[ticker]}", f"${precio:,.2f}", "Variación no disponible")
            except:
                st.warning(f"{ticker}: error al consultar")

    if st.checkbox("📋 Mostrar información extendida (cierre anterior, volumen)"):
        for ticker in tickers:
            try:
                info = yf.Ticker(ticker).info
                cierre = info.get("previousClose", "N/A")
                volumen = info.get("volume", "N/A")
                st.text(f"{ticker} - Cierre anterior: ${cierre} | Volumen: {volumen}")
            except:
                st.warning(f"{ticker}: error al consultar info extendida")

    if datos_variacion:
        top_gainers = sorted(datos_variacion, key=lambda x: x[4], reverse=True)[:3]
        top_losers = sorted(datos_variacion, key=lambda x: x[4])[:3]

        st.markdown("🏆 **Top Gainers:**")
        for t, n, p, c, v in top_gainers:
            st.markdown(f"- {t} ({n}): {v:+.2f}%")

        st.markdown("📉 **Top Losers:**")
        for t, n, p, c, v in top_losers:
            st.markdown(f"- {t} ({n}): {v:+.2f}%")

    if st.button("📤 Exportar selección a CSV"):
        df_export = pd.DataFrame([{
            "Ticker": t,
            "Nombre": n,
            "Precio actual": p,
            "Cierre anterior": c,
            "Variación (%)": v
        } for t, n, p, c, v in datos_variacion])
        st.download_button("Descargar CSV", df_export.to_csv(index=False), "precios_activos.csv", "text/csv")

def seccion_analisis():
    st.subheader("🧠 Análisis automático")
    st.markdown("🔍 **Análisis generado por IA**")

    # Requiere que exista una cartera ya cargada
    if "cartera" not in st.session_state or not st.session_state.cartera:
        st.warning("Cargá primero tu cartera en la sección 'Valuación de portafolio'.")
        return

    # Cálculo total
    resultados = []
    total_actual = 0
    total_invertido = 0

    for row in st.session_state.cartera:
        ticker = row["Ticker"]
        fecha_compra = pd.to_datetime(row["Fecha"])
        cantidad = row["Cantidad"]

        try:
            actual_price = yf.Ticker(ticker).info["regularMarketPrice"]
        except:
            actual_price = None

        try:
            historial = yf.Ticker(ticker).history(start=fecha_compra, end=fecha_compra + pd.Timedelta(days=5))
            precio_compra = historial["Close"].iloc[0] if not historial.empty else None
        except:
            precio_compra = None

        if actual_price and precio_compra:
            valor_actual = actual_price * cantidad
            valor_compra = precio_compra * cantidad
            rendimiento = (actual_price / precio_compra - 1) * 100

            resultados.append({
                "Ticker": ticker,
                "Valuación actual": valor_actual,
                "Valuación inicial": valor_compra,
                "Rendimiento (%)": rendimiento
            })

            total_actual += valor_actual
            total_invertido += valor_compra

    if not resultados:
        st.warning("No se pudieron obtener datos de valuación para los activos.")
        return

    df_resultados = pd.DataFrame(resultados)
    df_resultados = df_resultados.sort_values("Rendimiento (%)", ascending=False)
    top_rendimiento = df_resultados.head(3)["Ticker"].tolist()

    # ---- SECCIÓN 1: Análisis general
    st.markdown("### 💡 Análisis generado por IA")
    delta = (total_actual / total_invertido - 1) * 100 if total_invertido > 0 else 0
    ganancia_usd = total_actual - total_invertido

    st.markdown(f"""
- 📈 En base a tu portafolio actual, obtuviste un rendimiento total de **{delta:.2f}%** desde la fecha de adquisición de tus activos, con una ganancia neta de **${ganancia_usd:,.2f}**.
- ✅ Los activos con mejor rendimiento fueron: **{', '.join(top_rendimiento)}**.
- 📊 Comparado con un benchmark hipotético del 15% anual, tu portafolio {"superó" if delta > 15 else "quedó por debajo de"} esa referencia.
""")

    # ---- SECCIÓN 2: Alertas automatizadas
    st.markdown("### ⚠️ Alertas automatizadas")

    # 1. Alerta por concentración
    df_resultados["% cartera"] = df_resultados["Valuación actual"] / total_actual * 100
    concentrados = df_resultados[df_resultados["% cartera"] > 30]
    if not concentrados.empty:
        tickers_conc = ", ".join(concentrados["Ticker"].tolist())
        st.warning(f"🎯 Los activos {tickers_conc} representan más del 30% del total del portafolio. Esto puede ser una exposición excesiva.")

    # 2. Activos con pérdida mayor al 20%
    perdedores = df_resultados[df_resultados["Rendimiento (%)"] < -20]
    if not perdedores.empty:
        st.error("📉 Los siguientes activos tuvieron caídas mayores al 20%:")
        for _, row in perdedores.iterrows():
            st.markdown(f"- {row['Ticker']}: {row['Rendimiento (%)']:.2f}%")

    # 3. Portafolio con rendimiento pobre
    if delta < 5:
        st.info("ℹ️ El rendimiento total de tu portafolio es inferior al 5%. Podría ser momento de revisar tu estrategia.")

    # ---- SECCIÓN 3: Eventos económicos vinculados
    noticias = st.session_state.get("titulares_destacados", [])

    st.markdown("### 📰 Eventos económicos destacados que podrían haber influido:")
    if noticias:
        for n in noticias[:3]:
            st.markdown(f"- {n}")
    else:
        st.info("No se detectaron eventos destacados para esta semana.")

    st.caption(f"🤖 Análisis generado automáticamente el {datetime.now().strftime('%d/%m/%Y')}")


def seccion_portafolio():
    st.subheader("📊 Armado de portafolio")

    try:
        df_activos = pd.read_csv("assets_yahoo_top100.csv")
    except FileNotFoundError:
        st.error("No se encontró el archivo 'assets_yahoo_top100.csv'.")
        return

    tickers_dict = {row['Ticker']: row['Nombre'] for _, row in df_activos.iterrows()}
    tickers_lista = sorted(tickers_dict.keys())

    if "cartera" not in st.session_state:
        st.session_state.cartera = []

    # 🔁 Si no hay cartera, se genera una simulación
    if not st.session_state.cartera:
        st.info("Generando cartera simulada de prueba ($150.000)")
        tickers_sample = random.sample(tickers_lista, 5)
        simulated_cartera = []
        monto_objetivo = 150000
        monto_actual = 0

        for ticker in tickers_sample:
            try:
                precio_actual = yf.Ticker(ticker).info["regularMarketPrice"]
                if not precio_actual:
                    continue
                cantidad = random.randint(1, 10)
                inversion = precio_actual * cantidad
                if monto_actual + inversion > monto_objetivo:
                    break
                simulated_cartera.append({
                    "Ticker": ticker,
                    "Fecha": "2023-01-01",
                    "Cantidad": cantidad
                })
                monto_actual += inversion
            except:
                continue

        st.session_state.cartera = simulated_cartera

    # 🧾 Mostrar cartera actual
    df_cartera = pd.DataFrame(st.session_state.cartera)
    if df_cartera.empty:
        st.info("No se agregaron tenencias aún.")
        return

    st.markdown("### 🧾 Cartera actual:")
    for i, row in df_cartera.iterrows():
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
        col1.write(row["Ticker"])
        col2.write(row["Fecha"])
        col3.write(f"{row['Cantidad']}")
        if col5.button("❌", key=f"delete_{i}"):
            st.session_state.cartera.pop(i)
            st.rerun()


    # 📈 Formulario para seguir agregando activos manualmente
    st.markdown("### ➕ Agregar activo a la cartera")
    with st.form("form_nueva_tenencia", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            ticker = st.selectbox("Ticker", tickers_lista, index=0)
        with col2:
            fecha = st.date_input("Fecha de adquisición", value=pd.to_datetime("2023-01-01"))
        with col3:
            cantidad = st.number_input("Cantidad", min_value=0.01, step=1.0)
        if st.form_submit_button("Agregar a la cartera"):
            st.session_state.cartera.append({
                "Ticker": ticker,
                "Fecha": str(fecha),
                "Cantidad": cantidad
            })
            st.rerun()


    if st.button("🗑️ Limpiar cartera"):
        st.session_state.cartera = []
        st.rerun()


    # 💰 Cálculos
    resultados = []
    total_actual = 0
    total_invertido = 0
    df_hist_total = pd.DataFrame()

    for row in st.session_state.cartera:
        ticker = row["Ticker"]
        fecha_compra = pd.to_datetime(row["Fecha"])
        cantidad = row["Cantidad"]

        try:
            actual_price = yf.Ticker(ticker).info["regularMarketPrice"]
        except:
            actual_price = None

        try:
            historial = yf.Ticker(ticker).history(start=fecha_compra, end=fecha_compra + pd.Timedelta(days=5))
            precio_compra = historial["Close"].iloc[0] if not historial.empty else None
        except:
            precio_compra = None

        if actual_price and precio_compra:
            valor_actual = actual_price * cantidad
            valor_compra = precio_compra * cantidad
            rendimiento = (actual_price / precio_compra - 1) * 100

            resultados.append({
                "Ticker": ticker,
                "Fecha": fecha_compra.strftime("%Y-%m-%d"),
                "Cantidad": cantidad,
                "Precio compra": f"${precio_compra:.2f}",
                "Precio actual": f"${actual_price:.2f}",
                "Valuación actual": f"${valor_actual:,.2f}",
                "Rendimiento (%)": f"{rendimiento:.2f}%"
            })

            total_actual += valor_actual
            total_invertido += valor_compra

            hist = yf.Ticker(ticker).history(start=fecha_compra)
            if not hist.empty:
                hist["Valuación"] = hist["Close"] * cantidad
                hist = hist[["Valuación"]].rename(columns={"Valuación": ticker})
                df_hist_total = pd.concat([df_hist_total, hist], axis=1)

    # 📊 Visualización
    if resultados:
        st.markdown("### 💼 Valuación total del portafolio")
        st.success(f"Valuación actual: ${total_actual:,.2f}")
        st.info(f"Inversión original: ${total_invertido:,.2f}")
        delta = (total_actual / total_invertido - 1) * 100 if total_invertido > 0 else 0
        ganancia_usd = total_actual - total_invertido
        st.metric("Rendimiento total", f"{delta:.2f}%")
        st.metric("Ganancia / Pérdida", f"${ganancia_usd:,.2f}")

        st.markdown("### 📈 Resultados por activo")
        df_resultados = pd.DataFrame(resultados)
        st.dataframe(df_resultados)

        st.markdown("### 📊 Distribución del portafolio")
        try:
            df_resultados["Valuación actual"] = df_resultados["Valuación actual"].replace({"\$|," : ''}, regex=True).astype(float)
            fig = px.pie(df_resultados, names="Ticker", values="Valuación actual", title="Distribución del portafolio")
            st.plotly_chart(fig, use_container_width=True)
        except:
            st.warning("No se pudo generar el gráfico de distribución.")

        st.markdown("### 📉 Evolución histórica del portafolio")
        if not df_hist_total.empty:
            df_hist_total = df_hist_total.fillna(method="ffill").dropna()
            df_hist_total["Total"] = df_hist_total.sum(axis=1)
            st.line_chart(df_hist_total["Total"])

    # 📤 Exportación + carga CSV al final
    csv = pd.DataFrame(st.session_state.cartera).to_csv(index=False).encode("utf-8")
    st.download_button("📤 Exportar cartera", csv, "cartera.csv", "text/csv")

    st.markdown("### 📥 Cargar cartera desde archivo")
    archivo = st.file_uploader("Subí tu cartera en CSV", type="csv")
    if archivo:
        try:
            st.session_state.cartera = pd.read_csv(archivo).to_dict(orient="records")
            st.success("Cartera cargada desde archivo.")
            st.rerun()

        except Exception as e:
            st.error(f"Error al cargar el archivo: {e}")

# ---------- MENÚ PRINCIPAL ----------
st.sidebar.title("Secciones del informe")
seccion = st.sidebar.radio("", [
    "Valuación de portafolio",  # aparece primero
    "Evolución de activos",
    "Cotización del dólar",
    "Titulares económicos",
    "Precios actuales de activos",
    "Análisis automático"
])

if seccion == "Valuación de portafolio":
    seccion_portafolio()
elif seccion == "Evolución de activos":
    seccion_evolucion()
elif seccion == "Cotización del dólar":
    seccion_dolar()
elif seccion == "Titulares económicos":
    seccion_titulares()
elif seccion == "Precios actuales de activos":
    seccion_precios_actuales()
elif seccion == "Análisis automático":
    seccion_analisis()

















