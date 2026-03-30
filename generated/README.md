# Generated Protobuf Stubs

This directory stores Python protobuf/grpc stubs generated from `protos/`.

Primary generation command:

```bash
bash tools/gen_protos.sh
```

Runtime bootstrap helper:

```bash
bash tools/ensure_generated.sh
```

Services that import `generated.*` must call `ensure_generated.sh` before startup.
