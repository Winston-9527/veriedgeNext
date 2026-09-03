# Network Config

RPD uses concurrent sends with a shared requester-uplink bottleneck.

PPD publishes one ciphertext from requester to store, sends provider-specific access packages, then models parallel provider fetches from the store.

```json
{
  "LAN": {
    "requester_uplink_mbps": 940.0,
    "store_to_provider_mbps": 940.0,
    "rtt_ms": 2.0,
    "loss_pct": 0.0,
    "jitter_ms": 1.5
  },
  "WAN": {
    "requester_uplink_mbps": 40.0,
    "store_to_provider_mbps": 80.0,
    "rtt_ms": 80.0,
    "loss_pct": 1.0,
    "jitter_ms": 25.0
  }
}
```
