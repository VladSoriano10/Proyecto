import pandas as pd
from sqlalchemy import text

from db_config import engine_destino, engine_origen, probar_conexiones


def diferencial_fact_roaming():
    print("\n--- Iniciando Carga INCREMENTAL para fact_roaming ---")


    # LEER LA MARCA DE AGUA (sk_fecha)

    print("-> 1. Buscando la última fecha cargada en el Data Warehouse...")

    query_hwm = """
        SELECT COALESCE(MAX(sk_fecha), 19000101) 
        FROM fact_roaming;
    """
    with engine_destino.connect() as conn:
        # Envolvemos la consulta cruda con text()
        ultima_sk_fecha = conn.execute(text(query_hwm)).scalar()

    print(f"   Última fecha registrada (sk_fecha): {ultima_sk_fecha}")

    # EXTRACCIÓN UNIFICADA (Datos + Voz + Eventos)
    print("-> 2. Extrayendo tráfico nuevo desde el origen...")

    query_origen = f"""
        SELECT 
            id_operador AS nk_id_operador,
            id_tarifa_aplicada AS nk_id_tarifa,
            fecha_hora_conexion AS fecha_hora_transaccion,
            COALESCE(total_volumen_kb, 0) AS volumen_kb,
            0.0 AS duracion_min,
            0 AS cantidad_eventos,
            COALESCE(monto_sdr, 0) AS monto_sdr,
            COALESCE(monto_local_usd, 0) AS monto_local_usd
        FROM byte_gprs_sv
        WHERE TO_CHAR(fecha_hora_conexion, 'YYYYMMDD')::INT > {ultima_sk_fecha}

        UNION ALL

        SELECT 
            id_operador AS nk_id_operador,
            id_tarifa_aplicada AS nk_id_tarifa,
            fecha_hora_llamada AS fecha_hora_transaccion,
            0.0 AS volumen_kb,
            COALESCE(duracion_facturada_min, 0) AS duracion_min,
            0 AS cantidad_eventos,
            COALESCE(monto_sdr, 0) AS monto_sdr,
            COALESCE(monto_local_usd, 0) AS monto_local_usd
        FROM byte_portal_sv
        WHERE TO_CHAR(fecha_hora_llamada, 'YYYYMMDD')::INT > {ultima_sk_fecha}

        UNION ALL

        SELECT 
            id_operador AS nk_id_operador,
            id_tarifa_aplicada AS nk_id_tarifa,
            fecha_hora_evento AS fecha_hora_transaccion,
            0.0 AS volumen_kb,
            0.0 AS duracion_min,
            1 AS cantidad_eventos,
            COALESCE(monto_sdr, 0) AS monto_sdr,
            COALESCE(monto_local_usd, 0) AS monto_local_usd
        FROM byte_camel_sv
        WHERE TO_CHAR(fecha_hora_evento, 'YYYYMMDD')::INT > {ultima_sk_fecha};
    """
    df_hechos = pd.read_sql(query_origen, con=engine_origen)

    if df_hechos.empty:
        print("-> 3. No hay tráfico nuevo. El DW está al día.\n")
        return

    print(f"   Se extrajeron {len(df_hechos)} transacciones nuevas.")

    # Generamos los campos de fecha para los cruces con Pandas
    df_hechos["sk_fecha"] = (
        pd.to_datetime(df_hechos["fecha_hora_transaccion"])
        .dt.strftime("%Y%m%d")
        .astype(int)
    )
    df_hechos["fecha_comparacion"] = pd.to_datetime(
        df_hechos["fecha_hora_transaccion"]
    ).dt.date
    df_hechos["fecha_hora_comparacion"] = pd.to_datetime(
        df_hechos["fecha_hora_transaccion"]
    )

    # BÚSQUEDA DE LLAVES SUBROGADAS (SCD Tipo 2)
    print("-> 3. Cruzando llaves subrogadas con las Dimensiones...")

    # --- A. LOOKUP: DIM_OPERADOR ---
    df_dim_op = pd.read_sql(
        "SELECT sk_operador, nk_id_operador, fecha_inicio_vigencia, fecha_fin_vigencia FROM dim_operador",
        engine_destino,
    )
    df_hechos = df_hechos.merge(df_dim_op, on="nk_id_operador", how="left")
    mascara_op = (
        df_hechos["fecha_comparacion"] >= df_hechos["fecha_inicio_vigencia"]
    ) & (df_hechos["fecha_comparacion"] <= df_hechos["fecha_fin_vigencia"])
    df_hechos.loc[~mascara_op, "sk_operador"] = -1
    df_hechos["sk_operador"] = df_hechos["sk_operador"].fillna(-1).astype(int)
    df_hechos.drop(
        columns=["fecha_inicio_vigencia", "fecha_fin_vigencia"], inplace=True
    )  # Limpieza

    # --- B. LOOKUP: DIM_TARIFA ---
    df_hechos["nk_id_tarifa"] = df_hechos["nk_id_tarifa"].fillna(-1).astype(int)
    df_dim_tar = pd.read_sql(
        "SELECT sk_tarifa, nk_id_tarifa, fecha_inicio_vigencia, fecha_fin_vigencia FROM dim_tarifa",
        engine_destino,
    )
    df_hechos = df_hechos.merge(df_dim_tar, on="nk_id_tarifa", how="left")
    mascara_tar = (
        df_hechos["fecha_comparacion"] >= df_hechos["fecha_inicio_vigencia"]
    ) & (df_hechos["fecha_comparacion"] <= df_hechos["fecha_fin_vigencia"])
    df_hechos.loc[~mascara_tar, "sk_tarifa"] = -1
    df_hechos["sk_tarifa"] = df_hechos["sk_tarifa"].fillna(-1).astype(int)
    df_hechos.drop(
        columns=["fecha_inicio_vigencia", "fecha_fin_vigencia"], inplace=True
    )  # Limpieza

    # --- C. LOOKUP: DIM_TASA_CAMBIO (SDR a USD) ---
    df_dim_tasa = pd.read_sql(
        "SELECT sk_tasa, fecha_desde, fecha_hasta FROM dim_tasa_cambio WHERE moneda_origen = 'SDR' AND moneda_destino = 'USD'",
        engine_destino,
    )
    df_dim_tasa["fecha_desde"] = pd.to_datetime(df_dim_tasa["fecha_desde"])
    df_dim_tasa["fecha_hasta"] = pd.to_datetime(df_dim_tasa["fecha_hasta"])

    # Asignamos -1 por defecto y actualizamos si encontramos una tasa vigente
    df_hechos["sk_tasa"] = -1
    for index, row in df_dim_tasa.iterrows():
        mascara_tasa = (df_hechos["fecha_hora_comparacion"] >= row["fecha_desde"]) & (
            df_hechos["fecha_hora_comparacion"] <= row["fecha_hasta"]
        )
        df_hechos.loc[mascara_tasa, "sk_tasa"] = row["sk_tasa"]
    df_hechos["sk_tasa"] = df_hechos["sk_tasa"].astype(int)

    # CARGA AL DATA WAREHOUSE
    print("-> 4. Insertando registros en fact_roaming...")

    columnas_finales = [
        "sk_fecha",
        "sk_operador",
        "sk_tarifa",
        "sk_tasa",
        "volumen_kb",
        "duracion_min",
        "monto_sdr",
        "monto_local_usd",
        "cantidad_eventos",
    ]
    df_final = df_hechos[columnas_finales]

    df_final.to_sql(
        name="fact_roaming", con=engine_destino, if_exists="append", index=False
    )

    print(
        f"¡Carga incremental finalizada! Se insertaron {len(df_final)} hechos en fact_roaming.\n"
    )


if __name__ == "__main__":
    if probar_conexiones():
        diferencial_fact_roaming()
