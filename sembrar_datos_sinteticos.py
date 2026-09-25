#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sembrar_datos_sinteticos.py
===========================

Genera registros sintéticos de campo de prueba para la Pestaña 1
(visitas "reales" de demo) usando la capa **local** (`modules.datos_locales`).

- Escribe en `data/registros_locales.csv` (gitignored, rápido).
- Con `--sincronizar` los sube a MongoDB Atlas (`registros_campo`) para que el
  equipo los vea en Streamlit Cloud (será persistente en Mongo).
- Los sintéticos se marcan con `brigadista='sintetico_*'` para poder
  limpiarlos con `--limpiar` (borra del local y, si hay conexión, de Mongo).

Uso:
    python sembrar_datos_sinteticos.py                 # 500 registros locales
    python sembrar_datos_sinteticos.py --n 1000
    python sembrar_datos_sinteticos.py --sincronizar   # genera y sube a Mongo
    python sembrar_datos_sinteticos.py --limpiar       # elimina sinteticos
"""

import argparse
import sys

sys.stdout.reconfigure(encoding='utf-8')

from modules.datos_locales import limpiar_sinteticos, sembrar_sinteticos, sincronizar_a_mongo


def main() -> None:
    parser = argparse.ArgumentParser(description='Genera datos sintéticos de campo.')
    parser.add_argument('--n', type=int, default=500, help='Número de registros')
    parser.add_argument('--sincronizar', action='store_true',
                        help='Después de generar, subir a MongoDB')
    parser.add_argument('--limpiar', action='store_true',
                        help='Eliminar los registros sintéticos (local y Mongo)')
    args = parser.parse_args()

    if args.limpiar:
        res = limpiar_sinteticos()
        print(f'🧹 Sintéticos eliminados del CSV local: {res.get("n", 0)}')
        from modules.datos_campo import conexion_ok
        if conexion_ok():
            from modules.datos_campo import coleccion
            col = coleccion('registros_campo')
            if col is not None:
                eliminados = col.delete_many({'brigadista': {'$regex': '^sintetico_'}}) \
                    .deleted_count
                print(f'🧹 Sintéticos eliminados de Mongo: {eliminados}')
        return

    res = sembrar_sinteticos(args.n)
    print(res.get('mensaje'))
    if args.sincronizar:
        print('--- Sincronizando a Mongo ---')
        sync = sincronizar_a_mongo()
        print(sync.get('mensaje'))


if __name__ == '__main__':
    main()