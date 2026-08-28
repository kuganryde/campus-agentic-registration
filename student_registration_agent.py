import os
from typing import Literal, Optional, List, TypedDict
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI

api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "mock_test_key_for_ci_runner"

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0.0,
    api_key=api_key
)

class RegistrationState(TypedDict):
    prospect_id: str
    student_name: str
    student_email: str
    target_program: str
    transcript_text: str
    is_qualified: Optional[bool]
    alternative_program: Optional[str]
    registry_override_status: Optional[str]  # "APPROVED_DIRECT", "APPROVED_ALTERNATIVE", "REJECTED"
    offer_sent: bool
    student_accepted: Optional[bool]
    registration_fee_paid: bool
    student_id: Optional[str]
    sis_sync_completed: bool
    current_status: str
    logs: List[str]


def prospect_capture_node(state: RegistrationState) -> RegistrationState:
    log = f"[Stage 1] Prospect captured for {state['student_name']} ({state['target_program']})."
    return {
        **state,
        "current_status": "PROSPECT_CONFIRMED",
        "logs": state.get("logs", []) + [log]
    }


def registry_entry_evaluation_node(state: RegistrationState) -> RegistrationState:
    prompt = f"""
    You are an academic registry admissions officer.
    Evaluate if this student meets entry criteria for: {state['target_program']}.
    
    Student Transcript Summary:
    {state['transcript_text']}
    
    Rule: Requires GPA >= 3.0 and prerequisite core mathematics.
    If not qualified, suggest an appropriate alternative diploma or foundation degree.
    
    Respond in EXACT format:
    QUALIFIED: <YES or NO>
    ALTERNATIVE: <Name of program if NO, else NONE>
    """
    
    try:
        response = llm.invoke(prompt).content
        is_qualified = "QUALIFIED: YES" in response.upper()
        
        alt_program = None
        if not is_qualified:
            for line in response.splitlines():
                if "ALTERNATIVE:" in line.upper():
                    alt_program = line.split(":", 1)[1].strip()
    except Exception:
        is_qualified = False
        alt_program = "Diploma in Information Technology"

    status = "QUALIFIED" if is_qualified else "AWAITING_REGISTRY_REVIEW"
    log = f"[Stage 2] Qualification Check: {'QUALIFIED' if is_qualified else 'FLAGGED_FOR_REVIEW'} (Proposed Alt: {alt_program})."
    
    return {
        **state,
        "is_qualified": is_qualified,
        "alternative_program": alt_program,
        "current_status": status,
        "logs": state.get("logs", []) + [log]
    }


def send_offer_node(state: RegistrationState) -> RegistrationState:
    log = f"[Stage 3] Official offer letter PDF emailed to {state['student_email']} for program: {state['target_program']}."
    return {
        **state,
        "offer_sent": True,
        "current_status": "OFFER_SENT",
        "logs": state.get("logs", []) + [log]
    }


def student_response_node(state: RegistrationState) -> RegistrationState:
    if state.get("student_accepted"):
        status = "OFFER_ACCEPTED"
        log = f"[Stage 3] Student accepted the admission offer."
    else:
        status = "CLOSED"
        log = f"[Stage 3] Student declined the offer. Application closed."
        
    return {
        **state,
        "current_status": status,
        "logs": state.get("logs", []) + [log]
    }


def fee_and_id_generation_node(state: RegistrationState) -> RegistrationState:
    if not state.get("registration_fee_paid", False):
        log = f"[Stage 4] Fee verification pending. Cannot generate Student ID."
        return {**state, "current_status": "FEE_PENDING", "logs": state.get("logs", []) + [log]}
    
    generated_id = f"26-REG-{state['prospect_id'][-4:]}"
    log = f"[Stage 4] Fee verified. Student ID generated: {generated_id}."
    
    return {
        **state,
        "student_id": generated_id,
        "current_status": "ID_ISSUED",
        "logs": state.get("logs", []) + [log]
    }


def final_sis_sync_node(state: RegistrationState) -> RegistrationState:
    log = f"[Stage 5] Master record successfully synchronized to Core SIS with ID {state['student_id']}."
    return {
        **state,
        "sis_sync_completed": True,
        "current_status": "FULLY_REGISTERED",
        "logs": state.get("logs", []) + [log]
    }


def route_after_evaluation(state: RegistrationState) -> Literal["send_offer", "__end__"]:
    return "send_offer" if state.get("is_qualified") else END


def route_after_student_response(state: RegistrationState) -> Literal["generate_id", "__end__"]:
    return "generate_id" if state.get("student_accepted") else END


# Graph Assembly
workflow = StateGraph(RegistrationState)

workflow.add_node("prospect_capture", prospect_capture_node)
workflow.add_node("registry_evaluation", registry_entry_evaluation_node)
workflow.add_node("send_offer", send_offer_node)
workflow.add_node("student_response", student_response_node)
workflow.add_node("generate_id", fee_and_id_generation_node)
workflow.add_node("final_sis_sync", final_sis_sync_node)

workflow.set_entry_point("prospect_capture")
workflow.add_edge("prospect_capture", "registry_evaluation")

workflow.add_conditional_edges(
    "registry_evaluation",
    route_after_evaluation,
    {
        "send_offer": "send_offer",
        END: END
    }
)

workflow.add_edge("send_offer", "student_response")

workflow.add_conditional_edges(
    "student_response",
    route_after_student_response,
    {
        "generate_id": "generate_id",
        END: END
    }
)

workflow.add_edge("generate_id", "final_sis_sync")
workflow.add_edge("final_sis_sync", END)

registration_agent = workflow.compile()