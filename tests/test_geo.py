"""
tests/test_geo.py
=================

Pruebas de la capa de geografía electoral real de la Pestaña 1
(`modules/geo.py`). Verifica que las secciones se cargan desde el CSV de
referencia COMMITEADO (`referencia/marcos/secciones_iecm.csv`) incluso cuando
el KML del IECM no está disponible (caso Cloud / instalación sin `documentos/`),
que era el fallo del botón "Importar secciones IECM/INE".

Ejecutar desde la raíz del repo:
    python -m pytest tests/test_geo.py -v
"""

import pytest

import modules.geo as geo

KML_INEXISTENTE = 'documentos/inexistente/circunscripcionesDT/99.kml'


def test_parsear_kml_secciones_usa_csv_referencia_sin_kml(monkeypatch):
    """Aunque el KML no exista, se devuelven las secciones desde el CSV de referencia."""
    # Las pruebas fuerzan la ruta del KML a una inexistente (el argumento por
    # defecto queda ligado a su valor original al definirse la función).
    df = geo.parsear_kml_secciones(ruta=KML_INEXISTENTE)
    assert not df.empty
    assert len(df) >= 300  # ~355 secciones reales de Tlalpan
    assert 'id_seccion' in df.columns
    assert 'geometry_geojson' in df.columns
    # La geometría llega como dict (parseada de JSON), no como texto
    primera = df['geometry_geojson'].dropna().iloc[0]
    assert isinstance(primera, dict)
    assert df['id_seccion'].is_monotonic_increasing


def test_parsear_kml_secciones_vacio_sin_fuentes(monkeypatch):
    """Sin KML ni CSV de referencia, la función degrada a vacío (sin excepción)."""
    monkeypatch.setattr(geo, 'RUTA_REF_SECCIONES', 'referencia/inexistente.csv')
    assert geo.parsear_kml_secciones(ruta=KML_INEXISTENTE).empty