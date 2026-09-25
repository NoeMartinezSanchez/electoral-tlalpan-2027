#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_conexion_mongo.py
======================

Script de verificación local para la **Pestaña 1 (datos de campo)**:

1. Conecta a MongoDB Atlas (lee `[MONGO]` de `.streamlit/secrets.toml`).
2. Importa las **355 secciones del IECM** (KML) a la colección `secciones`.
3. Inserta **registros de prueba** en `registros_campo`.
4. Lee el resumen y el estado por sección (cobertura / intención).
5. Por defecto limpia los registros de prueba al final (usa `--keep` para no borrarlos).

Requisitos: estar sin VPN/red que interfiera con `*.mongodb.net`, y tener tu IP
permitida en Atlas → Network Access. Se ejecuta con:
    python test_conexion_mongo.py            # importa + prueba + limpia
    python test_conexion_mongo.py --keep     # conserva los registros de prueba
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')


def _leer_secrets() -> dict:
    """Lee URI/DB de `[MONGO]` en .streamlit/secrets.toml."""
    ruta = Path('.streamlit/secrets.toml')
    if not ruta.exists():
        print('[ERROR] No existe .streamlit/secrets.toml')
        sys.exit(1)
    bloque = re.search(r'\[MONGO\](.*?)(?:\[[A-Z_]+\]|\Z)',
                       ruta.read_text(encoding='utf-8'), re.DOTALL)
    if not bloque or 'URI' not in bloque.group(1):
        print('[ERROR] Falta la sección [MONGO] con URI en los Secrets.')
        sys.exit(1)
    uri = re.search(r'URI\s*=\s*["\']([^"\']+)["\']', bloque.group(1)).group(1)
    db = re.search(r'DB\s*=\s*["\']([^"\']+)["\']', bloque.group(1))
    return {'URI': uri, 'DB': db.group(1) if db else 'electoral_tlalpan'}


def main() -> None:
    parser = argparse.ArgumentParser(description='Verifica Mongo + importa IECM + inserta prueba.')
    parser.add_argument('--keep', action='store_true',
                        help='Conservar los registros de prueba (default: limpia al final).')
    args = parser.parse_args()

    cfg = _leer_secrets()
    print(f"[1] Conectando a MongoDB Atlas ({cfg['DB']}) ...")
    from pymongo import MongoClient
    cliente = MongoClient(cfg['URI'], serverSelectionTimeoutMS=8000)
    cliente.admin.command('ping')
    db = cliente[cfg['DB']]
    print('    ✔ Conexión OK')

    from modules.geo import parsear_colonias_iecm, parsear_kml_secciones

    print('[2] Importando colonias IECM (shapefile) -> colonias ...')
    df_col = parsear_colonias_iecm()
    if df_col.empty:
        print('    ✘ No se pudo parsear el shapefile de colonias (revisa documentos/inegi/)')
    else:
        col_colonias = db['colonias']
        for _, fila in df_col.iterrows():
            doc = {c: fila[c] for c in df_col.columns}
            doc['fuente'] = 'Colonias IECM (shapefile)'
            col_colonias.update_one({'cve': str(fila['cve'])}, {'$set': doc}, upsert=True)
        print(f'    ✔ {len(df_col)} colonias de Tlalpan importadas/actualizadas')

    print('[3] Importando secciones del IECM (KML) -> secciones ...')
    df = parsear_kml_secciones()
    if df.empty:
        print('    ✘ No se pudo parsear el KML (revisa documentos/Marco geografico electoral/)')
        cliente.close()
        sys.exit(1)
    col_sec = db['secciones']
    for _, fila in df.iterrows():
        doc = {c: fila[c] for c in df.columns if c != 'geometry_geojson'}
        doc['geometry_geojson'] = fila['geometry_geojson']
        doc['fuente'] = 'Marco Geográfico Electoral IECM 2021'
        col_sec.update_one({'id_seccion': int(fila['id_seccion'])}, {'$set': doc}, upsert=True)
    print(f'    ✔ {len(df)} secciones importadas/actualizadas en secciones')

    print('[4] Insertando registros de prueba en registros_campo ...')
    col_reg = db['registros_campo']
    sec_prueba = int(df.iloc[0]['id_seccion'])
    regs = [
        {'seccion_id': sec_prueba, 'tipo': 'simpatia', 'intencion': 'a_favor',
         'queja_texto': 'Muy buena la jornada de campo', 'queja_categoria': 'SIN_QUEJA',
         'queja_sentimiento': 'positivo', 'brigadista': 'prueba_sistema',
         'fecha': datetime.now().isoformat(), 'fuente': 'real'},
        {'seccion_id': sec_prueba, 'tipo': 'simpatia', 'intencion': 'indeciso',
         'queja_texto': '', 'queja_categoria': 'SIN_QUEJA',
         'queja_sentimiento': 'neutral', 'brigadista': 'prueba_sistema',
         'fecha': datetime.now().isoformat(), 'fuente': 'real'},
        {'seccion_id': sec_prueba, 'tipo': 'queja', 'intencion': None,
         'queja_texto': 'El tinaco lleva semanas vacío y las pipas no llegan',
         'queja_categoria': 'AGUA', 'queja_sentimiento': 'negativo',
         'brigadista': 'prueba_sistema', 'fecha': datetime.now().isoformat(),
         'fuente': 'real'},
    ]
    ids = col_reg.insert_many(regs).inserted_ids
    print(f'    ✔ {len(ids)} registros insertados en la sección {sec_prueba}')

    print('[5] Resumen y estado por sección ...')
    total = col_reg.count_documents({})
    sim = {i: col_reg.count_documents({'intencion': i}) for i in ('a_favor', 'indeciso', 'en_contra')}
    q_agua = col_reg.count_documents({'queja_categoria': 'AGUA'})
    print(f'    total registros: {total} | simpatías 💚{sim["a_favor"]} 💛{sim["indeciso"]} ❤️{sim["en_contra"]} | quejas AGUA: {q_agua}')

    import pandas as pd
    docs = list(col_reg.find({}, {'_id': 0}))
    reg_df = pd.DataFrame(docs)
    sec_app = col_sec.find_one({'id_seccion': sec_prueba}, {'_id': 0})
    base = float(sec_app.get('lista_nominal') or 0)
    n = len(reg_df[reg_df['seccion_id'] == sec_prueba])
    print(f'    cobertura sección {sec_prueba}: {n} registros / {int(base)} lista nominal = '
          f'{min(100.0, n/base*100):.2f}%')

    print('[6] LIMPIEZA')
    if args.keep:
        print('    --keep activo: los registros de prueba se conservan.')
    else:
        col_reg.delete_many({'brigadista': 'prueba_sistema'})
        print(f'    ✔ Registros de prueba eliminados (total restante: {col_reg.count_documents({})})')

    cliente.close()
    print('\n✔ PRUEBA LOCAL COMPLETA: Mongo + IECM + registros funcionan.')


if __name__ == '__main__':
    main()