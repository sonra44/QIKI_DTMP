1. В чём была проблема

`OrionVApp` жёстко использовал `ORIONV_PROCEDURES_DIR` или default `/workspace/config/orion_v/procedures`. В canonical container contour это корректно, но в локальном запуске и в `pytest` без внешнего env этот путь мог не существовать или существовать пустым, из-за чего `ProcedureEngine` загружал `0 procedures` и ORION-тесты падали из-за bootstrap/path, а не из-за business logic.

2. Где была хрупкость path resolution

- [`src/qiki/services/operator_console/orion_v/app.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py) напрямую делал `os.getenv("ORIONV_PROCEDURES_DIR", "/workspace/config/orion_v/procedures")`.
- [`src/qiki/services/operator_console/orion_v/procedure_engine.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/procedure_engine.py) честно загружал только из переданного каталога и не участвовал в resolution chain.
- canonical container overlay [`docker-compose.operator.yml`](/home/sonra44/QIKI_DTMP/docker-compose.operator.yml) монтирует `./config` в `/workspace/config`, поэтому runtime в контейнере был рабочим и скрывал проблему локального/тестового bootstrap.

3. Какие файлы изменены

- [`src/qiki/services/operator_console/orion_v/procedure_engine.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/procedure_engine.py)
- [`src/qiki/services/operator_console/orion_v/app.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py)
- [`tests/unit/test_orion_v_procedure_engine.py`](/home/sonra44/QIKI_DTMP/tests/unit/test_orion_v_procedure_engine.py)
- [`TASK_OUT/orion_procedure_path_fix.md`](/home/sonra44/QIKI_DTMP/TASK_OUT/orion_procedure_path_fix.md)

4. Как теперь определяется procedures directory

Новый priority order:

1. Явный `ORIONV_PROCEDURES_DIR`, если задан.
2. Canonical `/workspace/config/orion_v/procedures`, если там реально есть procedure files.
3. `QIKI_REPO_ROOT/config/orion_v/procedures`, если задан `QIKI_REPO_ROOT` и там есть procedure files.
4. Repo-relative autodiscovery от `procedure_engine.py` вверх по дереву до первого `config/orion_v/procedures`, где реально есть procedure files.
5. Если файлов не найдено нигде, возвращается первый существующий кандидат; если не существует ничего, остаётся canonical `/workspace/config/orion_v/procedures`.

Это означает: explicit override по-прежнему authoritative, canonical container path остаётся первым non-explicit кандидатом, а local/pytest получают устойчивый fallback к repo config.

5. Почему canonical runtime behavior не сломан

- `main_orion_v.py` не менялся как entrypoint.
- `docker-compose.operator.yml` не менялся.
- В canonical container contour `/workspace/config/orion_v/procedures` по-прежнему первый default-кандидат и будет выбран, если там есть реальные procedure files.
- Семантика `ProcedureEngine`, JSON procedures, subjects, ownership и decision logic не менялись.
- Explicit env override `ORIONV_PROCEDURES_DIR` всё ещё имеет наивысший приоритет.

6. Какие тесты добавлены/обновлены

- В [`tests/unit/test_orion_v_procedure_engine.py`](/home/sonra44/QIKI_DTMP/tests/unit/test_orion_v_procedure_engine.py) добавлен тест на fallback с пустого `/workspace`-подобного каталога на repo-root procedures.
- Там же добавлен тест, что `OrionVApp()` без внешних `ORIONV_PROCEDURES_DIR` и `QIKI_REPO_ROOT` всё равно загружает repo-relative procedures в обычном локальном/pytest режиме.

7. Как локально и в контейнере теперь должен работать ORION

- В контейнере ORION продолжает брать процедуры из `/workspace/config/orion_v/procedures` без изменения canonical behavior.
- Локально из репозитория `python main_orion_v.py` и unit tests больше не зависят от ручного внешнего `ORIONV_PROCEDURES_DIR`, если repo содержит `config/orion_v/procedures`.
- Если разработчик хочет override, он всё ещё может явно задать `ORIONV_PROCEDURES_DIR`.
