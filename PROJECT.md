# Synth Test

## Status & Sprint
- **Status**: Inicialización (sin implementación funcional)
- **Sprint goal**: Crear estructura base y formalizar el proyecto para desarrollo futuro

## Problema
Los equipos prueban APIs/pipelines de datos solo con casos "felices" que ellos mismos imaginan, dejando pasar bugs en casos límite (valores nulos, unicode raro, números extremos, formatos inesperados) que aparecen en producción.

## Mercado
Equipos de QA/backend que prueban APIs, equipos de datos que validan pipelines ETL, equipos de ML que prueban robustez de modelos ante inputs adversariales simples.

## Valor profesional
Demuestra dominio de testing basado en propiedades (property-based testing), generación de datos sintéticos guiada por esquema, y pensamiento adversarial sobre el propio software.

## Diferenciación
No es "otro generador de datos de prueba". Genera casos diseñados para romper basándose en categorías conocidas de bugs (boundary values, type confusion, encoding issues, casos estructuralmente extraños) a partir del esquema (OpenAPI/JSON Schema), no de datos aleatorios sin criterio.

## Modelo de negocio
CLI/librería open source gratuita; SaaS de pago para "fuzzing continuo" integrado en CI con reportes históricos de regresiones encontradas. **Sin tecnologías de pago en el stack**.

## Stack recomendado
- **Lenguaje:** Python (ecosistema maduro de property-based testing: Hypothesis como base conceptual). Sin costo.
- **Framework:** Construido sobre/inspirado en Hypothesis, extendido con generadores conscientes de esquema (JSON Schema/OpenAPI). Sin costo.
- **Base de datos:** Ninguna en el core (CLI stateless); SQLite/Postgres en la versión SaaS para histórico de "casos rompedores" encontrados. Sin costo en MVP.
- **Cloud:** N/A para el core. Sin costo.
- **APIs:** Lee especificaciones OpenAPI/JSON Schema como entrada; ejecuta requests HTTP reales contra el API objetivo en modo de prueba. Sin costo.
- **Infraestructura:** Ejecutable en CI como cualquier suite de tests. Sin costo.
- **Obs devise:** Reporte detallado de cada caso que causó fallo, con el input exacto para reproducibilidad ("shrinking" del caso mínimo que reproduce el bug). Sin costo.
- **Testing:** El propio proyecto se valida con meta-tests (probar que el generador efectivamente encuentra bugs inyectados deliberadamente en APIs de prueba). Sin costo.
- **Seguridad:** Modo de ejecución sandboxed con advertencia y confirmación explícita de entorno de prueba (para no usarse como herramienta de ataque).

## Requisitos funcionales
- Generar casos de prueba a partir de un esquema OpenAPI/JSON Schema cubriendo: valores límite, tipos incorrectos, nulos/vacíos, unicode/encoding extraño, tamaños extremos.
- Ejecutar los casos contra el endpoint objetivo y clasificar respuestas (esperado vs. error 5xx vs. comportamiento inconsistente).
- "Shrinking" automático: reducir un caso de fallo complejo al caso mínimo reproducible.
- Reporte exportable (JSON/HTML) con los casos que rompieron el sistema.
- Modo de integración en CI con umbral de fallo configurable.

## Requisitos no funcionales
- No debe generar tráfico que pueda interpretarse como ataque real (rate limiting propio, modo explícito "solo entornos de prueba").
- Reproducibilidad: cada caso generado debe ser re-ejecutable de forma determinista con una semilla.
- Tiempo de ejecución de una suite completa configurable (modo rápido en CI vs. modo exhaustivo nocturno).

## Arquitectura
A partir de un esquema, el generador construye un árbol de "estrategias" de generación por tipo de campo (string, número, enum, objeto anidado), cada una con generadores específicos de casos límite conocidos. Un motor de ejecución envía los casos generados al endpoint objetivo, captura la respuesta y la compara contra el contrato esperado (código de estado, esquema de respuesta). Cuando se detecta un fallo, el motor de shrinking reduce iterativamente el caso a su forma mínima reproducible antes de reportarlo.

## MVP
Generador para JSON Schema con 5 categorías de casos límite, ejecutor HTTP básico, reporte en terminal.

## Roadmap
- **V1:** Generador core + ejecutor HTTP + reporte terminal.
- **V2:** Soporte OpenAPI completo, shrinking automático, integración CI.
- **V3:** SaaS de fuzzing continuo con histórico de regresiones y dashboard.

## Complejidad
Media-Alta

## Tiempo estimado
2-3 semanas

## Impacto GitHub
7/10

## Valor empleabilidad
8/10
