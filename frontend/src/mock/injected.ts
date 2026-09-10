import type { BlockchainTransfer, GraphEdge } from "@/api/types";

/**
 * Bridge helper — converts a synthetic graph edge into a synthetic transfer
 * record so the existing transaction drawer can be reused. Demo-only.
 */
export function INJECTED_TRANSFER(edge: GraphEdge): BlockchainTransfer {
  return {
    transaction_hash: edge.transactionHash,
    block_number: null,
    block_timestamp: edge.timestamp,
    from_address: edge.source == null ? "" : edge.source.toLowerCase(),
    to_address: "",
    value: edge.amount,
    asset: edge.asset,
    category: edge.asset === "ETH" ? "external" : "erc20",
    direction: "out",
    raw_contract_address: edge.asset !== "ETH" ? "0x0000000000000000000000000000000000000000" : null,
    raw_contract_value: null,
    chain: "eth",
  };
}