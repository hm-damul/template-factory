# -*- coding: utf-8 -*-
"""
evm_verifier.py

목적:
- MetaMask(EVM) 온체인 결제 검증.
- RPC로 트랜잭션/영수증 조회 후 수신 주소·금액·체인·상태 검증.
- 운영: MERCHANT_WALLET_ADDRESS, RPC_URL, CHAIN_ID 등은 환경변수로 설정.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


def _normalize_address(addr: Optional[str]) -> str:
    """EVM 주소 비교를 위해 소문자로 통일."""
    if not addr:
        return ""
    return str(addr).strip().lower()


def _rpc_call(rpc_url: str, method: str, params: list) -> Dict[str, Any]:
    """JSON-RPC 호출. 실패 시 예외 또는 에러 dict 반환."""
    try:
        resp = requests.post(
            rpc_url,
            json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
            timeout=30,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            return {"error": data["error"].get("message", "rpc_error")}
        return data
    except requests.exceptions.RequestException as e:
        logger.exception("RPC 요청 실패: %s", e)
        return {"error": f"rpc_request_failed: {e}"}
    except Exception as e:
        logger.exception("RPC 처리 중 예외: %s", e)
        return {"error": f"rpc_error: {e}"}


def get_transaction(rpc_url: str, tx_hash: str) -> Dict[str, Any]:
    """
    eth_getTransactionByHash로 트랜잭션 조회.
    반환: {ok, tx?} 또는 {ok: False, error}
    """
    out = _rpc_call(rpc_url, "eth_getTransactionByHash", [tx_hash.strip()])
    if "error" in out:
        return {"ok": False, "error": out["error"]}
    tx = out.get("result")
    if tx is None:
        return {"ok": False, "error": "tx_not_found"}
    return {"ok": True, "tx": tx}


def get_transaction_receipt(rpc_url: str, tx_hash: str) -> Dict[str, Any]:
    """
    eth_getTransactionReceipt로 영수증 조회.
    반환: {ok, receipt?} 또는 {ok: False, error}
    """
    out = _rpc_call(rpc_url, "eth_getTransactionReceipt", [tx_hash.strip()])
    if "error" in out:
        return {"ok": False, "error": out["error"]}
    receipt = out.get("result")
    if receipt is None:
        return {"ok": False, "error": "receipt_not_found"}
    return {"ok": True, "receipt": receipt}


def wei_to_int(hex_wei: Optional[str]) -> int:
    """0x 접두사 wei 값을 정수로 변환."""
    if not hex_wei:
        return 0
    s = str(hex_wei).strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    if not s:
        return 0
    return int(s, 16)


def verify_evm_payment(
    rpc_url: str,
    tx_hash: str,
    merchant_address: str,
    expected_amount_wei: int,
    chain_id: int,
    from_address: Optional[str] = None,
) -> Dict[str, Any]:
    """
    온체인 결제 검증.
    - receipt.status == 1 (성공)
    - tx.to == merchant_address (대소문자 무시)
    - tx.value >= expected_amount_wei
    - tx.from == from_address (제공된 경우)
    - chain_id는 호출측에서 이미 확인했다고 가정(선택적으로 receipt나 tx에서 검증 가능한 체인만 사용)

    반환:
      {ok: True, from_wallet, to_wallet, value_wei, block_number, ...}
      {ok: False, error: "reason", ...}
    """
    merchant_norm = _normalize_address(merchant_address)
    from_norm = _normalize_address(from_address) if from_address else None

    tx_res = get_transaction(rpc_url, tx_hash)
    if not tx_res.get("ok"):
        return {"ok": False, "error": tx_res.get("error", "tx_fetch_failed")}

    receipt_res = get_transaction_receipt(rpc_url, tx_hash)
    if not receipt_res.get("ok"):
        return {"ok": False, "error": receipt_res.get("error", "receipt_fetch_failed")}

    tx = tx_res["tx"]
    receipt = receipt_res["receipt"]

    # status: 0x1 = 성공, 0x0 = 실패
    status_hex = receipt.get("status", "0x0")
    try:
        status_int = wei_to_int(status_hex)
    except (ValueError, TypeError):
        status_int = 0
    if status_int != 1:
        return {"ok": False, "error": "tx_failed_on_chain", "status": status_hex}

    # to 주소 (native transfer의 수신자)
    to_addr = _normalize_address(tx.get("to"))
    if to_addr != merchant_norm:
        return {
            "ok": False,
            "error": "recipient_mismatch",
            "expected": merchant_norm,
            "got": to_addr,
        }

    value_wei = wei_to_int(tx.get("value"))
    if value_wei < expected_amount_wei:
        return {
            "ok": False,
            "error": "amount_insufficient",
            "expected_wei": expected_amount_wei,
            "got_wei": value_wei,
        }

    if from_norm is not None:
        tx_from = _normalize_address(tx.get("from"))
        if tx_from != from_norm:
            return {
                "ok": False,
                "error": "sender_mismatch",
                "expected": from_norm,
                "got": tx_from,
            }

    block_hex = receipt.get("blockNumber")
    block_num = wei_to_int(block_hex) if block_hex else 0

    return {
        "ok": True,
        "from_wallet": _normalize_address(tx.get("from")),
        "to_wallet": to_addr,
        "value_wei": value_wei,
        "block_number": block_num,
        "tx_hash": tx_hash.strip(),
    }
