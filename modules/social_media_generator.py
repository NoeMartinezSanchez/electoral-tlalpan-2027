import random
from datetime import datetime, timedelta
import pandas as pd
from faker import Faker

TEMAS_ELECTORALES = {
    'Agua': ['agua', 'pipas', 'desabasto', 'huachicoleo', 'tinaco', 'pozo'],
    'Seguridad': ['seguridad', 'robo', 'extorsión', 'policía', 'cámaras', 'patrullas'],
    'Transporte': ['transporte', 'metrobús', 'bache', 'movilidad', 'tráfico', 'camión'],
    'Vivienda': ['vivienda', 'construcción', 'terreno', 'infonavit', 'renta'],
    'Empleo': ['empleo', 'trabajo', 'desempleo', 'chamba', 'salario'],
    'Educación': ['escuela', 'maestro', 'estudiante', 'colegio', 'universidad'],
    'Salud': ['salud', 'hospital', 'médico', 'clínica', 'enfermedad'],
    'Medio Ambiente': ['basura', 'árbol', 'parque', 'reciclaje', 'contaminación'],
    'Corrupción': ['corrupción', 'robo', 'gobierno', 'fraude', 'transparencia'],
    'Participación': ['voto', 'elección', 'ciudadano', 'participación', 'comunidad']
}

USUARIOS = [
    '@tlalpaneja_2027', '@votante_tlalpan', '@coapa_life', '@topilejo_activo',
    '@ciudadano_tlalpan', '@jovenes_coapa', '@mujeres_tlalpan', '@comunidad_topilejo',
    '@negocios_tlalpan', '@estudiantes_tlalpan', '@agua_tlalpan', '@seguridad_tlalpan'
]

