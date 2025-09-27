import asyncio
import json
import uuid
import nats

async def main():
    nc = None
    try:
        print("Connecting to NATS...")
        nc = await nats.connect('nats://qiki-nats-phase1:4222')
        print("Connected.")
        fut = asyncio.get_running_loop().create_future()

        async def handler(msg):
            print(f"Received response: {msg.data.decode()}")
            if not fut.done():
                fut.set_result(msg)

        await nc.subscribe('qiki.responses.control', cb=handler)
        print("Subscribed to response topic.")

        payload = {
            'command_name': 'PING',
            'parameters': {'echo': 'hello'},
            'metadata': {'message_id': str(uuid.uuid4()), 'source': 'checklist'}
        }
        
        print("Publishing PING command...")
        await nc.publish('qiki.commands.control', json.dumps(payload).encode())
        
        msg = await asyncio.wait_for(fut, timeout=5.0)
        print("--- NATS Round-trip Test Passed ---")
        # print(f"Response payload: {msg.data.decode()}")
    except Exception as e:
        print(f"--- NATS Round-trip Test FAILED: {e} ---")
    finally:
        if nc and nc.is_connected:
            await nc.close()
            print("Connection closed.")

if __name__ == "__main__":
    asyncio.run(main())