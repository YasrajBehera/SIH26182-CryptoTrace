# Initial API contracts

## Health
GET `/api/v1/health`

## Investigation
POST `/api/v1/investigations`

Request:
```json
{
  "address": "PUBLIC_WALLET_ADDRESS"
}
```

Response:
```json
{
  "wallet": "PUBLIC_WALLET_ADDRESS",
  "status": "created",
  "transactions": [],
  "message": "Blockchain ingestion module is not connected yet."
}
```

These contracts will evolve as modules are implemented. Avoid changing shared contracts without discussing the change with the team.
