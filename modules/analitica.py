"""
analitica.py
============

Agregaciones puras (pandas) para la analítica real de la Pestaña 1: resumen por
colonia, por distrito local y serie temporal de registros de campo. No depende
de Streamlit ni de MongoDB; recibe DataFrames y devuelve DataFrames, por lo que
es fácil de probar.

Los registros esperan tener al menos: seccion_id, tipo, intencion y, opcional,
'colonia' / 'queja_categoria' / 'fecha'.
"""

import pandas as pd

_TIPOS_SIMPATIA = ('simpatia', 'visita')
_SIN_COLONIA = 'Sin asignar'


def _colonia_label(registros: pd.DataFrame) -> pd.Series:
    """Etiqueta de colonia por registro ('Sin asignar' si falta)."""
    if 'colonia' not in registros:
        return pd.Series(_SIN_COLONIA, index=registros.index)
    return registros['colonia'].fillna(_SIN_COLONIA).astype(str).replace('', _SIN_COLONIA)


def resumen_por_colonia(registros: pd.DataFrame,
                        colonias_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Resumen por colonia: total de registros, simpatías (💚/💛/❤️), quejas,
    quejas de AGUA y % de quejas de agua (base: quejas de la colonia).

    Retorna:
        pd.DataFrame indexado por colonia, ordenado por total desc.
        Vacío si no hay registros.
    """
    if registros is None or registros.empty:
        return pd.DataFrame()
    df = registros.copy()
    df['_col'] = _colonia_label(df)
    filas = []
    for colonia, grupo in df.groupby('_col'):
        simpatias = grupo[grupo['tipo'].isin(_TIPOS_SIMPATIA)] \
            if 'tipo' in grupo else grupo
        sim = {}
        if 'intencion' in simpatias:
            sim = {i: int((simpatias['intencion'] == i).sum())
                   for i in ('a_favor', 'indeciso', 'en_contra')}
        quejas = int((grupo.get('tipo') == 'queja').sum()) \
            if 'tipo' in grupo else 0
        quejas_agua = 0
        if 'queja_categoria' in grupo:
            quejas_agua = int((grupo['queja_categoria'] == 'AGUA').sum())
        pct_agua = round(100.0 * quejas_agua / quejas, 1) if quejas else 0.0
        filas.append({'colonia': colonia, 'total': len(grupo),
                      'simpatias_favor': sim.get('a_favor', 0),
                      'simpatias_indeciso': sim.get('indeciso', 0),
                      'simpatias_contra': sim.get('en_contra', 0),
                      'quejas': quejas, 'quejas_agua': quejas_agua,
                      'pct_agua': pct_agua})
    resultado = pd.DataFrame(filas)
    return resultado.sort_values(['total', 'quejas_agua'], ascending=False) \
        .reset_index(drop=True)


def resumen_por_distrito(registros: pd.DataFrame,
                         secciones_df: pd.DataFrame) -> pd.DataFrame:
    """
    Resumen por distrito local a partir del mapeo sección → distrito
    (columna 'distrito' de secciones_df).

    Retorna:
        pd.DataFrame con distrito, total, simpatías y quejas. Vacío sin datos.
    """
    if registros is None or registros.empty or secciones_df is None \
            or secciones_df.empty:
        return pd.DataFrame()
    secciones = secciones_df.copy()
    if 'id' not in secciones.columns:
        return pd.DataFrame()
    mapa = secciones.set_index('id')['distrito'].to_dict() \
        if 'distrito' in secciones.columns else {}
    df = registros.copy()
    df['_distrito'] = df['seccion_id'].map(mapa).fillna('Sin asignar')
    filas = []
    for dto, grupo in df.groupby('_distrito'):
        simpatias = grupo[grupo.get('tipo').isin(_TIPOS_SIMPATIA)] \
            if 'tipo' in grupo else grupo
        sim = {}
        if 'intencion' in simpatias:
            sim = {i: int((simpatias['intencion'] == i).sum())
                   for i in ('a_favor', 'indeciso', 'en_contra')}
        quejas = int((grupo.get('tipo') == 'queja').sum()) if 'tipo' in grupo else 0
        filas.append({'distrito': dto, 'total': len(grupo),
                      'simpatias_favor': sim.get('a_favor', 0),
                      'simpatias_indeciso': sim.get('indeciso', 0),
                      'simpatias_contra': sim.get('en_contra', 0),
                      'quejas': quejas})
    resultado = pd.DataFrame(filas)
    return resultado.sort_values('total', ascending=False).reset_index(drop=True)


def serie_temporal(registros: pd.DataFrame, frecuencia: str = 'D') -> pd.DataFrame:
    """
    Serie temporal de registros de campo agrupada por periodo ('D' diario,
    'W' semanal, 'M' mensual), separando simpatías y quejas.

    Retorna:
        pd.DataFrame con 'fecha', 'total', 'simpatias', 'quejas'.
        Vacío si no hay registros con fecha válida.
    """
    if registros is None or registros.empty or 'fecha' not in registros:
        return pd.DataFrame()
    df = registros.copy()
    df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    df = df.dropna(subset=['fecha'])
    if df.empty:
        return pd.DataFrame()
    df['periodo'] = df['fecha'].dt.to_period(frecuencia).dt.to_timestamp()
    resumen = df.groupby('periodo').agg(
        total=('fecha', 'size'),
        simpatias=('tipo', lambda s: s.isin(_TIPOS_SIMPATIA).sum()),
        quejas=('tipo', lambda s: (s == 'queja').sum()),
    ).reset_index()
    resumen = resumen.rename(columns={'periodo': 'fecha'})
    return resumen.sort_values('fecha').reset_index(drop=True)