TEMPLATES_POR_TEMA = {
    'Agua': [
        'El agua en Tlalpan es un problema grave, las pipas no llegan a las colonias altas.',
        'Necesitamos soluciones reales para el desabasto de agua en toda la demarcación.',
        'El huachicoleo de agua está afectando a la comunidad y nadie hace nada.',
        'Exigimos que el gobierno regule las pipas ilegales que cobran una fortuna.',
        'Por fin arreglaron la fuga de agua en nuestra calle en Coapa, ojalá dure.',
        'La falta de agua en San Miguel Topilejo ya lleva semanas, la situación es insostenible.',
        'El agua del pozo sale con lodo. Urge mantenimiento de la infraestructura hídrica.'
    ],
    'Seguridad': [
        'Los asaltos en el transporte público en Tlalpan van en aumento. ¡Seguridad ya!',
        'La policía de cuadrante respondió muy rápido hoy ante un reporte, excelente servicio.',
        'Me robaron el espejo del auto en Villa Coapa, hace falta mayor patrullaje nocturno.',
        'Necesitamos más cámaras de vigilancia en las zonas oscuras y parques públicos.',
        'Ayer reportaron detonaciones cerca del parque. Qué miedo vivir con esta inseguridad.',
        'Organización vecinal para instalar alarmas comunitarias ante falta de patrullas.'
    ],
    'Transporte': [
        'El tráfico en la salida a Cuernavaca es insoportable todos los viernes por la tarde.',
        'El Metrobús línea 1 va súper lleno por las mañanas, urge mejorar la frecuencia de paso.',
        'Muchos baches dañando llantas en la Picacho Ajusco. ¡Por favor reparen las avenidas!',
        'Buen viaje hoy en el transporte público, aunque hace falta más mantenimiento a los camiones.',
        'Tlalpan necesita un sistema de transporte masivo más eficiente para conectar los pueblos.'
    ],
    'Vivienda': [
        'Las rentas en Coapa están carísimas, los jóvenes ya no pueden independizarse aquí.',
        'Hay construcciones irregulares en suelo de conservación. Están destruyendo el bosque del Ajusco.',
        'Queremos créditos de vivienda digna e Infonavit accesibles para los trabajadores locales.',
        'La regularización de predios en las zonas altas debe ser ordenada y sin fines políticos.',
        'Los desarrollos inmobiliarios excesivos están acabando con el suministro de servicios públicos.'
    ],
    'Empleo': [
        'Buscando chamba en Tlalpan. Lamentablemente casi todo es informal o muy mal pagado.',
        'Falta apoyo a pequeños negocios locales en la alcaldía para reactivar el empleo.',
        'El desempleo entre los recién egresados universitarios está muy alto actualmente.',
        'Afortunadamente encontré un buen trabajo cerca de mi casa en Coapa, gran alivio.',
        'Queremos ferias de empleo locales permanentes con salarios y prestaciones dignas.'
    ],
    'Educación': [
        'Las escuelas públicas de la alcaldía necesitan mantenimiento urgente, baños muy sucios.',
        'Excelente labor de los maestros de la zona, a pesar de los pocos recursos escolares.',
        'Urgen más becas estudiantiles para evitar la deserción de jóvenes en nivel bachillerato.',
        'La UAM Xochimilco y otras universidades de la periferia necesitan mejor iluminación exterior.',
        'Faltan espacios recreativos y talleres culturales gratuitos para niños en los pueblos.'
    ],
    'Salud': [
        'Los hospitales de la zona de hospitales tienen tiempos de espera larguísimos y urgencias saturadas.',
        'Faltan medicamentos básicos y material de curación en el centro de salud de Topilejo.',
        'Excelente atención médica recibida hoy en la clínica local. Doctores y enfermeras muy atentos.',
        'Exigimos mejores instalaciones de salud pública y médicos 24 horas en zonas rurales.',
        'Las campañas de vacunación y prevención están funcionando adecuadamente en la alcaldía.'
    ],
    'Medio Ambiente': [
        'El Parque Nacional Cumbres del Ajusco está muy descuidado y lleno de basura de visitantes.',
        'Urge una campaña de reciclaje y recolección de basura eficiente para evitar inundaciones.',
        'Estamos reforestando el bosque de Tlalpan en una iniciativa ciudadana genial. ¡Súmense!',
        'Hay tiraderos de basura clandestinos en avenidas principales de la alcaldía, es un asco.',
        'Falta mantenimiento continuo a las áreas verdes y camellones públicos.'
    ],
    'Corrupción': [
        'Denuncian a funcionarios pidiendo moches para otorgar licencias de construcción.',
        'Queremos total transparencia en el presupuesto asignado a bacheo y obras viales en Tlalpan.',
        'Es indignante el desvío de recursos en programas sociales locales, ¡exigimos auditoría!',
        'El nuevo portal de la alcaldía facilita consultar contratos y gastos públicos.',
        'Reportes de nepotismo en la contratación de personal de oficinas centrales de la demarcación.'
    ],
    'Participación': [
        'Mi voto en las próximas elecciones de 2027 será para quien solucione el desabasto de agua.',
        'Ayer participamos en la asamblea vecinal, muy buena organización comunitaria para seguridad.',
        'Los ciudadanos debemos involucrarnos más en las decisiones del presupuesto participativo.',
        'No dejes de votar en los siguientes procesos. La participación ciudadana transforma comunidades.',
        'Excelente respuesta vecinal para limpiar las calles del centro histórico este fin de semana.'
    ]
}

def clasificar_sentimiento(texto: str) -> str:
    """
    Clasifica de manera simple y lógica el sentimiento de un texto post.
    """
    texto_lower = texto.lower()
    
    palabras_negativas = [
        'grave', 'desabasto', 'huachicoleo', 'insostenible', 'inseguridad',
        'asaltos', 'robo', 'miedo', 'tráfico', 'insoportable', 'baches', 'dañando',
        'carísimas', 'regulación', 'desempleo', 'informal', 'sucios', 'urgente',
        'saturadas', 'espera', 'descuidado', 'moches', 'corrupción', 'desvío', 'nepotismo'
    ]
    palabras_positivas = [
        'excelente', 'arreglaron', 'buen', 'digna', 'afortunadamente', 'buen viaje',
        'dignas', 'becas', 'atentos', 'reforestando', 'genial', 'transparencia',
        'involucrarnos', 'limpiar', 'participación'
    ]
    
    if any(p in texto_lower for p in palabras_negativas):
        return 'negativo'
    elif any(p in texto_lower for p in palabras_positivas):
        return 'positivo'
    else:
        return 'neutral'

