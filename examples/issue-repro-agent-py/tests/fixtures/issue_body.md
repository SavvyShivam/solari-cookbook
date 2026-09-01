# `GET /widgets?limit=0` returns all widgets instead of none

## Steps to reproduce

```bash
curl 'http://localhost:5000/widgets?limit=0'
```

## Expected

An empty list `[]` — a limit of zero means return zero rows.

## Actual

All five widgets are returned. The handler uses `if limit:` and `0` is falsy,
so the slice is skipped entirely.

## Repro test

```python
def test_limit_zero_returns_empty():
    from app import app
    app.config.update(TESTING=True)
    resp = app.test_client().get("/widgets?limit=0")
    assert resp.status_code == 200
    assert resp.get_json() == []
```
