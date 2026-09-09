# Initial API contracts

## Health
GET `/api/v1/health`

## Wallet transfers (Member 1)
GET `/api/v1/wallets/{address}/transfers`

Optional query param: `limit` (1-10000).

Response:
```json
{
  "wallet_address": "0x...",
  "chain": "eth",
  "transfers": [
    {
      "transaction_hash": "0x...",
      "block_number": 123,
      "block_timestamp": "2023-01-01T00:00:00Z",
      "from_address": "0x...",
      "to_address": "0x...",
      "value": "1000",
      "asset": "USDT",
      "category": "erc20",
      "direction": "in",
      "raw_contract_address": "0x...",
      "raw_contract_value": "0x3e8",
      "chain": "eth"
    }
  ],
  "pagination": {
    "max_transfers": 1000,
    "fetched": 1,
    "truncated": false
  }
}
```

Status codes: `200` success, `400` invalid address, `502` provider/API failure
or missing API key, `500` unexpected internal error.

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
  "message": "Use GET /api/v1/wallets/{address}/transfers for blockchain ingestion."
}
```

These contracts will evolve as modules are implemented. Avoid changing shared contracts without discussing the change with the team.
