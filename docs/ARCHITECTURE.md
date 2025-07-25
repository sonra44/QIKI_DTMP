# Архитектура QIKI_DTMP

## Обзор

Три сервиса:

* Q-Sim Service
* Q-Core Agent
* Q-Operator Console

## Протоколы

* gRPC (protobuf) для межсервисного общения
* HTTP/JSON для Operator Console (опционально)

## Наблюдаемость

* structlog/json
* trace_id
* healthz/readyz
* Prometheus metrics

## Конфиги (DSL)

* config/fsm_transitions.yaml
* config/rules.yaml
* config/degradation.yaml
