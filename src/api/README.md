# API

Request/response models and handler facade that connects transport layers (REST/gRPC/UI/queue) to the orchestrator.

`handler.py` exposes a `RequestHandler.handle` method so a server can simply parse the incoming payload into `QueryRequest` and delegate.
