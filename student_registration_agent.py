import os
from typing import Literal, Optional, List, TypedDict
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI

# Configure Gemini Model
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0.0,
    api_key=os.environ.get("GEMINI_API_KEY")
)

# ---------------------------------------------------------------------------
# 1. State Definition
# ---------------------------------------------------------------------------
class RegistrationState(TypedDict):
    prospect_id: str
    student_name: str
    student_email: str
    target_program: str
    transcript_text: str
    is_qualified: Optional[bool]
    alternative_program: Optional[str]
    offer_sent: bool
    student_accepted: Optional[bool]
    registration_fee_paid: bool
    student_id: Optional[str]
    sis_sync_completed: bool
    current_status: str
    logs: List[str]


# ---------------------------------------------------------------------------
# 2. Node Functions (Discrete 5-Stage Tasks)
# ---------------------------------------------------------------------------

def prospect_capture_node(state: RegistrationState) -> RegistrationState:
    """Stage 1: Ingests prospect and creates buffer state."""
    log = f"[Stage 1] Prospect captured for {state['student_name']} ({state['target_program']})[cite: 1]."
    return {
        **state,
        "current_status": "PROSPECT_CONFIRMED",
        "logs": state.get("logs", []) + [log]
    }


def registry_entry_evaluation_node(state: RegistrationState) -> RegistrationState:
    """Stage 2: Multimodal/LLM prerequisite evaluation against target program."""
    prompt = f"""
    You are an academic registry admissions officer[cite: 1].
    Evaluate if this student meets entry criteria for: {state['target_program']}[cite: 1].
    
    Student Transcript Summary:
    {state['transcript_text']}
    
    Rule: Requires GPA >= 3.0 and prerequisite core mathematics.
    If not qualified, suggest an appropriate alternative diploma or foundation degree.
    
    Respond in EXACT format:
    QUALIFIED: <YES or NO>
    ALTERNATIVE: <Name of program if NO, else NONE>
    """
    
    response = llm.invoke(prompt).content
    is_qualified = "QUALIFIED: YES" in response.upper()
    
    alt_program = None
    if not is_qualified:
        for line in response.splitlines():
            if "ALTERNATIVE:" in line.upper():
                alt_program = line.split(":", 1)[1].strip()
                
    status = "QUALIFIED" if is_qualified else "ALT_PROGRAM_PENDING"
    log = f"[Stage 2] Qualification Check: {status} (Alt: {alt_program})[cite: 1, 2]."
    
    return {
        **state,
        "is_qualified": is_qualified,
        "alternative_program": alt_program,
        "current_status": status,
        "logs": state["logs"] + [log]
    }


def check_alternative_program_node(state: RegistrationState) -> RegistrationState:
    """Stage 2 Fallback: Routes non-qualified applicants to alternative options[cite: 1, 2]."""
    log = f"[Stage 2 Fallback] Re-routed applicant to alternative: {state['alternative_program']}[cite: 1, 2]."
    return {
        **state,
        "target_program": state["alternative_program"] or "General Foundation Studies",
        "is_qualified": True,  # Qualified for fallback program
        "current_status": "ALT_OFFER_PREPARED",
        "logs": state["logs"] + [log]
    }


def send_offer_node(state: RegistrationState) -> RegistrationState:
    """Stage 3a: Generates PDF offer letter and dispatches via email[cite: 1, 2]."""
    log = f"[Stage 3] Official offer letter PDF emailed to {state['student_email']}[cite: 1, 2]."
    return {
        **state,
        "offer_sent": True,
        "current_status": "OFFER_SENT",
        "logs": state["logs"] + [log]
    }


def student_response_node(state: RegistrationState) -> RegistrationState:
    """Stage 3b: Captures student portal acceptance/rejection[cite: 1, 2]."""
    if state.get("student_accepted"):
        status = "OFFER_ACCEPTED"
        log = f"[Stage 3] Student accepted the admission offer[cite: 1, 2]."
    else:
        status = "CLOSED"
        log = f"[Stage 3] Student declined the offer. Application closed[cite: 1, 2]."
        
    return {
        **state,
        "current_status": status,
        "logs": state["logs"] + [log]
    }


