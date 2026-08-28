import pytest
from fastapi.testclient import TestClient
from main import app, state_store
from student_registration_agent import (
    RegistrationState,
    prospect_capture_node,
    check_alternative_program_node,
    send_offer_node,
    student_response_node,
    fee_and_id_generation_node,
    final_sis_sync_node,
    route_after_evaluation,
    route_after_student_response,
)

client = TestClient(app)

# ---------------------------------------------------------------------------
# Unit Tests: State Graph Node & Routing Logic
# ---------------------------------------------------------------------------

def test_prospect_capture_node():
    initial_state: RegistrationState = {
        "prospect_id": "LEAD-1001",
        "student_name": "Alexander Wright",
        "student_email": "alex@example.com",
        "target_program": "BSc in Computer Science",
        "transcript_text": "GPA: 3.8",
        "is_qualified": None,
        "alternative_program": None,
        "offer_sent": False,
        "student_accepted": None,
        "registration_fee_paid": False,
        "student_id": None,
        "sis_sync_completed": False,
        "current_status": "PENDING",
        "logs": []
    }
    result = prospect_capture_node(initial_state)
    assert result["current_status"] == "PROSPECT_CONFIRMED"
    assert len(result["logs"]) == 1


def test_routing_logic_qualified_and_alternative():
    qualified_state: RegistrationState = {"is_qualified": True}
    assert route_after_evaluation(qualified_state) == "send_offer"

    unqualified_state: RegistrationState = {"is_qualified": False}
    assert route_after_evaluation(unqualified_state) == "check_alternative"


def test_fee_verification_and_id_minting():
    unpaid_state: RegistrationState = {
        "prospect_id": "LEAD-9988",
        "registration_fee_paid": False,
        "student_id": None,
        "current_status": "OFFER_ACCEPTED",
        "logs": []
    }
    res_unpaid = fee_and_id_generation_node(unpaid_state)
    assert res_unpaid["current_status"] == "FEE_PENDING"
    assert res_unpaid["student_id"] is None

    paid_state: RegistrationState = {
        "prospect_id": "LEAD-9988",
        "registration_fee_paid": True,
        "student_id": None,
        "current_status": "OFFER_ACCEPTED",
        "logs": []
    }
    res_paid = fee_and_id_generation_node(paid_state)
    assert res_paid["current_status"] == "ID_ISSUED"
    assert res_paid["student_id"] == "26-REG-9988"


# ---------------------------------------------------------------------------
# Integration Tests: API Webhook Endpoints
# ---------------------------------------------------------------------------

def test_full_pipeline_api_flow():
    # 1. Ingest Inbound Prospect
    inbound_payload = {
        "student_name": "Sarah Connor",
        "student_email": "sarah@example.com",
        "target_program": "BSc in Computer Science",
        "transcript_text": "GPA: 3.9, Pure Math: A, Advanced Physics: A"
    }
    res_ingest = client.post("/api/v1/prospects/inbound", json=inbound_payload)
    assert res_ingest.status_code == 202
    data = res_ingest.json()
    prospect_id = data["prospect_id"]
    assert prospect_id.startswith("LEAD-")

    # Manually transition state for deterministic API test
    state_store[prospect_id]["offer_sent"] = True
    state_store[prospect_id]["current_status"] = "OFFER_SENT"

    # 2. Accept Offer
    res_accept = client.post(f"/api/v1/admissions/{prospect_id}/offer-response", json={"accepted": True})
    assert res_accept.status_code == 200
    assert res_accept.json()["status"] == "OFFER_ACCEPTED"

    # 3. Simulate Payment Webhook
    pay_payload = {
        "prospect_id": prospect_id,
        "amount_paid": 500.0,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "transaction_reference": "TXN-UNIT-TEST-123"
    }
    res_pay = client.post("/api/v1/finance/webhooks/payment", json=pay_payload)
    assert res_pay.status_code == 200

    # 4. Check Final Status
    res_status = client.get(f"/api/v1/students/{prospect_id}/status")
    assert res_status.status_code == 200
    final_data = res_status.json()
    assert final_data["prospect_id"] == prospect_id
    assert final_data["student_name"] == "Sarah Connor"


def test_premature_payment_rejection():
    # Generate record without offer acceptance
    prospect_id = "LEAD-LOCKED1"
    state_store[prospect_id] = {
        "prospect_id": prospect_id,
        "student_name": "John Doe",
        "student_email": "john@example.com",
        "target_program": "BSc in Computer Science",
        "transcript_text": "GPA: 3.5",
        "is_qualified": True,
        "alternative_program": None,
        "offer_sent": True,
        "student_accepted": None,
        "registration_fee_paid": False,
        "student_id": None,
        "sis_sync_completed": False,
        "current_status": "OFFER_SENT",
        "logs": []
    }

    pay_payload = {
        "prospect_id": prospect_id,
        "amount_paid": 500.0,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "transaction_reference": "TXN-PREMATURE"
    }
    response = client.post("/api/v1/finance/webhooks/payment", json=pay_payload)
    assert response.status_code == 400
    assert "Student must accept offer prior to fee payment" in response.json()["detail"]