import os
import uuid
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

from student_registration_agent import registration_agent, RegistrationState

app = FastAPI(
    title="Campus Agentic Registration Sidecar API",
    version="1.0.0",
    docs_url="/docs"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

state_store: Dict[str, RegistrationState] = {}

class ProspectInboundDTO(BaseModel):
    student_name: str = Field(..., json_schema_extra={"example": "Alexander Wright"})
    student_email: EmailStr = Field(..., json_schema_extra={"example": "alex.wright@example.com"})
    target_program: str = Field(..., json_schema_extra={"example": "BSc in Computer Science"})
    transcript_text: str = Field(..., json_schema_extra={"example": "GPA: 3.8. Math: A, Physics: A, English: B+"})

class StudentOfferResponseDTO(BaseModel):
    accepted: bool = Field(..., description="True if student accepts the offer")

class PaymentWebhookDTO(BaseModel):
    prospect_id: str
    amount_paid: float
    currency: str = "USD"
    payment_status: str = Field(..., json_schema_extra={"example": "COMPLETED"})
    transaction_reference: str

@app.post("/api/v1/prospects/inbound", status_code=status.HTTP_202_ACCEPTED)
async def ingest_prospect_webhook(
    payload: ProspectInboundDTO,
    background_tasks: BackgroundTasks
):
    prospect_id = f"LEAD-{uuid.uuid4().hex[:6].upper()}"
    
    initial_state: RegistrationState = {
        "prospect_id": prospect_id,
        "student_name": payload.student_name,
        "student_email": payload.student_email,
        "target_program": payload.target_program,
        "transcript_text": payload.transcript_text,
        "is_qualified": None,
        "alternative_program": None,
        "offer_sent": False,
        "student_accepted": None,
        "registration_fee_paid": False,
        "student_id": None,
        "sis_sync_completed": False,
        "current_status": "PROSPECT_CONFIRMED",
        "logs": [f"[Stage 1] Ingested lead {prospect_id} from Marketing Module."]
    }
    
    state_store[prospect_id] = initial_state

    def run_evaluation_and_offer():
        current_state = state_store[prospect_id]
        updated_state = registration_agent.invoke(current_state)
        state_store[prospect_id] = updated_state

    background_tasks.add_task(run_evaluation_and_offer)
    
    return {
        "message": "Prospect ingested. Agent evaluation running in background.",
        "prospect_id": prospect_id,
        "status": "EVALUATION_IN_PROGRESS"
    }

@app.post("/api/v1/admissions/{prospect_id}/offer-response")
async def student_offer_response_webhook(
    prospect_id: str,
    payload: StudentOfferResponseDTO
):
    if prospect_id not in state_store:
        raise HTTPException(status_code=404, detail="Prospect record not found")
        
    current_state = state_store[prospect_id]
    current_state["student_accepted"] = payload.accepted
    
    if payload.accepted:
        current_state["current_status"] = "OFFER_ACCEPTED"
        current_state["logs"].append("[Stage 3] Student accepted the admission offer.")
        message = "Offer accepted. Please proceed to registration fee payment."
    else:
        current_state["current_status"] = "CLOSED"
        current_state["logs"].append("[Stage 3] Student declined the admission offer. Process closed.")
        message = "Offer declined. Application marked as CLOSED."
        
    state_store[prospect_id] = current_state
    return {"prospect_id": prospect_id, "status": current_state["current_status"], "message": message}

@app.post("/api/v1/finance/webhooks/payment")
async def finance_payment_webhook(
    payload: PaymentWebhookDTO,
    background_tasks: BackgroundTasks
):
    prospect_id = payload.prospect_id
    if prospect_id not in state_store:
        raise HTTPException(status_code=404, detail="Prospect record not found")
        
    if payload.payment_status != "COMPLETED":
        return {"message": "Payment not completed. No action taken."}

    current_state = state_store[prospect_id]
    if current_state.get("current_status") != "OFFER_ACCEPTED":
        raise HTTPException(status_code=400, detail="Student must accept offer prior to fee payment")

    current_state["registration_fee_paid"] = True
    current_state["logs"].append(f"[Stage 4] Fee confirmed via TxRef: {payload.transaction_reference}.")
    state_store[prospect_id] = current_state

    def run_id_and_sis_sync():
        updated_state = registration_agent.invoke(state_store[prospect_id])
        state_store[prospect_id] = updated_state

    background_tasks.add_task(run_id_and_sis_sync)

    return {
        "message": "Payment verified. Generating Student ID and syncing with SIS.",
        "prospect_id": prospect_id
    }

@app.get("/api/v1/students/{prospect_id}/status")
async def get_registration_status(prospect_id: str):
    if prospect_id not in state_store:
        raise HTTPException(status_code=404, detail="Prospect record not found")
        
    record = state_store[prospect_id]
    return {
        "prospect_id": record["prospect_id"],
        "student_name": record["student_name"],
        "program": record["target_program"],
        "status": record["current_status"],
        "is_qualified": record["is_qualified"],
        "student_id": record["student_id"],
        "sis_synced": record["sis_sync_completed"],
        "history_logs": record["logs"]
    }