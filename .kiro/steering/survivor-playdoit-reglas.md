---
inclusion: always
---

# Reglas del Survivor (PlayDoit) — lógica del juego

Estas son las reglas REALES del Survivor que juega el usuario en PlayDoit. El bot
debe optimizar para ellas. Son la fuente de verdad de la lógica de picks/estrategia.

## Mecánica
- **Eliminación directa por DERROTA.** Si el equipo elegido pierde, quedas
  eliminado. No hay segundas oportunidades.
- **EMPATE = "push".** Sobrevives, pero **no sumas punto**. Es supervivencia sin
  recompensa.
- **VICTORIA = punto.** Es lo que se busca: ganar asegura puntos.
- **1 pick por jornada, sin repetir equipo** en toda la temporada.
- **Fase regular = 17 jornadas** (Liga MX, 18 equipos, round-robin sencillo). Por
  lo tanto hay que usar ~17 equipos de los 18; uno se queda sin usar. (El usuario
  a veces dice "18"; el dato real son 17.)

## Objetivo de optimización (en orden de prioridad)
1. **Sobrevivir las 17 jornadas** (no perder NUNCA). Una sola derrota termina todo.
2. **Maximizar victorias** (puntos). El desempate entre ganadores del Survivor es
   **más victorias / menos empates**, así que ganar importa, no solo no-perder.
3. El **empate es un colchón de supervivencia** aceptable solo cuando no queda un
   equipo bueno y la jornada está muy pareja.

## Implicación estratégica (lo que el bot debe hacer)
- Es un **problema de asignación de temporada completa**: decidir en QUÉ jornada
  usar cada equipo, mirando todo el calendario, no jornada por jornada de forma
  miope. Hay que "guardar" equipos fuertes para jornadas difíciles y gastar a los
  equipos débiles en su matchup menos malo (de local vs rival flojo).
- Ejemplo del usuario: América es local vs Chivas en J5 (favorito moderado) pero
  visitante vs Atlante en J8 (favorito fuerte por momio). El bot decide en qué
  jornada conviene gastar a América considerando TODO el calendario.
- Requiere el **calendario completo de las 17 jornadas** (se publica cerca del
  arranque, ~17 de julio). Sin él, el planificador no puede correr completo.

## Señales reales disponibles (NO inventar nada)
- Modelo Poisson/Dixon-Coles sobre resultados reales de ESPN: P(ganar), P(empate),
  P(perder), goles esperados, por partido.
- Momios reales de odds-api.io (`comparador_mercado`) cuando hay cobertura
  (ventana de ~120 días; las jornadas lejanas no tendrán momios al inicio).
- Hallazgo medido (`analisis_riesgo`): el favorito del modelo gana solo ~52%; el
  favorito **visitante** falla ~58% vs ~44% del local. Priorizar favoritos locales
  y de alta confianza.

## Datos que NO tenemos (y por tanto no se deben fabricar)
- Alineaciones / titulares vs suplentes (API-Football bloqueada `PLAN_BLOCKED_2026`,
  ESPN no da XI probable). No afirmar "jugó con suplentes" como dato duro.
