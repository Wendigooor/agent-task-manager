# Gold Standard — ATM Reference

## Что это

Карта связи между **Agent Task Manager (ATM)** и **Autonomous Delivery Gold Standard** (57KB, 405 mandatory steps, PvP Arena Season 1).

Gold Standard — это "конституция" автономной доставки. ATM — это "суд", который её исполняет.

```
Gold Standard (конституция)
    ↓ определяет
ATM gates (законы)
    ↓ исполняет
gate_agent.py (судья)
    ↓ производит
Verdict (приговор)
```

## Источник

Gold Standard — это внутренний стандарт автономной доставки: 57KB, 405 обязательных шагов, выделенных из реальных экспериментов по доставке фич. Он определяет что значит "done" для агентной работы.

## Как ATM реализует Gold Standard

### ATM Execution Layer (раздел Gold Standard)

Gold Standard требует:
```
If atm is available, agent must use it.
If atm is unavailable or unused, max verdict = partial.
Manual demo_done is invalid.
```

ATM покрывает это через:
- `bin/atm` — CLI entry point
- `gate_agent.py` — gate runner engine
- `gateboard.py` — ORM + SQLite schema + CLI logic
- `.atm/state.db` — SQLite база (auto-created)
- `.atm/logs/<run-id>/` — логи команд

### Gate Ledger Rule

Gold Standard требует:
- Gate ledger создаётся ДО реализации
- Каждый gate имеет id, severity, status, owner, notes, evidence refs
- Gates стартуют как `pending`
- Gates обновляются во время работы, не в конце
- Финальный verdict вычисляется из gate statuses

ATM покрывает через:
- `atm init-run --id <run> --profile demo --contract <path>` — создаёт run
- `atm import-gates --profile demo` — импортирует gates из встроенного профиля
- `6 tables` в SQLite: runs, gates, gate_events (append-only), evidence_refs, command_runs, verdicts
- Статусы: pending → in_progress → passed/failed/blocked
- Запрещённые транзишены (например `pending → passed` для command gates)

### Operating Modes

Gold Standard определяет 4 режима (Patch/Feature/Demo/Benchmark). ATM покрывает через 4 встроенных профиля:

| Профиль | Соответствует | Какие gates |
|---------|---------------|-------------|
| `patch` | Mode A: Patch | Базовые проверки (build/typecheck) |
| `feature` | Mode B: Feature | Discovery + реализация + evidence |
| `demo` | Mode C: Demo | Всё из feature + UI/E2E/визуал |
| `benchmark` | Mode D: Benchmark | Всё из demo + timebox + rubric |

### Verdict Logic

Gold Standard требует:
```
if critical gate failed → verdict = failed/partial
if major gate failed → verdict = partial
if all passed → verdict = demo_done
```

ATM реализует через `atm verdict`:
```python
if critical gate failed:       verdict = failed
elif critical gate pending:    verdict = technical_partial
elif all gates passed:         verdict = demo_done
elif major gate failed:        verdict = reviewable_partial
elif verify found contradiction: verdict = invalid
else:                          verdict = technical_partial
```

### Anti-False-Done Lock

Gold Standard содержит раздел Readiness Assertion And Honesty Gate. ATM реализует через review lifecycle:
- `atm prepare-review` — export + audit + bundle
- `atm review-status` — check artifacts + parse verdict
- `atm complete-review` — anti-false-done: fix-response ≠ approval

Критическое правило из Gold Standard:
```
If ATM verdict and prose summary disagree, the stricter status wins.
Manual demo_done is invalid.
```

ATM enforce через:
- `atm verify` — проверяет противоречия
- `atm verdict` — вычисляет статус из gate state, не из prose
- `atm complete-review` — блокирует `demo_done` если review не пройден

### Anti-Pattern Checklist (Gold Standard)

Из 18 анти-паттернов, ATM напрямую предотвращает:

| Анти-паттерн | Как ATM предотвращает |
|--------------|----------------------|
| Gate archive theater | `init-run` требует id, `import-gates` создаёт gates до кода |
| ATM bypass | `atm verify` проверяет что gates существуют |
| Verdict forgery | `atm verdict` вычисляется из gate state |
| Thin evidence | `pass` требует evidence path или note |
| Premature done | `complete-review` не пропустит без approve |

## Как использовать

```bash
# 1. Прочитать Gold Standard
open https://github.com/Wendigooor/puff/blob/main/evidence/pvp-arena-season-1/AUTONOMOUS_DELIVERY_GOLD_STANDARD.md

# 2. Создать run через ATM
atm init-run --id my-feature --profile demo --contract ORIGINAL_CONTRACT.md

# 3. Импортировать gates
atm import-gates --profile demo

# 4. Работать через gates
atm next           # → следующий gate
atm start --gate X # → начать
atm run --gate X --command 'npm run build'  # → выполнить
atm pass --gate X --evidence screenshots/01.png  # → подтвердить

# 5. Финализировать
atm verify
atm verdict
atm export --out evidence/my-feature/
atm prepare-review --id my-feature
atm complete-review --id my-feature  # → anti-false-done
```

## Chain of custody

```
PUFF (контрольная панель)
  ↓ вызывает
Hermes/Codex/OpenCode (агент)
  ↓ использует
ATM (gate runner)
  ↓ исполняет
Gold Standard (конституция)
```

ATM — это единственный слой где "закон" встречается с "исполнением". Без ATM Gold Standard — просто текст. Без Gold Standard ATM — просто CLI с SQLite.