def generar_texto_por_tema(tema: str) -> str:
    """
    Genera texto realista basado en el tema político seleccionado.
    """
    return random.choice(TEMPLATES_POR_TEMA.get(tema, ['Participemos activamente por el cambio en Tlalpan.']))

def generar_posts(n=500) -> pd.DataFrame:
    """
    Genera n posts simulados de redes sociales con métricas realistas y hashtags asociados.
    """
    posts = []
    fake = Faker('es_MX') # Inicializado para mantener concordancia con la regla del agente
    
    # Rango de fechas: últimos 30 días
    ahora = datetime.now()
    
    for i in range(n):
        # Seleccionar red social con pesos
        red = random.choices(
            ['TikTok', 'Facebook', 'X', 'Instagram'],
            weights=[0.28, 0.32, 0.18, 0.22]
        )[0]
        
        # Generar fecha aleatoria
        dias_atras = random.randint(0, 30)
        horas_atras = random.randint(0, 23)
        minutos_atras = random.randint(0, 59)
        fecha = ahora - timedelta(days=dias_atras, hours=horas_atras, minutes=minutos_atras)
        
        # Tema y texto
        tema = random.choice(list(TEMAS_ELECTORALES.keys()))
        texto = generar_texto_por_tema(tema)
        
        # Clasificar sentimiento
        sentimiento = clasificar_sentimiento(texto)
        
        # Hashtags dinámicos según el tema y generales
        tema_hashtag = f"#{tema.replace(' ', '')}"
        hashtags_posibles = [
            '#Tlalpan', '#Elecciones2027', '#Voto', '#CDMX', '#Participación', 
            '#VecinosTlalpan', '#AlcaldiaTlalpan', '#CambioTlalpan', tema_hashtag
        ]
        num_hashtags = random.randint(2, 5)
        hashtags = list(set(random.sample(hashtags_posibles, k=min(num_hashtags, len(hashtags_posibles)))))
        
        # Likes, comentarios y shares según la plataforma
        # TikTok suele tener interacciones más infladas que X
        multiplicador = {
            'TikTok': 3.5,
            'Facebook': 1.8,
            'Instagram': 2.0,
            'X': 1.0
        }[red]
        
        likes = int(random.randint(5, 800) * multiplicador)
        comentarios = int(random.randint(1, 150) * (multiplicador * 0.4))
        compartidos = int(random.randint(0, 90) * (multiplicador * 0.3))
        
        posts.append({
            'id_post': 1000 + i + 1,
            'red_social': red,
            'usuario': random.choice(USUARIOS),
            'fecha': fecha,
            'texto': texto,
            'hashtags': hashtags,
            'likes': likes,
            'comentarios': comentarios,
            'compartidos': compartidos,
            'sentimiento': sentimiento,
            'tema_electoral': tema
        })
        
    df = pd.DataFrame(posts)
    df['engagement'] = df['likes'] + df['comentarios'] + df['compartidos']
    # engagement_rate simulado (engagement / seguidores ficticios)
    # Generamos un número de seguidores ficticio por post y calculamos
    seguidores_ficticios = [random.randint(500, 15000) for _ in range(len(df))]
    df['engagement_rate'] = round((df['engagement'] / seguidores_ficticios) * 100, 2)
    
    # Ordenar por fecha de forma descendente para simular feeds reales
    df = df.sort_values(by='fecha', ascending=False).reset_index(drop=True)
    return df
