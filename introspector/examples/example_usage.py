from pathlib import Path

import httpx

from project_introspector import EventEmitter, instrument_function, scan_project

PROJECT_NAME = "demo-service"
ANALYZER_URL = "http://127.0.0.1:8015"

snapshot = scan_project(Path("./src"), project_name=PROJECT_NAME)
httpx.post(f"{ANALYZER_URL}/events/static", json=snapshot.model_dump(mode="json")).raise_for_status()

emitter = EventEmitter(endpoint=f"{ANALYZER_URL}/events/runtime", project_name=PROJECT_NAME, batch_size=1)


@instrument_function(emitter=emitter, capture_args=True, capture_result=True)
def create_invoice(customer_id: str, amount: int) -> dict:
    return {"customer_id": customer_id, "amount": amount}


if __name__ == "__main__":
    print(create_invoice("cust-1", 42))
    emitter.flush()

    schema_response = httpx.get(f"{ANALYZER_URL}/schema/{PROJECT_NAME}")
    schema_response.raise_for_status()
    print("schema:")
    print(schema_response.json())

    llm_status = httpx.get(f"{ANALYZER_URL}/llm/status")
    llm_status.raise_for_status()
    print("llm status:")
    print(llm_status.json())
