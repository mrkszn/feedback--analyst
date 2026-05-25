# api.main.health

## Назначение

`GET /health` — простейший liveness-чек для платформенного health-probe (Fly/Railway/Kubernetes).

## Сигнатура

```python
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

## Шаги

Тривиально — возврат `{"status": "ok"}` со статусом 200.

## Тесты

`tests/test_api_health.py`:
- `test_health_returns_ok` — `TestClient(app).get("/health")` → 200 + `{"status":"ok"}`.

## /goal

`GET /health` → 200; тест зелёный.

## Next

— (конец v1 цепочки)