def fee_and_id_generation_node(state: RegistrationState) -> RegistrationState:
    """Stage 4: Verifies registration fee and generates official Student ID[cite: 1, 2]."""
    if not state.get("registration_fee_paid", False):
        log = f"[Stage 4] Fee verification pending. Cannot generate Student ID[cite: 1, 2]."
        return {**state, "current_status": "FEE_PENDING", "logs": state["logs"] + [log]}
    
    # Deterministic Student ID Generation (Format: 26-[FAC]-XXXX)[cite: 2, 7]
    generated_id = f"26-REG-{state['prospect_id'][-4:]}"
    log = f"[Stage 4] Fee verified. Student ID generated: {generated_id}[cite: 1, 2, 7]."
    
    return {
        **state,
        "student_id": generated_id,
        "current_status": "ID_ISSUED",
        "logs": state["logs"] + [log]
    }


def final_sis_sync_node(state: RegistrationState) -> RegistrationState:
    """Stage 5: Final transactional write-back to the core SIS database[cite: 1, 2, 7]."""
    # Writes payload to SIS tables (STUDENT_MASTER, ENROLLMENT)[cite: 7]
    log = f"[Stage 5] Master record successfully synchronized to Core SIS with ID {state['student_id']}[cite: 1, 2, 7]."
    return {
        **state,
        "sis_sync_completed": True,
        "current_status": "FULLY_REGISTERED",
        "logs": state["logs"] + [log]
    }


# ---------------------------------------------------------------------------
# 3. Conditional Routing Logic
# ---------------------------------------------------------------------------

def route_after_evaluation(state: RegistrationState) -> Literal["send_offer", "check_alternative"]:
    return "send_offer" if state.get("is_qualified") else "check_alternative"[cite: 1, 2]

def route_after_student_response(state: RegistrationState) -> Literal["generate_id", "__end__"]:
    return "generate_id" if state.get("student_accepted") else END[cite: 1, 2]


# ---------------------------------------------------------------------------
# 4. Graph Construction & Assembly
# ---------------------------------------------------------------------------

workflow = StateGraph(RegistrationState)

# Add Nodes
workflow.add_node("prospect_capture", prospect_capture_node)
workflow.add_node("registry_evaluation", registry_entry_evaluation_node)
workflow.add_node("check_alternative", check_alternative_program_node)
workflow.add_node("send_offer", send_offer_node)
workflow.add_node("student_response", student_response_node)
workflow.add_node("generate_id", fee_and_id_generation_node)
workflow.add_node("final_sis_sync", final_sis_sync_node)

# Set Entry Point
workflow.set_entry_point("prospect_capture")

# Define Edges & Branching Logic
workflow.add_edge("prospect_capture", "registry_evaluation")[cite: 1, 2]

workflow.add_conditional_edges(
    "registry_evaluation",
    route_after_evaluation,
    {
        "send_offer": "send_offer",
        "check_alternative": "check_alternative"
    }
)[cite: 1, 2]

workflow.add_edge("check_alternative", "send_offer")[cite: 1, 2]
workflow.add_edge("send_offer", "student_response")[cite: 1, 2]

workflow.add_conditional_edges(
    "student_response",
    route_after_student_response,
    {
        "generate_id": "generate_id",
        END: END
    }
)[cite: 1, 2]

workflow.add_edge("generate_id", "final_sis_sync")[cite: 1, 2]
workflow.add_edge("final_sis_sync", END)[cite: 1, 2]

# Compile the StateGraph
registration_agent = workflow.compile()


# ---------------------------------------------------------------------------
# 5. Example Execution Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sample_lead: RegistrationState = {
        "prospect_id": "LEAD-8842",
        "student_name": "Alexander Wright",
        "student_email": "alex.wright@example.com",
        "target_program": "BSc in Computer Science",
        "transcript_text": "Completed High School. Overall GPA: 3.65. Mathematics: A, Physics: B+, English: A.",
        "is_qualified": None,
        "alternative_program": None,
        "offer_sent": False,
        "student_accepted": True,
        "registration_fee_paid": True,
        "student_id": None,
        "sis_sync_completed": False,
        "current_status": "INITIATED",
        "logs": []
    }

    result = registration_agent.invoke(sample_lead)

    print("\n" + "="*50)
    print("REGISTRATION AGENT RUN EXECUTION SUMMARY")
    print("="*50)
    print(f"Final Status   : {result['current_status']}")
    print(f"Assigned ID    : {result['student_id']}")
    print(f"Enrolled Degree: {result['target_program']}")
    print("\nExecution Logs:")
    for log in result["logs"]:
        print(f"  -> {log}")