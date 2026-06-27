from fastapi import APIRouter, status, HTTPException, Query
from services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payment Provider Callbacks"])

@router.post("/webhook")
async def secure_payment_gateway_callback(tx_id: str = Query(..., alias="transaction_id")):
    """
    Universal external processor hook callback endpoint.
    Verifies state updates safely to prevent duplicate processing.
    """
    processing_state_success = await PaymentService.execute_webhook_completion(tx_id)
    if not processing_state_success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Transaction lookup failed or invoice already settled."
        )
    return {"status": "success", "detail": f"Account privileges updated for reference {tx_id}"}